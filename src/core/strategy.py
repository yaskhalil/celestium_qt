import polars as pl
from typing import Optional, Tuple
from pydantic import BaseModel
import structlog
from src.config import settings
from src.core.boolean_network import BooleanStateSpace
from src.models.classifier import Classifier
from src.core.allocator import Allocator
from src.core.oracle import Oracle

logger = structlog.get_logger()

class TradeProposal(BaseModel):
    quantity: float
    price: float
    tp: float
    sl: float

class SignalGenerator:
    """
    Deep strategy module encapsulating Boolean regime checks, classification,
    and size allocation. Decoupled from execution scheduling.
    """
    def __init__(self, bn: BooleanStateSpace, classifier: Classifier, allocator: Allocator, oracle: Oracle):
        self.bn = bn
        self.classifier = classifier
        self.allocator = allocator
        self.oracle = oracle

    def generate_proposal(self, context: pl.DataFrame, context_market: pl.DataFrame, vix_price: float) -> Tuple[Optional[TradeProposal], Optional[str]]:
        """
        Processes market context and generates a trade proposal if all strategy criteria pass.
        Returns a tuple of (Optional[TradeProposal], Optional[str] veto_reason).
        """
        # 1. Map context to Boolean state bits
        state = self.bn.map_to_bits(context, context_market)
        
        # 2. Check if state is in attractor
        if not self.bn.is_in_attractor(state):
            logger.info("SignalGenerator: State not in attractor, skipping", state=state)
            return None, None

        # 3. Predict signal probability
        signal_prob = self.classifier.predict(context)
        
        if signal_prob <= settings.SIGNAL_THRESHOLD:
            logger.debug("SignalGenerator: Signal below threshold", prob=signal_prob)
            return None, None

        # 4. Allocation Sizing
        last_bar = context.tail(1).to_dicts()[0]
        decision_price = last_bar["close"]
        atr = last_bar["atr"] if "atr" in last_bar else 1.0
        
        size = self.allocator.calculate_size(
            probability=signal_prob, 
            atr=atr, 
            balance=self.oracle.state.balance, 
            current_price=decision_price,
            daily_pnl=self.oracle.state.current_daily_pnl
        )
        
        if size <= 0:
            logger.debug("SignalGenerator: Calculated size is zero", prob=signal_prob)
            return None, None

        # 5. Oracle Risk Firewall Validation
        current_hurst = context["hurst"].tail(1).item() if "hurst" in context.columns else 0.5
        approved, reason = self.oracle.validate_trade(size, decision_price, "BUY",
                                                      current_hurst=current_hurst,
                                                      current_vix=vix_price)
        if not approved:
            logger.info("SignalGenerator: Signal vetoed by Oracle", reason=reason)
            return None, f"Oracle vetoed: {reason}"

        # 6. Construct Trade Proposal
        tp = decision_price + (atr * settings.PT_MULTIPLIER)
        sl = decision_price - (atr * settings.SL_MULTIPLIER)
        
        proposal = TradeProposal(
            quantity=size,
            price=decision_price,
            tp=tp,
            sl=sl
        )
        
        return proposal, None
