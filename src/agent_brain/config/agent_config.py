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

    # How long Ollama keeps a model resident in RAM/VRAM after a request. Default Ollama behaviour
    # is 5 minutes, so an idle table evicts the model and the next turn pays the full reload cost.
    # "-1" pins the model for the lifetime of the service (paired with startup warmup) so the first
    # — and every — real turn skips the load. Set to e.g. "10m" to cap memory on a shared box.
    LLM_KEEP_ALIVE: str = Field(default="-1", env="LLM_KEEP_ALIVE")

    @property
    def llm_keep_alive(self):
        """Ollama wants keep_alive as an int (seconds; -1 = forever) OR a duration string with a
        unit ("10m"). A bare "-1"/"0" string is parsed as a duration and rejected ('missing unit'),
        so coerce integer-like values to int and leave real duration strings ("10m") as-is."""
        v = self.LLM_KEEP_ALIVE.strip()
        try:
            return int(v)
        except ValueError:
            return v

    HF_TOKEN: str = Field(default="", env="HF_TOKEN")

    # Base URL of the Orchestrator backend (the single ledger). The agent's tools write through
    # this seam (POST /orders, /payments, /payments/verify) instead of touching a DB directly.
    ORCHESTRATOR_URL: str = Field(default="http://localhost:8000", env="ORCHESTRATOR_URL")

    # Base URL of the agent (LLM) HTTP service (src/agent_brain/server.py). The Jetson voice loop
    # (main.py) does mic→VAD→Whisper locally, then POSTs the recognised text here for the LLM to
    # process. Point this at the server box on the Jetson's .env (e.g. http://192.168.1.10:8100);
    # the default suits running everything on one machine.
    AGENT_URL: str = Field(default="http://localhost:8100", env="AGENT_URL")

    # Absolute path anchored at the project root so .env loads regardless of the
    # current working directory (e.g. when an eval script runs from a subdir).
    # A relative ".env" is resolved against CWD and silently misses the repo .env,
    # making every model fall back to its hardcoded default.
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding='utf-8',
        extra="ignore"
    )
