import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Try to use pydantic_settings, but provide fallback for Pydantic v1 or when package is missing
try:
    from pydantic_settings import BaseSettings
    
    class Settings(BaseSettings):
        """Application settings with Pydantic v2 support."""
        # API keys
        GOOGLE_MAPS_API_KEY: Optional[str] = None
        
        # App settings
        APP_NAME: str = "Voice-Driven Driver Assistant"
        API_V1_STR: str = "/api/v1"
        
        class Config:
            env_file = ".env"
            case_sensitive = True
            
except ImportError:
    # Fallback to basic settings implementation when pydantic_settings is not available
    print("WARNING: pydantic_settings package not found.")
    print("Please install it with: pip install pydantic-settings")
    print("Using a simplified Settings class as fallback.")
    
    class Settings:
        """Simple fallback Settings class that reads from environment variables."""
        def __init__(self):
            self.GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
            self.APP_NAME = os.environ.get("APP_NAME", "Voice-Driven Driver Assistant")
            self.API_V1_STR = os.environ.get("API_V1_STR", "/api/v1")
        
        def dict(self) -> Dict[str, Any]:
            """Return settings as a dictionary."""
            return {
                "GOOGLE_MAPS_API_KEY": self.GOOGLE_MAPS_API_KEY,
                "APP_NAME": self.APP_NAME,
                "API_V1_STR": self.API_V1_STR,
            }

# Create a settings instance
settings = Settings()
