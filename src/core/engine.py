import structlog
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio

from src.config import settings
from src.data.pipeline import DuckDBBuffer
from src.core.oracle import Oracle, AccountState
from src.core.boolean_network import BooleanStateSpace
from src.execution.router import AlpacaRouter
from src.models.classifier import Classifier
from src.core.allocator import Allocator
from src.core.advisor import Advisor

from src.data.ingestion import AlpacaIngestor
from src.execution.alpaca_client import AlpacaClient
from src.core.notifier import TelegramNotifier

logger = structlog.get_logger()

class ScheduledEngine:
    """
    Scheduled Engine: Dual-loop execution for safety and precision.
    Monitor (1m): Exits and position tracking.
    Signal (5m): Heavy model inference and entries.
    """

    def __init__(self, alpaca_client: AlpacaClient, account_state: Optional[AccountState] = None):
        self.account_state = account_state or AccountState.load()
        self.alpaca_client = alpaca_client
        self.buffer = DuckDBBuffer()
        self.bn = BooleanStateSpace()
        self.oracle = Oracle(self.account_state)
        self.allocator = Allocator()
        self.classifier = Classifier()
        
        self.router = AlpacaRouter(alpaca_client, self.account_state)
        self.ingestor = AlpacaIngestor(client=alpaca_client)
        self.advisor = Advisor()
        self.notifier = TelegramNotifier()
        
        self.scheduler = AsyncIOScheduler()
        self.running = False
        self.veto_logs = []
        
        # Live Trade Monitoring
        self.current_symbol = settings.SYMBOL
        self.context_symbol = settings.CONTEXT_SYMBOL
        self.stop_loss = 0.0
        self.take_profit = 0.0
        self.entry_price = 0.0

    async def tick_monitor(self):
        """Fast tick: Triggered every minute to monitor and exit positions."""
        symbol = self.current_symbol
        current_price = None
        
        # 0. Ingest latest data (Required for exit price check and context)
        try:
            await self.ingestor.fetch_and_persist(symbol, lookback_minutes=15)
            await self.ingestor.fetch_and_persist(self.context_symbol, lookback_minutes=15)
        except Exception as e:
            logger.error("Engine: Ingestion failed", error=str(e))

        # Check buffer for price
        context = self.buffer.get_context(symbol, window=5)
        if not context.is_empty():
            last_bar = context.tail(1).to_dicts()[0]
            current_price = last_bar["close"]

        # Fallback to Alpaca for real-time price monitoring if ingestion failed or was empty
        if current_price is None:
            logger.info("Engine: Fetching real-time price from Alpaca", symbol=symbol)
            current_price = await self.alpaca_client.get_last_price(symbol)
            
        if current_price is None:
            logger.error("Engine: Could not obtain current price for monitoring", symbol=symbol)
            return

        try:
            # Position Management (Exits)
            await self.router._verify_position(symbol)
            if self.router.current_position != 0:
                # Use current_price for monitoring logic
                if current_price <= self.stop_loss:
                    logger.warning("Engine: STOP LOSS HIT", price=self.stop_loss, current=current_price)
                    await self.router.execute_trade(symbol, abs(self.router.current_position), "SELL", price=current_price)
                    self.oracle.update_session(pnl=(current_price - self.entry_price) * self.router.current_position, 
                                               cash_flow=abs(self.router.current_position) * current_price,
                                               quantity=abs(self.router.current_position), side="SELL")
                elif current_price >= self.take_profit:
                    logger.info("Engine: TAKE PROFIT HIT", price=self.take_profit, current=current_price)
                    await self.router.execute_trade(symbol, abs(self.router.current_position), "SELL", price=current_price)
                    self.oracle.update_session(pnl=(current_price - self.entry_price) * self.router.current_position,
                                               cash_flow=abs(self.router.current_position) * current_price,
                                               quantity=abs(self.router.current_position), side="SELL")
        except Exception as e:
            logger.error("Engine: Monitor tick failed", error=str(e))

    async def tick_signal(self):
        """Slow tick: Triggered every 5 minutes to generate new trade signals."""
        logger.info("Engine: Signal check triggered (5m interval)")
        symbol = self.current_symbol

        # 1. Fetch context (Requires 111+ bars for model)
        # We also need the context symbol (QQQ) for the BooleanStateSpace
        try:
            context = self.buffer.get_context(symbol, window=150)
            context_market = self.buffer.get_context(self.context_symbol, window=150)
        except Exception as e:
            logger.error("Engine: Failed to fetch context", error=str(e))
            return

        if context.is_empty() or len(context) < 111 or context_market.is_empty():
            logger.warning("Engine: Insufficient data context. Attempting Alpaca historical backfill.", 
                           symbol_len=len(context), context_len=len(context_market))
            try:
                await self.ingestor.fetch_and_persist(symbol, lookback_minutes=200)
                await self.ingestor.fetch_and_persist(self.context_symbol, lookback_minutes=200)
                context = self.buffer.get_context(symbol, window=150)
                context_market = self.buffer.get_context(self.context_symbol, window=150)
            except Exception as e:
                logger.error("Engine: Alpaca backfill failed", error=str(e))

        if context.is_empty() or len(context) < 111:
            logger.warning("Engine: Still insufficient data context after backfill")
            return
            
        # Don't enter new trades if already in one
        await self.router._verify_position(symbol)
        if self.router.current_position != 0:
            logger.debug("Engine: Existing position active, skipping signal generation")
            return

        # 2. Map context to Boolean state bits
        # Note: We pass both to map_to_bits if it's designed to use market context
        state = self.bn.map_to_bits(context, context_market)
        
        # 3. Check if state is in an attractor
        if not self.bn.is_in_attractor(state):
            logger.info("Engine: State not in attractor, skipping", state=state)
            return

        # 4. Proceed with Layer 2 (Classifier)
        signal_prob = self.classifier.predict(context)
        
        if signal_prob > settings.SIGNAL_THRESHOLD:
            # 5. Allocator
            last_bar = context.tail(1).to_dicts()[0]
            decision_price = last_bar["close"]
            atr = last_bar["atr"] if "atr" in last_bar else 1.0
            size = self.allocator.calculate_size(signal_prob, atr, self.account_state.balance, decision_price)
            
            if size > 0:
                # 6. Oracle validation
                decision_price = last_bar["close"]
                if self.oracle.validate_trade(size, decision_price, "BUY", 
                                             current_hurst=context["hurst"].tail(1).item() if "hurst" in context.columns else 0.5):
                    logger.info("Engine: SIGNAL APPROVED. Executing trade.", 
                                size=size, price=decision_price)
                    
                    # Calculate targets (ATR-based)
                    self.entry_price = decision_price
                    self.take_profit = decision_price + (atr * settings.PT_MULTIPLIER)
                    self.stop_loss = decision_price - (atr * settings.SL_MULTIPLIER)

                    await self.router.execute_trade(symbol, size, "BUY", price=decision_price)
                    self.oracle.update_session(cash_flow=size * decision_price, quantity=size, side="BUY")
                else:
                    self.veto_logs.append(f"Oracle vetoed: prob {signal_prob}")
                    logger.info("Engine: Signal vetoed by Oracle")
        else:
            logger.debug("Engine: Signal below threshold", prob=signal_prob)

    def start(self):
        """Starts the scheduler with dual-loop configuration."""
        logger.info("Engine: Starting scheduler")
        asyncio.create_task(self.notifier.notify_system_status("🚀 CelestiumQT Trading Engine Started"))
        
        # 1. Fast Monitor Loop (Every 1 minute)
        self.scheduler.add_job(
            self.tick_monitor, 
            CronTrigger(day_of_week='mon-fri', hour='9-15', minute='*', timezone='America/New_York'),
            id='monitor_tick'
        )
        
        # 2. Slow Signal Loop (Every 5 minutes)
        self.scheduler.add_job(
            self.tick_signal,
            CronTrigger(day_of_week='mon-fri', hour='9-15', minute='0,5,10,15,20,25,30,35,40,45,50,55', timezone='America/New_York'),
            id='signal_tick'
        )
        
        # 3. EOD Flatten (4:00 PM ET)
        self.scheduler.add_job(
            self.tick_monitor,
            CronTrigger(day_of_week='mon-fri', hour='16', minute='0', timezone='America/New_York'),
            id='market_tick_eod'
        )
        
        self.scheduler.start()
        self.running = True

    async def stop(self):
        """Stops the scheduler and generates summary."""
        logger.info("Engine: Stopping scheduler")
        await self.notifier.notify_system_status("🛑 CelestiumQT Trading Engine Stopped")
        self.scheduler.shutdown()
        self.running = False
        
        await self.advisor.generate_summary(
            self.account_state, 
            self.veto_logs, 
            {} # Final metrics context
        )

if __name__ == "__main__":
    # Scheduler initialization replaced main loop
    from src.execution.alpaca_client import AlpacaClient
    
    async def main():
        # Initialize native AlpacaClient
        alpaca_client = AlpacaClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            base_url=settings.ALPACA_BASE_URL
        )
        
        engine = ScheduledEngine(alpaca_client)
        engine.start()
        
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            await engine.stop()

    asyncio.run(main())
