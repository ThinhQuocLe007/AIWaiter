from huggingface_hub.utils import logging
import logging

# Silence third-party lib noise 
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("faiss").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] [%(name)s]: %(message)s'
)

logger = logging.getLogger("ai_waiter_core")

def log_struct(message: str, **kwargs):
    """Log a message with structured key-value pairs."""
    extra_info = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
    if extra_info:
        logger.info(f"{message} >> {extra_info}")
    else:
        logger.info(message)
