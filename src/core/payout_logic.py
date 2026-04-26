from typing import Dict
from src.config import settings
from src.core.oracle import AccountState

class PayoutAuditor:
    """
    Implements Bulenox 50K EOD (Option 2) Payout Rules.
    Tracks reserves, withdrawal eligibility, and profit splits.
    """
    
    def __init__(self, state: AccountState):
        self.state = state
        self.safety_reserve = settings.SAFETY_THRESHOLD_RESERVE
        self.min_withdrawal = settings.MIN_WITHDRAWAL

    def calculate_withdrawable_amount(self) -> float:
        """
        Calculates how much can be taken out while preserving the reserve.
        Balance must be > $52,600 for a 50k account.
        """
        threshold = settings.STARTING_BALANCE + self.safety_reserve
        if self.state.balance <= threshold:
            return 0.0
            
        withdrawable = self.state.balance - threshold
        return max(0.0, withdrawable)

    def get_payout_projection(self) -> Dict:
        """
        Projects the net payout after Bulenox profit splits.
        Split: 100% of first $10,000, then 90% to Trader / 10% to Bulenox.
        """
        gross_withdrawable = self.calculate_withdrawable_amount()
        if gross_withdrawable < self.min_withdrawal:
            return {
                "eligible": False,
                "reason": f"Minimum withdrawal of ${self.min_withdrawal} not met.",
                "gross_available": gross_withdrawable
            }

        # Calculate split
        # We need to know how much has already been paid out to apply the $10k rule accurately.
        # For simplicity, we'll assume total_profit_since_payout represents accumulated gains.
        
        # Note: Bulenox usually tracks total paid out. 
        # If total_paid < 10,000: Net = Gross
        # Else: Net = Gross * 0.90
        
        # This is a simplified projection
        is_first_10k = self.state.total_profit_since_payout < 10000.0
        
        if is_first_10k:
            net_to_trader = gross_withdrawable # Simplified
        else:
            net_to_trader = gross_withdrawable * 0.90

        return {
            "eligible": True,
            "gross_available": round(gross_withdrawable, 2),
            "net_to_trader": round(net_to_trader, 2),
            "reserve_preserved": self.safety_reserve
        }
