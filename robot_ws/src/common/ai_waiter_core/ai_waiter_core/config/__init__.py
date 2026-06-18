from .base_settings import BaseSystemSettings
from .agent_config import AgentSettings
from .hardware_config import HardwareSettings
from .database_config import DatabaseSettings

class Settings(DatabaseSettings, AgentSettings, HardwareSettings):
    pass

settings = Settings()
