"""Floor plan — the one place the restaurant's coordinates come from.

Table waypoints used to be copied by hand into four files (the robot's `DESTINATIONS`, the
dispatcher's `TABLE_POS`/`TABLE_MARKER_POS`/`TABLE_HEADING`, `mock_robot.py`, and the map path in
`layout.py`). Changing to the real restaurant map meant editing all of them, and forgetting one
gave a robot that drives correctly while the dispatcher picks the wrong "nearest" robot and the
minimap draws tables in the wrong place (docs/guides/jetson-nav-merge-vi.md §3.1).

Now everyone reads one floorplan file — including the robot bridge itself, which loads the very
same JSON from its ROS package share. Edit it once.

Which file is chosen is `settings.floorplan_path`: the real robot's waypoints by default, or the
sim ones (`assets/data/floorplan.sim.json`) when the Gazebo demo is what's running. Both demos
stay supported; only the backend switches, the sim robot code keeps its own constants.

Everything is in the **saved SLAM map frame** (metres), the same frame the robot's heartbeat pose
and restaurant.pgm live in, so no recalibration is needed anywhere.
"""

import json
import math
from functools import lru_cache
from pathlib import Path

from ..config import REPO_ROOT, settings


@lru_cache
def path() -> Path:
    """The active floorplan file (relative settings resolve from the repo root)."""
    p = Path(settings.floorplan_path)
    return p if p.is_absolute() else REPO_ROOT / p


@lru_cache
def _raw() -> dict:
    return json.loads(path().read_text(encoding="utf-8"))


@lru_cache
def map_dir() -> Path:
    """Directory holding the SLAM map (.pgm + .yaml) the minimap draws.

    Falls back to the sim map while the real restaurant map has not been recorded yet — the panel
    keeps working, it just shows the old floor. Drop the real .pgm + .yaml into `map.dir` and
    restart the backend to switch (the choice, like the image itself, is cached per process).
    """
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


def _tables() -> list[dict]:
    return _raw()["tables"]


@lru_cache
def dock_pos() -> tuple[float, float]:
    a = _raw()["dock"]["approach"]
    return (float(a["x"]), float(a["y"]))


@lru_cache
def table_pos() -> dict[int, tuple[float, float]]:
    """Approach waypoint per table — where the robot physically parks to serve it."""
    return {
        int(t["id"]): (float(t["approach"]["x"]), float(t["approach"]["y"]))
        for t in _tables()
    }


@lru_cache
def table_marker_pos() -> dict[int, tuple[float, float]]:
    """Where the table itself is (its ArUco marker), for drawing the minimap icon.

    Tables whose marker position has not been measured fall back to their approach waypoint —
    the icon then sits on the robot's parking spot instead of the table body, which is a small
    visual offset rather than a missing table.
    """
    out: dict[int, tuple[float, float]] = {}
    for t in _tables():
        marker = t.get("marker")
        if marker:
            out[int(t["id"])] = (float(marker["x"]), float(marker["y"]))
        else:
            out[int(t["id"])] = (float(t["approach"]["x"]), float(t["approach"]["y"]))
    return out


@lru_cache
def table_heading() -> dict[int, tuple[float, float]]:
    """Approach heading per table as a unit vector, derived from the waypoint's yaw.

    The robot faces the table when it arrives, so this vector points from the parking spot at the
    table — the minimap uses it to push the table icon out past the marker.
    """
    out: dict[int, tuple[float, float]] = {}
    for t in _tables():
        yaw = math.radians(float(t["approach"].get("yaw_deg", 0.0)))
        out[int(t["id"])] = (math.cos(yaw), math.sin(yaw))
    return out
