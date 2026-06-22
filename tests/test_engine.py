import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import polars as pl
from src.core.engine import ScheduledEngine
import asyncio

@pytest.fixture
def mock_alpaca_client():
    client = MagicMock()
    client.get_last_price = AsyncMock(return_value=15.0)
    return client

@pytest.fixture
def engine(mock_alpaca_client):
    with patch('src.core.engine.DuckDBBuffer'), \
         patch('src.core.engine.BooleanStateSpace'), \
         patch('src.core.engine.Oracle'), \
         patch('src.core.engine.PositionManager'), \
         patch('src.core.engine.Classifier'), \
         patch('src.core.engine.Allocator'), \
         patch('src.core.engine.Advisor'), \
         patch('src.core.engine.AlpacaIngestor'):
        yield ScheduledEngine(mock_alpaca_client)

@pytest.mark.asyncio
async def test_engine_tick_attractor_veto(engine):
    """Test that the engine skips if the state is not in an attractor."""
    # Setup: mock data that is NOT in attractor
    engine.buffer.get_context.return_value = pl.DataFrame({"close": [100.0] * 150})
    engine.bn.map_to_bits.return_value = 5 # Not in target attractors
    engine.bn.is_in_attractor.return_value = False
    
    engine.router._verify_position = AsyncMock()
    engine.router.current_position = 0

    await engine.tick_signal()
    
    engine.classifier.predict.assert_not_called()

@pytest.mark.asyncio
async def test_engine_tick_success(engine):
    """Test that the engine executes a trade when all conditions pass."""
    # Setup: mock data in attractor and positive signal
    df = pl.DataFrame({
        "close": [100.0] * 150,
        "atr": [1.0] * 150,
        "hurst": [0.6] * 150
    })
    engine.buffer.get_context.return_value = df
    engine.bn.map_to_bits.return_value = 1
    engine.bn.is_in_attractor.return_value = True
    engine.classifier.predict.return_value = 0.9
    engine.allocator.calculate_size.return_value = 1
    engine.oracle.validate_trade.return_value = True
    
    engine.alpaca_client.get_last_price = AsyncMock(return_value=15.0)
    
    engine.router._verify_position = AsyncMock()
    engine.router.current_position = 0

    # We patch the router execution to avoid actual async execution
    with patch.object(engine.router, 'execute_trade', new_callable=AsyncMock, return_value=True) as mock_run:
        await engine.tick_signal()
        mock_run.assert_called_once()
        # Verify the call parameters
        args, kwargs = mock_run.call_args
        assert args[1] == 1 # Quantity
        assert args[2] == "BUY"
        assert kwargs["price"] == 100.0

@pytest.mark.asyncio
async def test_engine_tick_eod(engine):
    """Test that tick_eod calls router.flatten with the current price."""
    engine.alpaca_client.get_last_price = AsyncMock(return_value=123.45)
    engine.router.flatten = AsyncMock()

    await engine.tick_eod()

    engine.router.flatten.assert_called_once_with("SPYM", 123.45)
