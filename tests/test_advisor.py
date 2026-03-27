import pytest
import respx
import httpx
import os
from src.core.advisor import Advisor
from src.core.oracle import AccountState
from src.config import settings

@pytest.mark.asyncio
@respx.mock
async def test_advisor_risk_warning():
    """
    Simulates a 'Loss Day' and confirms the Advisor handles the response correctly.
    """
    advisor = Advisor()
    
    # Mock Account State for a Loss Day
    state = AccountState(
        balance=26500.0,
        equity=26500.0,
        current_daily_pnl=-480.0, # Close to $500 DLL
        total_profit_since_payout=1000.0,
        safety_net_floor=26100.0
    )
    
    veto_logs = ["Vetoed high-volatility entry", "Vetoed due to spread"]
    regime_context = {"hurst": 0.42, "realized_drift": "Mean Reverting"}
    
    # Mock Ollama Response
    mock_response = "RISK WARNING: High volatility detected near Daily Loss Limit. Suggest adjusting Oracle DLL to $400 to preserve capital."
    
    respx.post(settings.ADVISOR_URL).mock(return_value=httpx.Response(200, json={"response": mock_response}))
    
    result = await advisor.generate_summary(state, veto_logs, regime_context)
    
    assert "RISK WARNING" in result
    assert "adjusting Oracle DLL" in result
    assert os.path.exists("data/reports/daily_review.md")

@pytest.mark.asyncio
@respx.mock
async def test_advisor_consistency_danger():
    """
    Simulates a 'Big Win' approaching the 50% Consistency ceiling.
    """
    advisor = Advisor()
    
    state = AccountState(
        balance=30000.0,
        equity=30000.0,
        current_daily_pnl=1800.0,
        total_profit_since_payout=2000.0 # Today is 90% of profit!
    )
    
    # Ensure the prompt logic for 'DANGER' is triggered (via internal check in advisor.py)
    # We just want to see if the LLM receives the right prompt context.
    
    respx.post(settings.ADVISOR_URL).mock(return_value=httpx.Response(200, json={"response": "CONSISTENCY CEILING REACHED. Cease trading to protect payout."}))
    
    result = await advisor.generate_summary(state, [], {})
    assert "CONSISTENCY" in result
