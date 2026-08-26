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

from fastapi import APIRouter, Response
from PIL import Image

from ..services import floorplan

router = APIRouter(tags=["layout"])


def _map_meta() -> dict:
    pgm, yaml_path = floorplan.map_files()
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
    """Serve the SLAM map as a PNG (the panel minimap backdrop)."""
    pgm, _ = floorplan.map_files()
    img = Image.open(pgm).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
