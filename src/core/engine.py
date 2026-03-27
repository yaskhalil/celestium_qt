import asyncio
import structlog
from src.data.pipeline import LiveBuffer
from src.core.oracle import Oracle, AccountState, AccountStatus
from src.core.allocator import Allocator
from src.core.oracle import Oracle, AccountState, AccountStatus
from src.execution.router import Router
from src.models.classifier import Classifier

logger = structlog.get_logger()

class Engine:
    """Orchestrates Data -> Features -> Model -> Allocator -> Oracle -> Router"""

    def __init__(self, client: RithmicClient, account_state: Optional[AccountState] = None):
        # Load state from disk if not provided
        self.account_state = account_state or AccountState.load()
        self.buffer = LiveBuffer()
        self.oracle = Oracle(self.account_state)
        self.allocator = Allocator()
        self.classifier = Classifier()
        self.router = Router(client, self.account_state)
        self.running = False

    async def run(self, symbol: str = settings.SYMBOL):
        """Main Loop for the engine."""
        self.running = True
        logger.info("Engine: Starting Core Loop...")

        while self.running:
            # 1. EOD Check (Panic Flatten if near 4:59 PM ET)
            if not self.oracle.state.is_trading_allowed:
                if self.router.current_position != 0:
                    await self.router.panic_flatten(symbol)
                await asyncio.sleep(60)
                continue

            # 2. Get 15m context (request enough bars for indicators)
            context = self.buffer.get_15m_context(history_size=150)

            if context is not None and len(context) >= 100:
                # 3. Get Layer 2 Signal (Probability)
                signal_prob = self.classifier.predict(context) 

                if signal_prob > 0.6: # Filter low-confidence signals
                    # 4. Layer 2.5: Allocator (Scale Size)
                    atr = context["atr"].item() if "atr" in context.columns else 10.0
                    size = self.allocator.calculate_size(signal_prob, atr, self.oracle.state.balance)

                    if size > 0 and self.router.current_position == 0:
                        # 5. Layer 3: Oracle (Final Risk Gate)
                        price = context["close"].item()
                        if self.oracle.validate_trade(size, price, "BUY"):
                            # 6. Layer 4: Execution (Router)
                            await self.router.execute_trade(symbol, size, "BUY")

            await asyncio.sleep(1)

    def stop(self):
        self.running = False
