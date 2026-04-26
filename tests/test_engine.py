import pytest
from unittest.mock import MagicMock, patch
import polars as pl
from src.core.engine import ScheduledEngine
import asyncio

@pytest.fixture
def mock_webull_client():
    return MagicMock()

@pytest.fixture
def engine(mock_webull_client):
    with patch('src.core.engine.DuckDBBuffer'), \
         patch('src.core.engine.BooleanStateSpace'), \
         patch('src.core.engine.Oracle'), \
         patch('src.core.engine.WebullRouter'), \
         patch('src.core.engine.Classifier'), \
         patch('src.core.engine.Allocator'), \
         patch('src.core.engine.Advisor'), \
         patch('src.core.engine.TradeClient'), \
         patch('src.core.engine.WebullIngestor'):
        yield ScheduledEngine(mock_webull_client)

@pytest.mark.asyncio
async def test_engine_tick_attractor_veto(engine):
    """Test that the engine skips if the state is not in an attractor."""
    # Setup: mock data that is NOT in attractor
    engine.buffer.get_context.return_value = pl.DataFrame({"close": [100.0] * 150})
    engine.bn.map_to_bits.return_value = 5 # Not in {1, 3, 7}
    engine.bn.is_in_attractor.return_value = False
    
    await engine.tick()
    
    assert any("Not in attractor: 5" in log for log in engine.veto_logs)
    engine.classifier.predict.assert_not_called()

@pytest.mark.asyncio
async def test_engine_tick_success(engine):
    """Test that the engine executes a trade when all conditions pass."""
    # Setup: mock data in attractor and positive signal
    df = pl.DataFrame({
        "close": [100.0] * 150,
        "atr": [1.0] * 150
    })
    engine.buffer.get_context.return_value = df
    engine.bn.map_to_bits.return_value = 1
    engine.bn.is_in_attractor.return_value = True
    engine.classifier.predict.return_value = 0.9
    engine.allocator.calculate_size.return_value = 1
    engine.oracle.validate_trade.return_value = True
    
    from unittest.mock import AsyncMock, ANY
    engine.ingestor.fetch_and_persist = AsyncMock()

    # We patch the router execution to avoid actual async execution
    with patch.object(engine.router, 'execute_trade', new_callable=AsyncMock, return_value=True) as mock_run:
        await engine.tick()
        mock_run.assert_called_once()
        # Ensure the router was called via asyncio.run
        engine.router.execute_trade.assert_called_with(ANY, 1, "BUY", price=100.0)
