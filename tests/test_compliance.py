import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from src.execution.position_manager import PositionManager
from src.core.oracle import AccountState, AccountStatus, Oracle
from src.config import settings

@pytest.mark.asyncio
async def test_30s_hold_time_enforcement():
    """
    Test that the Router delays an exit if the 30s minimum hold hasn't been met.
    """
    # Mock Alpaca Client
    mock_client = MagicMock()
    mock_client.place_order = AsyncMock(return_value={"id": "test_order_id"})
    mock_client.get_position = AsyncMock()
    
    # Setup State
    state = AccountState(
        balance=50000.0,
        equity=50000.0,
        safety_net_floor=47500.0,
        daily_loss_limit=1100.0,
        soft_kill_switch=1050.0,
        daily_profit_ceiling=1200.0
    )
    
    oracle = Oracle(state)
    router = PositionManager(mock_client, state, oracle)
    
    # 1. Enter Trade
    # Simulate being in a trade
    router.current_position = 2
    state.current_entry_time = datetime.now(timezone.utc)
    
    # Mock verify_position to not overwrite current_position
    router._verify_position = AsyncMock()
    
    # 2. Attempt Immediate Exit (should delay)
    start_time = datetime.now(timezone.utc)
    
    # We expect execute_trade to wait
    # Note: We use a smaller min_hold for the test to avoid 30s hang
    router.min_hold_seconds = 2 
    
    await router.execute_trade("SPLG", 2, "SELL", price=18000.0)
    
    end_time = datetime.now(timezone.utc)
    elapsed = (end_time - start_time).total_seconds()
    
    assert elapsed >= 2

@pytest.mark.asyncio
async def test_daily_trade_cap_veto():
    """
    Test that the Oracle vetos new entries after 50 trades.
    """
    state = AccountState(
        balance=50000.0,
        equity=50000.0,
        safety_net_floor=47500.0,
        daily_loss_limit=1100.0,
        soft_kill_switch=1050.0,
        daily_profit_ceiling=1200.0,
        current_daily_trades=50, # Cap reached
        max_daily_trades=50
    )
    oracle = Oracle(state)
    
    # Attempt trade
    allowed = oracle.validate_trade(2, 20000.0, "BUY", current_hurst=0.6)
    
    assert allowed is False

@pytest.mark.asyncio
async def test_profit_ceiling_block():
    """
    Test that the Oracle blocks entries if profit ceiling hit.
    """
    state = AccountState(
        balance=51300.0,
        equity=51300.0,
        safety_net_floor=47500.0,
        daily_loss_limit=1100.0,
        soft_kill_switch=1050.0,
        daily_profit_ceiling=1200.0,
        current_daily_pnl=1250.0 # Ceiling hit
    )
    oracle = Oracle(state)
    
    # Attempt trade
    allowed = oracle.validate_trade(2, 20.0, "BUY", current_hurst=0.6)
    
    assert allowed is False
