# Dependency & Config Pivot: KDB+ to DuckDB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pivot the project's data storage and configuration from KDB+ (using `pykx`) to DuckDB.

**Architecture:** Replace the distributed KDB+ configuration with a local DuckDB file path in `pydantic-settings` and project dependencies.

**Tech Stack:** Python 3.12, DuckDB, Pydantic v2, uv.

---

### Task 1: Update Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Remove pykx and add duckdb in pyproject.toml**

Remove `"pykx"` from dependencies and add `"duckdb"`.

- [ ] **Step 2: Sync environment**

Run: `uv sync`
Expected: Environment updated successfully.

- [ ] **Step 3: Commit dependency changes**

```bash
git add pyproject.toml
git commit -m "build: replace pykx with duckdb dependency"
```

---

### Task 2: Update Settings Schema (TDD)

**Files:**
- Modify: `tests/test_config.py`
- Modify: `src/config.py`

- [ ] **Step 1: Write failing test in tests/test_config.py**

Replace KDB assertions with DuckDB path assertion.

```python
from src.config import Settings

def test_settings_load_duckdb():
    settings = Settings()
    assert hasattr(settings, "DUCKDB_PATH")
    assert settings.DUCKDB_PATH == "data/celestium.db"
    assert not hasattr(settings, "KDB_HOST")
    assert not hasattr(settings, "KDB_PORT")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py`
Expected: FAIL (DUCKDB_PATH missing, KDB_HOST/PORT still present)

- [ ] **Step 3: Update Settings in src/config.py**

Replace KDB_HOST and KDB_PORT with DUCKDB_PATH.

```python
    # DuckDB Connectivity
    DUCKDB_PATH: str = Field(default="data/celestium.db", alias="DUCKDB_PATH")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py`
Expected: PASS

- [ ] **Step 5: Commit config changes**

```bash
git add src/config.py tests/test_config.py
git commit -m "refactor: pivot settings schema from kdb to duckdb"
```

---

### Task 3: Update Environment File

**Files:**
- Modify: `.env`

- [ ] **Step 1: Remove KDB keys and add DUCKDB_PATH to .env**

Remove `KDB_HOST` and `KDB_PORT`.
Add `DUCKDB_PATH=data/celestium.db`.

- [ ] **Step 2: Verify settings load from .env**

Create a temporary test or check with a one-liner to ensure `.env` values are picked up.

- [ ] **Step 3: Commit final changes**

```bash
git add .env
git commit -m "config: update .env with duckdb path"
```
