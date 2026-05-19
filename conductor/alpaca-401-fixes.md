# Alpaca 401 Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement defensive key stripping and diagnostic logging in the Alpaca Client to resolve and identify configuration-based 401 errors.

**Architecture:** Add `strip()` to key initialization in `AlpacaClient` and add a startup log showing the first 4 characters of the active API key to help users debug environment issues on deployment servers.

**Tech Stack:** Python 3.12+, `httpx`, `structlog`

---

### Task 1: Update AlpacaClient Initialization

**Files:**
- Modify: `src/execution/alpaca_client.py:12-25`

- [ ] **Step 1: Write minimal implementation**

```python
    def __init__(self, api_key: str, secret_key: str, base_url: str = "https://paper-api.alpaca.markets"):
        self.api_key = api_key.strip()
        self.secret_key = secret_key.strip()
        self.base_url = base_url
        
        # Log key prefix for diagnostic purposes
        key_prefix = self.api_key[:4] if len(self.api_key) >= 4 else "NONE"
        logger.info("AlpacaClient initialized", base_url=self.base_url, key_prefix=key_prefix)
        
        # Data API is separate from Trading API
        self.data_url = "https://data.alpaca.markets/v2"
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json"
        }
```

- [ ] **Step 2: Commit**

```bash
git add src/execution/alpaca_client.py
git commit -m "fix: strip whitespace from Alpaca keys and add diagnostic logging"
```
