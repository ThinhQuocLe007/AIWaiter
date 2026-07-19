## 4.3.2 Stage I — Understanding: Intent Classification

> **Status:** draft
> **Cross-refs:** §4.3.1 for execution model, §4.3.3 for workers, §5.3.1 for router evaluation
> **Source:** `src/agent_brain/agent/nodes/hybrid_router_node.py` (58 lines), `semantic_router_node.py` (145 lines), `slm_router_node.py` (131 lines)
> **Figures needed:** Fig 4.3.2 (two-tier router flow: utterance → semantic gate → SLM fallback)

---

Before any action can be taken, the system must determine what the customer wants. This is a classification problem: given an utterance in Vietnamese, select one or more intents from the set {ORDER, ORDER_CONFIRM, SEARCH, PAYMENT, CHAT}. The router is the first node in the graph, and its output — the `current_intents` FIFO queue — determines which worker nodes execute downstream.

The router is designed as a **two-tier hybrid architecture**: a fast semantic router (Tier 1, ~15ms) handles unambiguous utterances via centroid-based cosine similarity, while a slower but more capable SLM router (Tier 2, ~1.8s) serves as the fallback for ambiguous, multi-intent, and context-dependent cases. This design follows from a latency-accuracy trade-off: ~33% of utterances can be classified instantaneously with zero errors, but the remaining cases require an LLM's contextual reasoning. Running all utterances through the LLM would add 1.8s of unnecessary latency for one-third of turns.

### 4.3.2.1 Intent Taxonomy

The system recognizes five intent categories, each routing to a distinct processing path downstream:

| Intent | Abbreviation | Vietnamese Trigger Examples | Worker | LLM Called? |
|--------|-------------|----------------------------|--------|-------------|
| **ORDER** | `ORDER` | "Cho 2 Ốc Hương", "Gọi thêm 1 Lẩu Thái", "Bỏ món X" | `order_worker` | Yes |
| **ORDER_CONFIRM** | `ORDER_CONFIRM` | "Xác nhận", "Chốt đơn", "Đặt đi", "Ok đặt nha" | `order_worker` | Yes |
| **SEARCH** | `SEARCH` | "Món nào cay cay?", "Ốc Hương giá bao nhiêu?", "Có món chay không?" | `search_worker` | Yes |
| **PAYMENT** | `PAYMENT` | "Tính tiền", "Cho xin bill", "Thanh toán QR" | `payment_dispatch` | No (deterministic) |
| **CHAT** | `CHAT` | "Chào em", "Cảm ơn", "Ngon quá", "Quán mở cửa đến mấy giờ?" | `chat_worker` | No (pure function) |

**ORDER_CONFIRM is a distinct intent, not a sub-type of ORDER**, because its processing path differs fundamentally. ORDER triggers `add_cart`/`remove_cart` tools that modify the cart, while ORDER_CONFIRM triggers `confirm_order` which sends the composed order to the kitchen. The distinction is critical for multi-intent decomposition: "Cho 2 Ốc Hương rồi tính tiền luôn" produces [ORDER, PAYMENT], whereas "Ok đặt đi" at the confirmation stage produces [ORDER_CONFIRM].

**Multi-intent support** handles compound utterances that express multiple sequential actions. The SLM router decomposes these into an ordered list, and the graph processes them as a FIFO queue (§4.3.5.3). Examples:

- "Cho 1 Lẩu Thái và tính tiền luôn" → [ORDER, PAYMENT]
- "Món này cay không? Nếu không cay thì lấy 2 phần" → [SEARCH, ORDER]
- "Xác nhận đơn và gọi thêm 1 Bia" → [ORDER_CONFIRM, ORDER]

### 4.3.2.2 Tier 1 — Semantic Router (Fast Path)

The semantic router encodes the utterance into a 1024-dimensional embedding, computes cosine similarity to five pre-computed per-intent centroid vectors, then applies temperature-scaled softmax with gap gating to decide whether the classification is confident enough to bypass the LLM.

#### Centroid Construction (Offline)

Each intent is represented by a centroid vector — the arithmetic mean of embeddings for all utterances belonging to that intent. The centroid construction process runs once offline:

1. A set of 192 hand-crafted Vietnamese utterances is written across the 5 intent categories. Each utterance is a realistic example of how a Vietnamese restaurant customer expresses that intent (e.g., "Cho em 2 phần Ốc Hương Xốt Trứng Muối nha" for ORDER, "Cho em hỏi quán mình có món chay nào không ạ?" for SEARCH).
2. Each utterance is embedded via `SentenceTransformer` using the `AITeamVN/Vietnamese_Embedding` model (1024-dimensional). This model is a BGE-M3 fine-tune optimized for Vietnamese semantic similarity.
3. Per-intent centroid vectors are computed as `c_i = (1/|U_i|) Σ embed(u)` for all utterances u in intent i.
4. The five centroids are saved to `centroids.npz` along with an embedding model fingerprint. At agent startup, the semantic router loads these centroids and verifies the fingerprint — if the embedding model has changed (dimensions differ), the router rejects the centroids and falls back to runtime re-encoding of the 192 utterances.

The fingerprint check is critical: mismatched centroids (built with a 1024-dim model, queried with a 768-dim model) would silently produce wrong cosine similarities with no error output. The fingerprint prevents this.

#### Online Inference

When an utterance arrives at the semantic router (`semantic_router_node.py:127`):

1. **Embed the utterance** using the same `SentenceTransformer` instance shared with the RAG retriever, producing a 1024-dim vector `q`.
2. **Compute cosine similarity** to each of the 5 centroid vectors: `s_i = cosine_similarity(q, c_i)`.
3. **Apply softmax-gap gating** via the `softmax_routing()` function:

```
Algorithm: Softmax-gap gating

1. max_sim = max(s_i for all intents i)
2. If max_sim < MIN_SIM_THRESHOLD (0.35):
   → reject (utterance too far from ALL centroids — likely CHAT or noise)
3. Compute softmax probabilities:
   p_i = exp(s_i / T) / Σ exp(s_j / T)   where T = 0.20
4. Sort probabilities descending. Let P₁ = top-1, P₂ = top-2.
5. If P₁ ≥ PROB_THRESHOLD (0.25) AND (P₁ − P₂) ≥ GAP_THRESHOLD (0.15):
   → accept: return the intent with highest probability
6. Else:
   → reject: return None (defer to Tier 2 SLM)
```

**Temperature calibration.** T = 0.20 was selected via grid search on the development set. Lower temperature sharpens the softmax distribution — at T = 0.20, a 0.1 difference in cosine similarity maps to a much larger probability gap than at T = 1.0. This prevents ambiguous utterances (e.g., "Ok" at IDLE, which is borderline between CHAT and ORDER_CONFIRM) from passing the gap threshold.

**Two-threshold design.** The gating uses two independent conditions that must hold simultaneously: (a) `max_sim ≥ 0.35` ensures the utterance has some semantic relationship to at least one intent centroid — it is not noise or completely out-of-domain; (b) `P₁ − P₂ ≥ 0.15` ensures the top intent is unambiguously separated from the runner-up. An utterance could have high similarity to one centroid (passing condition a) but also high similarity to a second centroid (failing condition b), indicating ambiguity that requires the SLM.

**Design rationale.** The semantic fast-track is designed to be **zero-error on accepted utterances**. The high gap threshold (0.15) ensures that only utterances with unambiguous intent membership pass. In evaluation on 80 test cases (§5.3.1), 27 utterances (33.8%) were fast-tracked with zero misclassifications. This is intentional: the semantic router sacrifices recall (only 33% fast-track rate) for precision (100% on fast-tracked cases). Any utterance that is even potentially ambiguous falls through to the SLM.

### 4.3.2.3 Tier 2 — SLM Router (Fallback)

When the semantic router rejects an utterance (returns `None`), the SLM router takes over. This is an LLM-based classifier using Qwen2.5 7B Instruct served by Ollama with structured output.

#### Model Configuration

The SLM router uses the same Qwen2.5 7B model as the workers and response node, but configured differently for deterministic classification:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `temperature` | 0.0 | Deterministic output — same utterance always produces the same classification |
| `num_ctx` | 8192 | Sufficient for long prompts with 14 few-shot examples |
| `keep_alive` | -1 | Model pinned in VRAM; no cold-start on classification turns |
| `with_structured_output` | `IntentPrediction` | Forces the LLM to output a Pydantic `IntentPrediction` schema with `intents: list[IntentType]` and `reasoning: str` |

The `IntentPrediction` Pydantic model (`schemas/routing.py`) constrains the LLM's output to valid JSON with a finite set of intent values. This eliminates parsing errors — the LLM cannot produce a malformed intent string or a classification outside the 5-category taxonomy.

#### Prompt Construction

The router prompt (`slm_router_node.py:94`) is assembled from four components, each designed for a specific role:

**1. System prompt** (`router_agent.md`, 83 lines). This is the core instruction set that defines the router's role, the five intent categories with Vietnamese trigger keywords, and a 4-step reasoning protocol:
- **Step 1 — Check context:** Read `order_stage` and recent chat history. A short affirmation ("ok", "ừ") at `AWAITING_CONFIRMATION` is ORDER_CONFIRM; the same utterance at `IDLE` is CHAT. This requires dynamic context injection (see below).
- **Step 2 — Identify primary intent:** Scan for action keywords ("cho" → ORDER, "tính tiền" → PAYMENT, question words → SEARCH).
- **Step 3 — Check for sequential intents:** If the utterance expresses multiple actions in sequence, output them in spoken order with deduplication.
- **Step 4 — Produce JSON output:** A `reasoning` string in Vietnamese explaining the classification, and the `intents` array.

**2. Few-shot examples** (`router.json`, 14 examples). These cover single-intent, multi-intent, and edge cases:
- Single-intent examples for each category: "Cho 2 Ốc Hương" → [ORDER], "Món này cay không?" → [SEARCH], "Tính tiền đi" → [PAYMENT], "Chào em" → [CHAT].
- Multi-intent examples: "Cho 1 Lẩu Thái và tính tiền luôn" → [ORDER, PAYMENT].
- Context-dependent edge cases: "Ok" at AWAITING_CONFIRMATION → [ORDER_CONFIRM] vs "Ok" at IDLE → [CHAT].
- Teencode and informal speech: "ad" (anh/chị), "vs" (với), "ck" (chồng).
- Short affirmations: "ừ", "uh", "được", "ok em".

The few-shot examples use LangChain's `FewShotChatMessagePromptTemplate`, which formats each example as a `(human, ai)` message pair. This enables KV-cache optimization — the static portion of the prompt (system + few-shot) is identical across turns, so Ollama reuses cached attention keys/values.

**3. Dynamic context** (last 2 conversation turns + current `order_stage`). This is the critical innovation that makes the router context-aware. Without it, "ok" is always classified as CHAT regardless of cart state. With it, "ok" at `AWAITING_CONFIRMATION` is correctly classified as ORDER_CONFIRM. The dynamic context is injected via the `chat_history` and `order_stage` template variables (`slm_router_node.py:51-59`), placed after the static few-shot examples to preserve prefix caching.

**4. User message.** The raw utterance text, appended last.

#### Structured Output and Error Handling

The SLM router chain is compiled once at module level (`slm_router_node.py:95`): `ChatPromptTemplate | ChatOllama.with_structured_output(IntentPrediction)`. This chain is reused for every turn — no re-compilation overhead.

Error handling covers two failure modes:
- **LLM unreachable** (Ollama crash, GPU OOM): `httpx.HTTPError` and `ConnectionError` are caught; the router defaults to `["CHAT"]` as the safest fallback — CHAT triggers a conversational response that prompts the customer to repeat themselves.
- **No user message found** (empty state, edge case): Defaults to `["CHAT"]` with a warning log.

### 4.3.2.4 Router Orchestration — The Hybrid Router Node

The `hybrid_router_node` (`hybrid_router_node.py:14`) orchestrates the two tiers:

```
def hybrid_router_node(state):
    1. Execute semantic_router_node(state) → {intent, confidence, all_similarities}
    2. If intent is not None:
       → fast-track: set current_intents = [intent], decided_by = "SEMANTIC"
       → return immediately (no LLM call)
    3. Else:
       → execute slm_router_node(state) → {current_intents}
       → fallback: use SLM's predicted intents, decided_by = "SLM"
    4. Build routing_meta (for tracing/debugging)
    5. Return {current_intents, routing_meta}
```

The `routing_meta` dict is stored in `AgentState` and includes: which tier decided, semantic confidence and similarities, SLM-predicted intents, and total routing latency. This metadata is used for evaluation (§5.3.1) and debugging — a LangSmith trace can show exactly why a particular utterance was routed to a particular worker.

**Deduplication.** When the SLM returns `intents`, duplicate consecutive intents are removed via `dict.fromkeys()` (`hybrid_router_node.py:40`). This handles the case where the LLM outputs `[ORDER, ORDER, PAYMENT]` — the deduplication produces `[ORDER, PAYMENT]`.

### 4.3.2.5 Routing Functions — Worker Dispatch

After the hybrid router sets `current_intents`, the routing function `_route_by_intent` (`graph.py:56`) maps the first intent to its worker node:

```python
INTENT_TO_WORKER = {
    "ORDER":          "order_worker",
    "ORDER_CONFIRM":  "order_worker",    # same worker, different tool call
    "SEARCH":         "search_worker",
    "PAYMENT":        "payment_dispatch", # deterministic, no LLM
    "CHAT":           "chat_worker",      # pure function, no LLM
}
```

ORDER and ORDER_CONFIRM both route to `order_worker` because they share the same tool bindings (cart CRUD + confirm), but the worker distinguishes them via the current `order_stage` and the per-intent sub-query in `intent_queries`.

The routing functions are pure functions (`AgentState → str`) that encapsulate the graph's branching logic, keeping the `StateGraph` construction declarative and the business logic testable in isolation.

### 4.3.2.6 Design Summary

| Property | Tier 1 — Semantic | Tier 2 — SLM |
|----------|-------------------|--------------|
| **Method** | Cosine similarity to 5 centroids | LLM with structured output + 14 few-shot examples |
| **Latency** | ~15ms | ~1.79s |
| **Fast-track rate** | 33.8% (27/80 eval cases) | N/A (all remaining cases) |
| **Accuracy on handled** | 100% (zero errors on 27 fast-tracked) | See §5.3.1 for full confusion matrix |
| **Multi-intent** | No (single-intent only) | Yes (decomposes "Cho X rồi tính tiền" → [ORDER, PAYMENT]) |
| **Context-aware** | No (utterance only) | Yes (last 2 turns + order_stage injected in prompt) |
| **Failure mode** | Rejects all ambiguous utterances (defer to Tier 2) | Defaults to CHAT on LLM error |

The hybrid design achieves the latency of the semantic router for unambiguous cases and the accuracy of the SLM for everything else. The cost — two tiers instead of one — is justified by the evaluation results: semantic-only accuracy is estimated at ~65%, and SLM-only latency is consistently ~1.8s. The hybrid achieves 90% accuracy at 1.19s mean latency (34% reduction from SLM-only), with zero errors on fast-tracked cases. The ablation experiments in §5.3.1 quantify this trade-off.
