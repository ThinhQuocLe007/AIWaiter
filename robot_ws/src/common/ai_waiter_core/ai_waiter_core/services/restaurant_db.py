import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from ai_waiter_core.config import settings
from ai_waiter_core.utils import logger


class RestaurantDB:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or settings.RESTAURANT_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'CONFIRMED',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    special_requests TEXT,
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    qr_url TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            ''')

            conn.commit()
            conn.close()
            logger.info("Restaurant Database initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Restaurant DB: {e}")
            raise

    # ── Sessions ──────────────────────────────────────────────

    def create_session(self, table_id: str) -> Optional[int]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
                INSERT INTO sessions (table_id, started_at)
                VALUES (?, ?)
            ''', (table_id, now))

            session_id = cursor.lastrowid
            conn.commit()
            conn.close()
            logger.info(f"Session #{session_id} started for Table {table_id}")
            return session_id
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None

    def close_session(self, session_id: int) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
                UPDATE sessions SET status = 'CLOSED', ended_at = ? WHERE id = ?
            ''', (now, session_id))

            updated = cursor.rowcount > 0
            conn.commit()
            conn.close()

            if updated:
                logger.info(f"Session #{session_id} closed")
            return updated
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def get_active_session(self, table_id: str) -> Optional[Dict[str, Any]]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM sessions WHERE table_id = ? AND status = 'ACTIVE' ORDER BY id DESC LIMIT 1
            ''', (table_id,))

            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None

    # ── Orders ────────────────────────────────────────────────

    def create_order(self, session_id: int) -> Optional[int]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
                INSERT INTO orders (session_id, created_at)
                VALUES (?, ?)
            ''', (session_id, now))

            order_id = cursor.lastrowid
            conn.commit()
            conn.close()
            logger.info(f"Order #{order_id} created for Session #{session_id}")
            return order_id
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None

    def add_items_to_order(self, order_id: int, items: List[dict]) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for item in items:
                cursor.execute('''
                    INSERT INTO order_items (order_id, name, quantity, unit_price, special_requests)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    order_id,
                    item['name'],
                    item['quantity'],
                    item.get('unit_price', 0.0),
                    item.get('special_requests')
                ))

            conn.commit()
            conn.close()
            logger.info(f"{len(items)} items added to Order #{order_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False

    def get_orders_by_session(self, session_id: int) -> List[Dict[str, Any]]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM orders WHERE session_id = ? ORDER BY created_at DESC', (session_id,))
            order_rows = cursor.fetchall()

            results = []
            for order_row in order_rows:
                cursor.execute('SELECT * FROM order_items WHERE order_id = ?', (order_row["id"],))
                item_rows = cursor.fetchall()
                items_data = [dict(item) for item in item_rows]
                total_price = sum(it["quantity"] * it["unit_price"] for it in items_data)
                results.append({
                    "id": order_row["id"],
                    "session_id": order_row["session_id"],
                    "total_price": total_price,
                    "status": order_row["status"],
                    "created_at": order_row["created_at"],
                    "items": items_data
                })

            conn.close()
            return results
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return []

    # ── Payments ──────────────────────────────────────────────

    def add_payment(self, session_id: int, amount: float, qr_url: str) -> Optional[int]:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute('''
                INSERT INTO payments (session_id, amount, qr_url, created_at)
                VALUES (?, ?, ?, ?)
            ''', (session_id, amount, qr_url, now))

            payment_id = cursor.lastrowid
            conn.commit()
            conn.close()
            logger.info(f"Payment #{payment_id} recorded for Session #{session_id}: {amount} VND")
            return payment_id
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None

    def get_payment(self, session_id: int) -> Optional[Dict[str, Any]]:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM payments WHERE session_id = ? ORDER BY id DESC LIMIT 1', (session_id,))
            row = cursor.fetchone()

            conn.close()
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return None

    def update_payment_status(self, session_id: int, status: str) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if status == "COMPLETED":
                cursor.execute('''
                    UPDATE payments SET status = ?, completed_at = ? WHERE session_id = ?
                ''', (status, now, session_id))
                self.close_session(session_id)
            else:
                cursor.execute('''
                    UPDATE payments SET status = ? WHERE session_id = ?
                ''', (status, session_id))

            updated = cursor.rowcount > 0
            conn.commit()
            conn.close()

            if updated:
                logger.info(f"Payment for Session #{session_id} updated to {status}")
            return updated
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            return False
