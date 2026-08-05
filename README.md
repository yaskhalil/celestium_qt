# CelestiumQT: Hierarchical Systematic Trading Stack

## Overview
CelestiumQT is a modular quantitative trading system optimized for high-precision execution on Cash Accounts (e.g., Alpaca/SPLG/SPY). It uses a hierarchical decision stack:
1. **Statistical Context:** (Hurst Exponent, ADX, ATR computed over 5-minute bars)
2. **Signal Generation:** (XGBoost Classifier natively trained on 1-year of S&P 500 history)
3. **Allocation:** (Dynamic Kelly-like sizing based on Capital-at-Risk / Stop-Loss distance)
4. **Risk Oracle:** (Deterministic T+1 Cash Settlement firewall to prevent Good Faith Violations)

---

## 🚀 Running the Pipeline Locally

To test the system or retrain the model locally, use the following commands. Ensure you have `DATABENTO_API_KEY` in your `.env` or exported.

### 1. Ingest Historical Data
Fetches 1-year of `ohlcv-1m` SPY data from Databento and resamples it into perfect 5-minute bars.
```bash
uv run python3 scripts/ingest_databento.py
```

### 2. Retrain the Model
Trains the XGBoost model (`alpha_v1.ubj`) using Walk-Forward Purged Cross-Validation across the historical data.
```bash
uv run python3 scripts/train.py
```

### 3. Run the Backtest
Runs the full evaluation engine (including the Oracle's T+1 Cash Settlement firewall and the dynamic risk allocator) over the historical data.
```bash
uv run python3 scripts/backtest.py
```

### 4. Open the TUI Dashboard
Launch the rich Terminal User Interface to monitor signals and live bot status.
```bash
uv run python3 scripts/tui.py
```

---

## ☁️ Deployment Guide (DigitalOcean Droplet)

### 1. Initial Server Setup
Run these commands on your droplet to prepare the environment:
```bash
# Update system and install dependencies
apt update && apt upgrade -y
apt install -y tzdata git curl

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Clone the repository into /opt
cd /opt
git clone git@github.com:yaskhalil/celestium_qt.git
cd celestium_qt

# Install project dependencies
uv sync
```

### 2. Configuration (`deployment_config.json` & `.env`)
Create a `.env` file in `/opt/celestium_qt/` to store your private keys:
```bash
ALPACA_API_KEY="your_key"
ALPACA_SECRET_KEY="your_secret"
ALPACA_BASE_URL="https://paper-api.alpaca.markets"
DATABENTO_API_KEY="your_db_key"
```

*Note: Risk parameters, multipliers, and `shadow_mode` are controlled dynamically via `deployment_config.json`.*

---

## 🔄 Updating the Droplet (Handling Git Conflicts)

If you modify the ML model (`alpha_v1.ubj`) locally and push to GitHub, your Droplet might throw a `merge conflict` error when you try to pull, because the Droplet may have generated its own local modifications.

To force the Droplet to flawlessly match your GitHub repository, run this:
```bash
cd /opt/celestium_qt
git fetch origin
git reset --hard origin/main
uv sync
systemctl restart celestium
```
*⚠️ **Warning**: `git reset --hard` will overwrite any uncommitted local changes on the Droplet.*

---

## 🚀 Push-to-Deploy (GitHub Actions)

Every push to `main` runs the full test suite in CI, then **auto-deploys to the Droplet** — no SSH by hand.

1. Add three repository secrets (GitHub → Settings → Secrets and variables → Actions):
   - `DEPLOY_HOST` — droplet IP or hostname
   - `DEPLOY_USER` — SSH user (`root`, or a user with passwordless sudo)
   - `DEPLOY_SSH_KEY` — the private key for that user (e.g. contents of `~/.ssh/id_ed25519`)

2. Verify the droplet can be reached by the key once: `ssh <DEPLOY_USER>@<DEPLOY_HOST>`
3. Push to `main`. CI tests run first; the deploy job runs `git reset --hard origin/main && uv sync && systemctl restart celestium` on `/opt/celestium_qt`.

The deploy job is skipped until `DEPLOY_HOST` is set, so CI is safe to enable immediately.

Both `deploy.yml` and `ingest_databento.yml` also expose `workflow_dispatch`, so you can trigger either one manually from the repo's **Actions** tab instead of waiting for a push or the Saturday cron schedule — useful for confirming a workflow fix actually worked.

### Weekly Data Refresh (`ingest_databento.yml`)
Runs every Saturday at 00:00 UTC: re-pulls the last year of `ohlcv-1m` SPY data from Databento, resamples it, and commits the refreshed dataset back to `main`. Needs the `DATABENTO_API_KEY` secret set, and needs the repo's Settings → Actions → General → Workflow permissions set to "Read and write permissions" (or an explicit `permissions: contents: write` in the workflow) so the commit-back step can push.

---

## 🛠 Service Management

CelestiumQT runs as a system service (`systemd`), ensuring it starts on boot and restarts automatically if it crashes.

- **Start Bot:** `systemctl start celestium`
- **Stop Bot:** `systemctl stop celestium`
- **Restart Bot:** `systemctl restart celestium`
- **Check Status:** `systemctl status celestium`

### Monitoring Logs
To watch the live trading logs and execution decisions in real-time:
```bash
journalctl -u celestium -f
```

---

## 🧠 Architecture Notes (2026 Build)
- **T+1 Oracle Firewall:** The system accurately tracks unsettled funds. Because SPY volatility is low, the Dynamic Allocator will naturally maximize your Buying Power to meet its 2% Risk Target. The Oracle correctly intercepts this and restricts trading to exactly ~1 trade per day to prevent Good Faith Violations (GFVs).
- **5-Minute Shift:** The pipeline was explicitly upgraded from 1-minute to 5-minute bars to eliminate market micro-noise and heavily increase the baseline win rate.
