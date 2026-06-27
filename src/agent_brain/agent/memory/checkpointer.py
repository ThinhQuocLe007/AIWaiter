import sqlite3
import os
from langgraph.checkpoint.sqlite import SqliteSaver
from ai_waiter_core.config import settings


def get_checkpointer():
    db_path = str(settings.CHECKPOINTS_DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return SqliteSaver(conn)


def create_thread_config(table_id: str, session_id=None):
    """Build the LangGraph thread config for a table's current serving session.

    `thread_id = session_id` ties the conversation memory to the billable session, so payment
    (which CLOSES the session) is the boundary: the next guest at this table resolves a NEW
    session id → a fresh thread → no context bleed. The table-scoped fallback only applies when
    no session is open yet (e.g. a word before kiosk seating) and is replaced once one exists.
    """
    thread_id = str(session_id) if session_id is not None else f"table-{table_id}-nosession"

    return {
        "configurable": {
            "thread_id": thread_id,
            "table_id": table_id
        },
        "metadata": {
            "session_id": session_id,
            "table_id": table_id
        }
    }
