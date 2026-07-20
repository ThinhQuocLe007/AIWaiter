## 4.3.2 Stage I — Understanding: Intent Classification

> **Status:** draft
> **Cross-refs:** §4.3.1 for execution model, §4.3.3 for workers, §5.3.1 for router evaluation
> **Source:** `src/training_semantic_router/classifier/predict.py` (84 lines), `classifier/model.py` (34 lines), `classifier/features.py` (45 lines), `src/agent_brain/agent/nodes/classifier_router_node.py`
> **Figures needed:** Fig 4.3.2 (MLP classifier pipeline: utterance → segmentation → embedding → context features → MLP → intent)

---

Before any action can be taken, the system must determine what the customer wants. This is a classification problem: given an utterance in Vietnamese, select the correct intent from the set {ORDER, SEARCH, PAYMENT, CHAT}. The classifier is the first node in the graph, and its output — the `current_intents` queue — determines which worker nodes execute downstream.

The router architecture evolved through three iterations: (1) a pure semantic centroid router achieving 89.0% on 100 cases, (2) a two-tier hybrid (semantic + SLM) achieving 73.3% on 45 cases, and (3) the final trained MLP classifier achieving 95.6% on 45 cases, 97.4% on a 39-case holdout, and 92.0% on 100 balanced cases. This section describes the final MLP architecture. The two prior iterations are evaluated as ablation baselines in §5.3.1.

### 4.3.2.1 Intent Taxonomy

The system recognizes four output classes at the classifier level. ORDER_CONFIRM utterances ("ok em", "chốt đơn") are merged with ORDER — the distinction is handled downstream by the order state machine (§4.3.5.2), not the classifier. Multi-intent utterances ("Cho 2 Ốc Hương rồi tính tiền luôn") are classified by their dominant intent; sequential multi-intent execution is handled by the graph's intent queue loop (§4.3.5.3).

| Intent | Vietnamese Trigger Examples | Worker | Notes |
|--------|----------------------------|--------|-------|
| **ORDER** | "Cho 2 Ốc Hương", "Gọi thêm 1 Lẩu Thái", "Bỏ món X", "Ok chốt đơn", "Đúng rồi đặt luôn" | `order_worker` | ORDER_CONFIRM merged at classifier level |
| **SEARCH** | "Món nào cay cay?", "Ốc Hương giá bao nhiêu?", "Có món chay không?" | `search_worker` | All informational queries |
| **PAYMENT** | "Tính tiền", "Cho xin bill", "Thanh toán QR" | `payment_dispatch` | Deterministic dispatch (no LLM) |
| **CHAT** | "Chào em", "Cảm ơn", "Ngon quá", "Quán đông ghê" | `chat_worker` | Smalltalk and non-task utterances |

### 4.3.2.2 MLP Classifier Architecture

The classifier is a 3-layer multi-layer perceptron trained on 3,712 synthetically generated and augmented Vietnamese utterances. It accepts a 778-dimensional input vector — the concatenation of a frozen 768-dim sentence embedding and 10 hand-crafted context features extracted from `AgentState`. The output is a 4-class probability distribution.

#### Input Features (778-dim)

**Embedding component (768-dim):** Each utterance is encoded via `bkai-foundation-models/vietnamese-bi-encoder`, a SentenceTransformer model pre-trained on Vietnamese sentence pairs. The bi-encoder produces L2-normalized 768-dimensional embeddings. This model was selected over general-domain alternatives (e.g., `AITeamVN/Vietnamese_Embedding`, 1024-dim) for its native handling of Vietnamese diacritics, compound words, and informal speech patterns — critical for a restaurant setting where customers use teencode ("ad", "vs", "ck", "z", "nhiêu") and dialectal variants.

**Context features (10-dim):** Ten features extracted from `AgentState` encode the conversation state that pure embedding similarity cannot see. These features are the key architectural innovation: an utterance of "ok" maps to ORDER when `order_stage=AWAITING_CONFIRMATION` but to CHAT at `IDLE` — the embedding alone cannot make this distinction, but the context features can.

| Feature | Dims | Description | Extraction |
|---------|------|-------------|------------|
| `order_stage` one-hot | 5 | IDLE, BUILDING, AWAITING_CONFIRMATION, CONFIRMED, MODIFYING | `state["order_stage"]` |
| `has_cart` | 1 | 1 if `active_cart` is non-empty, else 0 | `state["active_cart"] is not None` |
| `cart_size_norm` | 1 | `min(len(cart.items), 10) / 10` | Normalized cart item count |
| `has_search_context` | 1 | 1 if `search_context` is non-empty, else 0 | `state["search_context"] is not None` |
| `search_context_size_norm` | 1 | `min(len(search_context), 20) / 20` | Normalized search result count |
| `utterance_length_norm` | 1 | `min(len(utterance), 200) / 200` | Character count of raw text |

**Rationale for context features.** Each feature targets a specific ambiguity: (a) `order_stage` distinguishes "ok" as ORDER_CONFIRM vs CHAT based on whether the customer is currently confirming an order, (b) `has_cart` and `cart_size_norm` help distinguish "gọi thêm" (add to existing cart → ORDER) from "gọi món" (first order on empty cart → ORDER), (c) `has_search_context` and `search_context_size_norm` help the classifier recognize that the customer has already been searching for dishes, so a follow-up question is likely SEARCH rather than CHAT, (d) `utterance_length_norm` helps distinguish short affirmations ("ok", "ừ" — typically ORDER_CONFIRM) from longer queries (typically SEARCH or CHAT).

#### Network Architecture

```
Input (778-dim)
  │
  ├── Linear (778 → 256)
  ├── ReLU
  ├── Dropout (p=0.2)
  │
  ├── Linear (256 → 64)
  ├── ReLU
  ├── Dropout (p=0.2)
  │
  └── Linear (64 → 4)
        └── Softmax → {ORDER, SEARCH, PAYMENT, CHAT}
```

The network is intentionally small — 3 layers, ~220K parameters — because the embedding already provides a strong 768-dim semantic representation. The 10 context features inject conversation-state awareness. The dropout layers (p=0.2) prevent overfitting to the synthetic training data and ensure generalization to real customer utterances not seen during training. The model fits in under 1 MB on disk.

#### Training Pipeline

**Data.** 3,712 Vietnamese utterances were synthetically generated via an LLM and augmented with context features, covering all 4 intents across diverse restaurant scenarios. A subset of 795 raw utterances was expanded to 3,712 through systematic augmentation: each utterance was paired with multiple context configurations (different `order_stage` values at which that utterance could realistically occur, different cart/search states). The 4-class labels were assigned by the generating LLM and manually verified. A 39-case holdout set (`test_holdout.json`) was separated before augmentation and never seen during training.

**Training configuration.** 80/20 stratified train/validation split. CrossEntropyLoss with class weights inversely proportional to class frequency (SEARCH and CHAT are under-represented in the raw data, so they receive higher weights). Adam optimizer (lr=1e-3, weight_decay=1e-4). Early stopping with patience=10 on validation loss. All 3,712 × 768-dim embeddings are precomputed offline — training runs entirely on CPU in approximately 2 minutes.

**Artifacts.** Three files saved to `classifier/saved/`: `model.pt` (PyTorch state_dict), `label_encoder.json` (class→index mapping), `scaler.npz` (StandardScaler mean/scale for the 10 context features, fitted on the training set). These are loaded at agent startup and reused for every inference call.

#### Online Inference Pipeline

When an utterance arrives at the classifier (`classifier_router_node`):

1. **Word segmentation:** The utterance is tokenized via `underthesea.word_tokenize()`, preserving Vietnamese compound words ("ốc_hương", "trứng_muối") as single tokens.

2. **Embedding:** The segmented text is encoded by the frozen `bkai-foundation-models/vietnamese-bi-encoder` → 768-dim L2-normalized vector. This step is shared with the RAG retriever (§4.4), so the embedding model is loaded once and reused.

3. **Context extraction:** Ten features are extracted from the current `AgentState` using `extract_context_features()`. The `StandardScaler` (fitted on training data) is applied to normalize each feature to zero mean and unit variance.

4. **Concatenation:** The 768-dim embedding and 10-dim scaled context features are concatenated → 778-dim input vector.

5. **MLP forward pass:** The saved `model.pt` is loaded, the forward pass executes in ~0.17ms, and softmax produces a 4-class probability distribution.

6. **Output:** The classifier returns `{"intent": max_class, "confidence": max_prob, "all_probs": {...}}`. The `current_intents` queue is set to `[intent]` and the graph proceeds to the corresponding worker node.

### 4.3.2.3 Design Rationale

The MLP classifier was chosen over the prior two-tier hybrid router for four reasons:

**1. Latency.** The MLP forward pass (0.17ms) is three orders of magnitude faster than the SLM fallback path in the old two-tier hybrid (1.8s). Even compared to the semantic centroid computation (1.2ms cosine similarity), the MLP is 7× faster. The shared embedding step (~50ms) dominates total classification latency regardless of routing method, so the routing logic itself contributes negligibly.

**2. Determinism.** The MLP is a pure function of its input — same utterance + same context always produces the same output. An LLM-based router, even at temperature=0.0, can produce different outputs on different runs due to floating-point non-determinism in GPU matrix operations. For a restaurant system, "ok em" must route to ORDER 100% of the time.

**3. Context awareness.** The 10 context features encode conversation state that pure embedding similarity cannot see. The two-tier hybrid router achieved 73.3% on the 45-case evaluation set because many utterances fell below the semantic gate threshold (max_sim < 0.35) and defaulted to CHAT. The MLP's context features — particularly `order_stage` and `cart_size` — distinguish these cases correctly. Ten of the hybrid's 12 failures on the 45-case set are corrected by the MLP (§5.3.1).

**4. Accuracy.** On the 45-case A/B comparison, the MLP achieves 95.6% vs 73.3% for the hybrid — a 22-point improvement. On the 39-case holdout (never seen during training), the MLP achieves 97.4% with a single misclassification (a delivery query mapped to PAYMENT instead of SEARCH). ORDER, CHAT, and non-delivery SEARCH queries are classified perfectly.

**Limitation.** The MLP requires the frozen bi-encoder embedding model to remain unchanged. If the embedding model is swapped (e.g., upgrading from a 768-dim to a 1024-dim model), the classifier must be retrained because the input dimension and the embedding distribution change. The fingerprint check used by the semantic centroid router (offline) does not apply here — retraining is the only safe migration path.

### 4.3.2.4 Routing to Workers

After classification, the routing function `_route_by_intent` maps the predicted intent to its worker node:

```python
INTENT_TO_WORKER = {
    "ORDER":    "order_worker",          # LLM: tool_choice="any" for cart CRUD + confirm
    "SEARCH":   "search_worker",         # LLM: tool_choice="any" for search() + delegate()
    "PAYMENT":  "payment_dispatch",      # Deterministic — always emits request_payment
    "CHAT":     "chat_worker",           # Pure function — builds curated memory context
}
```

The routing function is a pure function (`AgentState → str`) that encapsulates the graph's branching logic, keeping the `StateGraph` construction declarative and the business logic testable in isolation.

### 4.3.2.5 Design Iteration History (Ablation Context)

The final MLP classifier is the third iteration of the router. The first two iterations serve as ablation baselines in §5.3.1:

| Iteration | Architecture | Accuracy (45-case) | Latency (routing) | Key Weakness |
|-----------|-------------|--------------------|--------------------|--------------|
| 1 — Semantic centroid | Cosine similarity to 5 per-intent centroids, softmax-gap gating | 89.0% (100-case) | ~1.2ms | Max_sim < 0.35 → NONE on ~11% of utterances. Centroid representation too coarse for restaurant-domain ambiguity |
| 2 — Two-tier hybrid | Semantic fast-path + SLM fallback (Qwen2.5 7B, 14 few-shot) | 73.3% | ~1.8s (SLM) | Low centroid similarity → default to CHAT. SLM latency 1.8s per fallback. No context features |
| **3 — MLP classifier** | Frozen bi-encoder (768-dim) + 10 context features → MLP → 4-class | **95.6%** | **~0.17ms** | Embedding step (~50ms) dominates. Delivery queries still confused with PAYMENT |

The progression from iteration 1 to 3 demonstrates that (a) pure embedding similarity is insufficient — context features are necessary, (b) LLM-based routing adds latency without proportional accuracy gain over a trained classifier, and (c) a small MLP trained on domain-specific data outperforms both a hand-crafted gating system and a general-purpose LLM on this task.
