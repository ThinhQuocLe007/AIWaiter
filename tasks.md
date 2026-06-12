# Payment — Table-based Payment Tools

## Goal: Tools resolve everything from `table_id` — no `session_id` needed in tool args

```
Customer says "Tính tiền" (table T1)
  → payment_worker runs, injects table context
  → LLM calls request_payment(table_id="T1")
  → tool resolves active session + calculates total internally
  → returns QR + amount + message
  → schedule_mock_verify → auto-complete after 5s
```

## Schemas

### `schemas/payment.py` (modify)

- [x] `PaymentRequest(BaseModel)`: `table_id: str` (no `session_id`, no `amount`)
- [x] `PaymentResponse(BaseModel)`: `status`, `table_id`, `session_id`, `qr_url`, `amount`, `message`
- [x] `VerifyPaymentResponse(BaseModel)`: `status`, `table_id`, `message`

### `schemas/order.py` (revert)

- [x] Remove `session_id` from `ConfirmOrderResponse` (not needed, LLM doesn't need it)

### `schemas/__init__.py`

- [x] Update exports

## State & Graph (revert)

### `agent/state.py`

- [x] Remove `session_id` field (unnecessary)

### `agent/graph.py`

- [x] Remove `session_id` capture from `state_updater_node` (was never added)
- [x] Fix `_route_after_validator` for payment worker

## Tools

### `agent/tools/request_payment.py`

- [x] `@tool(args_schema=PaymentRequest)` with `table_id: str`
- [x] Resolve active session: `db.get_active_session(table_id)`
- [x] Calculate total: `db.get_orders_by_session(session_id)` → sum prices
- [x] Generate QR + schedule mock verify
- [x] Return `PaymentResponse` with `table_id`, `session_id`, `qr_url`, `amount`

### `agent/tools/verify_payment.py`

- [x] `@tool` with `table_id: str`
- [x] Resolve active session → get payment → check/update status
- [x] Return `VerifyPaymentResponse` with `table_id`

### `agent/nodes/deterministic_validator_node.py`

- [x] Revert to `table_id` check (from `session_id`)

### `agent/tools/confirm_order.py`

- [x] Remove `session_id` from return (not needed by LLM)

## Payment Worker Node

### System prompt — `payment_worker_agent.md`

- [x] Update tool descriptions to use `table_id` instead of `session_id`

### Node — `payment_worker_node.py`

- [x] Simplify context: just pass `table_id` (no session_id lookup needed)
- [x] Keep `request_payment` + `verify_payment` bound

## Verify

- [ ] Run existing tests
- [ ] Manual: `request_payment(table_id="T1")` → resolves session, QR, auto-verify
