# CelestiumQT: Hierarchical Systematic Trading Stack

## Overview
CelestiumQT is a modular quantitative trading system optimized for high-precision execution. It uses a hierarchical decision stack (Statistical Context -> Signal Generation -> Risk Oracle) to automate trading while strictly adhering to prop firm rules (e.g., Apex/Bulenox).

---

## Deployment Guide (Digital Ocean Droplet)

### 1. Prerequisites
- A Digital Ocean Droplet (Ubuntu 22.04+ recommended).
- SSH access to the droplet (`ssh root@your_ip`).
- A private GitHub repository with your code.

### 2. Initial Server Setup
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

### 3. Configuration (.env)
Create a `.env` file in `/opt/celestium_qt/` to store your private keys:
```bash
WEBULL_APP_KEY="your_key"
WEBULL_APP_SECRET="your_secret"
WEBULL_ACCOUNT_ID="your_id"
DATABENTO_API_KEY="your_key"
SHADOW_MODE="True"
```

---

## Service Management

CelestiumQT runs as a system service (`systemd`), ensuring it starts on boot and restarts automatically if it crashes.

### Basic Commands
- **Start Bot:** `systemctl start celestium`
- **Stop Bot:** `systemctl stop celestium`
- **Restart Bot:** `systemctl restart celestium`
- **Check Status:** `systemctl status celestium`

### Monitoring Logs
To watch the live trading logs and execution:
```bash
journalctl -u celestium -f
```

---

## Toggling Shadow Mode
Shadow Mode allows the bot to generate signals and log decisions without sending real orders to the exchange.

1. **Enable Shadow Mode:**
   - Edit `.env`: `SHADOW_MODE="True"`
   - Restart: `systemctl restart celestium`

2. **Disable Shadow Mode (Live Trading):**
   - Edit `.env`: `SHADOW_MODE="False"`
   - Restart: `systemctl restart celestium`

---

## Updating the Droplet
When you push new code to GitHub, update your droplet with these commands:
```bash
cd /opt/celestium_qt
git pull origin main
uv sync
systemctl restart celestium
```

---

## Troubleshooting
- **Missing Timezone:** If the bot fails with a `ZoneInfoNotFoundError`, run `apt install tzdata`.
- **Model Missing:** If `models/alpha_v1.ubj` is not found, run `uv run python3 scripts/train.py` to generate the trading model.
- **Webull Pending:** If logs show `status: PENDING`, approve the API connection in your Webull mobile app.
