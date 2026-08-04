# Core System (Layer 3 & 4)

Handles business logic, risk firewall, state machine.

## Components

### `oracle.py` (Oracle Gate)
- Deterministic Risk Firewall.
- Veto trades -> Daily Loss Limit (DLL), Profit Ceiling, Hurst threshold, GFV protection (T+1 settlement).
- Save/Load state -> `data/account_state.json`.

### `engine.py`
- Main scheduled event loop.
- Poll signals -> Execute trades.

### `allocator.py`
- Capital allocator. Define position sizes.

### `backtest_engine.py`
- Simulates historical trading. Uses `DuckDB` + `Polars`.

### `regime_filter.py`
- Trend-regime gate (close > SMA20, Hurst, ADX) computed from real features.

### `logging_setup.py`
- Central structlog configuration: JSON logs to rotating file + console, level from LOG_LEVEL.

### `payout_logic.py`
- Manage reserve threshold, payout liquid capital.

### `advisor.py` (Advisor Layer 4)
- Local LLM post-close summaries.

### `notifier.py`
- Telegram alerts -> Risk vetoes, session close.
- Interactive Telegram Controller:
  - Background polling loop in `engine.py` listens to user inputs from the configured Telegram chat.
  - `/status` - Retrieve system status, mode, balance, equity, daily PNL, positions, and vetoes count.
  - `/pause` - Manually pause Oracle trading to veto new signals.
  - `/resume` - Manually resume Oracle trading.
  - `/positions` - View active position sizes, entry price, stop loss, and take profit.
  - `/vetoes` - View list of Oracle veto logs for today.
  - `/performance` - View model details, historical backtest report, and live session performance stats.
  - `/help` - Show the interactive help menu.
