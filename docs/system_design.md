# System Design

High-level architecture for CelestiumQT. For per-module detail see `data.md`, `features.md`, `models.md`, `core.md`, `execution.md`.

## Overview

CelestiumQT is a systematic trading bot for Cash Accounts (Alpaca, target symbol `SPYM`). It runs as a single long-lived `systemd` service (`src/main.py`), polling on a schedule rather than streaming, and makes every trade decision through a fixed 4-layer pipeline before anything reaches the broker.

## Decision Pipeline

```
  Ingestion/Storage        Layer 1              Layer 2            Layer 3            Layer 4
  ────────────────    ─────────────────    ──────────────    ───────────────    ─────────────────
  Databento/DuckDB -> RegimeFilter      -> Classifier      -> Allocator      -> Oracle
  (data/*.py)          (features/regime.py) (models/classifier.py) (core/allocator.py) (core/oracle.py)
                        Hurst/ADX/SMA20      XGBoost prob.       Kelly-like size    DLL / GFV / profit
                        trend gate           buy/sell/hold                          ceiling firewall
                                                                                          |
                                                                                          v
                                                                              PositionManager -> Alpaca
                                                                              (execution/position_manager.py)
```

`src/core/strategy.py` (`SignalGenerator`) orchestrates layers 1-4 and returns a `(TradeProposal, veto_reason)` tuple — it is purely generative and decoupled from scheduling. `src/core/engine.py` (`ScheduledEngine`) owns the polling loop that calls it and hands approved proposals to `PositionManager` for execution.

**No trade bypasses `Oracle.validate_trade`.** The Oracle is the single deterministic gate — every other layer can suggest a trade, only the Oracle can approve one crossing into execution.

## Process Layout

`src/main.py` is the entrypoint:
1. Validates timezone data and Alpaca credentials, aborts startup if either fails.
2. Syncs real account state (`equity`, `cash`) from Alpaca — no hardcoded balances.
3. Loads/creates persistent `AccountState` (`data/account_state.json`) and reconciles any open position already held at the broker.
4. Boots `ScheduledEngine` (the trading loop) and `TelegramBot` (the control/alerting channel) as concurrent asyncio tasks.
5. On shutdown (`SIGINT`/`SIGCancel`): stops the bot, stops the engine, persists state, closes the Alpaca client — in that order, so no in-flight state is lost.

Two supporting entrypoints reuse the same pipeline components without the live loop:
- `scripts/backtest.py` — runs `BacktestEngine` (DuckDB + Polars) over historical data through the same Oracle/Allocator logic.
- `scripts/train.py` — retrains the XGBoost classifier via walk-forward purged cross-validation.
- `scripts/tui.py` — read-only Textual dashboard for monitoring a running instance (see `tui_dashboard.md`).

## State & Configuration

- **`AccountState`** (`data/account_state.json`) — balance, equity, daily PnL, trading history, position status. The source of truth the Oracle firewall checks against; saved after every state-changing event.
- **`deployment_config.json`** — the only config that's meant to change at runtime (currently `shadow_mode`), toggled live via the `/shadow` Telegram command rather than requiring a redeploy.
- **`Settings`** (`src/config.py`, Pydantic `BaseSettings`) — everything else: API keys (env-backed, never hardcoded), symbol, risk-limit percentages. Risk limits are percentages of the actual synced balance, not fixed dollar amounts.
- **`data/celestium.db`** (DuckDB) — historical OHLCV bars, written by the ingestion pipeline, read by the backtest engine and feature generation.

## Control & Observability

- **Logging** (`core/logging_setup.py`) — structlog: colored human-readable console output + rotating JSON file (`data/logs/celestium.log`, 5MB × 3 backups), one shared processor pipeline for both.
- **Telegram** (`core/notifier.py`, `core/telegram_bot.py`) — outbound alerts (trade fills, risk vetoes, daily recap, startup/shutdown) plus an inbound command channel (`/status`, `/pause`, `/resume`, `/positions`, `/vetoes`, `/performance`, `/shadow`, `/backtest`) for operating the bot without shell access.
- **MCP server** (`core/mcp_server.py`) — exposes read-only account-state tools/resources over MCP for external agent access.

## Deployment

Single DigitalOcean droplet running the bot as a `systemd` service (`celestium.service`). CI (GitHub Actions) runs the test suite on every push to `main` and auto-deploys via `git reset --hard origin/main && uv sync && systemctl restart celestium`. A separate weekly workflow re-ingests the trailing year of Databento data and commits it back to `main`. See `README.md` for the exact commands.

## Design Decisions Worth Knowing

- **5-minute bars, not 1-minute** — deliberately upgraded to cut market micro-noise and raise baseline win rate.
- **T+1 settlement is enforced structurally**, not just checked — the Oracle tracks unsettled funds and will cap trading (often to ~1 trade/day) to prevent Good Faith Violations, even when the allocator would otherwise size a trade that fits buying power.
- **Alpaca is the sole broker/data source.** Webull and Rithmic integrations existed earlier in the project's history and were fully removed (see git history around `5c500b5`); no code should reference them going forward.
