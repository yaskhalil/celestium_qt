import structlog
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio

import httpx
import json
import os
from src.config import settings
from src.data.pipeline import DuckDBBuffer
from src.core.oracle import Oracle, AccountState, AccountStatus
from src.core.boolean_network import BooleanStateSpace
from src.execution.position_manager import PositionManager
from src.models.classifier import Classifier
from src.core.allocator import Allocator
from src.core.advisor import Advisor
from src.core.strategy import SignalGenerator

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

    def __init__(self, alpaca_client: AlpacaClient, account_state: Optional[AccountState] = None, notifier: Optional[TelegramNotifier] = None):
        self.account_state = account_state or AccountState.load()
        self.alpaca_client = alpaca_client
        self.buffer = DuckDBBuffer()
        self.bn = BooleanStateSpace()
        self.notifier = notifier or TelegramNotifier()
        self.oracle = Oracle(self.account_state, self.notifier)
        self.allocator = Allocator()
        self.classifier = Classifier()
        self.strategy = SignalGenerator(self.bn, self.classifier, self.allocator, self.oracle)
        
        self.router = PositionManager(alpaca_client, self.account_state, self.oracle, self.notifier)
        self.ingestor = AlpacaIngestor(client=alpaca_client)
        self.advisor = Advisor()
        
        self.scheduler = AsyncIOScheduler()
        self.running = False
        self.veto_logs = []
        
        # Live Trade Monitoring
        self.current_symbol = settings.SYMBOL
        self.context_symbol = settings.CONTEXT_SYMBOL

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
            # Position Management (Exits) via Deepened Interface
            await self.router.update_price(symbol, current_price)
        except Exception as e:
            logger.error("Engine: Monitor tick failed", error=str(e))

    async def tick_eod(self):
        """EOD Flatten: Runs at 3:55 PM ET to unconditionally close remaining positions."""
        logger.info("Engine: EOD Flatten triggered")
        symbol = self.current_symbol
        current_price = await self.alpaca_client.get_last_price(symbol)
        if current_price is None:
            logger.error("Engine: Could not obtain price for EOD flatten", symbol=symbol)
            return

        try:
            await self.router.flatten(symbol, current_price)
        except Exception as e:
            logger.error("Engine: EOD Flatten failed", error=str(e))

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

        # Fetch VIXY (ProShares VIX ETF) to use as circuit breaker volatility proxy
        vix_price = await self.alpaca_client.get_last_price("VIXY") or 15.0

        # Generate proposal from strategy module
        proposal, veto_reason = self.strategy.generate_proposal(context, context_market, vix_price)

        if veto_reason:
            self.veto_logs.append(veto_reason)
            return

        if proposal:
            logger.info("Engine: SIGNAL APPROVED. Executing trade.", 
                        size=proposal.quantity, price=proposal.price)
            await self.router.execute_trade(symbol, proposal.quantity, "BUY", price=proposal.price, tp=proposal.tp, sl=proposal.sl)

    def start(self):
        """Starts the scheduler with dual-loop configuration."""
        logger.info("Engine: Starting scheduler")
        self.running = True
        asyncio.create_task(self.notifier.notify_startup(self.account_state.balance, settings.SHADOW_MODE))
        
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
        
        # 3. EOD Flatten (3:55 PM ET)
        self.scheduler.add_job(
            self.tick_eod,
            CronTrigger(day_of_week='mon-fri', hour='15', minute='55', timezone='America/New_York'),
            id='market_tick_eod'
        )
        
        # 4. EOD Telegram Recap (4:05 PM ET)
        self.scheduler.add_job(
            self.trigger_eod_recap,
            CronTrigger(day_of_week='mon-fri', hour='16', minute='5', timezone='America/New_York'),
            id='market_tick_recap'
        )
        
        # 5. DB Vacuum (Saturday Midnight)
        self.scheduler.add_job(
            self.buffer.storage.vacuum,
            CronTrigger(day_of_week='sat', hour='0', minute='0', timezone='America/New_York'),
            id='db_vacuum'
        )
        
        self.scheduler.start()
 
    async def stop(self):
        """Stops the scheduler and generates summary."""
        logger.info("Engine: Stopping scheduler")
        self.running = False
        
        await self.notifier.notify_shutdown(self.account_state.balance)
        self.scheduler.shutdown()
        
        await self.advisor.generate_summary(
            self.account_state, 
            self.veto_logs, 
            {} # Final metrics context
        )



    async def trigger_eod_recap(self):
        """Sends daily PNL recap at close."""
        history = self.account_state.trading_history
        veto_count = len(self.veto_logs)
        payout_cap = self.account_state.liquid_payout_capital
        
        # Clear vetos for next session
        self.veto_logs = []
        
        if not history:
            await self.notifier.notify_daily_recap(0.0, self.account_state.balance, 0, veto_count, payout_cap)
            return
            
        today = history[-1]
        await self.notifier.notify_daily_recap(today.pnl, self.account_state.balance, today.trade_count, veto_count, payout_cap)


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
