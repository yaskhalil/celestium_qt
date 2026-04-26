# Webull Router Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `src/execution/router.py` from Rithmic to Webull SDK, enforcing limit orders and T+1 compliance for a $400 account.

**Architecture:**
- Replace `RithmicClient` with `webullsdktrade.api.API`.
- Use `AccountState` to track `current_entry_time` and PnL.
- Implement `execute_trade` with Webull's `place_order`.
- Strictly enforce `LIMIT` orders.

**Tech Stack:** `webull-python-sdk-tpa`, `structlog`, `asyncio`, `pytest`.

---

### Task 1: Initialize WebullRouter with API

**Files:**
- Modify: `src/execution/router.py`

- [ ] **Step 1: Update imports and remove Rithmic dependency**
- [ ] **Step 2: Update `__init__` to accept `webullsdktrade.api.API`**

### Task 2: Implement execute_trade with Webull SDK

**Files:**
- Modify: `src/execution/router.py`

- [ ] **Step 1: Implement `execute_trade` logic using `api.place_order`**
- [ ] **Step 2: Enforce `LIMIT` orders only**
- [ ] **Step 3: Handle `instrument_id` vs `symbol`**

### Task 3: Order Status Tracking and Position Management

**Files:**
- Modify: `src/execution/router.py`

- [ ] **Step 1: Implement `_on_order_update` or a polling mechanism for order status**
- [ ] **Step 2: Ensure `current_position` is updated correctly**

### Task 4: Verification and Testing

**Files:**
- Create: `tests/test_router.py`

- [ ] **Step 1: Write unit tests for `execute_trade` with mocks**
- [ ] **Step 2: Verify compliance guards**
- [ ] **Step 3: Run tests and verify success**

### Task 5: Commit Changes

- [ ] **Step 1: Commit the migrated router and new tests**
