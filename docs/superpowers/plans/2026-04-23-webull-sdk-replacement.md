# Webull SDK Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken Webull SDK with a native `httpx` async client.

**Architecture:** 
1. **Signing Logic**: Implement the Webull TPA HMAC-SHA1 signature algorithm.
2. **Async Client**: Use `httpx.AsyncClient` for all Webull interactions.
3. **Integration**: Inject the new client into `WebullRouter` and `WebullIngestor`.

**Tech Stack:** httpx, hashlib, hmac, base64.

---

### Task 1: Core Signing & Client Skeleton
**Files:**
- Create: `src/execution/webull_client.py`
- Test: `tests/test_webull_client.py`

- [ ] **Step 1: Write the failing test for signature generation**
Create `tests/test_webull_client.py`. Use a simple test case to verify the logic.

- [ ] **Step 2: Implement `WebullClient` and signing logic**
Create `src/execution/webull_client.py` with `_generate_signature` using `hmac`, `hashlib`, and `urllib.parse.quote`.

- [ ] **Step 3: Run test to verify passes**
Run: `pytest tests/test_webull_client.py -v`

- [ ] **Step 4: Commit**
```bash
git add src/execution/webull_client.py tests/test_webull_client.py
git commit -m "feat: implement native Webull signing logic"
```

### Task 2: Implement Core Endpoints
**Files:**
- Modify: `src/execution/webull_client.py`

- [ ] **Step 1: Implement `request` method**
Add an async `request(self, method, uri, params=None, body=None)` method to `WebullClient` that handles header generation, signing, and `httpx` execution. Base URL: `https://api.webull.com`.

- [ ] **Step 2: Implement Trading Methods**
Add `get_account_balance(self, account_id)`, `get_positions(self, account_id)`, and `place_order(self, account_id, order_params)`.

- [ ] **Step 3: Implement Market Data Method**
Add `get_bars(self, symbol, interval, count=150)`.

- [ ] **Step 4: Commit**
```bash
git add src/execution/webull_client.py
git commit -m "feat: implement Webull trading and market data endpoints"
```

### Task 3: Router & Ingestor Integration
**Files:**
- Modify: `src/execution/router.py`
- Modify: `src/data/ingestion.py`
- Modify: `src/core/engine.py`
- Modify: `scripts/check_system.py`

- [ ] **Step 1: Update Router**
Replace `webullsdktrade.api.API` with `WebullClient` in `WebullRouter.__init__` and calls.

- [ ] **Step 2: Update Ingestor**
Replace `API` with `WebullClient` in `WebullIngestor`.

- [ ] **Step 3: Update Engine Initialization**
In `src/core/engine.py`, initialize `WebullClient` and pass it to the engine.

- [ ] **Step 4: Update System Check**
Modify `scripts/check_system.py` to use `WebullClient`.

- [ ] **Step 5: Commit**
```bash
git add src/execution/router.py src/data/ingestion.py src/core/engine.py scripts/check_system.py
git commit -m "refactor: integrate native WebullClient into core systems"
```

### Task 4: Dependency Cleanup
**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Remove SDK packages**
Remove `webull-python-sdk-*`, `six`, `urllib3<2.0`, and `setuptools<70` from `pyproject.toml`. Keep `httpx`.

- [ ] **Step 2: Sync environment**
Run: `uv sync`

- [ ] **Step 3: Run all tests**
Run: `pytest tests/`

- [ ] **Step 4: Commit**
```bash
git add pyproject.toml
git commit -m "cleanup: remove problematic Webull SDK dependencies"
```
