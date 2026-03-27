import asyncio
import structlog
from src.data.pipeline import LiveBuffer
from src.core.oracle import Oracle, AccountState, AccountStatus
from src.core.allocator import Allocator
from src.core.oracle import Oracle, AccountState, AccountStatus
from src.execution.router import Router
from src.models.classifier import Classifier

from src.core.advisor import Advisor

class Engine:
    """Orchestrates Data -> Features -> Model -> Allocator -> Oracle -> Router -> Advisor"""

    def __init__(self, client: RithmicClient, account_state: Optional[AccountState] = None):
        # Load state from disk if not provided
        self.account_state = account_state or AccountState.load()
        self.buffer = LiveBuffer()
        self.oracle = Oracle(self.account_state)
        self.allocator = Allocator()
        self.classifier = Classifier()
        self.router = Router(client, self.account_state)
        self.advisor = Advisor()
        self.running = False
        self.veto_logs = [] # To be consumed by Advisor
        self.current_hurst = 0.5 # Layer 1 state

    async def run(self, symbol: str = settings.SYMBOL):
        """Main Loop for the engine."""
        self.running = True
        logger.info("Engine: Starting Core Loop...")

        try:
            while self.running:
                # 1. EOD Check (Panic Flatten if near 4:59 PM ET)
                if not self.oracle.state.is_trading_allowed:
                    if self.router.current_position != 0:
                        await self.router.panic_flatten(symbol)
                        await self.advisor.generate_summary(
                            self.account_state, 
                            self.veto_logs, 
                            {'hurst': self.current_hurst}
                        )
                    await asyncio.sleep(60)
                    continue

                # 2. Get 15m context
                context = self.buffer.get_15m_context(history_size=150)

                if context is not None and len(context) >= 100:
                    # Update internal context for Advisor
                    # ... logic to calculate hurst ...
                    
                    # 3. Get Layer 2 Signal
                    signal_prob = self.classifier.predict(context) 

                    if signal_prob > 0.6: 
                        # 4. Allocator
                        atr = context["atr"].item() if "atr" in context.columns else 10.0
                        size = self.allocator.calculate_size(signal_prob, atr, self.oracle.state.balance)

                        if size > 0 and self.router.current_position == 0:
                            # 5. Oracle Final Gate
                            price = context["close"].item()
                            if self.oracle.validate_trade(size, price, "BUY"):
                                # 6. Router
                                await self.router.execute_trade(symbol, size, "BUY")
                            else:
                                self.veto_logs.append(f"Vetoed signal at {price} prob {signal_prob}")
        finally:
            # Final Audit on shutdown
            await self.advisor.generate_summary(
                self.account_state, 
                self.veto_logs, 
                {'hurst': self.current_hurst}
            )

    def stop(self):
        self.running = False
