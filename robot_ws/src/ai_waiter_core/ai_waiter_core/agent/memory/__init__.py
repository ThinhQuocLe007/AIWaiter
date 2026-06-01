from .checkpointer import get_checkpointer, create_thread_config

# Alias for backward compatibility in existing test suites
create_config = create_thread_config

__all__ = [
    "get_checkpointer",
    "create_thread_config",
    "create_config"
]
