## 4.6 Knowledge Retrieval Pipeline

> **Status:** draft
> **Cross-refs:** §2.5 (Need 4 — sensory queries to relevant items), §4.1 (FR2 — menu search by attributes), §4.2 (C8 — sensory queries don't match menu structure), §5.3.4 (retrieval evaluation)
> **Source:** `src/agent_brain/services/retriever/hybrid_retriever.py` (102 lines), `indices/bm25.py` (58 lines), `indices/vector.py` (87 lines), `fusion/rrf.py` (68 lines), `document_loader.py` (72 lines), `filters.py` (67 lines)
> **Figures needed:** Fig 4.6 — Closed-loop RAG pipeline (customer utterance → LLM rewrite → BM25 + FAISS → RRF fusion → LLM rephrase → grounded response)

---

Addressing C8: customers describe food by sensory experience — "món gì ấm bụng?" (what's warm and filling?), "ăn cay" (spicy), "món chay" (vegetarian) — which shares zero lexical overlap with menu entries indexed by name and category. Standard RAG (embed query → retrieve similar documents → generate) fails when query and document speak different languages.

This section presents a closed-loop retrieval pipeline: the LLM rewrites the customer's vague utterance into concrete search terms before retrieval, a hybrid BM25+FAISS+RRF retriever searches the 217-dish menu, and the LLM rephrases the results in natural Vietnamese after retrieval — forming a rewrite → retrieve → rephrase loop. Multi-turn search context is retained in AgentState to prevent redundant queries.

---

### 4.6.1 Query Rewriting

The first stage of the closed-loop pipeline runs before any retrieval occurs. Rather than embedding the customer's raw utterance, the search worker (§4.5.3) uses the LLM to rewrite it into concrete, searchable Vietnamese terms.

**Why rewriting is necessary.** The utterance "món gì ấm bụng cho ngày lạnh?" contains no words that appear in the menu. BM25 finds zero matches. FAISS retrieves the nearest vectors in embedding space, which for this query are general-domain sentences about comfort and warmth — not food items. The retrieval gap is not one of index quality or embedding model choice; it is a fundamental query-document mismatch. The query must be transformed before search.

**How rewriting works.** The search worker's system prompt (`search_agent.md`) instructs the LLM to reason about Vietnamese culinary categories and produce concrete search terms:

1. **Input:** The customer's raw utterance, plus the last 2 conversation turns for context.
2. **LLM reasoning:** The model identifies the customer's underlying need — "ấm bụng" means they want something hot, filling, and comforting. In Vietnamese cuisine, these attributes map to noodle soups (bún, phở), hot pots (lẩu), porridges (cháo), and stews (súp). The LLM performs this cultural reasoning and produces a list of these concrete categories.
3. **Output:** A rewritten query string such as `"lẩu, súp, cháo, món nước nóng, bún, phở"` — terms that are lexically present in the menu.

The rewritten query becomes both the BM25 search terms (each term is a keyword) and the FAISS embedding input (the full rewritten query is embedded). The LLM's `query` argument in the `search()` tool call carries this rewritten text.

**Contrast with keyword extraction.** Query rewriting is not keyword extraction. Keyword extraction from "món gì ấm bụng cho ngày lạnh?" would produce "món", "ấm", "bụng", "lạnh" — none of which match menu entries. The LLM must translate sensory language into food-category language using cultural knowledge of Vietnamese cuisine, not just extract tokens from the input string.

**Contrast with HyDE (Hypothetical Document Embeddings).** HyDE generates a hypothetical relevant document and embeds it for retrieval. The rewritten query in this system is more targeted — it produces search keywords optimized for both BM25 exact matching and FAISS semantic matching, rather than a free-form document that may introduce noise.

---

### 4.6.2 Hybrid Retrieval

After the query is rewritten, it is sent through two parallel retrieval paths: a sparse BM25 index for exact keyword matching and a dense FAISS index for semantic similarity. The results from both are fused via Reciprocal Rank Fusion (RRF). This hybrid design exploits the complementary strengths of sparse and dense retrieval:

- **BM25 (sparse):** strong for exact keyword matches on dish names, ingredient mentions, and category labels. "Ốc Hương" → finds all dishes containing "Ốc Hương" in their name or description.
- **FAISS (dense):** strong for semantic similarity on taste profiles, dietary attributes, and sensorily described preferences. "món cay" → finds dishes with spicy taste metadata even if the word "cay" does not appear in the dish name.

**Why both, not one or the other.** Dense retrieval alone is weak on rare dish names and proper nouns — the embedding for "Ốc Hương Xốt Trứng Muối" may be closer to general restaurant terms than to the specific dish variant. Sparse retrieval alone is blind to semantic synonyms — "hải sản" (seafood) and "tôm mực cá" (shrimp squid fish) describe the same category but share no tokens. The hybrid design guarantees that at least one retriever finds a relevant match for any query type.

#### 4.6.2.1 BM25 Sparse Index

**Construction.** The BM25 index is built offline from the 217-dish menu (`assets/data/menu.json`). For each dish, a search document is created by concatenating metadata fields optimized for keyword matching:
- Dish name (full Vietnamese)
- Category (Lẩu, Ốc, Hải Sản, Nướng, etc.)
- Tags (spicy, seafood, soup, etc.)
- Taste profile (rich, sour, sweet, etc.)
- Description (preparation details, key ingredients)

**Vietnamese word segmentation.** Before indexing, each document is tokenized via `underthesea.word_tokenize()`. Vietnamese is a monosyllabic language where compound words carry meaning as units: "bún bò Huế" is one lexical item (a specific noodle soup), not three independent tokens. Tokenization via `underthesea` produces `["bún_bò_huế"]` (single token with underscores), preserving compound word semantics for BM25 term matching. A query for "bò Huế" will match "bún_bò_huế" partially (token overlap), while without segmentation the query "bò" would match "bò" in "bò lúc lắc" (a different dish), producing false positives.

**BM25 parameters.** The `BM25Okapi` implementation from `rank_bm25` is used with `k1=1.2` (term frequency saturation) and `b=0.75` (document length normalization). The index is serialized to disk as a pickle file and loaded at agent startup. Raw retrieval retrieves `k=10` documents per query.

#### 4.6.2.2 FAISS Dense Index

**Embedding model.** The `bkai-foundation-models/vietnamese-bi-encoder` (768-dim, L2-normalized) is used as the sentence encoder. This is a Vietnamese-specific bi-encoder trained on Vietnamese sentence pairs — critical for handling diacritic sensitivity. General-domain multilingual models (e.g., `paraphrase-multilingual-MiniLM-L12-v2`) degrade on Vietnamese tonal languages because diacritics carry semantic meaning: "ốc" (snail) and "ọc" (not a word) differ only in tone mark position, yet standard multilingual tokenizers strip or ignore diacritics.

**Document representation.** Each dish is represented by a single embedding vector of its combined metadata fields (name + category + tags + taste_profile + description), identical to the BM25 document text but embedded as a dense 768-dimensional vector rather than tokenized.

**Index structure.** The FAISS `IndexFlatIP` (inner product, equivalent to cosine similarity on L2-normalized vectors) stores all 217 dish embeddings plus documents for restaurant info, best-seller recommendations, and VIP customer profiles. The index is serialized to `storage/vector/faiss_index/` with a fingerprint file that records the embedding model identifier — on load, the model identity is verified against the fingerprint to prevent dimension mismatches from embedding model changes. Raw retrieval retrieves `k=10` documents per query.

**Embedding pipeline.** The rewritten query is embedded via the same bi-encoder, producing a 768-dim L2-normalized vector. Cosine similarity to all document vectors is computed via FAISS inner product search. The top-10 results by similarity score are returned.

#### 4.6.2.3 RRF Fusion

Reciprocal Rank Fusion (RRF) merges the BM25 and FAISS result lists without requiring comparable scores. BM25 scores are unbounded term-weight sums; FAISS scores are cosine similarities in [−1, 1]. RRF works on ranks, not scores:

```
score(d) = Σ_{r ∈ rankers} 1 / (k + rank_r(d))
```

where `k=60` (a constant that smooths rank differences) and `rank_r(d)` is document `d`'s position in retriever `r`'s result list (1-indexed). A document appearing at rank 1 in both lists scores `1/61 + 1/61 ≈ 0.033`; a document at rank 1 in BM25 and rank 5 in FAISS scores `1/61 + 1/65 ≈ 0.032`.

**Parallel execution.** BM25 and FAISS retrieval run concurrently via `ThreadPoolExecutor(max_workers=2)` — the two retrievers are independent and CPU-bound (BM25 token matching) vs. memory-bound (FAISS vector search) on different resources. Combined retrieval wall-clock time is approximately `max(BM25_time, FAISS_time)` rather than `BM25_time + FAISS_time`.

**Fused ranking.** Documents appearing in both result lists receive scores from both rankers. Documents appearing in only one list receive a score from that ranker only. The fused list is sorted by descending RRF score and truncated to `k=5` final results, each annotated with its dish name, price, category, tags, and taste profile for downstream use in response generation.

#### 4.6.2.4 Dual-Lane Gatekeeper

Before fusion, a gatekeeper filters out irrelevant results — preventing noise from entering the LLM's context:

- **Semantic lane:** the top FAISS cosine similarity score must be ≥ 0.35. If all FAISS scores are below this threshold, the semantic lane fails.
- **Lexical lane:** the RAW (unrewritten) customer utterance must contain at least one token that appears in the top BM25 document's text. If no match, the lexical lane fails.

Both lanes must fail for the query to be rejected. If either lane passes, retrieval proceeds normally. If both fail, the `search` tool returns an empty list — the agent responds with "Dạ, quán không có món đó ạ" rather than fabricating or guessing. This is safer than feeding noisy results to the LLM, which may hallucinate based on irrelevant retrieved text.

**Metadata post-filters.** After RRF fusion, result documents can be filtered by optional criteria: `max_price`, `min_price`, `diet_type` (e.g., "chay"), and `category` (e.g., "Lẩu"). Filters are applied via substring matching to the document metadata and only to documents of type "menu" (not supporting sources like restaurant info or customer profiles).

---

### 4.6.3 Result Rephrasing

After retrieval returns the top-5 fused dishes, the LLM in the response node evaluates and rephrases them. This is the third stage of the closed-loop — the search worker rewrote the query, the retriever found matching dishes, and now the response node grounds the reply in those dishes.

**What rephrasing does beyond listing results.** A raw list of returned dishes — "Lẩu Cá Tầm Măng Chua 250k, Súp Cua 120k, Cháo Hàu 90k" — is not a conversationally appropriate response. The response node receives the retrieved dishes in a `SearchResponseContext` and performs three operations:

1. **Relevance assessment:** The LLM evaluates each retrieved dish against the original customer intent. If the customer asked for "ấm bụng" dishes, Lẩu Cá Tầm and Cháo Hàu are relevant (hot, filling); Súp Cua is borderline (soup-based but not necessarily filling). The LLM can reorder or deprioritize results based on intent match.

2. **Vietnamese natural language generation:** The LLM produces a conversational reply: "Dạ, cho ngày lạnh quán mình có Lẩu Cá Tầm Măng Chua 250.000đ, Cháo Hải Sản 120.000đ, và Súp Cua 90.000đ ạ. Anh/chị muốn thử món nào ạ?" The reply includes prices (from metadata), natural Vietnamese particles ("ạ", "nha"), and a follow-up prompt that keeps the ordering conversation flowing.

3. **Empty result handling:** If retrieval returned no results (both gatekeeper lanes failed or no dishes matched the rewritten query), the LLM detects the empty context and generates an appropriate apology: "Dạ, quán mình không có món đó ạ. Anh/chị muốn xem thực đơn không ạ?" This prevents hallucination from empty retrieval — the LLM never fabricates a dish because no retrieval context exists to fabricate from.

---

### 4.6.4 Multi-Turn Search Context

Restaurant conversations span multiple turns. A customer may search for "Ốc Hương" in turn 3, add an item to their cart, then search for "Ốc Hương" again in turn 6. Without search context, the agent repeats the same search and presents the same results — the customer perceives the agent as forgetful and the conversation feels unnatural.

**The "ĐÃ BIẾT" mechanism.** The search worker's system prompt includes a dynamic "ĐÃ BIẾT" (already known) section that lists:

1. **Previous search results:** Items returned by the last `search()` call, retained in `AgentState.search_context` across turns. Each item includes the dish name and key attributes (price, category, taste profile).
2. **Cart items:** All dishes currently in the active cart (`AgentState.active_cart.items`). A customer who already ordered "Ốc Hương Xốt Trứng Muối" may ask about it later — the agent should know it's in the cart and not re-search.

When the LLM reads the "ĐÃ BIẾT" section before deciding whether to call `search()`, it can determine: "The customer is asking about Ốc Hương, which was already searched in turn 3. The results are known. I should answer from the existing search context rather than re-querying."

**Implementation.** The "ĐÃ BIẾT" context is injected into the search worker's system prompt at each turn by `chat_worker_node._to_curated_memory()`, which reads from `AgentState.search_context` and `AgentState.active_cart.items`. The mechanism is prompt-based and requires no additional state management infrastructure — it leverages the existing LangGraph conversation memory.

**Limitation.** Currently, `curated_memory` only populates from SEARCH turns, not from ORDER turns. Dishes ordered but never searched are invisible to follow-up questions. A customer who says "Cho 2 Ốc Hương" (no search) then asks "Cái đó có cay không?" receives "Không có trong thực đơn" because no search context exists for the ordered item. This is a known limitation documented in the implementation progress tracker (`inprogress.md`, Problem 1: Entity Tracker), addressed in a planned enhancement.

---

### 4.6.5 Index Lifecycle

The hybrid retrieval index is built offline and loaded at startup:

**Building.** The `builder.py` script in the retriever service orchestrates index construction:
1. `DocumentLoader` reads `menu.json`, `best_seller.json`, `restaurant_info.txt`, and `customer_info.json`.
2. FAISS index is built from all document embeddings (217 dishes + supporting sources).
3. BM25 index is built from tokenized document texts (via `underthesea.word_tokenize`).
4. Both indices are serialized to `storage/vector/faiss_index/` and `storage/vector/bm25.pkl`.

**Loading.** At agent startup (`server.py` warmup sequence), the `RetrieverManager` singleton loads both indices into memory. The FAISS index is loaded via `faiss.read_index()` with `allow_dangerous_deserialization=True` (a FAISS requirement that should be secured with checksum verification in production — see code review issue #25 in `tasks_on_section.md`). The BM25 index is loaded via `pickle.load()`.

**Rebuilding.** When the menu changes (items added, prices updated, categories reorganized), the index must be rebuilt. The `make reindex` target runs the builder, which regenerates both indices from the current menu. The agent service does not hot-reload indices — a restart is required after reindexing.

**Fingerprint verification.** To prevent embedding model/dimension mismatches, the FAISS index stores a fingerprint file recording the model name used at build time. On load, the retriever compares the current embedding model's identity to the fingerprint. A mismatch indicates that the embedding model has changed and the FAISS index must be rebuilt with the new model's dimensions.
