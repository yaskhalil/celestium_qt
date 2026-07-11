import os
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Webull Connectivity (Legacy)
    WEBULL_APP_KEY: str = Field(default="", alias="WEBULL_APP_KEY")
    WEBULL_APP_SECRET: str = Field(default="", alias="WEBULL_APP_SECRET")
    WEBULL_ACCESS_TOKEN: str = Field(default="", alias="WEBULL_ACCESS_TOKEN")
    WEBULL_ACCOUNT_ID: str = Field(default="", alias="WEBULL_ACCOUNT_ID")

    # DuckDB Connectivity
    DUCKDB_PATH: str = Field(default="data/celestium.db", alias="DUCKDB_PATH")

    # Rithmic Connectivity (Legacy - To be removed)
    RITHMIC_USERNAME: str = Field(default="user", alias="RITHMIC_USERNAME")
    RITHMIC_PASSWORD: str = Field(default="pass", alias="RITHMIC_PASSWORD")
    RITHMIC_SYSTEM_NAME: str = Field(default="Rithmic Paper Trading", alias="RITHMIC_SYSTEM_NAME")
    
    # Databento (Historical Data)
    DATABENTO_API_KEY: str = Field(default="YOUR_DATABENTO_KEY", alias="DATABENTO_API_KEY")

    # Alpaca (Unified Data & Execution)
    ALPACA_API_KEY: str = Field(default="", alias="ALPACA_API_KEY")
    ALPACA_SECRET_KEY: str = Field(default="", alias="ALPACA_SECRET_KEY")
    ALPACA_BASE_URL: str = Field(default="https://paper-api.alpaca.markets", alias="ALPACA_BASE_URL")

    # Trading Target
    SYMBOL: str = "SPYM"
    CONTEXT_SYMBOL: str = "QQQ"
    EXCHANGE: str = "NASD"
    
    # ── Dynamic Risk Limits (% of Balance) ─────────────────────────────
    # All risk limits are now percentages of the actual account balance,
    # fetched from Alpaca at startup. The old hardcoded $50K defaults are gone.
    
    # Daily Loss Limit: % of balance that triggers intraday halt
    DLL_PCT: float = Field(default=0.05, alias="DLL_PCT")  # 5% of balance
    # Daily Profit Ceiling: % gain before auto-locking for the day
    PROFIT_CEILING_PCT: float = Field(default=0.06, alias="PROFIT_CEILING_PCT")  # 6% of balance
    # Balance Floor: % of starting balance that triggers full stop
    FLOOR_PCT: float = Field(default=0.90, alias="FLOOR_PCT")  # 90% of starting balance = 10% max drawdown
    # Safety reserve: % of balance held back from trading
    RESERVE_PCT: float = Field(default=0.05, alias="RESERVE_PCT")  # 5%
    # Soft kill switch: % of DLL that triggers early flatten
    SOFT_KILL_PCT: float = Field(default=0.85, alias="SOFT_KILL_PCT")  # 85% of DLL

    # ── Position & Trading Limits ─────────────────────────────────────
    MAX_POSITION_PCT: float = Field(default=0.30, alias="MAX_POSITION_PCT")  # Max 30% of balance in one position
    MAX_DAILY_TRADES: int = 50
    HURST_THRESHOLD: float = 0.42
    
    # Strategy Parameters
    SHADOW_MODE: bool = Field(default=True, alias="SHADOW_MODE")
    COMMISSION_PER_LOT: float = 0.60
    SIGNAL_THRESHOLD: float = 0.4
    TICK_VALUE: float = 2.0
    PT_MULTIPLIER: float = 1.0
    SL_MULTIPLIER: float = 0.5

    # Allocator Settings
    REFERENCE_ATR: float = 20.0
    
    # Advisor (Local LLM)
    ADVISOR_URL: str = Field(default="http://localhost:11434/api/generate", alias="ADVISOR_URL")
    ADVISOR_MODEL: str = Field(default="llama3", alias="ADVISOR_MODEL")

    # Telegram Notifications
    TELEGRAM_ENABLED: bool = Field(default=False, alias="TELEGRAM_ENABLED")
    TELEGRAM_BOT_TOKEN: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID: str = Field(default="", alias="TELEGRAM_CHAT_ID")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Global instance
settings = Settings()

# Hook: Load deployment overrides if they exist
DEPLOYMENT_PATH = "deployment_config.json"
if os.path.exists(DEPLOYMENT_PATH):
    try:
        with open(DEPLOYMENT_PATH, "r") as f:
            overrides = json.load(f)
            for k, v in overrides.items():
                attr_name = k.upper()
                if hasattr(settings, attr_name):
                    setattr(settings, attr_name, v)
        print(f"--- DEPLOYMENT CONFIG LOADED: {DEPLOYMENT_PATH} ---")
    except Exception as e:
        print(f"Error loading deployment config: {e}")
