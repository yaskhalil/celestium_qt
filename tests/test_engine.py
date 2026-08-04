import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import polars as pl
from src.core.engine import ScheduledEngine
from src.core.strategy import TradeProposal

SIGNAL_DF = pl.DataFrame({"close": [100.0] * 150, "timestamp": list(range(150))})


@pytest.fixture
def mock_alpaca_client():
    client = MagicMock()
    client.get_last_price = AsyncMock(return_value=15.0)
    client.get_last_price_conservative = AsyncMock(return_value=15.0)
    return client


@pytest.fixture
def engine(mock_alpaca_client):
    with patch('src.core.engine.DuckDBBuffer'), \
         patch('src.core.engine.RegimeFilter'), \
         patch('src.core.engine.Oracle'), \
         patch('src.core.engine.PositionManager'), \
         patch('src.core.engine.Classifier'), \
         patch('src.core.engine.Allocator'), \
         patch('src.core.engine.Advisor'), \
         patch('src.core.engine.AlpacaIngestor'), \
         patch('src.core.engine.SignalGenerator'):
        yield ScheduledEngine(mock_alpaca_client)


def _setup_engine_state(engine):
    """Common wiring: real context df, flat position, no pending exits."""
    engine.buffer.get_context.return_value = SIGNAL_DF
    engine.router.sync_position = AsyncMock()
    engine.router.current_position = 0
    engine.router.execute_trade = AsyncMock(return_value="order-1")


@pytest.mark.asyncio
async def test_engine_tick_signal_veto(engine):
    """A vetoed proposal must NOT result in an executed trade."""
    _setup_engine_state(engine)
    engine.strategy.generate_proposal.return_value = (None, "Oracle vetoed: DLL breached")

    await engine.tick_signal()

    engine.router.execute_trade.assert_not_called()


@pytest.mark.asyncio
async def test_engine_tick_signal_success(engine):
    """An approved proposal must be executed with the right parameters."""
    _setup_engine_state(engine)
    proposal = TradeProposal(quantity=1, price=100.0, tp=102.0, sl=98.0)
    engine.strategy.generate_proposal.return_value = (proposal, None)

    await engine.tick_signal()

    engine.router.execute_trade.assert_called_once_with(
        "SPYM", 1, "BUY", price=100.0, tp=102.0, sl=98.0
    )


@pytest.mark.asyncio
async def test_engine_tick_signal_skips_when_in_position(engine):
    """Engine must not generate a new signal while a position is open."""
    _setup_engine_state(engine)
    engine.router.current_position = 5

    await engine.tick_signal()

    engine.strategy.generate_proposal.assert_not_called()


@pytest.mark.asyncio
async def test_engine_tick_eod(engine):
    """Test that tick_eod calls router.flatten with the current price."""
    engine.alpaca_client.get_last_price = AsyncMock(return_value=123.45)
    engine.router.flatten = AsyncMock()

    await engine.tick_eod()

    engine.router.flatten.assert_called_once_with("SPYM", 123.45)
