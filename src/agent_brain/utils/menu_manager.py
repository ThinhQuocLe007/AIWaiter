import json
import logging
from src.agent_brain.config import settings

logger = logging.getLogger(__name__)

class MenuManager:
    """
    Centralized programmatic lookup helper.
    Exposes key-value access to menu items and prices to support math calculations.
    """
    def __init__(self):
        self.menu_map = {}
        self.load_menu()

    def load_menu(self):
        menu_path = settings.assets_dir / "data" / "menu.json"
        if not menu_path.exists():
            logger.error(f"Menu JSON file not found at {menu_path}")
            return
            
        try:
            with open(menu_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Create a clean lookup table: {"item name": price}
                self.menu_map = {item['name'].lower().strip(): float(item['price']) for item in data}
            logger.info(f"Successfully loaded {len(self.menu_map)} items into MenuManager price map.")
        except Exception as e:
            logger.exception(f"Error loading menu inside MenuManager: {e}")

    def get_price(self, item_name: str) -> float:
        """Look up the price of a menu item by its exact or case-insensitive name."""
        if not item_name:
            return 0.0
        return self.menu_map.get(item_name.lower().strip(), 0.0)
