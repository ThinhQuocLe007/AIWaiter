"""GET /menu — the canonical menu for the customer UI (stores/menu.ts loadMenu())."""

from fastapi import APIRouter

from ..services.menu_loader import load_menu

router = APIRouter(tags=["menu"])


@router.get("/menu")
def get_menu() -> list[dict]:
    """Raw menu items (same shape as assets/data/menu.json)."""
    return load_menu()
