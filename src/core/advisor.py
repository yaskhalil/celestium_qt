import structlog
import json
import httpx
import os
from datetime import datetime
from src.core.oracle import AccountState
from src.config import settings

logger = structlog.get_logger()

REPORT_PATH = "data/reports/daily_review.md"

class Advisor:
    """
    Layer 4: The Advisor (Quant Architect Mode).
    Uses Ollama 'quant-advisor' to analyze:
    1. Regime Drift (Predicted vs. Realized)
    2. Oracle Veto Analysis
    3. Apex 4.0 Compliance (50% rule)
    """
    
    def __init__(self, ollama_url: str = settings.ADVISOR_URL):
        self.ollama_url = ollama_url
        self.model = settings.ADVISOR_MODEL

    async def generate_summary(self, state: AccountState, veto_logs: list, regime_context: dict) -> str:
        """
        Queries Ollama with surgical prompt engineering.
        """
        logger.info("Advisor: Auditing Session Data...")
        
        # 1. Surgical Prompt Construction
        prompt = f"""
        Role: CelestiumQT Lead Architect Audit (2026)
        
        [SESSION DATA]
        Current Balance: ${state.balance}
        Daily PnL: ${state.current_daily_pnl}
        Account Status: {state.status}
        Total Profit Since Payout: ${state.total_profit_since_payout}
        
        [REGIME DRIFT ANALYSIS]
        Predicted Curvature (Layer 1): {regime_context.get('hurst', 0.5)} (Hurst)
        Realized Price Action: {regime_context.get('realized_drift', 'Neutral')}
        
        [ORACLE VETO LOGS]
        Count: {len(veto_logs)}
        Last Veto Reasons: {veto_logs[-3:] if veto_logs else 'None'}
        
        [APEX 4.0 COMPLIANCE]
        50% Consistency Ceiling Status: {'DANGER' if (state.current_daily_pnl > 0 and (state.current_daily_pnl / (state.total_profit_since_payout + 0.01) > 0.45)) else 'Safe'}
        
        INSTRUCTIONS:
        1. Analyze Regime Drift: Is our statistical context failing?
        2. Veto Analysis: Why did the Oracle block high-confidence signals?
        3. Compliance: Are we approaching the 50% profit ceiling?
        4. Suggest specific threshold adjustments (e.g., widen ATR filter or adjust Oracle daily loss).
        
        OUTPUT FORMAT: Markdown 3-sentence summary followed by action items.
        """
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    result = response.json().get("response", "No commentary generated.")
                    self._save_report(result)
                    return result
                else:
                    return f"Advisor Error: {response.status_code}"
                    
        except Exception as e:
            logger.error("Advisor: LLM Audit Failed", error=str(e))
            return "Advisor Offline: Check Ollama Status."

    def _save_report(self, report: str):
        """Saves output to daily_review.md for human oversight."""
        os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(REPORT_PATH, "a") as f:
            f.write(f"\n\n# Audit Report: {timestamp}\n")
            f.write(report)
        logger.info("Advisor: Report saved to disk", path=REPORT_PATH)
