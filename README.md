<<<<<<< HEAD
# celestial_qt
=======
# CelestiumQT: Hierarchical Systematic Trading Stack

## Overview
CelestiumQT is a modular quantitative trading system designed for **Apex Trader Funding** (Prop Firm) accounts. The system utilizes a hierarchical decision stack to filter market noise and enforce institutional-grade risk management.

**Core Strategy:** Mid-frequency Trend/Mean-Reversion (15m Timeframe).
**Target Account:** Apex $25k EOD Drawdown.

---

## Tech Stack
- **Language:** Python 3.12+ (Asyncio)
- **Environment:** `uv` for ultra-fast dependency management.
- **Data Engine:** `Polars` (Rust-backed vectorized processing).
- **Inference:** `XGBoost` (Layer 2) + `PyTorch` (Layer 1 Regime Context).
- **Validation:** `Pydantic v2` (Oracle Gate schemas).
- **Logging:** `structlog` (Structured JSON logging).

---

## The Hierarchical Logic
The system processes data through four distinct layers:

1. **Layer 1 (Statistical Context):** Calculates the **Hurst Exponent ($H$)** and **ADX** to classify the regime (Trending vs. Mean Reverting).
   $$H = \frac{\log(R/S)}{\log(n)}$$
2. **Layer 2 (Signal Generation):** An XGBoost classifier outputs trade probability based on regime-aware features.
3. **Layer 3 (The Oracle Gate):** A deterministic risk firewall that vetoes any trade violating Apex rules (Safety Net, Consistency, Daily Loss).
4. **Layer 4 (Execution):** Async order routing via Rithmic Protocol.

---

## Operational Guide
For development, follow the standards defined in `.cursorrules`:
- **Development:** Surgical edits, validation-driven development, and type-safe async code.
- **Rules:** Adhere to the 4-layer architecture and use Polars/Pydantic/structlog.
- **Testing:** Always run `pytest` before proposing a fix.

---

## Technical Roadmap (Phase 1 MVP)

### Step 1: Initialize Environment
```bash
uv init
uv add polars pydantic pydantic-settings xgboost scipy websockets structlog pytest torch
```

### Step 2: Build the Oracle Firewall (src/core/oracle.py)
- Implement `ApexRules` schema using Pydantic.
- Define a $26,100 balance floor hard-veto.
- Implement the 50% Consistency Rule validator.

### Step 3: Data Ingestion & Polars Pipeline (src/data/)
- Establish async stream for NQ/MNQ 1-minute bars.
- Build the Polars resampler to generate 15-minute windows.
- Implement the Hurst Exponent calculation in `features/regime.py`.

### Step 4: Model Training (scripts/train.py)
- Conduct Walk-Forward Optimization on historical OHLCV.
- Feature set: [Hurst, ADX, ATR, Normalized Momentum].
- Target: 1.5:1 Reward-to-Risk ratio success.

### Step 5: Integration & Validation
- Run `pytest` on the Oracle Gate to ensure zero-leakage of risk limits.
- Deploy to Paper Trading on a simulated Rithmic feed.
>>>>>>> 6724fe6 (Initial commit: CelestiumQT project structure, core logic, and .cursorrules)
