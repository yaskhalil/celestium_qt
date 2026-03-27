import structlog
import json
import httpx
from datetime import datetime
from src.core.oracle import AccountState

logger = structlog.get_logger()

class Advisor:
    """
    Layer 4: The Advisor.
    Uses a local LLM (Ollama) to generate post-session summaries and risk analysis.
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434/api/generate"):
        self.ollama_url = ollama_url

    async def generate_summary(self, state: AccountState) -> str:
        """
        Queries Ollama to summarize the current account status and history.
        """
        logger.info("Advisor: Generating Post-Close Summary...")
        
        # 1. Prepare Context for LLM
        history_summary = [
            {"date": s.date.strftime("%Y-%m-%d"), "pnl": s.pnl} 
            for s in state.trading_history[-5:]
        ]
        
        prompt = f"""
        You are CelestiumQT Lead Architect. Analyze this trading state:
        Current Balance: ${state.balance}
        Daily PnL: ${state.current_daily_pnl}
        Status: {state.status}
        Recent History: {json.dumps(history_summary)}
        
        Rules:
        - Apex 4.0 Safety Net: $26,100
        - 50% Consistency Rule applies.
        
        Provide a 3-sentence summary of performance and any risk of account failure.
        """
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": "mistral", # or llama3
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json().get("response", "No advisor commentary available.")
                    logger.info("Advisor: Summary Generated Successfully")
                    return result
                else:
                    return f"Advisor Error: {response.status_code}"
                    
        except Exception as e:
            logger.error("Advisor: LLM connection failed", error=str(e))
            return "Advisor: (Offline)"
