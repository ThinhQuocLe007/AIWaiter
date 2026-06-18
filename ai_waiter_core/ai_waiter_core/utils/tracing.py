import functools
from typing import Any, Dict, List, Optional
from langsmith import traceable
from langsmith import Client

def flush_traces():
    """
    Ensure all traces are sent to LangSmith before exiting.
    In langsmith >= 0.1.x, we use Client().flush() instead of wait_for_all_tracers.
    """
    client = Client()
    client.flush()

def trace_latency(name: str, run_type: str = "chain"):
    """
    A decorator to trace the latency of a function and report it to LangSmith.
    Replaces the old manual TracingManager.
    """
    def decorator(func):
        @traceable(name=name, run_type=run_type)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator
