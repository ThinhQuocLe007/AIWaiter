from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class AgentSettings(BaseSettings):
    ROUTER_MODEL: str = Field(default="qwen3:4b-instruct-2507-q4_K_M", env="ROUTER_MODEL")
    WORKER_MODEL: str = Field(default="qwen3:4b-instruct-2507-q4_K_M", env="WORKER_MODEL")
    RESPONSE_MODEL: str = Field(default="qwen3:4b-instruct-2507-q4_K_M", env="RESPONSE_MODEL")
    HF_TOKEN: str = Field(default="", env="HF_TOKEN")
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8',
        extra="ignore" 
    )
