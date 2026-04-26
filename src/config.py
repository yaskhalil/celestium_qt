import os
import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Webull Connectivity
    WEBULL_APP_KEY: str = Field(default="", alias="WEBULL_APP_KEY")
    WEBULL_APP_SECRET: str = Field(default="", alias="WEBULL_APP_SECRET")
    WEBULL_ACCOUNT_ID: str = Field(default="", alias="WEBULL_ACCOUNT_ID")

    # DuckDB Connectivity
    DUCKDB_PATH: str = Field(default="data/celestium.db", alias="DUCKDB_PATH")

    # Rithmic Connectivity (Legacy - To be removed)
    RITHMIC_USERNAME: str = Field(default="user", alias="RITHMIC_USERNAME")
    RITHMIC_PASSWORD: str = Field(default="pass", alias="RITHMIC_PASSWORD")
    RITHMIC_SYSTEM_NAME: str = Field(default="Rithmic Paper Trading", alias="RITHMIC_SYSTEM_NAME")
    
    # Databento (Historical Data)
    DATABENTO_API_KEY: str = Field(default="YOUR_DATABENTO_KEY", alias="DATABENTO_API_KEY")

    # Trading Target
    SYMBOL: str = "AAPL"
    EXCHANGE: str = "NASD"
    
    # Risk Limits (Bulenox 50K EOD - Option 2)
    STARTING_BALANCE: float = 50000.0
    BALANCE_FLOOR: float = 47500.0  # Initial floor for 50k account ($2,500 drawdown)
    DAILY_LOSS_LIMIT: float = 1100.0
    SOFT_KILL_SWITCH: float = 1050.0 # Trigger flatten before hard limit
    TOTAL_PROFIT_TARGET: float = 3000.0
    DAILY_PROFIT_CEILING: float = 1200.0 # 40% of $3,000
    MAX_POSITION_SIZE_MINI: int = 7
    MAX_POSITION_SIZE_MICRO: int = 70
    CONSISTENCY_THRESHOLD: float = 0.40 # 40% Rule
    MAX_DAILY_TRADES: int = 50
    QUALIFYING_THRESHOLD: float = 100.0
    HURST_THRESHOLD: float = 0.42
    
    # Strategy Parameters
    SHADOW_MODE: bool = Field(default=True, alias="SHADOW_MODE")
    COMMISSION_PER_LOT: float = 0.60 # MNQ Round-trip
    SIGNAL_THRESHOLD: float = 0.4
    TICK_VALUE: float = 2.0 # Micro Nasdaq
    PT_MULTIPLIER: float = 1.0
    SL_MULTIPLIER: float = 0.5

    # Allocator Settings
    REFERENCE_ATR: float = 20.0
    
    # Advisor (Local LLM)
    ADVISOR_URL: str = Field(default="http://localhost:11434/api/generate", alias="ADVISOR_URL")
    ADVISOR_MODEL: str = Field(default="llama3", alias="ADVISOR_MODEL")

    # Payout Rules
    SAFETY_THRESHOLD_RESERVE: float = 2600.0
    MIN_WITHDRAWAL: float = 1000.0

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
