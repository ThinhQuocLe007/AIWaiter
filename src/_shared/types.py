"""Cross-role type vocabulary.

Single source of truth for the status strings / table-id normalisation that
cross the orchestrator ↔ agent ↔ voice seam. The orchestrator stores these
as TEXT in SQLite, the agent reads them as Pydantic strings, and the voice
device mirrors the same vocabulary back to the tablet — having a Python
``str`` enum everywhere keeps all three roles aligned.
"""
from __future__ import annotations

import re
from enum import Enum


# ── Status enums (str-valued so .value round-trips to/from the SQLite TEXT columns) ─────

class TableStatus(str, Enum):
    """Table serving-lifecycle (the panel's per-table badge)."""
    TRONG = "TRONG"               # free
    DANG_PHUC_VU = "DANG_PHUC_VU"  # occupied (seated, possibly with active order)
    DA_THANH_TOAN = "DA_THANH_TOAN"  # paid, waiting for staff to clear


class SessionStatus(str, Enum):
    """One visit by one party (a session's gộp bill is the sum of its orders)."""
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class OrderStatus(str, Enum):
    """An order's journey from the kitchen's point of view."""
    CHO_BEP = "CHO_BEP"           # waiting in the kitchen queue
    DANG_LAM = "DANG_LAM"          # being cooked
    XONG = "XONG"                  # ready to deliver


class OrderItemStatus(str, Enum):
    """Per-item status (mirrors the order's, with a per-item granular exception)."""
    CHO_BEP = "CHO_BEP"
    DANG_LAM = "DANG_LAM"
    XONG = "XONG"


class PaymentStatus(str, Enum):
    """The gộp payment for a session."""
    PENDING = "PENDING"
    PAID = "PAID"


class TaskKind(str, Enum):
    """A system task the dispatcher hands to a robot."""
    GO_TO_TABLE = "go_to_table"   # robot drives to a table (seating / call)
    DELIVER = "deliver"             # robot brings food from the kitchen
    CALL = "call"                   # robot goes to ask the guest "thêm món / thanh toán?"


class TaskStatus(str, Enum):
    """Task lifecycle (PENDING → ASSIGNED → IN_PROGRESS → DONE)."""
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class RobotStatus(str, Enum):
    """Per-robot state (the panel's robot board)."""
    IDLE = "idle"
    BUSY = "busy"
    # Task finished, driving back to the dock (still assignable — a new task can be queued).
    RETURNING = "returning"
    OFFLINE = "offline"


# ── Table id normalisation (the one function the agent & orchestrator both need) ───────

_TBL_DIGITS = re.compile(r"\d+")


def normalise_table_id(raw: str | int) -> int:
    """Normalise a table reference to the backend's INT id.

    The agent's tools receive table ids from the LLM as the human-readable
    form (``"T1"``, ``"T03"``, ``"  bàn 2 "``); the orchestrator REST API
    keys tables by INT. This is the one function that does the conversion
    at the seam, so both sides stay in sync.
    """
    if isinstance(raw, int):
        return raw
    match = _TBL_DIGITS.search(str(raw))
    if not match:
        raise ValueError(f"Cannot parse a table id from {raw!r}")
    return int(match.group(0))
