# Project: CelestiumQT (2026)
**Core Goal:** High-precision systematic trading for Apex Trader Funding 25k EOD accounts.
**Tech Stack:** Python 3.12+, Polars (Rust-backed), Pydantic v2, async-rithmic.

## 1. Architectural Hierarchy
- **Layer 1:** Statistical Context (Hurst Exponent, ADX, ATR).
- **Layer 2:** Signal Generation (XGBoost Classifier).
- **Layer 3:** Oracle Gate (Deterministic Risk Firewall).
- **Layer 4:** Advisor (Local LLM for post-close summaries).

## 2. Apex 4.0 EOD Rules (Updated March 2026)
- **Drawdown Type:** EOD (Recalculates at 4:59 PM ET).
- **Safety Net Floor:** $26,100 (Balance + $1,000 Drawdown + $100 buffer).
- **50% Consistency Rule:** No single trading day > 50% of total profit since last payout.
- **Daily Loss Limit (DLL):** $500 (Enforced intraday).
- **Overnight Rule:** Must be flat by 4:59 PM ET. No metals (GC, SI, HG suspended).
- **Payout:** 5 qualifying days (min profit reached) required.

## 3. Coding Standards
- Use **Polars** instead of Pandas for all data processing.
- Prioritize **Async/Await** for all I/O and Rithmic communication.
- Every trade proposal must pass through `src/core/oracle.py`.
- Implement **Property-Based Testing** with `hypothesis` for risk limits.
