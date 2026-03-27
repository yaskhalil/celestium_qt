from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # API Keys
    RITHMIC_USERNAME: str = Field(default="user", env="RITHMIC_USERNAME")
    RITHMIC_PASSWORD: str = Field(default="pass", env="RITHMIC_PASSWORD")
    
    # Risk Limits (Apex 2026 Rules)
    BALANCE_FLOOR: float = 26100.0
    DAILY_LOSS_LIMIT: float = 500.0
    MAX_POSITION_SIZE: int = 1  # 1 contract
    CONSISTENCY_THRESHOLD: float = 0.50 # 50% Rule

    class Config:
        env_file = ".env"

settings = Settings()
