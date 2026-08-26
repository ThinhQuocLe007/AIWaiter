"""SQLite layer for the Orchestrator (warehouse fleet + navigation tasks).

Plain sqlite3 (no ORM) keeps things small; swapping to SQLAlchemy later only
changes this file. Connections are per-call (FastAPI is multi-threaded by
default) with row factory set so rows behave like dicts.

The status-string vocabulary used in the TEXT columns is the same one exported by
``src._shared.types`` (RobotStatus, TaskStatus, TaskKind). SQLite stores raw
TEXT so the enums aren't enforced at the DB level — they're enforced on the
Python side by Pydantic in the REST schemas (``schemas/__init__.py``). The
defaults in the schema below match the enum ``.value`` strings; if you change
one, change the other.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from src._shared.types import RobotStatus, TaskStatus

from ..config import settings

# Warehouse data model.
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS robots (
    id              TEXT PRIMARY KEY,
    name            TEXT,
    status          TEXT NOT NULL DEFAULT '{RobotStatus.OFFLINE.value}',
    battery         REAL,
    x               REAL,
    y               REAL,
    current_task_id INTEGER,
    activity        TEXT
);

-- A navigation task the dispatcher hands to an AGV. `kind` is a TaskKind value; `target_token`
-- is the brain-emitted section/place token (e.g. "A", "dock"); `pose_*` is the resolved goal
-- pose in the warehouse map frame (set by the dispatcher via the position_parser).
CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kind          TEXT NOT NULL,        -- navigate | return | charge
    target_token  TEXT,
    pose_x        REAL,
    pose_y        REAL,
    pose_yaw      REAL,
    robot_id      TEXT,
    status        TEXT NOT NULL DEFAULT '{TaskStatus.PENDING.value}',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    """Per-call connection; commits on success, rolls back on error."""
    conn = _connect(settings.db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create the schema (idempotent). Called once on startup."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _apply_migrations(conn)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    # Columns added after the first release. `CREATE TABLE IF NOT EXISTS` never alters an existing
    # table, so we ADD COLUMN them on startup for DBs seeded before these existed (idempotent).
    migrations: dict[str, list[tuple[str, str]]] = {
        "robots": [("activity", "TEXT")],
    }
    for table, cols in migrations.items():
        existing = {r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        for name, decl in cols:
            if name not in existing:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {name} {decl}')
