from .checkpointer import create_thread_config, get_checkpointer

# Alias for backward compatibility in existing test suites
create_config = create_thread_config

__all__ = [
    "get_checkpointer",
    "create_thread_config",
    "create_config"
]
