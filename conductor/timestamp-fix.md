# DuckDB Timestamp & Alpaca Logs Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the DuckDB `TIMESTAMP WITH TIME ZONE -> TIMESTAMP_NS` conversion error and clean up expected 404 position errors from Alpaca.

**Architecture:** 
1. `AlpacaIngestor` will convert the Polars timestamp column to `America/New_York` and strip the timezone before saving to DuckDB.
2. `AlpacaClient` will gracefully catch the 404 HTTPStatusError in `get_position()` and return `0.0` *without* logging it as a global API error.

**Tech Stack:** Python 3.12+, Polars, DuckDB, `httpx`

---

### Task 1: Fix Timestamp in Ingestor

**Files:**
- Modify: `src/data/ingestion.py:27-37`

- [ ] **Step 1: Write minimal implementation**

```python
            # AlpacaClient already returns a Polars DataFrame with the correct schema
            # We must convert the timezone to NY and strip it for DuckDB TIMESTAMP_NS
            df = df.with_columns(
                pl.col("timestamp").dt.convert_time_zone("America/New_York").dt.replace_time_zone(None)
            )

            df = df.select([
                pl.col("timestamp"),
                pl.col("symbol"),
                pl.col("open"),
                pl.col("high"),
                pl.col("low"),
                pl.col("close"),
                pl.col("volume")
            ])
```

- [ ] **Step 2: Commit**

```bash
git add src/data/ingestion.py
git commit -m "fix: convert alpaca timestamps to naive NY time for duckdb"
```

### Task 2: Suppress 404 Logging in AlpacaClient

**Files:**
- Modify: `src/execution/alpaca_client.py:32-44` (Specifically `_request` to not log 404s for positions, or modify `get_position` to handle it). Actually, it's better to modify `_request` to accept an `ignore_errors` list or handle it in `get_position`. Let's modify `_request` to optionally ignore specific status codes for logging.

- [ ] **Step 1: Write minimal implementation**

```python
    async def _request(self, method: str, url: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None, ignore_status: list = None) -> Dict[str, Any]:
        if ignore_status is None:
            ignore_status = []
            
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=body,
                headers=self.headers,
                timeout=10.0
            )
            if response.status_code != 200:
                if response.status_code not in ignore_status:
                    logger.error("Alpaca API Error", status=response.status_code, text=response.text, url=url)
                response.raise_for_status()
            return response.json()
```

- [ ] **Step 2: Update get_position to use ignore_status**

Update `src/execution/alpaca_client.py:79-87`:

```python
    async def get_position(self, symbol: str) -> float:
        """Fetches current position for a symbol."""
        url = f"{self.base_url}/v2/positions/{symbol}"
        try:
            res = await self._request("GET", url, ignore_status=[404])
            return float(res.get("qty", 0))
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return 0.0
            raise e
```

- [ ] **Step 3: Commit**

```bash
git add src/execution/alpaca_client.py
git commit -m "fix: suppress 404 error logging for empty positions"
```
