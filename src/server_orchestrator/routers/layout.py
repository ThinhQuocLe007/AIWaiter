"""Floor-plan layout + SLAM map API — for the panel minimap.

The minimap draws the **real saved SLAM map** (restaurant.pgm) as the backdrop and overlays the
tables and the live robot on top. Everything is in the **saved SLAM map frame**: the table
waypoints (from the shared floorplan file the robot itself navigates by — services/floorplan.py)
and the robot's heartbeat pose are all in that frame, which is exactly the frame restaurant.yaml
maps to image pixels — so the overlay lines up with the scanned walls without any recalibration.

Which map file is served is decided by floorplan.map_files(): the real restaurant map once it has
been recorded, otherwise the sim map as a stand-in.

Frame → pixel transform (the frontend does the same with the metadata from GET /layout):
    px = (x - origin_x) / resolution
    py = height_px - (y - origin_y) / resolution      # image y grows downward
"""

from functools import lru_cache
from io import BytesIO

from fastapi import APIRouter, Response
from PIL import Image

from ..services import floorplan
from ..services.dispatcher import DOCK_POS, TABLE_HEADING, TABLE_MARKER_POS

router = APIRouter(tags=["layout"])

TABLE_SIZE = 0.7  # metres, square footprint drawn at each table

# The icon is anchored at the table's ArUco marker (TABLE_MARKER_POS — the marker hangs at the
# table itself), then pushed a little further along the robot's approach heading so the square
# is centred on the table body just beyond the marker rather than on the marker post.
TABLE_EDGE_OFFSET = 0.35  # metres past the marker, along the approach heading


@lru_cache
def _map_png() -> bytes:
    """The SLAM occupancy map (.pgm) re-encoded as PNG so a browser can render it. Cached."""
    pgm, _ = floorplan.map_files()
    buf = BytesIO()
    Image.open(pgm).convert("L").save(buf, format="PNG")
    return buf.getvalue()


@lru_cache
def _map_meta() -> dict:
    """Map image size (from the PGM) + resolution/origin (from the YAML sidecar)."""
    pgm, yaml_path = floorplan.map_files()
    with Image.open(pgm) as img:
        width, height = img.size
    resolution, origin_x, origin_y = 0.05, -1.12, -5.96  # fallbacks = restaurant.yaml defaults
    for line in yaml_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("resolution:"):
            resolution = float(line.split(":", 1)[1])
        elif line.startswith("origin:"):
            nums = line.split("[", 1)[1].split("]", 1)[0].split(",")
            origin_x, origin_y = float(nums[0]), float(nums[1])
    return {
        "image_url": "/map/image.png",
        "width": width,
        "height": height,
        "resolution": resolution,
        "origin_x": origin_x,
        "origin_y": origin_y,
    }


@router.get("/map/image.png")
def map_image() -> Response:
    """Serve the SLAM map as PNG (browsers can't render the raw .pgm)."""
    return Response(content=_map_png(), media_type="image/png")


@router.get("/layout")
def get_layout() -> dict:
    """SLAM map metadata + table/dock positions (map frame, metres) for the minimap."""
    tables = []
    for tid, (x, y) in sorted(TABLE_MARKER_POS.items()):
        hx, hy = TABLE_HEADING.get(tid, (0.0, 0.0))
        tables.append({
            "id": tid,
            "x": x + hx * TABLE_EDGE_OFFSET,
            "y": y + hy * TABLE_EDGE_OFFSET,
            "w": TABLE_SIZE,
            "h": TABLE_SIZE,
        })
    return {
        "map": _map_meta(),
        "tables": tables,
        "dock": {"x": DOCK_POS[0], "y": DOCK_POS[1]},
    }
