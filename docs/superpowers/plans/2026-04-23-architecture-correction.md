# Architecture & Webull Migration Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pivot from KDB+ to DuckDB, fix async deadlocks in the engine, update configuration for a $400 account, and harden position tracking.

**Architecture:** 
1. **Data Layer**: Replace KDB+/PyKX with DuckDB for OHLCV persistence.
2. **Engine**: Switch `BackgroundScheduler` to `AsyncIOScheduler` for safe async execution.
3. **Execution**: Implement live position verification in the `WebullRouter`.
4. **Config**: Re-calibrate risk limits for a $400 equity account.

**Tech Stack:** DuckDB, Polars, APScheduler (AsyncIO), webull-python-sdk.

---

### Task 1: Dependency & Config Pivot
**Files:**
- Modify: `pyproject.toml`
- Modify: `src/config.py`
- Modify: `.env`

- [ ] **Step 1: Update Dependencies**
Remove `pykx` and add `duckdb`.

Modify `pyproject.toml` (dependencies):
```toml
dependencies = [
    "duckdb",
    "polars",
    # ... other existing deps
]
```

- [ ] **Step 2: Sync environment**
Run: `uv sync`

- [ ] **Step 3: Update Settings Schema**
Replace KDB settings with DuckDB path in `src/config.py`.

```python
class Settings(BaseSettings):
    # ...
    DUCKDB_PATH: str = Field(default="data/celestium.db", alias="DUCKDB_PATH")
```

- [ ] **Step 4: Update .env**
Update `.env` to remove `KDB_HOST/PORT` and add `DUCKDB_PATH=data/celestium.db`.

- [ ] **Step 5: Commit**
```bash
git add pyproject.toml src/config.py .env
git commit -m "refactor: pivot from kdb+ to duckdb configuration"
```

### Task 2: Implement DuckDB Storage Layer
**Files:**
- Create: `src/data/duck_storage.py`
- Modify: `src/data/pipeline.py`
- Modify: `src/data/ingestion.py`

- [ ] **Step 1: Create DuckDB Storage Helper**
Implement a simple class `DuckDBStorage` in `src/data/duck_storage.py` to handle Polars -> DuckDB persistence using `duckdb.connect(path).register('df', df).execute("INSERT INTO ...")`.

- [ ] **Step 2: Update Ingestor**
Modify `src/data/ingestion.py` to use `DuckDBStorage` instead of `kx_conn`. Ensure the table `ohlcv` is created if it doesn't exist.

- [ ] **Step 3: Update Pipeline Buffer**
Replace `KDBBuffer` with `DuckDBBuffer` in `src/data/pipeline.py`. Use DuckDB to query the last N bars and return a Polars DataFrame.

- [ ] **Step 4: Verify with Test**
Create `tests/test_duck_storage.py` and ensure we can write and read back a Polars DataFrame.

- [ ] **Step 5: Commit**
```bash
git add src/data/duck_storage.py src/data/pipeline.py src/data/ingestion.py tests/test_duck_storage.py
git commit -m "feat: implement duckdb storage layer"
```

### Task 3: Fix Async Engine Deadlocks
**Files:**
- Modify: `src/core/engine.py`

- [ ] **Step 1: Switch Scheduler Type**
In `src/core/engine.py`, change `from apscheduler.schedulers.background import BackgroundScheduler` to `from apscheduler.schedulers.asyncio import AsyncIOScheduler`.

- [ ] **Step 2: Convert Tick to Async**
Change `def tick(self)` to `async def tick(self)`.

- [ ] **Step 3: Correct Await Logic**
Replace `asyncio.run(self.router.execute_trade(...))` with `await self.router.execute_trade(...)`. Ensure all async calls inside `tick` are awaited.

- [ ] **Step 4: Commit**
```bash
git add src/core/engine.py
git commit -m "fix: resolve async deadlocks by switching to AsyncIOScheduler"
```

### Task 4: Harden Router Position Tracking
**Files:**
- Modify: `src/execution/router.py`

- [ ] **Step 1: Implement Position Verification**
Add an async method `_verify_position()` to `WebullRouter` that calls `self.api.account_v2.get_account_positions` and updates `self.current_position`.

- [ ] **Step 2: Update execute_trade**
In `execute_trade`, call `await self._verify_position()` before placing an order to ensure the internal state matches the broker's reality.

- [ ] **Step 3: Commit**
```bash
git add src/execution/router.py
git commit -m "feat: harden router with live position verification"
```

### Task 5: Re-calibrate Configuration
**Files:**
- Modify: `deployment_config.json`

- [ ] **Step 1: Update limits**
Update `starting_balance` to 400.0, `balance_floor` to 300.0, `daily_loss_limit` to 20.0, and `symbol` to "SPY".

- [ ] **Step 2: Commit**
```bash
git add deployment_config.json
git commit -m "config: recalibrate for $400 webull equity account"
```
