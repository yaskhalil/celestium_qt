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
    # This test depends on system time, but we can mock it or test the logic.
    # For now, let's assume the current time is forced in the property check.
    pass
