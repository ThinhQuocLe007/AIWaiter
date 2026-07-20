# AI Waiter — Code Review Issues

**Date**: 2026-07-20
**Scope**: Full codebase review (agent_brain, server_orchestrator, edge_voice, frontends, _shared, training_semantic_router)

---

## Critical

### 1. Classifier router hard import crashes agent on missing model
- **File**: `src/agent_brain/agent/nodes/classifier_router_node.py:30`
- **Problem**: `from src.training_semantic_router.classifier.predict import classify` runs at module import time. If `model.pt` is missing/corrupt or the training module isn't installed, the entire agent service fails to start. The `_safe_classify()` wrapper only guards inference time, not import time.
- **Fix**: Lazy-import inside `_safe_classify()`:
```python
def _safe_classify(...):
    try:
        from src.training_semantic_router.classifier.predict import classify
        return _classify_one(...)
    except Exception:
        ...
```

### 2. Connection manager fails to clean up robot/voice registries on disconnect
- **File**: `src/server_orchestrator/realtime/connection_manager.py:68-69, 80-81, 118-119`
- **Problem**: Three related bugs:
  - `broadcast()` calls `self.disconnect(ws, role)` when a socket fails, but `robot_id` defaults to `None`. Robot/voice-device sockets are removed from `_by_role` but **stay** in `_robots` / `_voice_devices`.
  - `send_to_robot()` pops the stale entry from `_robots` on exception but never calls `disconnect()`, so the stale socket stays in `_by_role['robot']`.
  - Same pattern in `send_to_voice_device()`.
- **Fix**: Accept `robot_id`/`device_id` in `disconnect()` and call it from all three codepaths.

---

## High

### 3. Admin reset endpoint has no authentication
- **File**: `src/server_orchestrator/routers/admin.py:19`
- **Problem**: `POST /admin/reset` wipes all orders, payments, tasks, and seatings. Unauthenticated — any network client can destroy restaurant state.
- **Fix**: Add a shared-secret header check or env guard (`ALLOW_ADMIN_RESET=true`).

### 4. SQLite checkpointer without WAL mode — concurrent write collisions
- **File**: `src/agent_brain/agent/memory/checkpointer.py:10-13`
- **Problem**: `sqlite3.connect(db_path, check_same_thread=False)` without journal mode or busy timeout. LangGraph writes from multiple FastAPI threadpool threads. Two concurrent table requests will hit `database is locked`.
- **Fix**:
```python
conn = sqlite3.connect(db_path, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
```

### 5. confirm_order sends 0đ items to backend when menu_manager returns 0.0
- **File**: `src/agent_brain/agent/tools/confirm_order.py:30`
- **Problem**: `menu_manager.get_price(item.name)` returns `0.0` for unknown items. If the validator has a bug (e.g., a new menu item not yet in MenuManager), a 0đ order reaches the backend, gets persisted, and shows in the kitchen panel.
- **Fix**: Reject items with `price == 0.0`:
```python
price = menu_manager.get_price(item.name)
if price == 0.0:
    raise ValueError(f"Item '{item.name}' not found in menu — validator should have caught this")
```

---

## Medium

### 6. ThreadPoolExecutor leaked for process lifetime in RetrieverManager
- **File**: `src/agent_brain/services/retriever/hybrid_retriever.py:15`
- **Problem**: `self.executor = ThreadPoolExecutor(max_workers=2)` is created once and never shut down. If `RetrieverManager` is ever re-instantiated, additional threads leak.
- **Fix**: Add a `cleanup()` method or `__del__` with `executor.shutdown(wait=False)`.

### 7. SSE streaming leaks thread-local queue on client disconnect
- **File**: `src/agent_brain/server.py:189-259`, `src/agent_brain/agent/nodes/response_node.py`
- **Problem**: `set_output_queue(q)` at line 190 sets a thread-local queue. If the SSE client disconnects mid-stream, the generator is abandoned and `set_output_queue(None)` at line 229 is never called. The next request on that thread inherits a stale queue, sending sentences to the wrong client.
- **Fix**: Wrap the generator body in `try/finally` with `set_output_queue(None)` in the finally block.

### 8. Edge voice SSE generator leaks ThreadPoolExecutor on disconnect
- **File**: `src/edge_voice/main.py:206-231`
- **Problem**: Same pattern as #7. `ThreadPoolExecutor` created at line 206, shutdown at line 231. Client disconnect mid-stream → executor leaks → LLM thread runs orphaned.
- **Fix**: Use `with ThreadPoolExecutor(...) as ex:` inside try/finally.

### 9. Edge voice load_dotenv with relative path
- **File**: `src/edge_voice/main.py:46`
- **Problem**: `load_dotenv()` resolves `.env` against CWD. If `main.py` is run from a different directory (common on Jetson autostart), env vars fall back to hardcoded defaults.
- **Fix**: `load_dotenv(Path(__file__).resolve().parents[2] / ".env")`.

### 10. Data race on VAD state in TTS thread
- **File**: `src/edge_voice/output/tts_engine.py:141`
- **Problem**: `player.play_sentence()` in the TTS playback thread reads `self._vad.is_speaking()`, which reads `len(self._current_utterance)`. The VAD thread writes `_current_utterance` concurrently. No lock — classic data race.
- **Fix**: Use a `threading.Event` flag on the VAD thread: `self._customer_speaking = threading.Event()`. TTS thread checks `is_set()`.

### 11. Cross-call transactions broken — separate DB connections per call
- **File**: `src/server_orchestrator/data/db.py:138-149`
- **Problem**: `get_conn()` returns a new `sqlite3.Connection` per call. `create_order()` → `create_task()` → `try_assign_robot()` each call `get_conn()` separately. If `create_order` succeeds but `try_assign_robot` fails, the order is persisted without a robot assignment. The reverse is also possible — a task gets assigned without a valid order.
- **Fix**: Either pass a connection down the call chain, or document that each operation is an independent micro-transaction.

### 12. Missing prompt file crashes graph invocation with 500
- **File**: `src/agent_brain/utils/prompt_utils.py:43`
- **Problem**: `load_prompt()` raises `FileNotFoundError` if a system prompt `.md` file is deleted. This propagates uncaught through the graph node → LangGraph → endpoint → 500 to the client.
- **Fix**: Validate all prompts exist at startup (`_warmup`). Return a safe fallback string if a prompt is missing at runtime.

### 13. DROP TABLE payments in migration silently destroys data
- **File**: `src/server_orchestrator/data/db.py:170-178`
- **Problem**: `_migrate_payments_to_session()` does `conn.execute("DROP TABLE payments")` when old schema detected. All payment records lost. No warning logged, no backup created.
- **Fix**: At minimum log a warning with the row count. Optionally rename to `payments_legacy` instead of dropping.

### 14. Python hash() as document ID in RRF fusion
- **File**: `src/agent_brain/services/retriever/fusion/rrf.py:57`
- **Problem**: `doc_id = hash(doc.page_content)` — Python's `hash()` is randomized per-process via `PYTHONHASHSEED`. Works fine within one search call (dedup-by-content), but if fusion results were ever cached across queries, IDs would mismatch.
- **Fix**: Use `doc.metadata.get("name")` or a deterministic content hash (hashlib).

### 15. Circuit breaker doesn't reset order_stage
- **File**: `src/agent_brain/agent/nodes/deterministic_validator_node.py:350-351`
- **Problem**: After 3 retry loops, validator returns `is_valid=False` but `order_stage` stays at its current value (e.g., `AWAITING_CONFIRMATION`). The next user turn sees the same stage with a fresh `loop_count=0` — the cycle can repeat.
- **Fix**: Reset `order_stage` to `IDLE` when the circuit breaker fires.

### 16. Dead edges on disconnected router node
- **File**: `src/agent_brain/agent/graph.py:150-166, 171-180`
- **Problem**: `START → classifier_router` is active. The old `router` node (hybrid_router_node) is still added with conditional edges, but nothing routes to it — dead code. If someone changes START back to `router`, the `classifier_router` edges become dead. Fragile rollback.
- **Fix**: Use a config flag/feature gate to choose the active router at construction time instead of keeping both wired.

### 17. Separate orchestrator DB connections prevent session cross-call integrity
- **File**: `src/server_orchestrator/data/db.py`
- **Problem**: `ensure_active_session()` and `create_order()` use separate connections. If two concurrent requests hit the same table simultaneously (voice order + tablet button), two sessions could be created for the same table.
- **Fix**: Use `INSERT OR IGNORE` with a unique constraint on `table_id` + `status = 'active'` in the sessions table, or add a row-level lock.

---

## Low

### 18. MENU_NAMES lazy proxy retries on every call if menu.json missing
- **File**: `src/agent_brain/utils/menu_utils.py:68`
- **Problem**: `_LazyMenuNames._load()` returns `[]` on file-not-found but doesn't negative-cache. Each subsequent call re-reads the missing file. Harmless but noisy in logs.
- **Fix**: Cache the empty list too, or raise clearly at first access.

### 19. Duplicated PaymentStatus enum between _shared and agent_brain
- **File**: `src/_shared/types.py:44-47` vs `src/agent_brain/schemas/payment.py:6-9`
- **Problem**: Backend defines `PaymentStatus.PENDING | PAID`. Agent defines `PaymentStatus.PENDING | COMPLETED | FAILED`. The `verify_payment` tool compares with a string literal `"PAID"`, not the enum. If the backend changes the status string, the agent silently breaks.
- **Fix**: Use `_shared.types.PaymentStatus` everywhere. Remove the duplicate.

### 20. normalise_table_id ValueError → 500 instead of 400
- **File**: `src/_shared/types.py:91` (called from `server_orchestrator/routers/voice.py`)
- **Problem**: If a client sends a malformed table ID, `normalise_table_id` raises `ValueError` which propagates uncaught → 500.
- **Fix**: Catch `ValueError` in the API layer and return `400`.

### 21. Warmup fails silently — health endpoint reports agent_loaded: true
- **File**: `src/agent_brain/server.py:44-64, 104-106`
- **Problem**: Warmup catches all exceptions. If Ollama is down, models skip warmup but the service starts. `/health` returns `agent_loaded: true` even though no models are resident.
- **Fix**: Track which models warmed up in `/health` response. Optionally fail startup if critical models can't load.

### 22. remove_cart tool returns total_price=0.0
- **File**: `src/agent_brain/agent/tools/remove_cart.py:17-22`
- **Problem**: `CartRemoveResponse(total_price=0.0)` regardless of actual cart state. The `update_state_node` recalculates downstream, so no data corruption — just the LLM sees an inaccurate response.
- **Fix**: Compute the remaining total before returning, or remove the field.

### 23. Duplicate API_URL definition in frontend
- **File**: `src/frontends/shared/rest.ts:8` and `src/frontends/customer_ui/src/data/api.ts:8`
- **Problem**: Both files define `const API_URL = import.meta.env.VITE_API_URL ?? '/api'`. If the env var name changes, both must be updated.
- **Fix**: Export from one shared location.

### 24. bm25.py build() overwrites index before completion
- **File**: `src/agent_brain/services/retriever/indices/bm25.py:21-33`
- **Problem**: `build()` assigns `self.documents = documents` then builds `BM25Okapi`. If building fails, the index is in an inconsistent state (documents set, tokenized_docs partial, bm25 None).
- **Fix**: Build into local variables, atomically assign after success.

### 25. vector.py FAISS load_local allows dangerous deserialization
- **File**: `src/agent_brain/services/retriever/indices/vector.py:35`
- **Problem**: `allow_dangerous_deserialization=True` means a malicious FAISS index file could execute arbitrary code via pickle. The file is in `storage/vector/` — should be write-protected in production.
- **Fix**: Verify a checksum against a known hash before loading.
