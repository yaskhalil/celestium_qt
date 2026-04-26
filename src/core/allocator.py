import structlog
import math
from src.config import settings

logger = structlog.get_logger()

class Allocator:
    """
    The Dynamic Allocator: Translates Alpha signals into specific position sizes.
    Bridges Layer 2 (Model) and Layer 3 (Oracle).
    """
    
    def __init__(self, max_contracts: int = settings.MAX_POSITION_SIZE_MICRO):
        self.max_contracts = max_contracts

    def calculate_size(self, probability: float, atr: float, balance: float) -> float:
        """
        Calculates optimal contract size based on:
        1. Signal Confidence (XGBoost Probability)
        2. Market Volatility (ATR)
        3. Risk Limits
        """
        # 1. Confidence Filter
        # Threshold: If prob < settings.SIGNAL_THRESHOLD, we don't trade.
        if probability < settings.SIGNAL_THRESHOLD:
            return 0
            
        # 2. Base Size calculation
        # Simple Linear Scaling
        confidence_multiplier = (probability - (settings.SIGNAL_THRESHOLD - 0.1)) * 2
        base_size = self.max_contracts * confidence_multiplier
        
        # 3. Volatility Adjustment
        # If ATR is high, we reduce size to keep dollar risk constant.
        reference_atr = settings.REFERENCE_ATR
        vol_multiplier = reference_atr / max(atr, 5.0) # Floor at 5.0 to avoid division by zero
        
        final_size = base_size * vol_multiplier
        
        # 4. Apex Safety Constraints
        # Never exceed the settings.MAX_POSITION_SIZE
        final_size = max(0.0, min(final_size, self.max_contracts))
        
        # 5. Min size check
        # If the math says 0.8 contracts, we take 1 if confidence is high enough.
        # UPDATED: For fractionals, we use 0.01 as minimum.
        if final_size < 0.01 and probability > 0.7:
            final_size = 0.01

        logger.info("Allocator: Size calculated", 
                    prob=round(probability, 3), 
                    atr=round(atr, 2), 
                    final_size=round(final_size, 5))
                    
        return round(float(final_size), 5)
