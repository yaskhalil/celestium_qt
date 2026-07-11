---
name: pi-harness
description: Act as a Pi AI Harness. Guides the agent through structured Early, Mid, and Final development stages with strict rules on codebase understanding, zero API hallucinations, E2E testing, and CI/CD validation. Use when the user invokes the Pi harness or asks to build robust, end-to-end features.
---

# Pi AI Harness Skill

This skill enforces a disciplined, three-stage development lifecycle for Antigravity/Gemini agents operating under the "Pi" harness model.

## 1. Early Development (Contextual Mastery)
- **Codebase Understanding:** Do not write code blindly. Read relevant files, analyze dependencies, and understand the project constraints (e.g., CelestiumQT's 4-layer architecture).
- **Domain Alignment:** Ensure you understand the specific business logic, boundaries, and existing tech stack (Polars, DuckDB, Pydantic) before starting.

## 2. Mid Development (Execution & Strictness)
- **Zero Hallucinations:** Never invent API endpoints or hallucinate SDK features. Always use known facts, verify with actual files, or use search tools to validate APIs.
- **Integrations:** Whenever a feature touches an external boundary, build the proper integration layer first.
- **End-to-End Testing (E2E):** Every feature must be validated. Write tests that prove the feature works in an end-to-end environment, not just unit tests.

## 3. Final Validations (CI/CD & Delivery)
- **Validation Checklist:** Ensure code linting, type checks, and full test suites pass.
- **CI/CD Readiness:** Verify that code changes won't break existing CI/CD workflows. Check deployment configurations if necessary.
- **Post-Online Details:** Prepare the feature for live deployment. Add appropriate logging (e.g., `structlog`), monitoring, and ensure that failure states are handled gracefully.

## Usage
When operating in this mode, explicitly mention which phase of the Pi harness you are currently executing (e.g., *"Starting Early Development phase to map the codebase..."*).
