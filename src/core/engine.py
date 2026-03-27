import asyncio
import structlog
from src.data.pipeline import LiveBuffer
from src.core.oracle import Oracle, AccountState, AccountStatus
from src.core.allocator import Allocator
from src.models.classifier import Classifier

logger = structlog.get_logger()

class Engine:
    """Orchestrates Data -> Features -> Model -> Allocator -> Oracle"""
    
    def __init__(self, account_state: AccountState):
        self.buffer = LiveBuffer()
        self.oracle = Oracle(account_state)
        self.allocator = Allocator()
        self.classifier = Classifier()
        self.running = False

    async def run(self):
        """Main Loop for the engine."""
        self.running = True
        logger.info("Engine: Starting Core Loop...")
        
        while self.running:
            # 1. Get 15m context
            context = self.buffer.get_15m_context()
            
            if context is not None:
                # 2. Get Layer 2 Signal (Probability)
                # Note: Classifier.predict should be updated to return float probability
                signal_prob = self.classifier.predict(context) 
                
                if signal_prob > 0.5:
                    # 3. Layer 2.5: Allocator (Scale Size)
                    atr = context["atr"].item() if "atr" in context.columns else 10.0
                    size = self.allocator.calculate_size(signal_prob, atr, self.oracle.state.balance)
                    
                    if size > 0:
                        # 4. Layer 3: Oracle (Final Risk Gate)
                        # We simulate a BUY for the side here
                        if self.oracle.validate_trade(size, context["close"].item(), "BUY"):
                            logger.info("TRADE SIGNAL READY", size=size, prob=signal_prob)
                            # 5. Layer 4: Execution (Router)
                            # await self.router.buy(...)
            
            await asyncio.sleep(1)
            
    def stop(self):
        self.running = False
