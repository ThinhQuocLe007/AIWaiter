"""Append-only transcript logger for voice ↔ LLM turns (offline review / eval).

Each call to :func:`log_turn` writes ONE JSON object (JSONL — one line per turn) to a
per-day file under ``storage/conversations/``:

    storage/conversations/2026-07-04.jsonl

A line records the guest's recognised utterance, the agent's spoken reply, and the UI
decision (stage + action), tagged with table/session/timestamp so turns can be grouped
back into a conversation without a DB. Read it with ``jq``, e.g. one table's visit:

    jq -c 'select(.table_id=="T1")' storage/conversations/2026-07-04.jsonl

This is best-effort telemetry: a logging failure must never break a guest's turn, so
every write is wrapped and only warns. It is deliberately separate from the LangGraph
checkpointer (which stores agent *memory*); this file is the human-readable *history*.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.agent_brain.config import settings

log = logging.getLogger(__name__)


def _log_dir() -> Path:
    return settings.storage_dir / "conversations"


def log_turn(
    *,
    table_id: str,
    session_id: str | None,
    user_text: str,
    response: str,
    stage: str,
    action: dict[str, Any] | None,
) -> None:
    """Append one turn to today's JSONL transcript. Best-effort — never raises."""
    try:
        now = datetime.now(timezone.utc).astimezone()
        record = {
            "ts": now.isoformat(timespec="milliseconds"),
            "table_id": table_id,
            "session_id": session_id,
            "user": user_text,
            "assistant": response,
            "stage": stage,
            "action": action,
        }
        directory = _log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{now.strftime('%Y-%m-%d')}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001 — telemetry must not break the turn
        log.warning("Failed to log conversation turn (table=%s): %s", table_id, e)
