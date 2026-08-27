"""Warehouse layout API — for the operator panel minimap.

The minimap draws the **saved SLAM map** (warehouse_lidar.*) as the backdrop and
overlays the storage sections, named places and the live AGV on top. Everything
is in the **warehouse map frame**: the section/named-place waypoints (from the
shared layout file the AGV itself navigates by — services/floorplan.py) and the
AGV's heartbeat pose are all in that frame, which is exactly the frame the SLAM
map's YAML maps to image pixels — so the overlay lines up without recalibration.

Frame → pixel transform (the frontend does the same with the metadata below):
    px = (x - origin_x) / resolution
    py = height_px - (y - origin_y) / resolution      # image y grows downward
"""

import io
import math

from fastapi import APIRouter, Response
from PIL import Image, ImageDraw

from ..services import floorplan

router = APIRouter(tags=["layout"])


def _map_meta() -> dict:
    pgm, yaml_path = floorplan.map_files()
    try:
        import yaml

        with open(yaml_path, encoding="utf-8") as f:
            meta = yaml.safe_load(f)
        with Image.open(pgm) as img:
            width, height = img.size
        return {
            "image_url": "/layout/map.png",
            "resolution": float(meta["resolution"]),
            "origin": [float(meta["origin"][0]), float(meta["origin"][1])],
            "width_px": width,
            "height_px": height,
        }
    except Exception:
        # No SLAM map checked in (it lives in the robot / Gazebo workspace, not the repo). Serve a
        # synthetic meta sized to the known targets so the minimap still plots real section poses
        # instead of 500-ing the whole endpoint.
        return _synthetic_meta()


def _synthetic_meta() -> dict:
    """A placeholder map frame sized to the known targets, so poses → pixels still line up."""
    res = 0.05
    margin = 2.0
    pts = [(t["x"], t["y"]) for t in floorplan.all_targets().values()]
    dock = floorplan.dock_pose()
    pts.append((dock["x"], dock["y"]))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs) - margin, max(xs) + margin
    min_y, max_y = min(ys) - margin, max(ys) + margin
    return {
        "image_url": "/layout/map.png",  # backend draws a synthetic map when the real one is absent
        "resolution": res,
        "origin": [min_x, min_y],
        "width_px": max(1, math.ceil((max_x - min_x) / res)),
        "height_px": max(1, math.ceil((max_y - min_y) / res)),
    }


def _draw_synthetic_map() -> Image.Image:
    """Draw a warehouse-looking backdrop (walls + grid + a box per target) when the real SLAM map
    is absent. Sized with the same synthetic meta the layout endpoint returns, so the section dots
    the minimap overlays line up with the boxes drawn here."""
    meta = _map_meta()
    res = meta["resolution"]
    ox, oy = meta["origin"]
    W, H = meta["width_px"], meta["height_px"]
    img = Image.new("RGB", (W, H), (18, 24, 38))
    d = ImageDraw.Draw(img)
    step = max(1, int(1.0 / res))  # 1 m grid
    for x in range(0, W, step):
        d.line([(x, 0), (x, H)], fill=(28, 36, 56), width=1)
    for y in range(0, H, step):
        d.line([(0, y), (W, y)], fill=(28, 36, 56), width=1)
    d.rectangle([3, 3, W - 4, H - 4], outline=(90, 105, 130), width=3)
    r = max(6, int(0.9 / res))

    def px(x: float, y: float) -> tuple[float, float]:
        return ((x - ox) / res, H - (y - oy) / res)

    for t in floorplan.all_targets().values():
        cx, cy = px(t["x"], t["y"])
        d.rectangle([cx - r, cy - r, cx + r, cy + r], outline=(120, 140, 170), width=2, fill=(30, 40, 62))
    return img


@router.get("/layout")
def get_layout() -> dict:
    targets = []
    for entry in floorplan.all_targets().values():
        targets.append(
            {
                "id": entry.get("id"),
                "name": entry.get("name", entry.get("id")),
                "x": entry["x"],
                "y": entry["y"],
                "yaw": entry["yaw"],
            }
        )
    return {"map": _map_meta(), "dock": floorplan.dock_pose(), "targets": targets}


@router.get("/layout/map.png")
def get_map_png() -> Response:
    """Serve the SLAM map as a PNG (the panel/minitor minimap backdrop). When the real map is
    absent (it lives on the robot / Gazebo workspace), draw a synthetic warehouse map instead."""
    pgm, _ = floorplan.map_files()
    try:
        img = Image.open(pgm).convert("RGB")
    except Exception:
        img = _draw_synthetic_map()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
