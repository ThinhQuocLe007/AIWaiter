import json
import logging
from typing import List
from ai_waiter_core.config import settings

logger = logging.getLogger(__name__)

def get_menu_names() -> List[str]:
    """Dynamically loads menu item names from the JSON asset."""
    menu_path = settings.assets_dir / "data" / "menu.json"
    
    if not menu_path.exists():
        logger.error(f"Menu JSON file not found at {menu_path} for dynamic extraction.")
        return []
        
    try:
        with open(menu_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [item['name'] for item in data]
    except Exception as e:
        logger.error(f"Error loading menu names for schemas: {e}")
        return []

# Dynamic import-time array containing official menu items
MENU_NAMES = get_menu_names()
