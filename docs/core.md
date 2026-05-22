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

### `boolean_network.py`
- Logic constraints. Combine signals.

### `payout_logic.py`
- Manage reserve threshold, payout liquid capital.

### `advisor.py` (Advisor Layer 4)
- Local LLM post-close summaries.

### `notifier.py`
- Telegram alerts -> Risk vetoes, session close.
