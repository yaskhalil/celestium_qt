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

## 4. Pi AI Harness Guidelines (Agentic Workflows)
When operating as or attaching to the Pi AI harness, the Antigravity/Gemini agents MUST adhere to the following development lifecycle:
- **Early Development (Context & Understanding):** Prioritize codebase understanding. Map out the architecture, ingest core domain rules, and deeply analyze constraints (like the deterministic risk firewall) before proposing any solutions.
- **Mid Development (Strict Execution & Integrations):**
  - **No API Hallucinations:** Always ground API integrations in actual schemas (e.g., Alpaca, Rithmic). Validate before you write.
  - **Integrations First:** Write required integrations proactively when a dependency is needed.
  - **End-to-End Testing:** When building out features, always ensure that E2E tests are written alongside the functionality.
- **Final Validations (Deployment & CI/CD):**
  - Verify CI/CD pipeline compatibility and checks.
  - Ensure post-online validations, deployment logs, and live monitoring hooks are accounted for before finalizing tasks.
