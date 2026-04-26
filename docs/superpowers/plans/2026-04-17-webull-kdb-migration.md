# CelestiumQT Webull & KDB+ Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate CelestiumQT from a Rithmic-based Futures system to a $400 Webull Equity portfolio with KDB+ persistence and Boolean state validation.

**Architecture:** Pivot from an async streaming loop to a scheduled task architecture using APScheduler. Use pykx to bridge Polars-based features with KDB+ historical storage, and enforce T+1 settlement rules in the Oracle.

**Tech Stack:** Python 3.12, Webull (webull-python-sdk-tpa), KDB+ (pykx), Polars, APScheduler.

---

### Task 1: Dependency and Configuration Update

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/config.py`

- [ ] **Step 1: Update pyproject.toml dependencies**
Replace `async-rithmic` with `webull-python-sdk-tpa`, `pykx`, and `apscheduler`.

```toml
dependencies = [
    "polars",
    "pydantic",
    "xgboost",
    "scipy",
    "structlog",
    "pytest",
    "torch",
    "pydantic-settings>=2.13.1",
    "webull-python-sdk-tpa",
    "pykx",
    "apscheduler",
    "scikit-learn>=1.8.0",
    "httpx>=0.28.1",
]
```

- [ ] **Step 2: Add Webull and KDB+ settings to src/config.py**
Add placeholders for APP_KEY, APP_SECRET, and KDB_HOST.

```python
class Settings(BaseSettings):
    WEBULL_APP_KEY: str = ""
    WEBULL_APP_SECRET: str = ""
    WEBULL_ACCOUNT_ID: str = ""
    KDB_HOST: str = "localhost"
    KDB_PORT: int = 5001
    SYMBOL: str = "AAPL"
    # ... existing settings ...
```

- [ ] **Step 3: Commit**
```bash
git add pyproject.toml src/config.py
git commit -m "build: update dependencies for webull and kdb migration"
```

### Task 2: KDB+ Persistence Layer (Ingestion)

**Files:**
- Modify: `src/data/ingestion.py`

- [ ] **Step 1: Implement WebullIngestor with KDB+ pipeline**
Remove Rithmic logic and implement the Webull fetcher that pushes to KDB+.

```python
import pykx as kx
import polars as pl
from webullsdktrade.api import API
from webullsdkcore.client import ApiClient

class WebullIngestor:
    def __init__(self, api_client: ApiClient):
        self.api = API(api_client)
        self.kx_conn = kx.SyncQConnection(host=settings.KDB_HOST, port=settings.KDB_PORT)

    def fetch_and_persist(self, symbol: str):
        # Fetch hourly bars from Webull
        # Convert to Polars -> PyArrow -> KDB+
        bars = self.api.get_bars(symbol, interval="1h") 
        df = pl.from_dicts(bars)
        self.kx_conn.insert("ohlcv", kx.toq(df.to_arrow()))
```

- [ ] **Step 2: Commit**
```bash
git add src/data/ingestion.py
git commit -m "feat: implement WebullIngestor with kdb+ persistence"
```

### Task 3: KDBBuffer Implementation

**Files:**
- Modify: `src/data/pipeline.py`

- [ ] **Step 1: Replace LiveBuffer with KDBBuffer**
Query KDB+ for context windows instead of using in-memory list.

```python
class KDBBuffer:
    def __init__(self):
        self.kx_conn = kx.SyncQConnection(host=settings.KDB_HOST, port=settings.KDB_PORT)

    def get_context(self, symbol: str, window: int = 150) -> pl.DataFrame:
        query = f"select [window] from ohlcv where sym=`{symbol}"
        q_table = self.kx_conn(query)
        return pl.from_arrow(q_table.to_arrow())
```

- [ ] **Step 2: Commit**
```bash
git add src/data/pipeline.py
git commit -m "feat: replace LiveBuffer with KDBBuffer"
```

### Task 4: Boolean Network State Analysis

**Files:**
- Create: `src/core/boolean_network.py`

- [ ] **Step 1: Implement BooleanStateSpace logic**
Define the bit-mapping and attractor check.

```python
class BooleanStateSpace:
    def map_to_bits(self, context: pl.DataFrame) -> int:
        # Example: bit 0: close > sma_20
        # Returns integer representation of bitset
        return 0 

    def is_in_attractor(self, state: int) -> bool:
        # Check if state belongs to target attractor set A
        target_attractors = {1, 3, 7}
        return state in target_attractors
```

- [ ] **Step 2: Commit**
```bash
git add src/core/boolean_network.py
git commit -m "feat: add BooleanStateSpace for attractor validation"
```

### Task 5: Oracle T+1 Settlement Logic

**Files:**
- Modify: `src/core/oracle.py`

- [ ] **Step 1: Update AccountState for T+1 tracking**
Add `settled_cash` and `unsettled_cash` fields.

- [ ] **Step 2: Update Oracle.validate_trade**
Add GFV (Good Faith Violation) prevention logic.

```python
def validate_trade(self, ...):
    if side == "BUY":
        if self.state.unsettled_cash > 0:
            # Veto if buying with unsettled funds for a likely intraday flip
            pass
    return True
```

- [ ] **Step 3: Commit**
```bash
git add src/core/oracle.py
git commit -m "feat: update Oracle for Equity T+1 settlement rules"
```

### Task 6: Scheduled Engine

**Files:**
- Modify: `src/core/engine.py`

- [ ] **Step 1: Pivot to APScheduler triggered jobs**
Replace `while True` loop with `scheduler.add_job`.

```python
from apscheduler.schedulers.background import BackgroundScheduler

class ScheduledEngine:
    def __init__(self, ...):
        self.scheduler = BackgroundScheduler()
        self.bn = BooleanStateSpace()

    def tick(self):
        # 1. Fetch context
        # 2. Check Boolean Attractor
        # 3. If valid, evaluate Layer 2 -> Oracle -> Router
        pass

    def start(self):
        self.scheduler.add_job(self.tick, 'cron', hour='9-16', minute='0', timezone='US/Eastern')
        self.scheduler.start()
```

- [ ] **Step 2: Commit**
```bash
git add src/core/engine.py
git commit -m "feat: pivot Engine to scheduled job architecture"
```

### Task 7: Webull Router

**Files:**
- Modify: `src/execution/router.py`

- [ ] **Step 1: Implement WebullRouter with Limit Order enforcement**
Replace Rithmic `place_market_order` with Webull `place_order` (LIMIT).

- [ ] **Step 2: Commit**
```bash
git add src/execution/router.py
git commit -m "feat: implement WebullRouter with mandatory limit orders"
```
