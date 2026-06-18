from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class HardwareSettings(BaseSettings):
    DEVICE: str = Field(default="cuda", env="DEVICE")
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8',
        extra="ignore" 
    )
