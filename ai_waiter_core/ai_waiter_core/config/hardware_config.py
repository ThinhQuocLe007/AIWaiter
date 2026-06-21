from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class HardwareSettings(BaseSettings):
    DEVICE: str = Field(default="cuda", env="DEVICE")

    # Device for the embedding model only. Empty -> follow the global DEVICE.
    # Set to "cpu"/"cuda" to override just the embedding without touching STT/VAD.
    # On the Jetson Orin 8GB unified-memory target, set EMBEDDING_DEVICE=cpu to keep
    # the embedding model (~1.2GB) off the iGPU so Ollama can fit the whole LLM on
    # GPU instead of spilling layers to CPU. Easy CPU/GPU toggle for benchmarking.
    EMBEDDING_DEVICE: str = Field(default="", env="EMBEDDING_DEVICE")

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8',
        extra="ignore" 
    )
