# DataBento Ingestion Pivot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the failing Webull market data ingestion with a reliable DataBento polling mechanism.

**Architecture:** Pivot to a "Hybrid Poller" where DataBento (Historical API) provides the market data ("Eyes") and a native `httpx`-based Webull client handles trade execution ("Arms").

**Tech Stack:** Python 3.12, Databento SDK, httpx, Polars, DuckDB.

---

### Task 1: Databento Ingestor Implementation

**Files:**
- Modify: `src/data/ingestion.py`
- Create: `tests/test_ingestion.py`

- [ ] **Step 1: Write the failing test for DatabentoIngestor**

```python
import pytest
import polars as pl
from unittest.mock import MagicMock, patch
from src.data.ingestion import DatabentoIngestor

@pytest.mark.asyncio
async def test_databento_ingestor_fetch_success():
    # Mock Databento Client
    mock_db_client = MagicMock()
    mock_data = MagicMock()
    # Mocking to_df to return a pandas DF that Polars can consume
    import pandas as pd
    mock_df = pd.DataFrame({
        "ts_event": [pd.Timestamp("2026-04-28 10:00:00")],
        "open": [100.0],
        "high": [101.0],
        "low": [99.0],
        "close": [100.5],
        "volume": [1000]
    }).set_index("ts_event")
    mock_data.to_df.return_value = mock_df
    mock_db_client.timeseries.get_range.return_value = mock_data

    with patch("databento.Historical", return_value=mock_db_client):
        ingestor = DatabentoIngestor(api_key="fake_key")
        ingestor.storage = MagicMock() # Mock DuckDB storage
        await ingestor.fetch_and_persist("SPLG")
        
        # Verify get_range call
        mock_db_client.timeseries.get_range.assert_called_once()
        # Verify storage insertion
        ingestor.storage.insert_ohlcv.assert_called_once()
        inserted_df = ingestor.storage.insert_ohlcv.call_args[0][0]
        assert len(inserted_df) == 1
        assert inserted_df["symbol"][0] == "SPLG"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingestion.py -v`
Expected: FAIL (ImportError or AttributeError for DatabentoIngestor)

- [ ] **Step 3: Implement DatabentoIngestor**

```python
import databento as db
import polars as pl
import structlog
from datetime import datetime, timedelta
from src.data.duck_storage import DuckDBStorage

logger = structlog.get_logger()

class DatabentoIngestor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.storage = DuckDBStorage()

    async def fetch_and_persist(self, symbol: str, lookback_minutes: int = 60):
        logger.info("Ingestor: Fetching data from Databento", symbol=symbol)
        try:
            client = db.Historical(self.api_key)
            end = datetime.now()
            start = end - timedelta(minutes=lookback_minutes)
            
            # Continuous Futures use 'parent', Stocks use 'raw_symbol'
            stype = "parent" if ".FUT" in symbol else "raw_symbol"
            
            # API call is blocking in SDK, run in thread
            import asyncio
            data = await asyncio.to_thread(
                client.timeseries.get_range,
                dataset="GLBX.MDP3" if ".FUT" in symbol else "XNAS.ITCH",
                symbols=symbol,
                schema="ohlcv-1m",
                stype_in=stype,
                start=start.strftime("%Y-%m-%dT%H:%M:%S"),
                end=end.strftime("%Y-%m-%dT%H:%M:%S")
            )

            df_raw = data.to_df()
            if df_raw.empty:
                logger.warning("Ingestor: No data returned from Databento", symbol=symbol)
                return

            # Reset index to get ts_event as a column
            df = pl.from_pandas(df_raw.reset_index())
            
            # Map Databento schema to Celestium schema
            df = df.select([
                pl.col("ts_event").alias("timestamp"),
                pl.lit(symbol).alias("symbol"),
                pl.col("open").cast(pl.Float64),
                pl.col("high").cast(pl.Float64),
                pl.col("low").cast(pl.Float64),
                pl.col("close").cast(pl.Float64),
                pl.col("volume").cast(pl.Int64)
            ])

            self.storage.insert_ohlcv(df)
            logger.info("Ingestor: Data persisted to DuckDB", symbol=symbol, count=len(df))

        except Exception as e:
            logger.error("Ingestor: Databento Fetch Error", symbol=symbol, error=str(e))
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingestion.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/data/ingestion.py tests/test_ingestion.py
git commit -m "feat: replace WebullIngestor with DatabentoIngestor"
```

---

### Task 2: Webull Router Refactor

**Files:**
- Modify: `src/execution/router.py`

- [ ] **Step 1: Update WebullRouter to use native WebullClient**

```python
import asyncio
import uuid
import structlog
from datetime import datetime, timezone
from typing import Optional
from src.config import settings
from src.core.oracle import AccountState
from src.execution.webull_client import WebullClient # Use our native client

logger = structlog.get_logger()

class WebullRouter:
    def __init__(self, client: WebullClient, state: AccountState):
        self.client = client
        self.state = state
        self.current_position = 0
        self.min_hold_seconds = 30

    async def _verify_position(self, symbol: str):
        try:
            # Native client uses async request
            res = await self.client.request("GET", "/openapi/account/positions", params={"account_id": settings.WEBULL_ACCOUNT_ID})
            
            # Webull OpenAPI v1/v2 response structure varies, adjust based on actual discovery
            positions = res.get("data", []) if isinstance(res, dict) else []
            symbol_position = next((p for p in positions if p.get("symbol") == symbol), None)
            
            if symbol_position:
                self.current_position = float(symbol_position.get("position", 0))
            else:
                self.current_position = 0
            logger.info("Router: Position Verified", symbol=symbol, position=self.current_position)
        except Exception as e:
            logger.error("Router: Position Verification Error", error=str(e))

    async def execute_trade(self, symbol: str, quantity: float, side: str, price: float):
        await self._verify_position(symbol)
        
        if settings.SHADOW_MODE:
            logger.info("Router: SHADOW MODE - Order would be placed", symbol=symbol, side=side, qty=quantity, price=price)
            return "shadow_order_id"

        try:
            order_params = {
                "account_id": settings.WEBULL_ACCOUNT_ID,
                "client_order_id": uuid.uuid4().hex,
                "symbol": symbol,
                "side": side,
                "order_type": "LIMIT",
                "limit_price": str(round(price, 2)),
                "quantity": str(round(quantity, 2)),
                "time_in_force": "DAY"
            }
            res = await self.client.request("POST", "/openapi/order/place", body=order_params)
            order_id = res.get("order_id")
            logger.info("Router: Order Placed", order_id=order_id)
            return order_id
        except Exception as e:
            logger.error("Router: Execution Error", error=str(e))
            return None
```

- [ ] **Step 2: Commit**

```bash
git add src/execution/router.py
git commit -m "refactor: update WebullRouter to use native httpx client"
```

---

### Task 3: Engine Integration

**Files:**
- Modify: `src/core/engine.py`
- Modify: `src/main.py`

- [ ] **Step 1: Update ScheduledEngine to use DatabentoIngestor**

```python
# src/core/engine.py modifications
from src.data.ingestion import DatabentoIngestor
from src.execution.webull_client import WebullClient

class ScheduledEngine:
    def __init__(self, webull_client: WebullClient, account_state: Optional[AccountState] = None):
        self.account_state = account_state or AccountState.load()
        # ...
        self.router = WebullRouter(webull_client, self.account_state)
        self.ingestor = DatabentoIngestor(api_key=settings.DATABENTO_API_KEY)
        # ...
```

- [ ] **Step 2: Update main.py to initialize native WebullClient**

```python
# src/main.py modifications
from src.execution.webull_client import WebullClient

async def main():
    # Initialize native WebullClient
    webull_client = WebullClient(
        app_key=settings.WEBULL_APP_KEY,
        app_secret=settings.WEBULL_APP_SECRET,
        access_token=settings.WEBULL_ACCESS_TOKEN
    )
    
    state = AccountState.load()
    engine = ScheduledEngine(webull_client, state)
    # ...
```

- [ ] **Step 3: Commit**

```bash
git add src/core/engine.py src/main.py
git commit -m "feat: integrate DatabentoIngestor and native WebullClient into Engine"
```

---

### Task 4: Cleanup & Verification

- [ ] **Step 1: Remove legacy SDK from pyproject.toml**

Run: `uv remove webull-openapi-python-sdk`
Then: `uv sync`

- [ ] **Step 2: Final Dry Run**

Run the engine in shadow mode to ensure no 417 errors:
`uv run python3 src/main.py`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: remove legacy Webull SDK"
```
