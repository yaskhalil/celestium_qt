import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from src.execution.router import WebullRouter
from src.core.oracle import AccountState

@pytest.fixture
def mock_api():
    api = MagicMock()
    # Mock account response for verify_position
    mock_account_response = MagicMock()
    mock_account_response.status_code = 200
    mock_account_response.json.return_value = {"positions": []}
    api.account_v2.get_account_position.return_value = mock_account_response
    return api

@pytest.fixture
def mock_state():
    state = MagicMock(spec=AccountState)
    state.current_daily_pnl = 0.0
    state.daily_profit_ceiling = 1000.0
    state.current_entry_time = None
    return state

@pytest.mark.asyncio
async def test_execute_trade_limit_order(mock_api, mock_state):
    router = WebullRouter(mock_api, mock_state)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"order_id": "webull-order-999"}
    mock_api.order_v2.place_order.return_value = mock_response
    
    order_id = await router.execute_trade("AAPL", 5, "BUY", 150.25)
    
    assert order_id == "webull-order-999"
    mock_api.order_v2.place_order.assert_called_once()
    
    # Verify order parameters
    args, kwargs = mock_api.order_v2.place_order.call_args
    assert "new_orders" in kwargs
    stock_order = kwargs["new_orders"][0]
    assert stock_order["order_type"] == "LIMIT"
    assert stock_order["limit_price"] == "150.25"
    assert stock_order["quantity"] == "5"
    assert stock_order["side"] == "BUY"

@pytest.mark.asyncio
async def test_execute_trade_blocks_market_orders(mock_api, mock_state):
    # The current implementation requires price, effectively blocking market orders
    router = WebullRouter(mock_api, mock_state)
    order_id = await router.execute_trade("AAPL", 5, "BUY", None)
    
    assert order_id is None
    mock_api.order_v2.place_order.assert_not_called()

@pytest.mark.asyncio
async def test_daily_profit_ceiling_blocks_trade(mock_api, mock_state):
    mock_state.current_daily_pnl = 1500.0
    mock_state.daily_profit_ceiling = 1000.0
    router = WebullRouter(mock_api, mock_state)
    
    order_id = await router.execute_trade("AAPL", 1, "BUY", 150.0)
    
    assert order_id is None
    mock_api.order_v2.place_order.assert_not_called()

@pytest.mark.asyncio
async def test_position_tracking_on_fill(mock_api, mock_state):
    router = WebullRouter(mock_api, mock_state)
    
    # Setup mock to return a position
    mock_account_response = MagicMock()
    mock_account_response.status_code = 200
    mock_account_response.json.return_value = {"positions": [{"symbol": "AAPL", "position": "10"}]}
    mock_api.account_v2.get_account_position.return_value = mock_account_response
    
    # Verify position updates router state
    await router._verify_position("AAPL")
    
    assert router.current_position == 10.0

    # Setup mock to return partial position
    mock_account_response.json.return_value = {"positions": [{"symbol": "AAPL", "position": "6"}]}
    
    await router._verify_position("AAPL")
    
    assert router.current_position == 6.0
    
    # Setup mock to return no position
    mock_account_response.json.return_value = {"positions": []}
    
    await router._verify_position("AAPL")
    
    assert router.current_position == 0.0
