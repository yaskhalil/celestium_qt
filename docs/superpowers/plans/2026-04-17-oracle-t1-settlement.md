# Task 5: Oracle T+1 Settlement Logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement T+1 settlement logic in the Oracle to prevent Good Faith Violations (GFV) for Webull cash accounts.

**Architecture:** Update `AccountState` to track settled/unsettled cash. Update `Oracle` to veto trades that would use unsettled funds (GFV risk) and handle cash movement during session updates and EOD.

**Tech Stack:** Python 3.12+, Pydantic v2, structlog.

---

### Task 5.1: Update AccountState Model

**Files:**
- Modify: `src/core/oracle.py`

- [ ] **Step 1: Write the failing test**
Create a test that initializes `AccountState` and checks for `settled_cash` and `unsettled_cash` fields.

```python
def test_account_state_cash_fields():
    state = AccountState(balance=400.0)
    assert hasattr(state, 'settled_cash')
    assert hasattr(state, 'unsettled_cash')
    # Should default to balance if not provided
    assert state.settled_cash == 400.0
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_oracle.py -v`
Expected: FAIL (AttributeError)

- [ ] **Step 3: Update `AccountState`**
Add fields and a validator to ensure `settled_cash` defaults to `balance`.

```python
from pydantic import BaseModel, Field, ConfigDict, model_validator

class AccountState(BaseModel):
    # ... existing fields ...
    settled_cash: float = 0.0
    unsettled_cash: float = 0.0

    @model_validator(mode='after')
    def sync_cash_on_init(self) -> 'AccountState':
        if self.settled_cash == 0.0 and self.unsettled_cash == 0.0:
            self.settled_cash = self.balance
        return self
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_oracle.py -v`

- [ ] **Step 5: Commit**
```bash
git add src/core/oracle.py
git commit -m "feat(oracle): add settled and unsettled cash to AccountState"
```

### Task 5.2: Implement GFV Prevention in `validate_trade`

**Files:**
- Modify: `src/core/oracle.py`
- Test: `tests/test_oracle.py`

- [ ] **Step 1: Write the failing test**
Create a test case where a BUY order is vetoed because it exceeds `settled_cash`.

```python
def test_gfv_prevention():
    state = AccountState(balance=400.0, settled_cash=100.0, unsettled_cash=300.0)
    oracle = Oracle(state)
    # Trying to buy $150 worth of stock with only $100 settled
    assert oracle.validate_trade(1, 150.0, "BUY") is False
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_oracle.py -v`

- [ ] **Step 3: Update `validate_trade`**
Add the GFV check.

```python
def validate_trade(self, quantity: int, price: float, side: str, ...):
    # ... existing checks ...
    if side == "BUY":
        order_value = quantity * price * getattr(settings, 'TICK_VALUE', 1.0)
        if order_value > self.state.settled_cash:
            logger.error("VETO: GFV Risk - Using unsettled funds", 
                         required=order_value, settled=self.state.settled_cash)
            return False
    return True
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_oracle.py -v`

- [ ] **Step 5: Commit**
```bash
git add src/core/oracle.py
git commit -m "feat(oracle): implement GFV prevention logic in validate_trade"
```

### Task 5.3: Update `update_session` and `process_eod_anchor` for T+1 Logic

**Files:**
- Modify: `src/core/oracle.py`
- Modify: `src/core/backtest_engine.py` (to pass cost)

- [ ] **Step 1: Write the failing test**
Test that a trade exit correctly updates `unsettled_cash` and `settled_cash`.

```python
def test_t1_settlement_flow():
    state = AccountState(balance=400.0, settled_cash=400.0)
    oracle = Oracle(state)
    
    # 1. Simulate BUY entry (Manual deduction for test or through update_session)
    # Actually, we need to update update_session to handle both entry and exit?
    # Or just handle it at exit by knowing the cost.
    
    # Let's say we update update_session to take 'cost'
    # net_pnl = 10, cost = 340 (Buy $340, Sell $350)
    oracle.update_session(10.0, quantity=2, cost=340.0)
    
    assert state.unsettled_cash == 350.0 # Proceeds
    assert state.settled_cash == 60.0    # 400 - 340
    assert state.balance == 410.0       # 400 + 10
    
    # 2. Simulate EOD settlement
    oracle.process_eod_anchor()
    assert state.settled_cash == 410.0
    assert state.unsettled_cash == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Modify `Oracle` and `BacktestEngine`**
Update `update_session` signature and logic. Update `process_eod_anchor`. Update `BacktestEngine` to pass cost.

```python
# oracle.py
def update_session(self, gross_pnl: float, quantity: int = 0, cost: float = 0.0):
    commissions = quantity * settings.COMMISSION_PER_LOT
    net_pnl = gross_pnl - commissions
    
    self.state.current_daily_pnl += net_pnl
    self.state.balance += net_pnl
    self.state.equity = self.state.balance
    self.state.current_daily_trades += 1
    
    if cost > 0:
        self.state.settled_cash -= cost
        self.state.unsettled_cash += (cost + gross_pnl - commissions)
        
    self.state.save()

def process_eod_anchor(self):
    # ... existing logic ...
    self.state.settled_cash += self.state.unsettled_cash
    self.state.unsettled_cash = 0.0
    self.state.save()
```

- [ ] **Step 4: Run tests and verify all pass**
Run: `pytest tests/test_oracle.py -v`

- [ ] **Step 5: Commit**
```bash
git add src/core/oracle.py src/core/backtest_engine.py
git commit -m "feat(oracle): implement T+1 cash flow logic"
```
