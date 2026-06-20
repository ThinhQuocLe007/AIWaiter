from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class AgentSettings(BaseSettings):
    ROUTER_MODEL: str = Field(default="qwen3:4b-instruct-2507-q4_K_M", env="ROUTER_MODEL")
    WORKER_MODEL: str = Field(default="qwen3:4b-instruct-2507-q4_K_M", env="WORKER_MODEL")
    RESPONSE_MODEL: str = Field(default="qwen3:4b-instruct-2507-q4_K_M", env="RESPONSE_MODEL")

    # Context window pinned for ALL Ollama calls. The model supports up to 262144
    # tokens; left unset, Ollama may allocate a large KV cache (a major RAM cost on
    # the Jetson Orin 8GB). One uniform value avoids Ollama reloading the model per
    # distinct num_ctx. 6144 fits the largest prompt (order worker ~3.5k tokens with
    # the full menu) plus history/output headroom.
    LLM_NUM_CTX: int = Field(default=6144, env="LLM_NUM_CTX")

    HF_TOKEN: str = Field(default="", env="HF_TOKEN")
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8',
        extra="ignore" 
    )
