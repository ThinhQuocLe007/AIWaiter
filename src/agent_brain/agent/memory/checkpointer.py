import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from src.agent_brain.config import settings


def get_checkpointer():
    db_path = str(settings.CHECKPOINTS_DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return SqliteSaver(conn)


def create_thread_config(table_id: str, session_id=None, stream_queue=None):
    """Build the LangGraph thread config for a table's current serving session.

    `thread_id = session_id` ties the conversation memory to the billable session, so payment
    (which CLOSES the session) is the boundary: the next guest at this table resolves a NEW
    session id → a fresh thread → no context bleed. The table-scoped fallback only applies when
    no session is open yet (e.g. a word before kiosk seating) and is replaced once one exists.

    `stream_queue` rides in `configurable`, NOT in the graph state. State is checkpointed to
    SQLite after every turn, and a live ``queue.Queue`` is not msgpack-serialisable: putting it
    in state made every /chat/stream turn die with
    ``TypeError: Type is not msgpack serializable: Queue`` *after* the sentences had already
    been streamed and spoken — so the robot talked while the tablet hung on "…" forever,
    because the ``voice.reply`` mirror never ran. `configurable` is per-invocation runtime
    plumbing and is never written to the checkpoint, which is what this field needs.
    """
    thread_id = str(session_id) if session_id is not None else f"table-{table_id}-nosession"

    return {
        "configurable": {
            "thread_id": thread_id,
            "table_id": table_id,
            "stream_queue": stream_queue,
        },
        "metadata": {
            "session_id": session_id,
            "table_id": table_id
        }
    }
