# Fractional Sizing & Backtest Calibration Plan

**Goal:** Calibrate the system to accurately test and trade fractional stock/ETF positions for small equity accounts ($400), fixing integer constraints and incorrect PnL logic.

**Scope & Impact:**
- Fix `Allocator` to support fractional sizes instead of rounding to integers.
- Update `BacktestEngine` to dynamically size trades using the `Allocator` instead of a hardcoded fixed size.
- Adjust configuration for stock/ETF mechanics (`tick_value=1.0`, `commission=0.0`).
- Retain T+1 Cash Account settlement rules in the `Oracle`.

**Proposed Implementation:**

### Task 1: Enable Fractional Sizing in Allocator
**File:** `src/core/allocator.py`
- Remove `math.floor()` from `final_size` calculation.
- Update the minimum size check: instead of `if final_size == 0`, use `if final_size < 0.01 and probability > 0.7: final_size = 0.01`.
- Ensure output is a float rounded to 5 decimal places (e.g. `round(final_size, 5)`).

### Task 2: Dynamically Size Trades in BacktestEngine
**File:** `src/core/backtest_engine.py`
- Remove the `self.FIXED_LOT_SIZE` constant and its hardcoded usage.
- In `_simulate_day()`, retrieve dynamic size: `size = self.allocator.calculate_size(signal_prob, atr, self.state.balance)`.
- Use this `size` for `self.oracle.validate_trade()` and `self._enter_trade()`.

### Task 3: Fix Equity-Based Config Calibration
**File:** `deployment_config.json`
- Set `"tick_value": 1.0` (A $1.00 move is a $1.00 PnL per share).
- Add `"commission_per_lot": 0.0` to eliminate the $0.60 per share drag that destroys small account PnL.

### Verification
- Run `python scripts/backtest.py`.
- Ensure the backtest completes with realistic PnL calculations and fractional sizes in the `trades.json` output.
- Ensure T+1 GFV checks are successfully preventing over-trading when settled cash runs out.
