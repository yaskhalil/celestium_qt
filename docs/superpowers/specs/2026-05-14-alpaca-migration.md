# Alpaca Migration Plan

## Background & Motivation
The current system relies on Databento for historical/live data ($199/month minimum) and Webull for execution. For a $358 account trading fractional shares of SPLG, the data costs are unsustainable, and Webull's API connection (using reverse-engineered SDK tokens) is prone to breaking.

Switching to Alpaca provides a free, unified, and officially supported API for both data (IEX feed) and execution (fractional shares, cash accounts), bringing monthly costs to $0 while vastly improving stability.

## Scope & Impact
*   **Data Source**: Migrate from Databento to Alpaca Free Tier (IEX data).
*   **Execution Route**: Migrate from Webull to Alpaca.
*   **Market Context**: Since Alpaca does not support futures (NQ/MNQ), we will use QQQ as the proxy for the Nasdaq 100 context.
*   **Preserved**: The core trading logic (`BooleanNetwork`, `Oracle`, `Allocator`, `Advisor`) remains unchanged. The Oracle's T+1 settlement and risk limits are fully preserved.

## Implementation Steps

### Phase 1: Configuration
1.  **Update `src/config.py`**:
    *   Add `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, and `ALPACA_BASE_URL` (default to paper URL).
    *   Retain existing Webull/Databento config momentarily for backward compatibility if needed, or remove them to cleanly cut over.

### Phase 2: The Unified Client
1.  **Create `src/execution/alpaca_client.py`**:
    *   Implement an asynchronous client wrapper around `alpaca-py` (or `httpx` directly to Alpaca's REST API, matching the async structure of `WebullClient`).
    *   Methods needed: `get_bars()` (fetching historical OHLCV), `get_last_price()`, `get_position()`, and `place_order()`.

### Phase 3: Data Ingestion Refactor
1.  **Update `src/data/ingestion.py`**:
    *   Remove `DatabentoIngestor`.
    *   Create `AlpacaIngestor` that uses the new `AlpacaClient` to fetch recent 1-minute bars for the target symbol (SPLG) and the context proxy (QQQ).
    *   Ensure the schema matches the DuckDB storage requirements (`timestamp`, `open`, `high`, `low`, `close`, `volume`).

### Phase 4: Execution Router Refactor
1.  **Update `src/execution/router.py`**:
    *   Replace `WebullRouter` with `AlpacaRouter`.
    *   Adapt `_verify_position()` to read from Alpaca's positions endpoint.
    *   Adapt `execute_trade()` to submit fractional/notional market or limit orders to Alpaca.

### Phase 5: Engine Wiring
1.  **Update `src/core/engine.py`**:
    *   Initialize `AlpacaClient` instead of `WebullClient`.
    *   Wire `AlpacaIngestor` and `AlpacaRouter` into the `ScheduledEngine`.
    *   Update the fallback logic in `tick_monitor` and `tick_signal` to use the unified Alpaca data instead of the messy Databento/Webull fallback dance.

## Verification
1.  Run `pytest` to ensure core logical units (`Allocator`, `Oracle`) still pass.
2.  Run the system in `SHADOW_MODE=True` with paper trading credentials to verify:
    *   OHLCV data for SPLG and QQQ correctly flows into DuckDB.
    *   The `BooleanNetwork` successfully calculates states.
    *   The `AlpacaRouter` successfully submits mock orders.

## Migration & Rollback
*   **Rollback**: The original Webull and Databento logic can be restored via git if the Alpaca implementation fails testing.
*   **Migration**: Create an Alpaca Paper Trading account and generate API keys to populate `.env` before going live.
