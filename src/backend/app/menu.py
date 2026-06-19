"""Menu loading + seeding.

The canonical menu lives in assets/data/menu.json (shared with the customer UI and the RAG
pipeline). GET /menu returns it verbatim so the existing frontend adapter (menuAdapter.ts) can
keep doing the display-shaping client-side — Bước 1 just swaps its static import for this fetch.

We also seed the `dishes` table from the same file so future orders can FK to a dish row.
"""

import json
from functools import lru_cache

from .config import settings
from .db import get_conn


@lru_cache(maxsize=1)
def load_menu() -> list[dict]:
    """Raw menu items as stored in menu.json (cached for the process lifetime)."""
    with open(settings.menu_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {settings.menu_path}")
    return data


def seed_dishes() -> int:
    """Populate the dishes table from menu.json if it is empty. Returns row count."""
    items = load_menu()
    with get_conn() as conn:
        (count,) = conn.execute("SELECT COUNT(*) FROM dishes").fetchone()
        if count == 0:
            conn.executemany(
                "INSERT INTO dishes (name, price, category, available) VALUES (?, ?, ?, 1)",
                [(it["name"], float(it["price"]), it.get("category")) for it in items],
            )
        (total,) = conn.execute("SELECT COUNT(*) FROM dishes").fetchone()
    return total
