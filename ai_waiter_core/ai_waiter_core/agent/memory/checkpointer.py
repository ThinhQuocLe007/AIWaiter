import sqlite3
import os
from langgraph.checkpoint.sqlite import SqliteSaver
from ai_waiter_core.config import settings
from langsmith import uuid7


def get_checkpointer():
    db_path = str(settings.CHECKPOINTS_DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)


def create_thread_config(table_id: str, session_id: str = None):
    if not session_id:
        session_id = str(uuid7())

    return {
        "configurable": {
            "thread_id": session_id,
            "table_id": table_id
        },
        "metadata": {
            "session_id": session_id,
            "table_id": table_id
        }
    }
