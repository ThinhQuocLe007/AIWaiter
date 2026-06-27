"""SQLite layer for the Orchestrator (schema from mục 8 of SYSTEM_ARCHITECTURE.md).

Plain sqlite3 (no ORM) keeps Bước 0 small; swapping to SQLAlchemy later only changes this
file. Connections are per-call (FastAPI is multi-threaded by default) with row factory set so
rows behave like dicts.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import settings

# Mục 8 data model. `tables` is quoted because TABLE is a SQL keyword.
SCHEMA = """
CREATE TABLE IF NOT EXISTS "tables" (
    id               INTEGER PRIMARY KEY,
    name             TEXT NOT NULL,
    capacity         INTEGER NOT NULL DEFAULT 4,
    status           TEXT NOT NULL DEFAULT 'TRONG',
    current_order_id INTEGER,
    party_size       INTEGER,
    seated_at        TEXT
);

-- A serving session: one party's whole visit at a table (seating → pay → leave). Orders and
-- the single (gộp) payment hang off this. A table has many sessions over time, one ACTIVE.
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id   INTEGER NOT NULL,
    status     TEXT NOT NULL DEFAULT 'ACTIVE',   -- ACTIVE | CLOSED
    party_size INTEGER,
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    ended_at   TEXT,
    FOREIGN KEY (table_id) REFERENCES "tables"(id)
);

CREATE TABLE IF NOT EXISTS dishes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    price     REAL NOT NULL,
    category  TEXT,
    available INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    -- session_id is the owner (the ledger groups orders by session for the gộp bill). Nullable
    -- through Phase 1 so the current table-only POST /orders keeps working until the seam (Phase
    -- 2) starts setting it; table_id stays for fast kitchen/robot lookups.
    session_id INTEGER,
    table_id   INTEGER NOT NULL,
    status     TEXT NOT NULL DEFAULT 'CHO_BEP',
    total      REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (table_id) REFERENCES "tables"(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    dish_id  INTEGER,
    name     TEXT NOT NULL,
    qty      INTEGER NOT NULL DEFAULT 1,
    price    REAL NOT NULL DEFAULT 0,
    note     TEXT,
    status   TEXT NOT NULL DEFAULT 'CHO_BEP',
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS robots (
    id              TEXT PRIMARY KEY,
    name            TEXT,
    status          TEXT NOT NULL DEFAULT 'offline',
    battery         REAL,
    x               REAL,
    y               REAL,
    current_task_id INTEGER
);

CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    table_id   INTEGER,
    order_id   INTEGER,
    robot_id   TEXT,
    status     TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

"""

# Payments live in their own DDL because the model changed from per-order → per-session (gộp 1
# lần / phiên). Changing order_id → session_id flips a NOT NULL column, which SQLite can't ALTER,
# so legacy per-order tables are dropped and recreated (see _migrate_payments_to_session).
PAYMENTS_DDL = """
CREATE TABLE IF NOT EXISTS payments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    method     TEXT,
    amount     REAL NOT NULL,
    status     TEXT NOT NULL DEFAULT 'PENDING',   -- PENDING | PAID
    txn_ref    TEXT,
    qr_url     TEXT,
    paid_at    TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
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


# Columns added after the first release. `CREATE TABLE IF NOT EXISTS` never alters an existing
# table, so we ADD COLUMN them on startup for DBs seeded before these existed (idempotent).
_MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    "tables": [("party_size", "INTEGER"), ("seated_at", "TEXT")],
    "robots": [("activity", "TEXT")],
    "orders": [("session_id", "INTEGER")],
    "payments": [("qr_url", "TEXT")],
}


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for table, cols in _MIGRATIONS.items():
        existing = {r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        for name, decl in cols:
            if name not in existing:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {name} {decl}')


def _migrate_payments_to_session(conn: sqlite3.Connection) -> None:
    """Drop a legacy per-order `payments` table so PAYMENTS_DDL can recreate it per-session.

    Old rows are per-order mock confirmations with no session link; they're discarded (demo data,
    and the ledger is now gộp-by-session). Runs before PAYMENTS_DDL; a no-op once migrated.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(payments)")}
    if cols and "order_id" in cols and "session_id" not in cols:
        conn.execute("DROP TABLE payments")


def init_db() -> None:
    """Create the schema (idempotent). Called once on startup."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate_payments_to_session(conn)
        conn.executescript(PAYMENTS_DDL)
        _apply_migrations(conn)
