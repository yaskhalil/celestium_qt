# Design Spec: DataBento Ingestion Pivot (Approach 1)

**Date:** 2026-04-28
**Topic:** Replacing failing Webull market data with institutional-grade DataBento polling.
**Status:** Approved

## 1. Objective
Decouple the "Eyes" (Market Data) from the "Arms" (Execution) of CelestiumQT. This addresses the `417 INVALID_SYMBOL` error from Webull and provides more reliable data for both ETFs (`SPLG`) and Futures (`MNQ`).

## 2. Architecture
The system will pivot to a **Polling-Based Ingestion** model using DataBento's Historical API.

- **Data Provider:** DataBento (Historical API).
- **Execution Provider:** Webull (Native `httpx` Client).
- **Storage:** DuckDB (Persistent OHLCV).

### 2.1 Components

#### `DatabentoIngestor` (`src/data/ingestion.py`)
A new class to replace `WebullIngestor`.
- **Method:** `fetch_and_persist(symbol, lookback_minutes=60)`
- **Logic:**
    1. Call `databento.Historical.timeseries.get_range`.
    2. Convert the resulting DataFrame to Polars.
    3. Map Databento columns (`ts_event`, `open`, `high`, `low`, `close`, `volume`) to Celestium schema.
    4. Upsert into DuckDB via `DuckDBStorage`.
- **Symbology Support:** Detect if symbol contains `.FUT` (use `stype_in='parent'`) or is a stock (use `stype_in='raw_symbol'`).

#### `ScheduledEngine` (`src/core/engine.py`)
- Remove dependency on Webull SDK for data.
- Initialize `DatabentoIngestor` using `settings.DATABENTO_API_KEY`.
- Update `tick_monitor` to call `self.ingestor.fetch_and_persist(symbol)`.

#### `WebullRouter` (`src/execution/router.py`)
- Continue using Webull for order placement and position verification.
- Migration task: Ensure it uses the `WebullClient` (`httpx`) instead of the legacy SDK.

## 3. Data Flow
1. **Engine** triggers `tick_monitor` (1m).
2. **Ingestor** polls DataBento for the latest bars.
3. **DuckDB** stores the new bars.
4. **Engine** reads the last 150 bars from DuckDB for signal/exit logic.
5. **Router** (Webull) is called only for trade execution or position checks.

## 4. Error Handling
- **API Timeout:** If DataBento polling fails, the engine logs the error and skips the tick (preventing stale signal generation).
- **Empty Response:** Log warning and wait for next minute (standard for low-volume periods).
- **Rate Limits:** Implement basic exponential backoff if `429` is received.

## 5. Testing Strategy
- **Unit Test:** `tests/test_ingestion.py` using `respx` to mock DataBento API responses.
- **Integration Test:** `scripts/test_databento_live.py` (one-off script) to verify real-world connectivity and DuckDB persistence.
- **Dry Run:** Run `ScheduledEngine` in `SHADOW_MODE=True` to verify the loop completes without `417` errors.
