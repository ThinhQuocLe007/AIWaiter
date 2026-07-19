# Unified Restaurant Database & Payment System Design

## Overview

Consolidate order and payment data into a single `restaurant.db` SQLite database with three normalized tables: `orders`, `order_items`, and `payments`. Replace the current `order_db.py` (which stores items as a JSON blob) with a `restaurant_db.py` that parses items into individual rows and tracks payment lifecycle.

---

## Architecture

```
Schema → Service → Tool  (three-layer pattern)
```

### Layer 1: Schemas (`schemas/`)

```python
class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class PaymentRecord(BaseModel):
    id: int
    table_id: str
    amount: int
    status: PaymentStatus
    qr_url: str | None
    created_at: str
    completed_at: str | None

class PaymentResponse(BaseModel):
    status: Literal["success", "error"]
    qr_url: str | None
    amount: int | None
    message: str
```

`PaymentRecord` represents a database row (returned when querying). `PaymentResponse` is the tool return type (keep existing).

### Layer 2: Services (`services/`)

#### `restaurant_db.py` (replaces `order_db.py`)

Three tables:

```sql
orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id TEXT NOT NULL,
    total_price REAL NOT NULL,
    status TEXT DEFAULT 'CONFIRMED',
    created_at TEXT NOT NULL
)

order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    special_requests TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(id)
)

payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT DEFAULT 'PENDING',       -- PENDING | COMPLETED | FAILED
    qr_url TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
)
```

Key methods:

| Method | Description |
|---|---|
| `add_order(table_id, items, total_price)` | Insert order header + parse items into order_item rows |
| `get_order(order_id)` | Return order with nested items |
| `get_orders_by_table(table_id)` | List all orders for a table |
| `add_payment(table_id, amount, qr_url)` | Record a PENDING payment |
| `update_payment_status(payment_id, status)` | Complete/fail a payment |
| `get_payment_by_id(payment_id)` | Get single payment record |
| `get_payments_by_table(table_id)` | Payment history for a table |

The `add_order` method parses the `items` list (e.g., 3 dishes) into separate `order_items` rows with `unit_price` snapshot at order time.

#### `payment_mgr.py` (keep pure, no DB dependency)

| Method | Description |
|---|---|
| `generate_qr(table_id, amount)` | Generate VietQR image URL (existing) |
| `supported_methods()` | Return `["bank_transfer", "cash"]` |

### Layer 3: Tools (`agent/tools/`)

#### `request_payment.py` (updated flow)

```
request_payment(table_id, amount)
    |
    v
PaymentManager.generate_qr(table_id, amount)  → QR URL
    |
    v
RestaurantDB.add_payment(table_id, amount, qr_url)  → payment_id
    |
    v
Return PaymentResponse(qr_url, amount, status="success")
```

#### New tool: `verify_payment.py`

```
verify_payment(payment_id)
    |
    v
RestaurantDB.update_payment_status(payment_id, "COMPLETED")
    |
    v
Return VerifyPaymentResponse(status="success", message="...")
```

---

## Payment Lifecycle

### Agent State

Add `PaymentStage` to agent state alongside `OrderStage`:

```python
PaymentStage = Literal["NONE", "PENDING", "COMPLETED"]
```

### Flow

```
User: "Thanh toán đơn hàng"
    │
    ├── Router → intent: PAYMENT
    │
    ├── payment_worker_node
    │     └── LLM calls request_payment(table_id, amount)
    │           ├── PaymentManager.generate_qr() → URL
    │           ├── RestaurantDB.add_payment()  → payment_id
    │           └── returns PaymentResponse(qr_url)
    │
    ├── Agent replies: "Mời quét mã QR"
    │   payment_stage → PENDING
    │
    └── User: "Tôi đã thanh toán xong"
          │
          ├── Router → intent: PAYMENT
          ├── payment_worker_node
          │     └── LLM calls verify_payment(mock_payment_id)
          │           ├── RestaurantDB.update_payment_status(id, "COMPLETED")
          │           └── returns VerifyPaymentResponse(status="success")
          │
          └── Agent replies: "Cảm ơn, thanh toán thành công!"
              payment_stage → COMPLETED
```

Verification is simulated (no real gateway). In production, replace with a bank webhook / callback.

---

## Data Relationships

```
orders (1) ──< order_items (N)
  │
  └── (no direct FK to payments, but both reference table_id)
           │
     payments (by table_id, not by order_id)
```

Payments are linked by `table_id` rather than `order_id` for simplicity. A table can have multiple orders and multiple payments.

---

## Files to Create / Modify

| Action | File |
|---|---|
| MODIFY | `schemas/payment.py` — add `PaymentStatus` enum, `PaymentRecord` model |
| CREATE | `services/restaurant_db.py` — RestaurantDB class with 3 tables |
| DELETE | `services/order_db.py` — replaced by restaurant_db.py |
| KEEP | `services/payment_mgr.py` — unchanged, pure QR generation |
| MODIFY | `agent/tools/request_payment.py` — inject RestaurantDB.add_payment |
| CREATE | `agent/tools/verify_payment.py` — new tool for simulated verification |
| MODIFY | `agent/tools/__init__.py` — add verify_payment to CORE_TOOLS |
| MODIFY | `config/database_config.py` — ORDER_DB_PATH → RESTAURANT_DB_PATH |
| MODIFY | `scripts/setup.py` — update import to RestaurantDB |

---

## Verification (Capstone vs Production)

| Phase | Mechanism |
|---|---|
| **Capstone (simulated)** | Agent-driven: user says "đã thanh toán xong" → `verify_payment` tool → marks COMPLETED |
| **Production (real)** | Bank webhook → callback endpoint → `RestaurantDB.update_payment_status()` |
