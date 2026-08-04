import pytest
import asyncio
from datetime import datetime, time, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from src.execution.position_manager import PositionManager
from src.core.oracle import AccountState, AccountStatus, Oracle
from src.core.notifier import TelegramNotifier


class FakeNotifier(TelegramNotifier):
    """Async no-op notifier so tests never touch Telegram/network."""
    async def notify(self, message: str): ...
    async def notify_trade(self, *args, **kwargs): ...
    async def notify_risk_veto(self, reason: str): ...
    async def notify_startup(self, *args, **kwargs): ...
    async def notify_shutdown(self, *args, **kwargs): ...
    async def notify_daily_recap(self, *args, **kwargs): ...


@pytest.mark.asyncio
async def test_30s_hold_time_enforcement():
    """
    Test that the Router delays a SELL until the minimum hold time has elapsed.
    """
    mock_client = MagicMock()
    mock_client.place_order = AsyncMock(return_value={"id": "test_order_id"})
    mock_client.get_position = AsyncMock(return_value=2.0)
    mock_client.get_position_market_value = AsyncMock(return_value=36000.0)

    state = AccountState(balance=50000.0, equity=50000.0)
    oracle = Oracle(state)
    router = PositionManager(mock_client, state, oracle, notifier=FakeNotifier())

    # Simulate being in a trade, entered moments ago
    router.current_position = 2
    state.current_entry_time = datetime.now(timezone.utc)

    # Shorten the hold for the test to avoid a 30s hang
    router.min_hold_seconds = 2

    with patch("src.execution.position_manager.settings.SHADOW_MODE", False):
        start_time = datetime.now(timezone.utc)
        await router.execute_trade("SPLG", 2, "SELL", price=18000.0)
        end_time = datetime.now(timezone.utc)

    elapsed = (end_time - start_time).total_seconds()
    assert elapsed >= 2
    mock_client.place_order.assert_called_once()


def test_daily_trade_cap_veto():
    """The Oracle vetos new entries once the daily trade cap is reached."""
    state = AccountState(
        balance=50000.0,
        equity=50000.0,
        current_daily_trades=50,  # Cap reached
        max_daily_trades=50
    )
    oracle = Oracle(state)

    approved, reason = oracle.validate_trade(2, 20000.0, "BUY", current_hurst=0.6,
                                             current_time=time(10, 0))
    assert approved is False
    assert "cap" in reason.lower()


def test_profit_ceiling_block():
    """The Oracle blocks entries once the daily profit ceiling is hit."""
    state = AccountState(
        balance=20000.0,          # ceiling = 6% = $1,200
        equity=20000.0,
        current_daily_pnl=1250.0  # Ceiling hit
    )
    oracle = Oracle(state)

    approved, reason = oracle.validate_trade(2, 20.0, "BUY", current_hurst=0.6,
                                             current_time=time(10, 0))
    assert approved is False
    assert "ceiling" in reason.lower()
