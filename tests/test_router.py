import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.execution.router import WebullRouter
from src.core.oracle import AccountState

@pytest.fixture
def mock_api():
    return MagicMock()

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
    mock_api.place_order.return_value = mock_response
    
    order_id = await router.execute_trade("AAPL", 5, "BUY", 150.25)
    
    assert order_id == "webull-order-999"
    mock_api.place_order.assert_called_once()
    
    # Verify order parameters
    args, kwargs = mock_api.place_order.call_args
    stock_order = kwargs["stock_order"]
    assert stock_order["order_type"] == "LIMIT"
    assert stock_order["limit_price"] == "150.25"
    assert stock_order["qty"] == "5"
    assert stock_order["side"] == "BUY"

@pytest.mark.asyncio
async def test_execute_trade_blocks_market_orders(mock_api, mock_state):
    # The current implementation requires price, effectively blocking market orders
    router = WebullRouter(mock_api, mock_state)
    order_id = await router.execute_trade("AAPL", 5, "BUY", None)
    
    assert order_id is None
    mock_api.place_order.assert_not_called()

@pytest.mark.asyncio
async def test_daily_profit_ceiling_blocks_trade(mock_api, mock_state):
    mock_state.current_daily_pnl = 1500.0
    mock_state.daily_profit_ceiling = 1000.0
    router = WebullRouter(mock_api, mock_state)
    
    order_id = await router.execute_trade("AAPL", 1, "BUY", 150.0)
    
    assert order_id is None
    mock_api.place_order.assert_not_called()

@pytest.mark.asyncio
async def test_position_tracking_on_fill(mock_api, mock_state):
    router = WebullRouter(mock_api, mock_state)
    
    # Simulate a Buy Fill
    await router._on_order_update({
        "status": "FILLED",
        "side": "BUY",
        "filled_quantity": 10
    })
    
    assert router.current_position == 10
    assert mock_state.current_entry_time is not None
    assert mock_state.save.called

    # Simulate a Sell Fill (Partial Close)
    await router._on_order_update({
        "status": "FILLED",
        "side": "SELL",
        "filled_quantity": 4
    })
    
    assert router.current_position == 6
    
    # Simulate a Full Close
    await router._on_order_update({
        "status": "FILLED",
        "side": "SELL",
        "filled_quantity": 6
    })
    
    assert router.current_position == 0
    assert mock_state.current_entry_time is None
