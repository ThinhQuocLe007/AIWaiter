"""Pytest config for the AI Waiter test tree.

This is the single seam that wires the repo onto ``sys.path`` and loads the
``.env`` at the project root once per test session, so:

    from src.agent_brain.agent import AIWaiterGraph

resolves from any test under ``tests/`` (pytest, plain ``python``, or the
CLI scripts in ``tests/scripts/``). Mirrors what the existing
``evals/scripts/*.py`` files do per-script.

Also pins a unique ``TABLE_ID`` for the conversation smoke tests so reruns
don't pollute real sessions — see ``tests/scripts/run_conversation_demo.py``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo root = parent of this conftest.py's parent (tests/).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Load .env from the repo root exactly once. pydantic-settings inside
# src.agent_brain.config also loads it, but doing it here means the
# top-level `os.environ` reflects the .env too (useful for the CLI
# scripts that don't go through Settings()).
try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    # dotenv is in the base deps of pyproject.toml; if it's missing, the
    # test environment is broken anyway and the actual imports below
    # will surface a clearer error than silently missing env vars.
    pass
