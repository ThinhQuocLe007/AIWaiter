"""Session helpers — one party's whole visit at a table (seating → orders → gộp payment → leave).

The ledger groups orders and the single payment by `session_id`. These tiny helpers are shared by
the tables/orders/payments routers so "find/open/close the active session for a table" lives in one
place. They take an open connection (caller owns the transaction) and use plain sqlite3 rows.
"""

import sqlite3


def get_active_session(conn: sqlite3.Connection, table_id: int) -> sqlite3.Row | None:
    """The table's currently-open session, or None. One ACTIVE session per table at a time."""
    return conn.execute(
        "SELECT * FROM sessions WHERE table_id = ? AND status = 'ACTIVE' "
        "ORDER BY id DESC LIMIT 1",
        (table_id,),
    ).fetchone()


def create_session(
    conn: sqlite3.Connection, table_id: int, party_size: int | None = None
) -> int:
    cur = conn.execute(
        "INSERT INTO sessions (table_id, status, party_size) VALUES (?, 'ACTIVE', ?)",
        (table_id, party_size),
    )
    return int(cur.lastrowid)


def ensure_active_session(
    conn: sqlite3.Connection, table_id: int, party_size: int | None = None
) -> int:
    """Return the table's ACTIVE session id, opening one if none exists.

    Seating normally opens the session; this keeps a stray order (e.g. agent confirms before a
    kiosk seating) from failing — it lazily opens a session instead.
    """
    row = get_active_session(conn, table_id)
    return row["id"] if row else create_session(conn, table_id, party_size)


def close_session(conn: sqlite3.Connection, session_id: int) -> None:
    """Mark a session CLOSED (idempotent). Payment completion is the only caller (the boundary)."""
    conn.execute(
        "UPDATE sessions SET status = 'CLOSED', ended_at = datetime('now') "
        "WHERE id = ? AND status = 'ACTIVE'",
        (session_id,),
    )


def session_total(conn: sqlite3.Connection, session_id: int) -> float:
    """Gộp bill: sum of every order's total in the session."""
    row = conn.execute(
        "SELECT COALESCE(SUM(total), 0) AS t FROM orders WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return float(row["t"])
