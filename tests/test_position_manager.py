import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.execution.position_manager import PositionManager
from src.core.oracle import AccountState, Oracle
from src.execution.alpaca_client import AlpacaClient


@pytest.fixture
def mock_client():
    client = MagicMock(spec=AlpacaClient)
    client.get_position = AsyncMock(return_value=0.0)
    client.get_position_market_value = AsyncMock(return_value=0.0)
    client.place_order = AsyncMock(return_value={"id": "alpaca-order-999"})
    return client


@pytest.fixture
def mock_state():
    return AccountState(balance=50000.0, equity=50000.0)


@pytest.fixture
def mock_oracle():
    oracle = MagicMock(spec=Oracle)
    oracle.validate_sell.return_value = (True, "Approved")
    return oracle


@pytest.mark.asyncio
async def test_execute_trade_buy(mock_client, mock_state, mock_oracle):
    router = PositionManager(mock_client, mock_state, mock_oracle)

    with patch("src.execution.position_manager.settings.SHADOW_MODE", False):
        order_id = await router.execute_trade("SPLG", 5, "BUY", 150.25)

    assert order_id == "alpaca-order-999"
    mock_client.get_position.assert_called_once_with("SPLG")

    # Current interface: market orders via symbol/qty/side (limit params removed)
    mock_client.place_order.assert_called_once_with(
        symbol="SPLG", qty=5, side="BUY"
    )

    # Oracle state must be updated with the buy cost
    mock_oracle.update_session.assert_called_once_with(
        pnl=0.0, cash_flow=5 * 150.25, quantity=5, side="BUY", position_value=5 * 150.25
    )


@pytest.mark.asyncio
async def test_position_tracking(mock_client, mock_state, mock_oracle):
    router = PositionManager(mock_client, mock_state, mock_oracle)

    # Setup mock to return a position
    mock_client.get_position.return_value = 10.0
    mock_client.get_position_market_value.return_value = 1502.5

    await router.sync_position("SPLG")

    assert router.current_position == 10.0
    mock_client.get_position.assert_called_once_with("SPLG")

    # Setup mock to return no position
    mock_client.get_position.return_value = 0.0
    mock_client.get_position_market_value.return_value = 0.0

    await router.sync_position("SPLG")

    assert router.current_position == 0.0


@pytest.mark.asyncio
async def test_flatten_position(mock_client, mock_state, mock_oracle):
    router = PositionManager(mock_client, mock_state, mock_oracle)

    # Simulate an active position of 5 shares
    mock_client.get_position.return_value = 5.0
    mock_client.get_position_market_value.return_value = 751.25
    mock_client.place_order.return_value = {"id": "alpaca-order-exit"}

    with patch("src.execution.position_manager.settings.SHADOW_MODE", False):
        await router.flatten("SPLG", 150.25)

    mock_oracle.validate_sell.assert_called_once_with(5.0, 150.25)
    mock_client.place_order.assert_called_once_with(
        symbol="SPLG", qty=5.0, side="SELL"
    )
    # Exit proceeds settle through the Oracle
    mock_oracle.update_session.assert_called_once()
    args, kwargs = mock_oracle.update_session.call_args
    assert kwargs["side"] == "SELL"
    assert kwargs["quantity"] == 5.0
