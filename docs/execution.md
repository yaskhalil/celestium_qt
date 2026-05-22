# Execution System

Handles broker API communication and order routing.

## Components

### `alpaca_client.py`
- Main API client -> Alpaca Paper/Live Cash Accounts.
- Async/Await I/O.
- Enforce T+1 settlement logic context.

### `webull_client.py`
- Alternative broker client -> Webull SDK.
- Handles Webull specific auth/routing.

### `router.py`
- Order router. Direct trades to correct broker client.
