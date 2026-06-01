import pytest
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
from src.core.engine import ScheduledEngine
from src.core.oracle import AccountStatus, AccountState

@pytest.fixture
def mock_alpaca_client():
    return MagicMock()

@pytest.fixture
def engine(mock_alpaca_client):
    with patch('src.core.engine.DuckDBBuffer'), \
         patch('src.core.engine.BooleanStateSpace'), \
         patch('src.core.engine.Oracle'), \
         patch('src.core.engine.AlpacaRouter'), \
         patch('src.core.engine.Classifier'), \
         patch('src.core.engine.Allocator'), \
         patch('src.core.engine.Advisor'), \
         patch('src.core.engine.AlpacaIngestor'):
        
        # Instantiate ScheduledEngine
        eng = ScheduledEngine(mock_alpaca_client)
        eng.router._verify_position = AsyncMock() # Make verify_position an AsyncMock
        eng.notifier = AsyncMock() # Mock notifier
        yield eng

@pytest.mark.asyncio
async def test_cmd_help(engine):
    await engine.process_telegram_command("/help")
    engine.notifier.notify.assert_called_once()
    args, _ = engine.notifier.notify.call_args
    assert "CelestiumQT Commands" in args[0]

@pytest.mark.asyncio
async def test_cmd_status(engine):
    engine.router.current_position = 5.0
    engine.account_state.balance = 350.0
    await engine.process_telegram_command("/status")
    engine.notifier.notify.assert_called_once()
    args, _ = engine.notifier.notify.call_args
    assert "SYSTEM STATUS" in args[0]
    assert "`5.0` shares" in args[0]
    assert "$350.00" in args[0]

@pytest.mark.asyncio
async def test_cmd_pause_resume(engine):
    engine.account_state.status = AccountStatus.ACTIVE
    
    # Pause
    await engine.process_telegram_command("/pause")
    assert engine.account_state.status == AccountStatus.PAUSED
    engine.notifier.notify.assert_called_once_with("⏸ *SYSTEM PAUSED* - Oracle has been manually paused. New signals will be vetoed.")
    
    # Resume
    engine.notifier.notify.reset_mock()
    await engine.process_telegram_command("/resume")
    assert engine.account_state.status == AccountStatus.ACTIVE
    engine.notifier.notify.assert_called_once_with("▶️ *SYSTEM RESUMED* - Oracle is now active and monitoring signals.")

@pytest.mark.asyncio
async def test_cmd_positions(engine):
    engine.router.current_position = 0.0
    await engine.process_telegram_command("/positions")
    engine.notifier.notify.assert_called_once()
    assert "No active positions" in engine.notifier.notify.call_args[0][0]
    
    engine.notifier.notify.reset_mock()
    engine.router.current_position = 10.0
    engine.entry_price = 60.0
    engine.stop_loss = 58.0
    engine.take_profit = 64.0
    await engine.process_telegram_command("/positions")
    engine.notifier.notify.assert_called_once()
    assert "LONG" in engine.notifier.notify.call_args[0][0]
    assert "`10.0` shares" in engine.notifier.notify.call_args[0][0]
    assert "$60.00" in engine.notifier.notify.call_args[0][0]

@pytest.mark.asyncio
async def test_cmd_vetoes(engine):
    engine.veto_logs = []
    await engine.process_telegram_command("/vetoes")
    engine.notifier.notify.assert_called_once_with("🛡 *ORACLE VETOES*\nNo vetoes recorded today.")
    
    engine.notifier.notify.reset_mock()
    engine.veto_logs = ["Oracle vetoed: prob 0.3", "Vetoed: hurst threshold not met"]
    await engine.process_telegram_command("/vetoes")
    engine.notifier.notify.assert_called_once()
    assert "Oracle vetoed: prob 0.3" in engine.notifier.notify.call_args[0][0]

@pytest.mark.asyncio
async def test_cmd_performance_no_backtest(engine):
    with patch("os.path.exists", return_value=False):
        await engine.process_telegram_command("/performance")
        engine.notifier.notify.assert_called_once()
        args, _ = engine.notifier.notify.call_args
        assert "MODEL & TRADING PERFORMANCE" in args[0]
        assert "No backtest report found" in args[0]

@pytest.mark.asyncio
async def test_cmd_performance_with_backtest(engine):
    mock_backtest_json = '{"Total Net Profit": 15.5, "Win Rate": 0.55, "Total Trades": 100, "Max Drawdown": 2.0, "Recovery Factor": 7.75, "Consistency Score": 0.05}'
    
    # We patch exists to return True for the backtest report, and mock open for json loading
    def mock_exists(path):
        if "backtest_report.json" in path:
            return True
        return False

    with patch("os.path.exists", side_effect=mock_exists), \
         patch("builtins.open", mock_open(read_data=mock_backtest_json)):
        await engine.process_telegram_command("/performance")
        engine.notifier.notify.assert_called_once()
        args, _ = engine.notifier.notify.call_args
        assert "MODEL & TRADING PERFORMANCE" in args[0]
        assert "Historical Backtest (1-Year SPY)" in args[0]
        assert "55.0%" in args[0]
        assert "100" in args[0]

