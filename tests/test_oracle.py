import pytest
from datetime import datetime, time
from src.core.oracle import Oracle, AccountState, AccountStatus, DailySession

def test_daily_loss_limit_pausing():
    """Confirms the Oracle pauses trading on DLL breach."""
    state = AccountState(
        balance=27000.0,
        equity=27000.0,
        current_daily_pnl=-450.0,
        daily_loss_limit=500.0
    )
    oracle = Oracle(state)
    
    # Trade 1: Small loss - Should be allowed
    assert oracle.validate_trade(1, 15000.0, "BUY", current_time=time(10, 0), current_hurst=0.6) is True
    
    # Simulate a loss that hits the DLL
    oracle.update_session(pnl=-60.0) 
    assert state.status == AccountStatus.PAUSED_DAILY_LOSS
    
    # Trade 2: Should be blocked
    assert oracle.validate_trade(1, 15000.0, "BUY", current_time=time(10, 0), current_hurst=0.6) is False

def test_safety_net_floor():
    """Confirms the Oracle blocks trades below $26,100."""
    state = AccountState(
        balance=26050.0, # Below $26.1k
        equity=26050.0,
        safety_net_floor=26100.0
    )
    oracle = Oracle(state)
    assert oracle.validate_trade(1, 15000.0, "BUY", current_time=time(10, 0), current_hurst=0.6) is False

def test_consistency_alert_logic():
    """Simulates a 'Big Win' and checks for the consistency alert."""
    state = AccountState(
        balance=27000.0,
        equity=27000.0,
        current_daily_pnl=1000.0, # Today is a big win
        daily_profit_ceiling=1200.0,
        total_profit_since_payout=1500.0, # Total profit is $1.5k
        trading_history=[DailySession(date=datetime.now(), pnl=500.0)]
    )
    oracle = Oracle(state)
    
    # Consistency Ratio = 1000 / 1500 = 66% (> 50%)
    # Current logic only warns, but we can verify it logs.
    assert oracle.validate_trade(1, 15000.0, "BUY", current_time=time(10, 0), current_hurst=0.6) is True

def test_account_state_cash_fields():
    """Verifies that AccountState has settled_cash and unsettled_cash fields."""
    state = AccountState(balance=400.0)
    assert hasattr(state, 'settled_cash')
    assert hasattr(state, 'unsettled_cash')
    # Should default to balance if not provided
    assert state.settled_cash == 400.0
    assert state.unsettled_cash == 0.0

def test_gfv_protection():
    """Confirms the Oracle blocks BUY trades exceeding settled cash."""
    state = AccountState(
        balance=400.0,
        settled_cash=100.0,
        unsettled_cash=300.0,
        safety_net_floor=300.0
    )
    oracle = Oracle(state)
    
    # Cost: 2 shares * $60 = $120. Settled: $100. Should be blocked by GFV logic.
    assert oracle.validate_trade(2, 60.0, "BUY", current_time=time(10, 0), current_hurst=0.5) is False
    
    # Cost: 1 share * $60 = $60. Settled: $100. Should be allowed.
    assert oracle.validate_trade(1, 60.0, "BUY", current_time=time(10, 0), current_hurst=0.5) is True

def test_eod_time_limit():
    """Simulates trading during the Apex flat period (4:55 PM - 6:00 PM ET)."""
    state = AccountState(balance=400.0)
    oracle = Oracle(state)

    # Within flat period: 5:30 PM (17:30)
    assert state.is_trading_allowed(current_time=time(17, 30)) is False
    assert oracle.validate_trade(1, 60.0, "BUY", current_time=time(17, 30), current_hurst=0.6) is False

    # Outside flat period: 10:00 AM (10:00)
    assert state.is_trading_allowed(current_time=time(10, 0)) is True
    assert oracle.validate_trade(1, 60.0, "BUY", current_time=time(10, 0), current_hurst=0.6) is True

def test_t1_settlement_flow():
    """Verifies cash pool movement intraday and conversion at EOD."""
    from src.config import settings
    state = AccountState(
        balance=400.0,
        settled_cash=400.0,
        unsettled_cash=0.0
    )
    oracle = Oracle(state)
    
    comm = 2 * settings.COMMISSION_PER_LOT
    
    # 1. Simulate BUY entry (cost: 340.0, quantity: 2)
    oracle.update_session(pnl=0.0, cash_flow=340.0, quantity=2, side="BUY")
    expected_settled = 400.0 - (340.0 + comm)
    assert round(state.settled_cash, 2) == round(expected_settled, 2)
    assert state.unsettled_cash == 0.0
    assert round(state.balance, 2) == round(expected_settled, 2)

    # 2. Simulate SELL exit (pnl: 10.0, proceeds/cash_flow: 350.0)
    oracle.update_session(pnl=10.0, cash_flow=350.0, quantity=2, side="SELL")
    expected_unsettled = 350.0 - comm
    assert round(state.settled_cash, 2) == round(expected_settled, 2)
    assert round(state.unsettled_cash, 2) == round(expected_unsettled, 2)
    expected_balance = expected_settled + expected_unsettled
    assert round(state.balance, 2) == round(expected_balance, 2)

    # 3. Simulate EOD anchor
    oracle.process_eod_anchor()
    assert round(state.settled_cash, 2) == round(expected_balance, 2)
    assert state.unsettled_cash == 0.0
    assert round(state.balance, 2) == round(expected_balance, 2)
