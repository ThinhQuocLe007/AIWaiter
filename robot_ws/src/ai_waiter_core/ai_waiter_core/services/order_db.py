import sqlite3
import json
import os
from datetime import datetime
from ai_waiter_core.config import settings
from ai_waiter_core.utils import logger

class OrderDB:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or settings.ORDER_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """Create the orders table if it doesn't exist. Does NOT drop existing data."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_id TEXT NOT NULL,
                    items_json TEXT NOT NULL,
                    total_price REAL NOT NULL,
                    status TEXT DEFAULT 'CONFIRMED',
                    created_at TEXT NOT NULL
                )
            ''')
            conn.commit()
            conn.close()
            logger.info("Order Database initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Order DB: {e}")
            raise
    
    def add_order(self, table_id: str, cart_dict: dict):
        """
        Save a confirmed order from a Cart dictionary.
        cart_dict['items'] will now include 'special_requests'.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute('''
                INSERT INTO orders (table_id, items_json, total_price, created_at)
                VALUES (?, ?, ?, ?)
            ''', (
                table_id, 
                json.dumps(cart_dict['items']), # Automatically includes special_requests
                cart_dict['total_price'], 
                current_time
            ))
            
            order_id = cursor.lastrowid
            conn.commit()
            conn.close()
            logger.info(f"Order #{order_id} saved for Table {table_id}")
            return order_id
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None
