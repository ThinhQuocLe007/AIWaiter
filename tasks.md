# Refactor: Folder Structure — `schemas/` & `tools/`

## ✅ Completed (Router Enhancement — Softmax + Gap)
- [x] All previous router tasks — see old tasks.md for history

## 🎯 Goal

Restructure `schemas/` and `tools/` following the **Schema → Service → Tool** three-layer architecture. Replace string-based tool returns with typed Pydantic response models.

---

## 📋 Phase 1: Schemas — Add Response Models

### `schemas/payment.py` — New file
- [x] Create `schemas/payment.py` with `PaymentResponse(status, qr_url, amount, message)`

### `schemas/order.py` — Add response models
- [x] Add `SyncCartResponse(status, items, total_price, message)`
- [x] Add `ConfirmOrderResponse(status, order_id, message)`

### `schemas/search.py` — Add `SearchInput` + response model
- [x] Move `SearchMenuInput` from `tools/search/search.py` → `schemas/search.py` (rename to `SearchInput`)
- [x] Add `SearchResponse(status, results, message)`

### `schemas/__init__.py` — Update exports
- [x] Add all new response models to `__init__.py`

---

## 📋 Phase 2: Services — Extract Implementation Helpers

### Create `services/` folder
- [x] Move `tools/ordering/order_db.py` → `services/order_db.py`
- [x] Move `tools/payment/payment_mgr.py` → `services/payment_mgr.py`

### Create `services/retriever/` folder (move from `tools/search/`)
- [x] Move `tools/search/hybrid_retriever.py` → `services/retriever/hybrid_retriever.py`
- [x] Move `tools/search/indices/` → `services/retriever/indices/`
- [x] Move `tools/search/fusion/` → `services/retriever/fusion/`
- [x] Move `tools/search/loaders/` → `services/retriever/loaders/`
- [x] Move `tools/search/utils/normalization.py` → `services/retriever/normalization.py`
- [x] Inline `tools/search/utils/rrf.py` into `services/retriever/fusion/rrf.py`
- [x] Update all relative imports in moved files to absolute imports

---

## 📋 Phase 3: Tools — Flat Structure + Typed Returns

### Create flat `tools/` files
- [x] Create `tools/sync_cart.py` — refactor to return `SyncCartResponse`
- [x] Create `tools/confirm_order.py` — refactor to return `ConfirmOrderResponse`
- [x] Create `tools/search_tool.py` — refactor to return `SearchResponse`
- [x] Create `tools/request_payment.py` — refactor to return `PaymentResponse`

### Update `tools/__init__.py`
- [x] Update imports to flat file names

### Delete old tool sub-folders
- [x] Delete `tools/ordering/` (after confirming all references moved)
- [x] Delete `tools/payment/` (after confirming all references moved)
- [x] Delete `tools/search/` (after confirming all references moved)

---

## 📋 Phase 4: Graph & Nodes — Update Imports + Logic

### `graph.py`
- [x] Update `state_updater_node`: replace string parsing with `isinstance` checks on typed models
- [x] Update imports to use typed response models from schemas
- [x] Replace priority-based routing with sequential (first intent) routing
- [x] Add multi-intent loop: `_route_after_updater` pops processed intent, routes to next worker if more remain
- [x] Deduplicate `route_after_search` / `route_after_payment` → single `_route_if_tool_call`

### Worker nodes
- [x] `order_worker_node.py` — update imports (`..tools.sync_cart`, `..tools.confirm_order`)
- [x] `search_worker_node.py` — update imports (`..tools.search`)
- [x] `payment_worker_node.py` — update imports (`..tools.request_payment`)

---

## 📋 Phase 5: Database & Setup Script

### Fix `OrderDB`
- [x] Remove `DROP TABLE IF EXISTS` — data persists across restarts
- [x] Use `CREATE TABLE IF NOT EXISTS` only

### Create `scripts/setup.py`
- [x] Create directories (`storage/db/`, `storage/vector/`, etc.)
- [x] Init Order DB (no destructive drops)
- [x] Init Checkpoints DB
- [x] Build FAISS + BM25 indexes from `assets/data/`
- [x] Build centroids from `utterances.json`
- [x] Verify all required assets exist
- [x] `--force` flag to rebuild existing indexes
- [x] `--skip-centroids` flag

---

## 📋 Phase 6: Tests & Verification

- [x] Update `tests/test_modular_retriever.py` — fix import path
- [x] Update `evals/scripts/eval_retrieval.py` — fix import path
- [ ] Run: `pytest robot_ws/tests/ -v`
- [ ] Run: `python evals/scripts/eval_router.py`
- [ ] Run: `python evals/scripts/eval_retrieval.py`
- [ ] Verify E2E: `python -m pytest test/test_order_workflow.py -v`
