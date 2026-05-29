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

    def calculate_size(self, probability: float, atr: float, balance: float, current_price: float, daily_pnl: float = 0.0) -> float:
        """
        Calculates optimal contract size based on:
        1. Signal Confidence (XGBoost Probability)
        2. Market Volatility (ATR)
        3. Risk Limits (Dynamic Account Balance)
        4. Performance Streak (Asymmetric Scaling)
        """
        if probability < settings.SIGNAL_THRESHOLD:
            return 0
            
        # Standard Risk-Based Position Sizing
        base_risk_pct = 0.02  # Target 2% risk of total balance
        
        # Asymmetric Sizing (Task 4): Protect on losses, push on wins
        if daily_pnl < 0:
            base_risk_pct = 0.01  # Halve risk if in drawdown today
        elif daily_pnl > (balance * 0.01):
            base_risk_pct = 0.03  # Increase risk if up > 1% today
            
        # Scale risk by model confidence (prob threshold to 1.0 -> scaler 0.0 to 1.0)
        confidence_scaler = max(0.0, (probability - settings.SIGNAL_THRESHOLD) / (1.0 - settings.SIGNAL_THRESHOLD))
        adjusted_risk_pct = base_risk_pct * confidence_scaler
        
        capital_at_risk = balance * adjusted_risk_pct
        stop_loss_distance = max(atr * settings.SL_MULTIPLIER, 0.01) # Avoid division by zero
        
        # Calculate shares: (Amount we are willing to lose) / (Amount we lose per share)
        calculated_shares = capital_at_risk / stop_loss_distance
        
        # Hard constraint: Cannot exceed actual cash balance (accounting for 5% slippage/fees buffer)
        max_affordable_shares = (balance * 0.95) / max(current_price, 0.01)
        
        final_size = min(calculated_shares, max_affordable_shares)
        
        # Ensure minimum fractional size
        if final_size < 0.01 and probability > 0.6:
            final_size = 0.01

        logger.info("Allocator: Size calculated", 
                    prob=round(probability, 3), 
                    atr=round(atr, 2), 
                    final_size=round(final_size, 5))
                    
        return round(float(final_size), 5)
