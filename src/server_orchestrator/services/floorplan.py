"""Warehouse floor plan — the one place the warehouse coordinates come from.

Section waypoints used to be copied by hand into several files. Now everyone
(the dispatcher's "nearest robot" scoring, the panel minimap, and the
``position_parser``) reads one warehouse layout file. Edit it once.

The file (``settings.floorplan_path``) holds:
  * ``map``      — the saved SLAM map (.pgm + .yaml) the minimap draws.
  * ``dock``     — the AGV's home pose.
  * ``sections`` — storage sections (A–D) with a navigation pose each.
  * ``named_places`` — non-inventory destinations (dock / charging / qc / packing).

Everything is in the **warehouse map frame** (metres), the same frame the AGV's
heartbeat pose and the SLAM map live in, so no recalibration is needed.
"""

import json
import math
from functools import lru_cache
from pathlib import Path

from ..config import REPO_ROOT, settings


@lru_cache
def path() -> Path:
    """The active layout file (relative settings resolve from the repo root)."""
    p = Path(settings.floorplan_path)
    return p if p.is_absolute() else REPO_ROOT / p


@lru_cache
def _raw() -> dict:
    return json.loads(path().read_text(encoding="utf-8"))


@lru_cache
def map_dir() -> Path:
    """Directory holding the SLAM map (.pgm + .yaml) the minimap draws."""
    m = _raw()["map"]
    real = REPO_ROOT / m["dir"]
    if (real / m["image"]).exists() and (real / m["yaml"]).exists():
        return real
    return REPO_ROOT / m["fallback_dir"]


@lru_cache
def map_files() -> tuple[Path, Path]:
    """(.pgm, .yaml) of whichever map map_dir() resolved to."""
    m = _raw()["map"]
    d = map_dir()
    return d / m["image"], d / m["yaml"]


@lru_cache
def dock_pos() -> tuple[float, float]:
    a = _raw()["dock"]["approach"]
    return (float(a["x"]), float(a["y"]))


@lru_cache
def dock_pose() -> dict:
    """Full dock pose (x, y, yaw_rad) for Nav2 goal construction."""
    a = _raw()["dock"]["approach"]
    yaw = math.radians(float(a.get("yaw_deg", 0.0)))
    return {"x": float(a["x"]), "y": float(a["y"]), "yaw": yaw}


def _pose(d: dict) -> dict:
    p = d["pose"]
    return {
        "x": float(p["x"]),
        "y": float(p["y"]),
        "yaw": math.radians(float(p.get("yaw_deg", 0.0))),
    }


@lru_cache
def section_poses() -> dict[str, dict]:
    """Storage sections keyed by their id (``"A"`` …), each with name/contains/pose."""
    out: dict[str, dict] = {}
    for s in _raw().get("sections", []):
        out[s["id"]] = {
            "id": s["id"],
            "name": s.get("name", f"Khu {s['id']}"),
            "contains": s.get("contains", ""),
            **_pose(s),
        }
    return out


@lru_cache
def named_place_poses() -> dict[str, dict]:
    """Named, non-inventory destinations (dock / charging / qc / packing) keyed by key."""
    out: dict[str, dict] = {}
    for key, val in _raw().get("named_places", {}).items():
        out[key] = {"id": key, "name": val.get("name", key), **_pose(val)}
    return out


@lru_cache
def label_index() -> dict[str, dict]:
    """Lowercased Vietnamese label → pose entry, for spoken "dẫn tôi đến Cầu cảng" matches."""
    idx: dict[str, dict] = {}
    for entry in {**named_place_poses(), **section_poses()}.values():
        label = (entry.get("name") or "").strip().lower()
        if label:
            idx[label] = entry
    return idx


def all_targets() -> dict[str, dict]:
    """Every navigable target (sections + named places) keyed by id/key."""
    return {**section_poses(), **named_place_poses()}
