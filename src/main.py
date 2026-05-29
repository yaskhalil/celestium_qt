import asyncio
import structlog
from src.execution.alpaca_client import AlpacaClient
from src.core.engine import ScheduledEngine
from src.core.oracle import AccountState
from src.config import settings

# Setup logging
structlog.configure()
logger = structlog.get_logger()

def verify_timezone():
    """Verify that the required timezone data is available."""
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo("America/New_York")
    except Exception:
        logger.error("Timezone data missing. Please install 'tzdata' package: pip install tzdata")
        raise RuntimeError("Missing timezone data for America/New_York")

async def main():
    """Async entry point (The Event Loop)"""
    verify_timezone()
    logger.info("Initializing CelestiumQT (Alpaca Unified Mode)")
    
    # 1. Initialize native AlpacaClient
    alpaca_client = AlpacaClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        base_url=settings.ALPACA_BASE_URL
    )
    
    # 2. Load Persistent Account State
    state = AccountState.load()

    # 3. Fetch actual Alpaca Account Balance
    try:
        account_info = await alpaca_client.get_account()
        actual_equity = float(account_info.get("equity", settings.STARTING_BALANCE))
        actual_cash = float(account_info.get("cash", actual_equity))
        logger.info("Synced actual balance from Alpaca", equity=actual_equity, cash=actual_cash)
        
        # If first time syncing, or starting balance is 0, initialize it
        if getattr(state, "initial_starting_balance", 0.0) == 0.0:
            logger.info("Initializing starting balance from Alpaca", balance=actual_equity)
            state.initial_starting_balance = actual_equity
            state.balance = actual_equity
            state.equity = actual_equity
            state.settled_cash = actual_cash
            state.save()
        else:
            # Continually sync current equity to prevent drift
            state.balance = actual_equity
            state.equity = actual_equity
    except Exception as e:
        logger.error("Failed to fetch Alpaca account. Using defaults.", error=str(e))
    
    # 4. Initialize the scheduled engine
    engine = ScheduledEngine(alpaca_client, state)
    engine.start()
    
    # Start the event loop
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("CelestiumQT shutting down...")
    except Exception as e:
        logger.error("Critical failure", error=str(e))
    finally:
        # Stop scheduler and save state
        await engine.stop()
        state.save()
        await alpaca_client.close()

if __name__ == "__main__":
    asyncio.run(main())
