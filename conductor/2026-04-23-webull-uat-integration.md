# Webull UAT Integration Plan

**Goal:** Integrate the official Webull Python SDK using the correct `webull.core` namespace and configure it for the US UAT environment.

**Context:** The previous `webull-python-sdk-*` packages were broken and the manual HTTP client struggled with undocumented TPA routing changes. The user provided the definitive pattern: using `webull.core.client.ApiClient`, `webull.trade.trade_client.TradeClient`, and explicitly setting the endpoint to the UAT server (`us-openapi-alb.uat.webullbroker.com`).

---

### Task 1: SDK Installation & Dependency Update
- Add the correct Webull SDK package to `pyproject.toml` (likely `webull-openapi` or `webull`).
- Run `uv sync` to install it.
- Remove the temporary `src/execution/webull_client.py` file, as we will use the SDK directly.

### Task 2: System Check Update
- Update `scripts/check_system.py` to use the exact snippet provided by the user:
  ```python
  from webull.core.client import ApiClient
  from webull.trade.trade_client import TradeClient
  
  api_client = ApiClient(app_key, app_secret, "us")
  api_client.add_endpoint("us", "us-openapi-alb.uat.webullbroker.com")
  trade_client = TradeClient(api_client)
  res = trade_client.account_v2.get_account_list()
  ```
- Verify connectivity.

### Task 3: Router & Ingestor Update
- **Router:** Update `WebullRouter.__init__` in `src/execution/router.py` to accept `TradeClient`.
- Implement `_verify_position` using `trade_client.account_v2.get_account_position(account_id)`.
- Implement `execute_trade` using `trade_client.order_v2.place_order(...)` (or the equivalent v2 placement method).
- **Ingestor:** Update `WebullIngestor` in `src/data/ingestion.py` to use `MarketDataClient` (or equivalent `webull.market.market_client`) to fetch `get_bars`.
