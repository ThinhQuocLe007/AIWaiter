from pydantic_settings import SettingsConfigDict

from .base_settings import BaseSystemSettings, ROOT
from .agent_config import AgentSettings
from .hardware_config import HardwareSettings
from .database_config import DatabaseSettings

class Settings(DatabaseSettings, AgentSettings, HardwareSettings):
    # Pin .env to an ABSOLUTE path anchored at the project root. The per-class
    # configs use a relative `env_file=".env"`, which pydantic-settings resolves
    # against the current working directory — so the file was only found when the
    # process happened to run from the repo root. Resolving against ROOT makes
    # .env load regardless of CWD.
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

settings = Settings()
