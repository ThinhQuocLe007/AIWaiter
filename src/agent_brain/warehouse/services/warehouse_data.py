"""Warehouse data access (static, demo-grade).

In-memory load of ``data/inventory.csv``. The public methods are the **stable interface** the
agent tools/workers call. For the demo there is no live DB — this is the single source of truth.

The RAG index only *resolves* a spoken item name to a canonical record; facts (stock, supplier,
handling, …) come from here. ``position_token`` is the **section** only (e.g. "A") — another team
maps the section to real coordinates; the brain never emits geometry.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from src.agent_brain.warehouse.paths import inventory_path


@dataclass
class Item:
    item: str
    sku: str
    section: str
    aisle: str
    bin: str
    quantity: float
    unit: str
    desc: str
    category: str = ""
    supplier: str = ""
    min_stock: float = 0.0
    handling: str = ""
    last_received: str = ""
    barcode: str = ""

    @property
    def position_token(self) -> str:
        """Section label the edge consumes (e.g. "A"). Geometry is the other team's job."""
        return self.section


class WarehouseData:
    def __init__(self, path: Path | None = None):
        self._path = Path(path) if path else inventory_path()
        self._by_name: dict[str, Item] = {}
        self._by_sku: dict[str, Item] = {}
        self._by_barcode: dict[str, Item] = {}

    def reload(self) -> None:
        """(Re)load the source."""
        by_name: dict[str, Item] = {}
        by_sku: dict[str, Item] = {}
        by_barcode: dict[str, Item] = {}
        with self._path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if not (row.get("item") or "").strip():
                    continue
                item = Item(
                    item=row["item"].strip(),
                    sku=(row.get("sku") or "").strip(),
                    section=(row.get("section") or "").strip(),
                    aisle=(row.get("aisle") or "").strip(),
                    bin=(row.get("bin") or "").strip(),
                    quantity=_to_float(row.get("quantity")),
                    unit=(row.get("unit") or "").strip(),
                    desc=(row.get("desc") or "").strip(),
                    category=(row.get("category") or "").strip(),
                    supplier=(row.get("supplier") or "").strip(),
                    min_stock=_to_float(row.get("min_stock")),
                    handling=(row.get("handling") or "").strip(),
                    last_received=(row.get("last_received") or "").strip(),
                    barcode=(row.get("barcode") or "").strip(),
                )
                by_name[item.item.lower()] = item
                if item.sku:
                    by_sku[item.sku.lower()] = item
                if item.barcode:
                    by_barcode[item.barcode.lower()] = item
        self._by_name = by_name
        self._by_sku = by_sku
        self._by_barcode = by_barcode

    # ── Fetch API (the agent calls these) ─────────────────────────────────────
    def get_item_by_name(self, name: str) -> Item | None:
        return self._by_name.get(name.strip().lower())

    def get_item_by_sku(self, sku: str) -> Item | None:
        return self._by_sku.get(sku.strip().lower())

    def get_item_by_barcode(self, barcode: str) -> Item | None:
        return self._by_barcode.get(barcode.strip().lower())

    def get_stock(self, sku: str) -> float | None:
        item = self.get_item_by_sku(sku)
        return item.quantity if item else None

    def get_location(self, sku: str) -> dict | None:
        item = self.get_item_by_sku(sku)
        return {"section": item.section, "aisle": item.aisle, "bin": item.bin} if item else None

    def search(self, query: str, limit: int = 5) -> list[Item]:
        q = query.strip().lower()
        hits = [
            it
            for it in self._by_name.values()
            if q in it.item.lower()
            or q in it.desc.lower()
            or q in it.category.lower()
            or q in it.supplier.lower()
        ]
        return hits[:limit]

    def all_items(self) -> list[Item]:
        return list(self._by_name.values())

    @classmethod
    def from_csv(cls, path: str | Path) -> "WarehouseData":
        inst = cls(Path(path))
        inst.reload()
        return inst


def _to_float(value: str | None) -> float:
    try:
        return float((value or "0").replace(",", "."))
    except ValueError:
        return 0.0
