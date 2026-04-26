# Webull SDK Replacement Design

## 1. Objective
Replace the buggy and incompatible `webull-python-sdk-*` packages with a native, async-first `WebullClient` to ensure stability on modern Python environments and eliminate blocking I/O.

## 2. Requirements
- **Authentication**: Implement HMAC-SHA1 request signing according to Webull TPA specifications.
- **Async I/O**: Use `httpx.AsyncClient` for all network operations.
- **Core Functionality**:
    - Fetch account balance.
    - Fetch current positions.
    - Place equity limit orders.
    - Fetch historical OHLCV bars (for ingestion).
- **Compliance**: Handle T+1 settlement logic and Webull-specific header requirements.

## 3. Architecture

### `src/execution/webull_client.py`
A stateless client class that encapsulates signing logic and request execution.

**Signing Logic**:
1.  **Headers**: Construct required headers:
    - `x-app-key`: From config.
    - `x-timestamp`: ISO8601 UTC.
    - `x-signature-nonce`: Unique UUID or random string.
    - `x-signature-algorithm`: `HMAC-SHA1`.
    - `x-signature-version`: `1.0`.
2.  **Parameters**: Sort all headers (lower-cased keys) and query parameters alphabetically.
3.  **Body**: If a body exists, calculate `MD5(JSON(body)).upper()`.
4.  **String to Sign**: `uri + "&" + sorted_params_string + "&" + body_md5`.
5.  **Signature**: `Base64(HMAC-SHA1(app_secret + "&", quoted_string_to_sign))`.

### Integration Points
- **`WebullRouter`**: Updated to use `WebullClient` for orders and position checks.
- **`WebullIngestor`**: Updated to use `WebullClient` for fetching bars.

## 4. Proposed Hosting Solution
Once the Webull API is verified, I propose hosting CelestiumQT on **Google Cloud Run**.

**Why Cloud Run?**
1.  **Fully Managed**: No server maintenance.
2.  **Docker Support**: We can use a pinned Python 3.12 image with DuckDB and all dependencies pre-installed.
3.  **Scaling**: It handles the scheduler perfectly; the `AsyncIOScheduler` will keep the process alive as long as the container is running.
4.  **Cost**: "Pay-as-you-go" - likely free or <$5/month for our low-frequency (hourly) trading needs.
5.  **Security**: Native support for Secret Manager to store Webull API keys.

## 5. Verification Plan
- **Unit Tests**: Mock `httpx` responses to verify signing logic produces expected headers.
- **Integration Test**: Use `scripts/check_system.py` to perform a real (authenticated) call to Webull.
- **Dry Run**: Execute a `tick` in shadow mode to ensure end-to-end flow works.
