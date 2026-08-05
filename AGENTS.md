# AGENTS.md — CelestiumQT

## Commands
- Run tests: `uv run python -m pytest tests/ -q`
- Run one test: `uv run python -m pytest tests/test_oracle.py::test_gfv_protection -q`
- Backtest: `uv run python scripts/backtest.py`
- Live bot: `uv run python src/main.py`
- Use `uv` exclusively. Never pip/poetry.

## Architecture (4 layers — respect the boundaries)
1. `src/features/` — statistical context (Hurst, ADX, ATR, SMA20 via `add_regime_features`)
2. `src/models/` — XGBoost inference (`Classifier`)
3. `src/core/oracle.py` — deterministic risk firewall. **No trade bypasses `Oracle.validate_trade`.**
4. `src/execution/` — order routing (`PositionManager`, `AlpacaClient`)

Strategy wiring lives in `src/core/strategy.py` (RegimeFilter → Classifier → Allocator → Oracle).

## Conventions
- Python 3.12+, strict typing, `Final`/`Literal`/`Annotated` where apt.
- Polars for all data. Lazy eval for big frames. No pandas.
- Pydantic v2 models for schemas; limits are % of balance via `settings.DLL_PCT` etc. — NEVER reintroduce dollar-value limit settings.
- structlog for logs; call `setup_logging()` at process entry (src/core/logging_setup.py).
- asyncio everywhere; `asyncio.TaskGroup` for concurrency; graceful SIGINT/SIGTERM.
- Every feature/fix ships with a test in `tests/`.

## Pitfalls (read before touching)
- `Oracle.validate_trade` returns `(approved: bool, reason: str)` — a tuple is ALWAYS truthy. Unpack it. Checking the tuple directly silently ignores every veto (this happened in backtest_engine).
- Feature columns (hurst/adx/atr/sma_20) must come from `DuckDBBuffer.get_context(with_features=True)`. Raw OHLCV has no features — gates then read silent defaults and become no-ops.
- AccountState risk limits are computed properties (% of balance). Unknown kwargs are silently ignored by pydantic — pass only real fields.
- Don't copy concepts from other domains (Boolean networks/STP biology) into the trading stack. The regime gate is `RegimeFilter`, a plain named trend check.
- T+1 settlement: SELL proceeds land in `unsettled_cash`; they cannot fund same-day BUYs (GFV). Expect ~1-3 round trips/day max on full-size positions.
- Backtest PnL is (exit - entry) * shares. No TICK_VALUE multiplier (that was futures-era).

## Deploy
- Push to main → GitHub Actions runs tests → auto-deploys to droplet (needs DEPLOY_HOST/DEPLOY_USER/DEPLOY_SSH_KEY secrets).
- Droplet path `/opt/celestium_qt`, systemd service `celestium`, logs via `journalctl -u celestium -f`.
- `deploy.yml`'s `env:` for secrets lives at the job level (`jobs.deploy.env`), never workflow-level — GitHub rejects the whole file if `secrets` is referenced in a top-level `env:` block (see MISTAKES.md).
- `ingest_databento.yml` (Saturday cron) commits refreshed data back to `main` — needs `permissions: contents: write` in the workflow file itself, since the repo-wide Actions default can revert to read-only.
- Both workflows have `workflow_dispatch` enabled — trigger manually from the Actions tab to test without waiting for the schedule/a push.
