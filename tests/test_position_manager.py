import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.execution.position_manager import PositionManager
from src.core.oracle import AccountState, Oracle
from src.execution.alpaca_client import AlpacaClient

@pytest.fixture
def mock_client():
    client = MagicMock(spec=AlpacaClient)
    client.get_position = AsyncMock()
    client.place_order = AsyncMock()
    return client

@pytest.fixture
def mock_state():
    state = MagicMock(spec=AccountState)
    state.current_daily_pnl = 0.0
    state.daily_profit_ceiling = 1000.0
    state.current_entry_time = None
    return state

@pytest.fixture
def mock_oracle():
    oracle = MagicMock(spec=Oracle)
    return oracle

@pytest.mark.asyncio
async def test_execute_trade_limit_order(mock_client, mock_state, mock_oracle):
    router = PositionManager(mock_client, mock_state, mock_oracle)
    
    # Mock responses
    mock_client.get_position.return_value = 0.0
    mock_client.place_order.return_value = {"id": "alpaca-order-999"}
    
    with patch("src.execution.position_manager.settings.SHADOW_MODE", False):
        order_id = await router.execute_trade("SPLG", 5, "BUY", 150.25)
    
    assert order_id == "alpaca-order-999"
    assert mock_client.get_position.call_count == 1
    assert mock_client.place_order.call_count == 1
    
    # Verify order parameters
    mock_client.place_order.assert_called_once_with(
        symbol="SPLG",
        qty=5,
        side="BUY",
        order_type="limit",
        limit_price=150.25
    )
    
    # Verify oracle was updated
    mock_oracle.update_session.assert_called_once_with(cash_flow=5 * 150.25, quantity=5, side="BUY")

@pytest.mark.asyncio
async def test_position_tracking(mock_client, mock_state, mock_oracle):
    router = PositionManager(mock_client, mock_state, mock_oracle)
    
    # Setup mock to return a position
    mock_client.get_position.return_value = 10.0
    
    # Verify position updates router state
    await router._verify_position("SPLG")
    
    assert router.current_position == 10.0
    mock_client.get_position.assert_called_once_with("SPLG")

    # Setup mock to return no position
    mock_client.get_position.return_value = 0.0
    
    await router._verify_position("SPLG")
    
    assert router.current_position == 0.0

@pytest.mark.asyncio
async def test_flatten_position(mock_client, mock_state, mock_oracle):
    router = PositionManager(mock_client, mock_state, mock_oracle)
    
    # 1. Setup mock to simulate active position of 5 shares
    mock_client.get_position.return_value = 5.0
    mock_client.place_order.return_value = {"id": "alpaca-order-exit"}
    
    with patch("src.execution.position_manager.settings.SHADOW_MODE", False):
        await router.flatten("SPLG", 150.25)
        
    mock_client.place_order.assert_called_once_with(
        symbol="SPLG",
        qty=5.0,
        side="SELL",
        order_type="market",
        limit_price=None
    )
