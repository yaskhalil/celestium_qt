# Execution System

Handles broker API communication and order routing.

## Components

### `alpaca_client.py`
- Sole broker API client -> Alpaca Paper/Live Cash Accounts.
- Async/Await I/O.
- Enforce T+1 settlement logic context.

### `position_manager.py`
- Single point of broker integration: order placement (BUY/SELL, with shadow-mode fallback), position tracking, SL/TP exit monitoring, GFV-compliant 30s minimum hold before sells, feeds PnL/cash flow back into Oracle/AccountState.
