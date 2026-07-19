## 4.3.4 Stage III — Validation: Deterministic Safety Net

> **Status:** draft
> **Cross-refs:** §4.1.3 (NFR3), §4.3.3 for workers, §4.3.5 for tools, §5.3.2 for validator evaluation
> **Source:** `src/agent_brain/agent/nodes/deterministic_validator_node.py` (341 lines)
> **Figures needed:** Fig 4.3.4 (menu name resolution pipeline: 5-level matching cascade)

---

This stage is the key reliability contribution of the system. LLM output is probabilistic regardless of temperature — an LLM can hallucinate a dish name that does not exist on the menu, produce a nonsensical quantity, or attempt to confirm an order with invalid items. Before any LLM output becomes a system action (adding to cart, confirming an order, requesting payment), a deterministic validation layer inspects the output and rejects anything that would corrupt system state.

The validator is a pure-rules layer with no machine learning: every check is a hand-written predicate with a definitive yes/no answer. It cannot prevent the LLM from hallucinating, but it can detect hallucinated output before it reaches the cart or the backend. This architecture pattern — **LLM → validate → action, never LLM → action** — is the central safety invariant of the system (NFR3, §4.1.3).

### 4.3.4.1 Execution Context

The validator (`deterministic_validator_node.py:192`) runs **after** the worker produces a tool call but **before** the `ToolNode` executes it. This placement is deliberate: the LLM proposes actions (tool calls), but the validator inspects them first. If the validator approves (`is_valid=True`), the routing function sends the tool calls to the `ToolNode` for execution. If the validator rejects (`is_valid=False`), the tool calls never execute — instead, validation `feedback` is fed back to the worker for retry.

The validator inspects **all tool calls** in the LLM's output, not just the first one. The LLM can produce multiple tool calls in one message (e.g., `add_cart` for two items), and each is validated independently.

### 4.3.4.2 Simultaneous Add+Confirm Rejection

The first validation check is not about menu items — it is about state machine correctness (`deterministic_validator_node.py:203-221`). If the LLM emits both `add_cart` and `confirm_order` in the same turn, the `confirm_order` is stripped and an error is added to `feedback`:

> "Không thể vừa thêm món vừa xác nhận đơn trong cùng lượt. Các món chưa được thêm: [...]. Hãy gọi add_cart riêng, sau đó mới confirm_order."

**Rationale.** The cart state machine (§4.3.5.2) requires the customer to explicitly confirm after seeing the cart. If the LLM could both add items and confirm in one turn, the customer would never see what was added before the order is sent to the kitchen. This check enforces the two-step workflow: add → echo → confirm.

### 4.3.4.3 Menu Name Resolution

The core validation logic for `add_cart` and `remove_cart` tool calls is menu name resolution: determining whether the item the LLM produced actually exists on the restaurant's 217-item menu. The resolution pipeline (`resolve_menu_name` in `src/agent_brain/utils/menu_utils.py`) is a five-level cascade, from fastest/most reliable to slowest/least reliable:

| Level | Method | Example Input → Output | Latency |
|-------|--------|------------------------|---------|
| 1. Exact match | Direct string comparison against 217 dish names | "Ốc Hương Xốt Trứng Muối" → exact match | ~0.01ms |
| 2. Diacritic-insensitive | Unicode NFD decomposition, strip diacritics, compare | "Oc Huong Xot Trung Muoi" → "Ốc Hương Xốt Trứng Muối" | ~0.05ms |
| 3. Prefix match | Check if any menu item starts with the input string | "Ốc Hương" → "Ốc Hương Xốt Trứng Muối" | ~0.1ms |
| 4. Substring match | Check if the input string appears anywhere in any menu item | "Xốt Trứng Muối" → "Ốc Hương Xốt Trứng Muối" | ~0.5ms |
| 5. Token Jaccard fallback | Tokenize both strings, compute Jaccard similarity, threshold ≥ 0.3 | "Lau Thai Hai San" → "Lẩu Thái Hải Sản" (similarity ~0.6) | ~2ms |

Each level is tried in sequence. The first match stops the cascade and returns the resolved name. This prioritizes speed — exact matches are the most common case (the validator-normalized LLM output usually matches a menu item directly) and cost virtually nothing.

**Return value.** `resolve_menu_name` returns a dict with `kind` and `resolved` fields:
- `kind: "exact"` or `kind: "single"` — a single unambiguous match was found. The item is valid.
- `kind: "ambiguous"` — multiple menu items match (e.g., "Ốc Hương" matches 11 sauce variants). The item is flagged, not resolved.
- `kind: "none"` — no match found at any level. The item is off-menu.

### 4.3.4.4 Off-Menu Item Handling

Items that fail all five resolution levels (`kind: "none"`) are captured in `unavailable_items` (`deterministic_validator_node.py:179-189`). Each unavailable item carries:
- `name`: The raw LLM-produced name.
- `suggestion`: The nearest menu item found via `find_nearest_menu_name()`, a helper that uses the same token-Jaccard fallback to find the closest valid dish, or `None` if nothing is close.

**The validator never auto-corrects or substitutes.** It only flags and suggests. The decision to accept the suggestion or choose something else remains with the customer, mediated by the response node:

> "Dạ, món 'Cơm Tấm' không có trong thực đơn của quán mình ạ. Món gần giống nhất là 'Cơm Chiên' (150k). Anh/chị có muốn thử món này không ạ?"

This design choice — flag but don't substitute — prevents the system from ordering the wrong dish on the customer's behalf. A near-match like "Cơm Tấm" → "Cơm Chiên" is semantically plausible but could be wrong (the customer might have wanted "Cơm Rang" instead). The system errs on the side of asking, not assuming.

### 4.3.4.5 Ambiguity Detection

Generic names that match multiple menu items (`kind: "ambiguous"`) are flagged in `ambiguous_items` (`deterministic_validator_node.py:154-159`). This is a critical Vietnamese restaurant-specific challenge: a dish family like "Ốc Hương" (sea snails) has 11 sauce variants on the menu:

> Ốc Hương Xốt Trứng Muối (170k), Ốc Hương Xốt Me (170k), Ốc Hương Xốt Tỏi (160k), Ốc Hương Xốt Bơ (170k), Ốc Hương Rang Muối (160k), ...

When a customer says "Cho 1 Ốc Hương," the prefix match resolves to *all* variants — none is a unique match. The validator flags this ambiguity and the response node asks for clarification:

> "Dạ, Ốc Hương có nhiều loại sốt: trứng muối, me, tỏi, bơ, rang muối... anh/chị muốn loại nào ạ?"

**Ambiguous items are never auto-resolved** — this is a deliberate design choice. Choosing a specific sauce variant for the customer would be incorrect and potentially frustrating (if the wrong sauce arrives). The system forces the customer to disambiguate.

### 4.3.4.6 Modifier Stripping

Vietnamese customers frequently append special requests directly to the dish name: "Lẩu Thái, ít cay," "Ốc Hương Xốt Trứng Muối - thêm hành," "Cơm Chiên (không hành)." The validator extracts these modifiers via regex patterns (`deterministic_validator_node.py:18-22`) matching common delimiters: parentheses `(...)`, comma `, ...`, and dash `- ...`.

The stripping logic (`_extract_modifier`, `deterministic_validator_node.py:116-124`):
1. Try each pattern in order: `(...)`, `, ...`, `- ...`
2. If a pattern matches, extract the modifier text and strip it from the name
3. Re-resolve the cleaned name against the menu
4. If the cleaned name resolves to a valid item, store the modifier in the item's `special_requests` field rather than the name

This means "Lẩu Thái, ít cay" is stored as `{name: "Lẩu Thái", special_requests: "ít cay"}` — the kitchen sees the correct dish with the customer's preference separated from the name.

### 4.3.4.7 State Consistency Checks

Beyond menu validation, the validator enforces three state consistency rules that prevent the LLM from corrupting the conversation state:

#### Additive-Turn Detection

LLMs are stateless per call — they receive the prompt, produce a response, and have no memory of prior turns. If the customer says "thêm 1 Bia Sài Gòn" and the LLM's prompt accidentally omits the existing cart, the LLM might produce `add_cart([Bia Sài Gòn])` — overwriting a cart that previously had 3 items.

The validator detects additive turns via keyword markers: "thêm," "nữa," "lấy thêm," "gọi thêm," "cho thêm" (`deterministic_validator_node.py:12`). If the utterance contains an additive marker and the LLM's `add_cart` output does not include the existing cart items, the validator automatically restores them (`_restore_cart_if_additive`, `deterministic_validator_node.py:83-113`). The restored items are prepended to the new items, ensuring the cart accumulates rather than replacing.

#### Context-Duplicate Items

A related LLM statelessness problem: the LLM sometimes re-adds the entire cart from context. If the cart contains [Ốc Hương, Lẩu Thái] and the customer says "thêm 1 Bia," the LLM might produce `add_cart([Ốc Hương, Lẩu Thái, Bia])` — re-adding all existing items plus the new one.

The validator deduplicates against the existing cart (`_deduplicate_against_cart`, `deterministic_validator_node.py:34-63`): items already in the cart that the customer *did not mention* in the current utterance are stripped. The customer's utterance text is checked to determine which items were actually mentioned — an existing item is kept only if the customer explicitly referenced it.

#### Remove-Name Resolution

For `remove_cart` tool calls, the validator resolves the raw item name against the current cart contents (`_resolve_remove_name`, `deterministic_validator_node.py:66-80`). The LLM might say "bỏ Ốc Hương" when the cart contains "Ốc Hương Xốt Trứng Muối" — a prefix match resolves the vague name to the full menu name in the cart. If the name cannot be matched to any cart item, an error is added: "Món 'X' không có trong giỏ hàng hiện tại."

### 4.3.4.8 Per-Tool Validation Logic

Each tool type receives specific validation beyond menu name resolution:

| Tool | Additional Validations |
|------|----------------------|
| `add_cart` | All five checks above: simultaneous confirm rejection, name resolution, ambiguity, modifiers, additive restoration, cart deduplication |
| `remove_cart` | Verify cart is non-empty; resolve name against cart; reject if item not in cart |
| `clear_cart` | Reject if cart already empty (no-op prevention) |
| `confirm_order` | Require `order_stage == AWAITING_CONFIRMATION` (cannot confirm before drafting); require non-empty cart; inject `table_id` into args |
| `request_payment` | Inject `table_id` into args; require `table_id` present |
| `verify_payment` | Inject `table_id` into args; require `table_id` present |

For `confirm_order`, `request_payment`, and `verify_payment`, the validator automatically injects the session's `table_id` into the tool call arguments (`deterministic_validator_node.py:227-230`). These tools call the orchestrator backend, which requires a `table_id` to identify the table. The LLM does not know the `table_id` — it operates on session-scoped state — so the validator provides it from `AgentState`.

### 4.3.4.9 Retry and Circuit Breaker

When the validator finds errors, it constructs per-tool `ToolMessage` objects with formatted error feedback (`deterministic_validator_node.py:294-334`):

```
[Lỗi Xác Thực cho add_cart]:
- Món 'Cơm Tấm' không có trong menu. Gợi ý món gần nhất: 'Cơm Chiên'.
```

These `ToolMessage` objects are appended to the message history. When the worker is invoked for retry, it sees its own prior tool call followed by the validator's error feedback — the full failure context.

The `loop_count` is incremented with each failed validation. At `loop_count >= 3` (`MAX_RETRY_LOOPS`), the circuit breaker engages: the validator returns `is_valid=False` but the routing function `_route_after_validator` routes to `state_outcome` instead of returning to the worker. The `state_outcome` builds a `RetryResponseContext` with an apology, and the `response_node` verbalizes it:

> "Dạ, em xin lỗi anh/chị, em xử lý thông tin bị lỗi. Anh/chị kiểm tra lại giúp em nhé ạ."

The system always produces a response — even after repeated LLM failures, the customer hears an apology rather than silence.

### 4.3.4.10 Validator Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Deterministic** | No ML, no randomness. Every check is a predicate with a definitive answer. |
| **Rejects, doesn't substitute** | Off-menu items are flagged with suggestions, never auto-corrected. Ambiguous items ask for clarification. |
| **Firewall placement** | Runs *after* LLM proposes, *before* tools execute. Failed tool calls never reach the ToolNode. |
| **Bounded execution** | Circuit breaker at 3 retries guarantees termination. |
| **Specific feedback** | Error messages name the exact problem and item, enabling the LLM to fix its output. |
| **Zero false positives on known menu** | Exact and prefix matches are deterministic. Only the Jaccard fallback (level 5) involves a similarity threshold that could produce a false match — and it is gated at ≥ 0.3, conservative enough to reject most borderline cases. |

The validator's effectiveness is quantified in §5.3.2: across 4 adversarial out-of-menu scenarios, the validator caught 100% of off-menu items and zero invalid items reached `confirm_order`. This is the strongest safety result in the AI evaluation.
