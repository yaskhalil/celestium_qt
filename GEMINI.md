# Project: CelestiumQT (2026)
**Core Goal:** High-precision systematic trading for Alpaca Cash Accounts (Initial target: SPLG).
**Tech Stack:** Python 3.12+, Polars, DuckDB, Pydantic v2, Alpaca API (httpx).

## 1. Architectural Hierarchy
- **Layer 1:** Statistical Context (Hurst Exponent, ADX, ATR).
- **Layer 2:** Signal Generation (XGBoost Classifier).
- **Layer 3:** Oracle Gate (Deterministic Risk Firewall).
- **Layer 4:** Advisor (Local LLM for post-close summaries).

## 2. Alpaca Cash Account Rules (Updated May 2026)
- **Settlement:** T+1 (Funds from today's trades are available tomorrow).
- **Good Faith Violation (GFV):** Avoid trading with unsettled funds.
- **Starting Balance:** $358.00 (Example target for SPLG fractional calibration).
- **Daily Loss Limit (DLL):** $20.00 (Enforced intraday).
- **Overnight Rule:** Cash accounts can hold overnight, but the bot defaults to flat by 3:59 PM ET for risk management.

## 3. Coding Standards
- Use **Polars** instead of Pandas for all data processing.
- Use **DuckDB** for historical OHLCV storage and context fetching.
- Prioritize **Async/Await** for all I/O and Alpaca communication (via `AlpacaClient`).
- Every trade proposal must pass through `src/core/oracle.py`.
- Implement **Property-Based Testing** with `hypothesis` for risk limits.

