from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

from .base_settings import ROOT

class AgentSettings(BaseSettings):
    ROUTER_MODEL: str = Field(default="gemma4:e2b-it-qat", env="ROUTER_MODEL")
    WORKER_MODEL: str = Field(default="gemma4:e2b-it-qat", env="WORKER_MODEL")
    RESPONSE_MODEL: str = Field(default="gemma4:e2b-it-qat", env="RESPONSE_MODEL")

    # Context window pinned for ALL Ollama calls. The model supports up to 262144
    # tokens; left unset, Ollama may allocate a large KV cache (a major RAM cost on
    # the Jetson Orin 8GB). One uniform value avoids Ollama reloading the model per
    # distinct num_ctx. 8192 fits the largest prompt (order worker ~3.5k tokens with
    # the full menu) plus history/output headroom.
    LLM_NUM_CTX: int = Field(default=8192, env="LLM_NUM_CTX")

    HF_TOKEN: str = Field(default="", env="HF_TOKEN")

    # Base URL of the Orchestrator backend (the single ledger). The agent's tools write through
    # this seam (POST /orders, /payments, /payments/verify) instead of touching a DB directly.
    ORCHESTRATOR_URL: str = Field(default="http://localhost:8000", env="ORCHESTRATOR_URL")

    # Absolute path anchored at the project root so .env loads regardless of the
    # current working directory (e.g. when an eval script runs from a subdir).
    # A relative ".env" is resolved against CWD and silently misses the repo .env,
    # making every model fall back to its hardcoded default.
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding='utf-8',
        extra="ignore"
    )
