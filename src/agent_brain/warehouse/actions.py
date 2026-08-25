"""Helpers to build the ChatResponse action/position contract from live item data."""

from __future__ import annotations

from src.agent_brain.warehouse.types import Action, PositionToken
from src.agent_brain.warehouse.services.warehouse_data import Item


def position_from_item(item: Item) -> PositionToken:
    return PositionToken(
        token=item.position_token,
        section=item.section or None,
        aisle=item.aisle or None,
        bin=item.bin or None,
    )


def navigate_action(item: Item) -> Action:
    return Action(type="navigate", position=position_from_item(item))


def item_to_dict(item: Item) -> dict:
    return {
        "item": item.item,
        "sku": item.sku,
        "section": item.section,
        "aisle": item.aisle,
        "bin": item.bin,
        "quantity": item.quantity,
        "unit": item.unit,
        "desc": item.desc,
        "category": item.category,
        "supplier": item.supplier,
        "min_stock": item.min_stock,
        "handling": item.handling,
        "last_received": item.last_received,
        "barcode": item.barcode,
    }
