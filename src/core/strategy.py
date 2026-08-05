"""
Strategy Module — Orchestrates the 4-layer decision stack.

Layer 1 (Regime Filter):   Close > SMA20, Hurst trending, ADX strength
Layer 2 (Classifier):      XGBoost model predicts entry probability
Layer 3 (Allocator):       Dynamic Kelly-like position sizing (2% base risk)
Layer 4 (Oracle):          Risk firewall — DLL, profit ceiling, GFV, floor, volatility

Returns (TradeProposal, veto_reason) tuple.
Decoupled from execution scheduling — purely generative.
"""
import polars as pl
from typing import Optional, Tuple
from pydantic import BaseModel
import structlog
from src.config import settings
from src.core.regime_filter import RegimeFilter
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
    Strategy module: trend-regime gate, model inference, and size allocation.
    Decoupled from execution scheduling.
    """
    def __init__(self, regime_filter: RegimeFilter, classifier: Classifier,
                 allocator: Allocator, oracle: Oracle):
        self.regime_filter = regime_filter
        self.classifier = classifier
        self.allocator = allocator
        self.oracle = oracle

    def generate_proposal(self, context: pl.DataFrame, context_market: pl.DataFrame,
                          vix_price: float) -> Tuple[Optional[TradeProposal], Optional[str]]:
        """
        Processes market context and generates a trade proposal if all strategy
        criteria pass. Returns (proposal, veto_reason); proposal is None when
        the trade was vetoed or no signal fired.
        """
        # 1. Trend-regime gate (close > SMA20, Hurst trending, ADX strength)
        if not self.regime_filter.is_trending(context, context_market):
            logger.info("SignalGenerator: regime gate closed, skipping")
            return None, "Regime filter: not trending"

        # 2. Predict signal probability
        signal_prob = self.classifier.predict(context)

        if signal_prob <= settings.SIGNAL_THRESHOLD:
            logger.debug("SignalGenerator: Signal below threshold", prob=signal_prob)
            return None, None

        # 3. Allocation Sizing
        last_bar = context.tail(1).to_dicts()[0]
        decision_price = last_bar["close"]
        atr = last_bar["atr"] if "atr" in last_bar else settings.REFERENCE_ATR

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

        # 4. Oracle Risk Firewall Validation
        current_hurst = context["hurst"].tail(1).item() if "hurst" in context.columns else settings.HURST_THRESHOLD
        approved, reason = self.oracle.validate_trade(size, decision_price, "BUY",
                                                      current_hurst=current_hurst,
                                                      current_vix=vix_price)
        if not approved:
            logger.info("SignalGenerator: Signal vetoed by Oracle", reason=reason)
            return None, f"Oracle vetoed: {reason}"

        # 5. Construct Trade Proposal
        tp = decision_price + (atr * settings.PT_MULTIPLIER)
        sl = decision_price - (atr * settings.SL_MULTIPLIER)

        proposal = TradeProposal(
            quantity=size,
            price=decision_price,
            tp=tp,
            sl=sl
        )

        return proposal, None
