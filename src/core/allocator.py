import structlog
import math
from src.config import settings

logger = structlog.get_logger()

class Allocator:
    """
    The Dynamic Allocator: Translates Alpha signals into specific position sizes.
    Bridges Layer 2 (Model) and Layer 3 (Oracle).
    """
    
    def __init__(self, max_contracts: int = settings.MAX_POSITION_SIZE):
        self.max_contracts = max_contracts

    def calculate_size(self, probability: float, atr: float, balance: float) -> int:
        """
        Calculates optimal contract size based on:
        1. Signal Confidence (XGBoost Probability)
        2. Market Volatility (ATR)
        3. Risk Limits
        """
        # 1. Confidence Filter
        # Threshold: If prob < 0.55, we don't trade.
        if probability < 0.55:
            return 0
            
        # 2. Base Size calculation
        # Simple Linear Scaling: 0.6 prob -> 1 contract, 0.9 prob -> Max contracts
        # We use math.floor to be conservative.
        confidence_multiplier = (probability - 0.5) * 2 # 0.6 -> 0.2, 0.9 -> 0.8
        base_size = self.max_contracts * confidence_multiplier
        
        # 3. Volatility Adjustment
        # If ATR is high, we reduce size to keep dollar risk constant.
        # Reference ATR: 15m NQ average (Mock value: 20 points)
        reference_atr = 20.0 
        vol_multiplier = reference_atr / max(atr, 5.0) # Floor at 5.0 to avoid division by zero
        
        final_size = math.floor(base_size * vol_multiplier)
        
        # 4. Apex Safety Constraints
        # Never exceed the settings.MAX_POSITION_SIZE
        final_size = max(0, min(final_size, self.max_contracts))
        
        # 5. Min size check
        # If the math says 0.8 contracts, we take 1 if confidence is high enough.
        if final_size == 0 and probability > 0.7:
            final_size = 1

        logger.info("Allocator: Size calculated", 
                    prob=round(probability, 3), 
                    atr=round(atr, 2), 
                    final_size=final_size)
                    
        return int(final_size)
