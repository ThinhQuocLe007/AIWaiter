"""Position parser — turn a brain-emitted section *token* into a warehouse pose.

The warehouse brain only ever emits a geometry-agnostic ``PositionToken`` (e.g.
``"A"``, ``"dock"``, or the spoken label ``"Cầu cảng"``). This module is the
server-side half of the contract: it maps that token to a concrete Nav2 goal
pose (x, y, yaw) in the warehouse map frame, using the single layout file
(``services/floorplan.py``). The brain never computes coordinates; the robot
never has to understand Vietnamese — it just receives a pose.

The parser is deliberately tolerant:
  * ``"A"`` / ``"khu A"`` / ``"a"``         -> section A's pose
  * ``"dock"`` / ``"cầu cảng"``             -> the named place pose
  * a partial label (``"cảng"``)             -> matched against Vietnamese names

It returns ``None`` for anything it cannot resolve, so the caller can reject the
navigation request instead of dispatching to a phantom location.
"""

from __future__ import annotations

from src.server_orchestrator.services import floorplan


def _normalise(token: str) -> str:
    return token.strip().lower().lstrip("khu ").strip()


def parse_position(token: str) -> dict | None:
    """Resolve a section/place token to a navigation pose.

    Returns a dict ``{"id", "name", "x", "y", "yaw", "label"}`` or ``None``.
    """
    if not token:
        return None
    raw = token.strip()
    key = _normalise(raw)

    targets = floorplan.all_targets()
    # 1. Exact key/id match (section id "A", named-place key "dock", ...).
    if key in targets:
        return _build(targets[key])
    # 2. Case-insensitive exact label match (e.g. "Cầu cảng", "Khu A").
    labels = floorplan.label_index()
    if raw.lower() in labels:
        return _build(labels[raw.lower()])
    # 3. Substring against labels (e.g. "cảng" -> "Cầu cảng").
    for label, entry in labels.items():
        if key and key in label:
            return _build(entry)
    # 4. Substring against ids/keys.
    for tkey, entry in targets.items():
        if key and key in tkey.lower():
            return _build(entry)
    return None


def _build(entry: dict) -> dict:
    return {
        "id": entry.get("id"),
        "name": entry.get("name", entry.get("id")),
        "x": entry["x"],
        "y": entry["y"],
        "yaw": entry["yaw"],
        "label": entry.get("name", entry.get("id")),
    }


def known_tokens() -> list[str]:
    """All resolvable tokens (ids + keys + labels) — handy for validation/debug."""
    return sorted({*floorplan.all_targets().keys(), *floorplan.label_index().keys()})
