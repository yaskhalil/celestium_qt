"""
Dynamic Position Allocator — Translates alpha signals into position sizes (Layer 3).

Implements risk-based Kelly-like sizing:
- Base risk: 2% of capital at risk per trade
- Asymmetric scaling: Halve risk in drawdown, increase on winning streaks
- Confidence scaling: Scale risk by model probability vs threshold
- Hard constraints: Cannot exceed affordable shares or max position % of balance
- Fractional shares: Supports micro-lot execution for risk management

The allocator ensures position sizing respects both risk management and balance constraints.
"""
import structlog
import math
from src.config import settings

logger = structlog.get_logger()

class Allocator:
    """
    The Dynamic Allocator: Translates Alpha signals into specific position sizes.
    Bridges Layer 2 (Model) and Layer 3 (Oracle).
    """
    
    def __init__(self, max_position_pct: float | None = None):
        self.max_position_pct = max_position_pct if max_position_pct is not None else settings.MAX_POSITION_PCT

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
        
        # Cap by max position percentage of balance
        max_position_shares = (balance * self.max_position_pct) / max(current_price, 0.01)
        final_size = min(calculated_shares, max_affordable_shares, max_position_shares)
        
        # Ensure minimum fractional size
        if final_size < 0.01 and probability > 0.6:
            final_size = 0.01

        logger.info("Allocator: Size calculated", 
                    prob=round(probability, 3), 
                    atr=round(atr, 2), 
                    final_size=round(final_size, 5))
                    
        return round(float(final_size), 5)
