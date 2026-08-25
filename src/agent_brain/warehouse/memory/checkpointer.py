"""Session memory — sqlite checkpointer keyed by session_id (one worker shift = one thread)."""

from __future__ import annotations

from langgraph.checkpoint.sqlite import SqliteSaver

from src.agent_brain.warehouse.paths import storage_path


def get_checkpointer(db_path: str | None = None) -> SqliteSaver:
    import sqlite3

    if db_path is None:
        db_path = str(storage_path() / "checkpoints.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)
