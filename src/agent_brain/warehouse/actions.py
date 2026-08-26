"""Helpers to build the ChatResponse action/position contract from live item data."""

from __future__ import annotations

from src.agent_brain.warehouse.types import NavigateAction, PositionToken
from src.agent_brain.warehouse.services.warehouse_data import Item


def position_from_item(item: Item) -> PositionToken:
    return PositionToken(
        token=item.position_token,
        section=item.section or None,
        slot=item.slot or None,
        color=item.color or None,
    )


def navigate_action(item: Item) -> NavigateAction:
    return NavigateAction(position=position_from_item(item))


def item_to_dict(item: Item) -> dict:
    return {
        "item": item.item,
        "sku": item.sku,
        "section": item.section,
        "slot": item.slot,
        "color": item.color,
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
