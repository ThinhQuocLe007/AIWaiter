"""Cross-role type vocabulary.

Single source of truth for the status strings that cross the orchestrator ↔
agent ↔ voice seam. The orchestrator stores these as TEXT in SQLite, the agent
reads them as Pydantic strings, and the robot mirrors the same vocabulary back —
having a Python ``str`` enum everywhere keeps all roles aligned.

This is the **warehouse** vocabulary: the robot is an AGV that navigates to a
storage section or a named place (dock / charging / packing / QC) on command from
the warehouse brain.
"""
from __future__ import annotations

import re
from enum import Enum

# ── Status enums (str-valued so .value round-trips to/from the SQLite TEXT columns) ─────

class TaskKind(str, Enum):
    """A system task the dispatcher hands to an AGV."""
    NAVIGATE = "navigate"   # drive to a target section / named place (pose supplied)
    RETURN = "return"         # drive back to the dock
    CHARGE = "charge"         # drive to the charging station


class TaskStatus(str, Enum):
    """Task lifecycle (PENDING → ASSIGNED → IN_PROGRESS → DONE, or CANCELLED)."""
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class RobotStatus(str, Enum):
    """Per-robot state (the panel's robot board)."""
    IDLE = "idle"
    BUSY = "busy"
    # Task finished, driving back to the dock (still assignable — a new task can be queued).
    RETURNING = "returning"
    OFFLINE = "offline"
    # Mid-task stop ("dừng lại") or preempted by a newer goal: no active task, but the robot is
    # physically parked somewhere, not at the dock. Still assignable — a new task re-drives it.
    HOLDING = "holding"


# ── Session-id normalisation (the one function the agent & orchestrator both need) ───────

_TBL_DIGITS = re.compile(r"\d+")


def normalise_table_id(raw: str | int) -> int:
    """Normalise a conversation/session reference to the backend's INT id.

    The warehouse brain keys each voice session by a string (e.g. ``"T1"``,
    ``"  bàn 2 "``); the orchestrator fans voice events out by that id. This is
    the one function that extracts the numeric id at the seam, so both sides
    stay in sync. Kept named ``normalise_table_id`` only to limit churn at the
    voice-bridge call sites.
    """
    if isinstance(raw, int):
        return raw
    match = _TBL_DIGITS.search(str(raw))
    if not match:
        raise ValueError(f"Cannot parse a session id from {raw!r}")
    return int(match.group(0))
