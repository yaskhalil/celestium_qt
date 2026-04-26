# Webull SDK Replacement Implementation Plan

**Goal:** Replace the broken Webull SDK with a native `httpx` async client.

**Architecture:** 
1. **Signing Logic**: Implement the Webull TPA HMAC-SHA1 signature algorithm.
2. **Async Client**: Use `httpx.AsyncClient` for all Webull interactions.
3. **Integration**: Inject the new client into `WebullRouter` and `WebullIngestor`.

---

### Task 1: Core Signing & Client Skeleton
- Create `src/execution/webull_client.py` and implement `_generate_signature` using `hmac`, `hashlib`, and `urllib.parse.quote`.
- Create `tests/test_webull_client.py` to verify the logic.

### Task 2: Implement Core Endpoints
- Add an async `request` method to `WebullClient` that handles header generation, signing, and `httpx` execution. Base URL: `https://api.webull.com`.
- Add `get_account_balance`, `get_positions`, `place_order`, and `get_bars` methods.

### Task 3: Router & Ingestor Integration
- Modify `src/execution/router.py`: Replace `webullsdktrade.api.API` with `WebullClient`.
- Modify `src/data/ingestion.py`: Replace `API` with `WebullClient`.
- Modify `src/core/engine.py` and `scripts/check_system.py` to initialize and use the new client.

### Task 4: Dependency Cleanup
- Modify `pyproject.toml`: Remove `webull-python-sdk-*`, `six`, `urllib3<2.0`, and `setuptools<70`. Keep `httpx`.
- Sync environment and run tests.
