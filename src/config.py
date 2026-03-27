from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Rithmic Connectivity
    RITHMIC_USERNAME: str = Field(default="user", alias="RITHMIC_USERNAME")
    RITHMIC_PASSWORD: str = Field(default="pass", alias="RITHMIC_PASSWORD")
    RITHMIC_SYSTEM_NAME: str = Field(default="Rithmic Paper Trading", alias="RITHMIC_SYSTEM_NAME")
    
    # Trading Target
    SYMBOL: str = "NQZ4"
    EXCHANGE: str = "CME"
    
    # Risk Limits (Apex 4.0 Rules)
    BALANCE_FLOOR: float = 26100.0
    DAILY_LOSS_LIMIT: float = 500.0
    MAX_POSITION_SIZE: int = 1  # 1 contract
    CONSISTENCY_THRESHOLD: float = 0.50 # 50% Rule
    
    # Allocator Settings
    REFERENCE_ATR: float = 20.0
    
    # Advisor Settings
    ADVISOR_URL: str = "http://localhost:11434/api/generate"
    ADVISOR_MODEL: str = "quant-advisor" # Matches the 2026 Modelfile

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
