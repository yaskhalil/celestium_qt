from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, ConfigDict

class Settings(BaseSettings):
    # API Keys
    RITHMIC_USERNAME: str = Field(default="user", alias="RITHMIC_USERNAME")
    RITHMIC_PASSWORD: str = Field(default="pass", alias="RITHMIC_PASSWORD")
    
    # Risk Limits (Apex 4.0 Rules)
    BALANCE_FLOOR: float = 26100.0
    DAILY_LOSS_LIMIT: float = 500.0
    MAX_POSITION_SIZE: int = 1  # 1 contract
    CONSISTENCY_THRESHOLD: float = 0.50 # 50% Rule

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
