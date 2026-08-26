"""Document loading for the FIXED corpus.

Three static sources (rebuild the index only when they change):
  - inventory items  (each row → one document, used for fuzzy item resolution)
  - warehouse sections (from data/warehouse.json, for "khu A có gì" questions)
  - SOP / FAQ markdown under data/  (optional, for "how to" questions)

Quantities/status are NOT indexed here — they come live from `warehouse_data`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.agent_brain.warehouse.colors import vi as color_vi
from src.agent_brain.warehouse.paths import ROOT, settings
from src.agent_brain.warehouse.services.warehouse_data import WarehouseData
from src.agent_brain.warehouse.services import warehouse_info


@dataclass
class Doc:
    text: str
    meta: dict = field(default_factory=dict)
    tokens: list[str] = field(default_factory=list)  # whitespace tokens for BM25


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def load_inventory_docs(data: WarehouseData) -> list[Doc]:
    docs: list[Doc] = []
    for it in data.all_items():
        handling = f" Lưu ý: {it.handling}." if it.handling else ""
        text = (
            f"{it.item} ({it.sku}): {it.desc}. "
            f"Danh mục: {it.category}. Nhà cung cấp: {it.supplier}. "
            f"Vị trí: khu {it.section}, ô {it.slot}, hộp màu {color_vi(it.color)}. "
            f"Tồn kho: {it.quantity} {it.unit}. Mức tối thiểu: {it.min_stock} {it.unit}.{handling}"
        )
        docs.append(Doc(text=text, meta={"kind": "item", "sku": it.sku, "item": it.item},
                        tokens=_tokenize(text)))
    return docs


def load_section_docs() -> list[Doc]:
    docs: list[Doc] = []
    info = warehouse_info.load_warehouse_info()
    for key, val in info.get("sections", {}).items():
        text = f"Khu {key} ({val.get('name', '')}): {val.get('contains', '')}."
        docs.append(Doc(text=text, meta={"kind": "section", "section": key}, tokens=_tokenize(text)))
    for key, val in info.get("named_places", {}).items():
        text = f"{val.get('label', key)}: {val.get('desc', '')}".strip().rstrip(":")
        docs.append(Doc(text=text, meta={"kind": "named_place", "name": key},
                        tokens=_tokenize(text)))
    return docs


def load_sop_docs(data_dir: Path | None = None) -> list[Doc]:
    docs: list[Doc] = []
    base = data_dir or (ROOT / "data")
    if not base.exists():
        return docs
    for md in sorted(base.glob("*.md")):
        text = md.read_text(encoding="utf-8").strip()
        if not text:
            continue
        docs.append(Doc(text=text, meta={"kind": "sop", "source": md.name}, tokens=_tokenize(text)))
    return docs


def load_all_docs(data: WarehouseData | None = None) -> list[Doc]:
    data = data or WarehouseData()
    data.reload()
    return load_inventory_docs(data) + load_section_docs() + load_sop_docs()
