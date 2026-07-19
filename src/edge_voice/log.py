"""Logging for the voice device — stdlib only, on purpose.

The device used to borrow ``log_struct`` from ``src.agent_brain.utils``. That package's
``__init__`` also imports the brain's tracing + graph helpers, so a single log helper pulled
``langsmith``, ``langchain_core`` and ``huggingface_hub`` onto the Jetson — none of which the
robot role installs (``--extra voice``), and none of which it runs: the LLM lives on the server.

Same output format as the brain's logger so the two roles' logs read alike.
"""

import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] [%(name)s]: %(message)s")

# PortAudio/ALSA device scans and the edge-tts HTTP client are chatty at INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)

logger = logging.getLogger("src.edge_voice")


def log_struct(message: str, **kwargs) -> None:
    """Log a message with structured key-value pairs."""
    extra_info = " | ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"{message} >> {extra_info}" if extra_info else message)
