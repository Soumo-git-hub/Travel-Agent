from pydantic import BaseSettings
from typing import Optional

class APISettings(BaseSettings):
    # API Configuration
    API_VERSION: str = "v1"
    API_PREFIX: str = "/api"
    DEBUG: bool = False
    
    # Security
    API_KEY_HEADER: str = "X-API-Key"
    API_KEY: Optional[str] = None
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 3600  # 1 hour
    
    # CORS
    ALLOWED_ORIGINS: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create global settings instance
api_settings = APISettings() 