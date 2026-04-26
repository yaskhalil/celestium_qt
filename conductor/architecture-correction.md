# Architecture & Webull Migration Correction Plan

## 1. Objective
Address critical red flags in the current codebase: Asynchronous deadlocks, incorrect deployment configuration, position tracking hallucination, and the KDB+ licensing/blocking issue by pivoting to DuckDB.

## 2. Scope & Impact
*   **Asynchrony**: `ScheduledEngine` will migrate from a synchronous `BackgroundScheduler` to `AsyncIOScheduler` or a dedicated async loop to safely call `WebullRouter`.
*   **Configuration**: Update `deployment_config.json` from $50k CME settings to $400 Webull settings (e.g., `SPY`, $400 starting balance).
*   **Database Migration**: Remove `pykx` and KDB+ entirely. Introduce `duckdb` for historical OHLCV data storage and context fetching. DuckDB integrates natively with Polars and has zero commercial licensing fees.
*   **Position Tracking**: Improve `WebullRouter` to query active positions instead of blindly incrementing a local counter upon limit order submission.

## 3. Implementation Steps

### Phase 1: Database Migration (KDB+ -> DuckDB)
1.  **Dependencies**: Remove `pykx` from `pyproject.toml` and add `duckdb`. Run `uv sync`.
2.  **Configuration**: Replace `KDB_HOST`/`KDB_PORT` with `DUCKDB_PATH` in `src/config.py` and `.env`.
3.  **Data Layer**:
    *   Update `src/data/pipeline.py`: Replace `KDBBuffer` with `DuckDBBuffer`.
    *   Update `src/data/ingestion.py`: Replace KDB+ insertions with DuckDB inserts using Polars/Arrow.
    *   Update `scripts/check_system.py`: Replace `check_kdb` with `check_duckdb`.
4.  **Tests**: Update `tests/test_pipeline.py`, `tests/test_ingestion.py`, and `tests/test_config.py` to mock/test DuckDB instead of KDB+.

### Phase 2: Engine & Async Fixes
1.  **Engine Structure**: Modify `src/core/engine.py` to use `apscheduler.schedulers.asyncio.AsyncIOScheduler`.
2.  **Tick Execution**: Ensure `engine.tick()` is an `async def` and `await self.router.execute_trade(...)` is properly awaited inside the loop, preventing `RuntimeError`.

### Phase 3: Configuration & Router Hardening
1.  **Config**: Update `deployment_config.json` to reflect a $400 Webull cash account reality (e.g., `starting_balance`: 400, `balance_floor`: 300, `daily_loss_limit`: 20).
2.  **Router**: Update `src/execution/router.py` to rely on actual Webull account position checks before execution, avoiding "ghost" positions.

## 4. Verification
*   Run `scripts/check_system.py` to confirm Webull connectivity and DuckDB initialization.
*   Run the test suite (`uv run pytest`) to ensure all data and engine mocks pass.
*   Execute a dry run of the engine to confirm the scheduler ticks asynchronously without blocking.
