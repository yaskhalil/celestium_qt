import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, ANY, patch
from src.execution.router import WebullRouter
from src.core.oracle import AccountState
from src.execution.webull_client import WebullClient

@pytest.fixture
def mock_client():
    client = MagicMock(spec=WebullClient)
    client.request = AsyncMock()
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
    router = WebullRouter(mock_client, mock_state)
    
    # Mock _verify_position response
    mock_client.request.side_effect = [
        {"data": []}, # For _verify_position
        {"order_id": "webull-order-999"} # For place_order
    ]
    
    with patch("src.execution.router.settings.SHADOW_MODE", False):
        order_id = await router.execute_trade("AAPL", 5, "BUY", 150.25)
    
    assert order_id == "webull-order-999"
    assert mock_client.request.call_count == 2
    
    # Verify order parameters in the second call
    args, kwargs = mock_client.request.call_args_list[1]
    assert args[0] == "POST"
    assert args[1] == "/openapi/order/place"
    body = kwargs["body"]
    assert body["order_type"] == "LIMIT"
    assert body["limit_price"] == "150.25"
    assert body["quantity"] == "5"
    assert body["side"] == "BUY"

@pytest.mark.asyncio
async def test_position_tracking(mock_client, mock_state):
    router = WebullRouter(mock_client, mock_state)
    
    # Setup mock to return a position
    mock_client.request.return_value = {"data": [{"symbol": "AAPL", "position": "10"}]}
    
    # Verify position updates router state
    await router._verify_position("AAPL")
    
    assert router.current_position == 10.0
    mock_client.request.assert_called_once_with("GET", "/openapi/account/positions", params=ANY)

    # Setup mock to return no position
    mock_client.request.return_value = {"data": []}
    
    await router._verify_position("AAPL")
    
    assert router.current_position == 0.0
