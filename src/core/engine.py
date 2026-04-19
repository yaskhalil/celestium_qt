import structlog
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio

from src.config import settings
from src.data.pipeline import KDBBuffer
from src.core.oracle import Oracle, AccountState
from src.core.boolean_network import BooleanStateSpace
from src.execution.router import WebullRouter
from src.models.classifier import Classifier
from src.core.allocator import Allocator
from src.core.advisor import Advisor

logger = structlog.get_logger()

class ScheduledEngine:
    """
    Scheduled Engine: Triggers 'tick' periodically using APScheduler.
    Orchestrates Data -> Boolean Attractor -> Classifier -> Oracle -> Router.
    """

    def __init__(self, webull_client, account_state: Optional[AccountState] = None):
        self.account_state = account_state or AccountState.load()
        self.buffer = KDBBuffer()
        self.bn = BooleanStateSpace()
        self.oracle = Oracle(self.account_state)
        self.allocator = Allocator()
        self.classifier = Classifier()
        self.router = WebullRouter(webull_client, self.account_state)
        self.advisor = Advisor()
        
        self.scheduler = BackgroundScheduler()
        self.running = False
        self.veto_logs = []

    def tick(self):
        """Triggered every hour during market hours (9:30 AM - 4:00 PM ET)."""
        logger.info("Engine: Tick triggered")
        symbol = settings.SYMBOL

        # 1. Fetch context from KDBBuffer
        try:
            context = self.buffer.get_context(symbol, window=150)
        except Exception as e:
            logger.error("Engine: Failed to fetch context", error=str(e))
            return

        if context.is_empty() or len(context) < 100:
            logger.warning("Engine: Insufficient data context", length=len(context))
            return

        # 2. Map context to Boolean state bits
        state = self.bn.map_to_bits(context)
        
        # 3. Check if state is in an attractor
        if not self.bn.is_in_attractor(state):
            logger.info("Engine: State not in attractor, skipping", state=state)
            self.veto_logs.append(f"Not in attractor: {state}")
            return

        # 4. Proceed with Layer 2 (Classifier)
        signal_prob = self.classifier.predict(context)
        
        if signal_prob > settings.SIGNAL_THRESHOLD:
            # 5. Allocator
            atr = context["atr"].tail(1).item() if "atr" in context.columns else 1.0
            size = self.allocator.calculate_size(signal_prob, atr, self.account_state.balance)
            
            if size > 0:
                # 6. Oracle validation
                decision_price = context["close"].tail(1).item()
                if self.oracle.validate_trade(size, decision_price, "BUY"):
                    # 7. Router execution (using Webull logic)
                    logger.info("Engine: SIGNAL APPROVED. Executing trade.", 
                                size=size, price=decision_price)
                    
                    # Router.execute_trade is async, so we run it in a new event loop
                    # since we are in a background thread from BackgroundScheduler.
                    asyncio.run(self.router.execute_trade(symbol, size, "BUY", price=decision_price))
                else:
                    self.veto_logs.append(f"Oracle vetoed: prob {signal_prob}")
                    logger.info("Engine: Signal vetoed by Oracle")
        else:
            logger.debug("Engine: Signal below threshold", prob=signal_prob)

    def start(self):
        """Starts the scheduler."""
        logger.info("Engine: Starting scheduler")
        # Market hours: 9 AM - 4 PM ET (cron triggered at start of every hour)
        self.scheduler.add_job(
            self.tick, 
            CronTrigger(hour='9-16', minute='0', timezone='US/Eastern'),
            id='market_tick'
        )
        self.scheduler.start()
        self.running = True

    def stop(self):
        """Stops the scheduler and generates summary."""
        logger.info("Engine: Stopping scheduler")
        self.scheduler.shutdown()
        self.running = False
        
        asyncio.run(self.advisor.generate_summary(
            self.account_state, 
            self.veto_logs, 
            {} # Final metrics context
        ))

if __name__ == "__main__":
    # Scheduler initialization replaced main loop
    import time
    from webullsdkcore.client import ApiClient
    
    # Placeholder for actual client initialization
    client = ApiClient(settings.WEBULL_APP_KEY, settings.WEBULL_APP_SECRET)
    engine = ScheduledEngine(client)
    engine.start()
    
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        engine.stop()
