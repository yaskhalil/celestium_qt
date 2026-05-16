import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, ANY, patch
from src.execution.router import AlpacaRouter
from src.core.oracle import AccountState
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

@pytest.mark.asyncio
async def test_execute_trade_limit_order(mock_client, mock_state):
    router = AlpacaRouter(mock_client, mock_state)
    
    # Mock responses
    mock_client.get_position.return_value = 0.0
    mock_client.place_order.return_value = {"id": "alpaca-order-999"}
    
    with patch("src.execution.router.settings.SHADOW_MODE", False):
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

@pytest.mark.asyncio
async def test_position_tracking(mock_client, mock_state):
    router = AlpacaRouter(mock_client, mock_state)
    
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
