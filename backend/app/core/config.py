# Load .env FIRST before any pydantic-settings initialization
# This ensures environment variables are available when Settings() is instantiated
from dotenv import load_dotenv
load_dotenv()

from pydantic_settings import BaseSettings
from typing import Optional
class Settings(BaseSettings):
    PROJECT_NAME: str = "Remora-Quant Trading System"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    
    # API Keys
    CLAUDE_KEY: str = ""
    GEMINI_KEY: str = ""
    GEMINI_API_KEY: str = ""  # Alternative for ADK compatibility
    DEEPSEEK_KEY: str = ""
    ZHIPU_KEY: str = ""  # ZhipuAI GLM API Key
    
    # ADK (AI Trading Assistant) Configuration
    ADK_ENABLED: bool = False
    OPENROUTER_API_KEY: str = ""
    ADK_MODEL: Optional[str] = None
    ADK_TIMEOUT: int = 120
    STOCKBIT_COOKIES: Optional[str] = None
    
    # GoAPI Configuration (Indonesia Stock Data)
    GO_API_KEY: str = ""
    GO_API_LABEL: str = ""
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Risk Management (Remora-Quant)
    DAILY_LOSS_LIMIT: float = 0.025  # 2.5% daily loss limit (Kill Switch)
    MAX_POSITION_SIZE: float = 0.15  # 15% max per stock
    MAX_PORTFOLIO_EXPOSURE: float = 0.80  # 80% max total exposure
    
    # Trading Settings (Looping Strategy)
    SCOUT_SIZE: float = 0.30  # 30% initial position
    CONFIRM_SIZE: float = 0.30  # 30% confirmation
    ATTACK_SIZE: float = 0.40  # 40% aggressive
    PULLBACK_THRESHOLD: float = 0.02  # 2% pullback for re-entry
    
    # OBI Thresholds
    OBI_ACCUMULATION_THRESHOLD: float = 0.3  # OBI > 0.3 = Accumulation
    OBI_DISTRIBUTION_THRESHOLD: float = -0.3  # OBI < -0.3 = Distribution

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

