import asyncio
import structlog
from src.execution.alpaca_client import AlpacaClient
from src.core.engine import ScheduledEngine
from src.core.oracle import AccountState
from src.config import settings

structlog.configure()
logger = structlog.get_logger()

def verify_timezone():
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo("America/New_York")
    except Exception:
        logger.error("Timezone data missing. Install 'tzdata': pip install tzdata")
        raise RuntimeError("Missing timezone data for America/New_York")

async def main():
    verify_timezone()
    logger.info("Initializing CelestiumQT (Alpaca Unified Mode)")

    # 1. Initialize Alpaca client
    alpaca = AlpacaClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        base_url=settings.ALPACA_BASE_URL
    )

    # 2. Validate API keys before booting anything
    if not await alpaca.test_connection():
        logger.critical("Alpaca API keys invalid — aborting startup")
        print("ERROR: Alpaca API keys failed validation. Check your .env file.")
        return

    # 3. Sync actual account state from Alpaca
    account_info = await alpaca.sync_account()
    actual_equity = account_info.get("equity", 0)
    actual_cash = account_info.get("cash", 0)
    logger.info("Account synced", equity=actual_equity, cash=actual_cash)

    if actual_equity <= 0:
        logger.critical("Account has zero balance — aborting")
        print("ERROR: Alpaca account has zero balance. Cannot start.")
        return

    # 4. Load or initialize persistent state
    state = AccountState.load()
    state.initial_starting_balance = actual_equity
    state.balance = actual_cash
    state.equity = actual_equity
    state.settled_cash = actual_cash
    state.save()

    # 5. Reconcile any open position from broker
    try:
        current_qty = await alpaca.get_position(settings.SYMBOL)
        market_value = await alpaca.get_position_market_value(settings.SYMBOL)
        if current_qty != 0:
            logger.warning("Open position detected on startup",
                          symbol=settings.SYMBOL, qty=current_qty,
                          market_value=market_value)
            state.position_market_value = market_value
            state.equity = state.balance + market_value
            state.save()
    except Exception as e:
        logger.error("Position reconciliation failed", error=str(e))

    # Log computed dynamic risk limits
    limits = state.to_dict()
    logger.info("Risk limits computed", **limits)

    # 6. Boot engine + Telegram bot
    from src.core.telegram_bot import TelegramBot
    engine = ScheduledEngine(alpaca, state)
    bot = TelegramBot(engine)

    engine.start()
    bot.start()

    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error("Critical failure", error=str(e))
    finally:
        await bot.stop()
        await engine.stop()
        state.save()
        await alpaca.close()

if __name__ == "__main__":
    asyncio.run(main())
