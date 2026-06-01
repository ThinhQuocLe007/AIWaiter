# 0006: Semantic Router Dataset — Deep Analysis of Problems

> **Subject:** Why the semantic router underperforms in specific cases, rooted in dataset design and the 1-NN algorithm.
> **Date:** 2026-05-31

---

## 1. Executive Summary

The semantic router achieves 91.25% accuracy on 80 eval cases, but the 7 failures reveal systematic — not random — problems in the utterance dataset and the 1-nearest-neighbor (1-NN) classification algorithm. This document explains *why* each problem exists at the embedding-space level.

### Root Cause Chain

```
1-NN algorithm (no centroid averaging)
    ↓ amplifies
Class imbalance (ORDER=46, PAYMENT=18)
    ↓ combined with
High lexical overlap (SEARCH ∩ PAYMENT = 14 shared words)
    ↓ combined with
Single global threshold (0.85) for all 4 intents
    ↓ combined with
Generic multilingual embedding model (BAAI/bge-m3)
    ↓ produces
7 systematic failures, all on "hard" difficulty cases
```

---

## 2. Algorithm: Why 1-NN Is the Wrong Choice

### 2.1 How It Works Now

```python
def route(self, query: str) -> Dict[str, Any]:
    query_vec = self.model.encode([query])
    best_route = None
    max_sim = -1.0
    
    for route_name, embeddings in self.route_embeddings.items():
        similarities = cosine_similarity(query_vec, embeddings)[0]
        current_max = np.max(similarities)  # ← takes max of individual utterances
        if current_max > max_sim:
            max_sim = current_max
            best_route = route_name
    
    return {
        "intent": best_route if max_sim >= self.threshold else None,
        "confidence": float(max_sim)
    }
```

The classification decision is: *"Which single utterance among all 118 utterances is the most similar to this query? Whatever its class is, that's the predicted intent."*

### 2.2 The Amplification Effect

With 1-NN, **more samples = more chance to win.** Here's why:

```
ORDER has 46 utterances spread across embedding space
PAYMENT has 18 utterances in a smaller region
CHAT has 19 utterances in a diffuse region  

→ A random query in the "ordering" region of space will find
  one of 46 ORDER candidates before it finds one of 18 PAYMENT candidates
  — simply because there are more of them.
```

This is why your eval shows 31/80 cases fast-tracked by SEMANTIC. The reviewer calibrated optimal per-intent thresholds:

| Intent | Optimal Threshold | Current | Effect |
|--------|-------------------|---------|--------|
| ORDER | 0.78 | 0.85 | **Underscores** — valid orders below 0.85 fall to SLM unnecessarily |
| SEARCH | 0.80 | 0.85 | Slightly undershooting |
| PAYMENT | 0.82 | 0.85 | Slightly undershooting |
| CHAT | 0.76 | 0.85 | **Overscores** — CHAT queries above 0.85 incorrectly fast-tracked |

Using one threshold for all intents is like judging a fish, a bird, and a dog by the same climbing ability.

### 2.3 The Fix: Centroid-Based Classification

Instead of matching against individual utterances, compute the **mean embedding** (centroid) for each intent class:

```python
def _encode_all_routes(self):
    for route_name, utterances in self.routes.items():
        embeddings = self.model.encode(utterances)
        self.route_centroids[route_name] = np.mean(embeddings, axis=0)  # ← centroid

def route(self, query: str) -> Dict[str, Any]:
    query_vec = self.model.encode([query])[0]
    similarities = {}
    for route_name, centroid in self.route_centroids.items():
        similarities[route_name] = cosine_similarity([query_vec], [centroid])[0][0]
    best_route = max(similarities, key=similarities.get)
    ...
```

**Why this helps:**
- Outlier utterances no longer dominate. The centroid averages away noise.
- Class imbalance is neutralized. 46 ORDER utterances and 18 PAYMENT utterances both produce exactly ONE centroid each.
- The centroid represents the *semantic center* of the intent, not individual phrasing quirks.

---

## 3. Utterance Dataset: Deep Structural Problems

### 3.1 The ORDER Intention Contamination

The ORDER utterances (45 total) contain **three semantically distinct sub-intents** that cluster in different regions of embedding space:

```
┌─────────────────────────────────────────────────────┐
│              ORDER utterance subtypes                │
├─────────────┬──────────┬────────────────────────────┤
│ Subtype     │ Count    │ Embedding characteristic    │
├─────────────┼──────────┼────────────────────────────┤
│ ORDER_PLACE │ 35       │ Specific food names,        │
│             │          │ quantities. High-dimensional│
│             │          │ unique pattern per item.    │
│             │          │ Example: "Cho 1 Bò Lúc Lắc  │
│             │          │ ko hành"                   │
├─────────────┼──────────┼────────────────────────────┤
│ ORDER_CONFIRM│ 8       │ Short, generic. No food     │
│             │          │ names. Close to CHAT space. │
│             │          │ Example: "Đúng rồi, đặt đi" │
├─────────────┼──────────┼────────────────────────────┤
│ ORDER_MODIFY│ 2        │ Cancel/substitute language. │
│             │          │ Unique vocabulary space.    │
│             │          │ Example: "Bỏ Mực Nướng..."  │
└─────────────┴──────────┴────────────────────────────┘
```

**The problem:** The centroid of all 45 utterances is pulled into a space that represents *none* of these subtypes well.

```
Visual (simplified 2D projection):

       ORDER_PLACE cluster
       (food names, quantities)
            ●  ●  ●
         ●    ●  ●
              ●     ●
                    ↗ CENTROID (pulled toward middle)
                    ‖
                    ‖
       CHAT space  ●──●  ORDER_CONFIRM cluster
       (greetings) ●  ●  (generic confirmations)
```

When the query is "Ừ, mình đồng ý với đơn đó" (RT-006 — ORDER_CONFIRM), it's semantically closest to the CHAT cluster because it has no food names and is polite/generic. Both the 1-NN and the centroid struggle because:
- 1-NN: The nearest PAYMENT or CHAT utterance might be closer than any ORDER_CONFIRM utterance
- Centroid: The ORDER centroid was pulled toward the food-name region by the 35 ORDER_PLACE samples

**Fix:** Either (a) split ORDER into two sub-groups with separate centroids, or (b) remove ORDER_CONFIRM from semantic utterances entirely and let the SLM router handle those (they *need* conversation context to disambiguate).

### 3.2 The SEARCH Intention Pollution

SEARCH utterances (37 total) mix two different semantic categories:

| Subtype | Count | Example |
|---------|-------|---------|
| Menu/info queries | 34 | "Phở bò giá bao nhiêu?", "Có món chay không?" |
| Facility queries | 3 | "Nhà vệ sinh ở đâu vậy?", "Có wifi không bạn?" |

These are **functionally the same** (both route to `search_worker`), but **semantically different**. The facility queries are closer to CHAT in embedding space (they're general questions, not food-specific). The mixed centroid slightly weakens SEARCH detection for menu-specific queries.

### 3.3 The SEARCH ↔ PAYMENT Lexical Overlap Problem

This is the single biggest source of failures (5 of 7). 14 words appear in both SEARCH and PAYMENT utterances:

| Shared Word | SEARCH Meaning | PAYMENT Meaning | Why It Confuses |
|-------------|---------------|-----------------|-----------------|
| `bao` / `nhiêu` | "Giá bao nhiêu?" (how much does X cost?) | "Tổng bao nhiêu?" (what's the total?) | Identical words, different context |
| `xem` | "Xem thực đơn" (show menu) | "Xem hóa đơn" (show bill) | Same verb, different object |
| `cho` | "Cho tôi xem..." (let me see...) | "Cho tôi xem hóa đơn" (let me see bill) | Same phrase prefix |
| `đơn` | "Thực đơn" (menu — literally "food list") | "Hóa đơn" (bill/invoice) | `đơn` appears in both compounds |
| `ăn` | "Món ăn" (food) | "Trả tiền ăn" (pay for meal) | Context-dependent |

**Why cosine similarity fails here:** Embedding models like BAAI/bge-m3 encode these words similarly regardless of context. The phrase "Cho tôi xem hóa đơn" (PAYMENT) and "Cho tôi xem thực đơn" (SEARCH) produce highly similar embedding vectors because:

```
cosine_sim("Cho tôi xem hóa đơn", "Cho tôi xem thực đơn") ≈ 0.85+
cosine_sim("Cho tôi xem hóa đơn", "Tính tiền giùm")       ≈ 0.70
```

The **prefix overlap** dominates the cosine similarity, and the **object noun** (hóa đơn vs thực đơn) is only a small part of the 1024-dim vector.

**This is the root cause of RT-046, RT-069, RT-078, and RT-079 failures.**

#### Case Study: RT-046 Failure

```
Query:    "Bàn mình gọi 3 món rồi, tổng hết bao nhiêu rồi nhỉ?"
Expected: PAYMENT
Got:      SEARCH

Why:
1. "bao nhiêu" appears in 1 SEARCH utterance, 3 PAYMENT utterances
2. But the SEARCH utterance "Phở bò giá bao nhiêu?" also has food names ("Phở bò")
   which make it semantically similar to a query containing "món"
3. The query says "3 món" (3 dishes) — the word "món" is the #1 most frequent
   SEARCH word (23 occurrences) but only appears implicitly in PAYMENT
4. 1-NN finds the closest match, and the composite embedding leans SEARCH
   due to "món" + "bao nhiêu" appearing together
```

#### Case Study: RT-069 Failure

```
Query:    "Cho mình xem tổng hóa đơn, nếu dưới 200k thì gọi thêm Chè Khúc Bạch"
Expected: [PAYMENT, ORDER]  (check bill first, then conditionally order)
Got:      [SEARCH, ORDER]   (xem hóa đơn → SEARCH)

Why:
"Cho mình xem tổng hóa đơn" lexical structure:
  "Cho mình xem" → common in SEARCH (Cho mình xem thực đơn)
  "tổng hóa đơn" → PAYMENT vocabulary

The prefix "Cho mình xem" matches SEARCH patterns with high cosine similarity,
overpowering the object "hóa đơn". The SLM few-shots also lack PAYMENT examples
with the "xem hóa đơn" pattern.
```

### 3.4 The Class Imbalance Problem: Quantified

| Intent | Utterance Count | Eval Cases | Utterances/Case |
|--------|-----------------|------------|------------------|
| ORDER | 45 | 18 (+15 multi) | 2.5x coverage |
| SEARCH | 37 | 18 (+15 multi) | 2.0x coverage |
| PAYMENT | 18 | 14 (+15 multi) | 1.3x coverage |
| CHAT | 19 | 15 | 1.3x coverage |

PAYMENT has 2.5x fewer training utterances than ORDER but faces a similar number of eval cases. With 1-NN, this means:
- A query that is *genuinely* PAYMENT has only 18 candidates to match against
- If any of those 18 is poorly phrased or produces weird embeddings, the fallback options are limited
- Meanwhile, ORDER has 45 chances to accidentally win a close call

### 3.5 Missing PAYMENT Utterance Patterns

The following payment-related vocabulary is **completely absent** from the utterances file:

```
Missing words: tách, chia, momo, chuyển, khoản, vietqr, qr, invoice
```

This means the semantic router has **zero embedding representations** for:
- "Chia đôi hóa đơn" (split bill evenly)
- "Tính riêng từng người" (separate checks)
- "Trả bằng MoMo" (pay via e-wallet)
- "Chuyển khoản" (bank transfer)
- "Cho mình cái QR" (show QR code)

These are all real customer utterances in Vietnamese restaurants. Without them in the dataset, any PAYMENT query using this vocabulary will fail to find a close match and may be routed to SEARCH or CHAT instead.

### 3.6 Near-Duplicate Utterances Waste Capacity

In the ORDER category, many utterances follow the same structural pattern:

```
Pattern: [verb] [quantity] [item_name] [optional_note]

"Cho tôi 2 bát Phở Bò Đặc Biệt"
"Lấy cho mình 3 ly Sinh Tố Bơ Dừa nhé"
"Cho mình 2 Nem Nướng Nha Trang và 1 Súp Cua Tóc Tiên"
"Đặt 3 ly Cà Phê Sữa Đá Sài Gòn"
"Gọi 1 Lẩu Thái Tomyum Hải Sản cho bàn mình"
"Cho 2 phần Bò Nướng Đá Cuội"
"Lấy 1 Cơm Tấm Sườn Bì Chả với 1 Bò Kho Bánh Mì"
```

These are **structurally identical** — only the item names differ. The embedding model encodes them as nearly identical vectors because:
- Verbs ("cho", "gọi", "lấy", "đặt") are synonyms → similar embeddings
- Item names are the only distinguishing factor → small contribution to overall similarity
- BAAI/bge-m3 was not specifically trained on Vietnamese food names → "Phở Bò Đặc Biệt" and "Sinh Tố Bơ Dừa" may not produce strongly distinct embeddings

**Impact:** 20 near-duplicate ORDER utterances add less information than 5 diverse ORDER_MODIFY or ORDER_CONFIRM utterances would. The per-utterance information gain diminishes sharply after ~15 training examples of the same structure.

---

## 4. Embedding Model: Wrong Tool for the Job

### 4.1 BAAI/bge-m3 Characteristics

`BAAI/bge-m3` is a **general-purpose multilingual embedding model** trained on 100+ languages with a contrastive learning objective. It was designed for cross-lingual document retrieval, not for Vietnamese intent classification.

Key limitations for this use case:

1. **No Vietnamese-specific fine-tuning.** Vietnamese is tonal, monosyllabic, and has different word boundary rules than English/Chinese. bge-m3 treats Vietnamese words with the same tokenizer as English, missing tonal distinctions.

2. **Vocabulary coverage issues.** Vietnamese restaurant-specific vocabulary ("nướng", "chiên", "xào", "lẩu", "kho", "hấp") may map to generic multilingual tokens that don't capture their culinary meaning.

3. **No restaurant domain adaptation.** "Tính tiền" (pay) and "tính toán" (calculate) share the token "tính" but mean different things. bge-m3 treats them similarly.

4. **Synonyms not encoded.** In Vietnamese food ordering, "gọi", "đặt", "lấy", "cho" are all synonymous verbs meaning "order." bge-m3 encodes them as different tokens and relies on context to group them — but with short queries (5-15 words), there isn't enough context.

### 4.2 Comparison with Vietnamese-Specific Alternative

| Property | BAAI/bge-m3 (current) | keepitreal/vietnamese-sbert |
|----------|----------------------|---------------------------|
| Training languages | 100+ (multilingual) | Vietnamese only |
| Vietnamese vocabulary | Generic tokenizer | PhoBERT-based tokenizer |
| Tonal awareness | Limited | Full (Vietnamese phoneme-aware) |
| Restaurant domain | Unknown | Unknown (but VN-specific helps) |
| "gọi" vs "đặt" vs "lấy" | Different tokens | Better synonym grouping |
| Embedding dimension | 1024 | 768 |

**Note:** Even `keepitreal/vietnamese-sbert` was not trained on restaurant-specific data. Testing is required to confirm improvement. The theoretical advantage is the Vietnamese tokenizer and tonal awareness.

---

## 5. Eval Dataset Alignment Issues

### 5.1 Terminology Inconsistency

The eval dataset header says:
```json
"routes": ["ORDER", "SEARCH", "PAYMENT", "CHAT", "COMPLEX"]
"cases_per_route": {"ORDER": 18, "MENU": 18, ...}
```

- Route list uses `SEARCH` but `cases_per_route` uses `MENU`
- `COMPLEX` appears in routes but the codebase replaced it with multi-intent lists (`["ORDER", "PAYMENT"]`)
- RT-054 through RT-065 label facility/restaurant-info queries as `SEARCH` when they could reasonably be `CHAT`

### 5.2 Missing Eval Case Types

The 80 eval cases have good coverage of the main intents but lack:

- **Temporal ambiguity:** "Lúc nãy tôi đã gọi rồi mà" (I already ordered) — is this ORDER (follow-up) or CHAT (complaint)?
- **Multi-turn context:** Cases that test whether the router remembers previous intents
- **Code-switching:** "Cho mình 1 phở bò please, và check bill luôn" (mixed VN/EN)
- **Extreme teencode:** "ck bill gium, e ditrui" → ("check bill giùm, em đi thôi")

---

## 6. Fix Plan (Priority-Ordered)

### P1: Algorithm Fix (1 Day)

| Step | What | Lines | Expected Impact |
|------|------|-------|-----------------|
| 1 | Switch from 1-NN to centroid-based classification | ~15 | Eliminate class imbalance bias |
| 2 | Implement per-intent thresholds: (ORDER=0.78, SEARCH=0.80, PAYMENT=0.82, CHAT=0.76) | ~10 | Reduce false positives/negatives |
| 3 | After centroid, compute `softmax` over similarities for confidence calibration | ~5 | Better confidence signal for hybrid router |

**Expected accuracy improvement:** 91.25% → ~94-95% (estimated from the 5 SEARCH/PAYMENT confusion cases that centroids + per-threshold would fix)

### P2: Dataset Fix (2-3 Hours)

| Step | What | Add/Remove | Impact |
|------|------|------------|--------|
| 4 | Add 15 diverse PAYMENT utterances (split bill, e-wallet, casual) | +15 to PAYMENT | Fix class imbalance, add missing vocabulary |
| 5 | Remove 8 ORDER_CONFIRM utterances from semantic dataset | -8 from ORDER | Let SLM handle these with conversation context |
| 6 | Add 5 ORDER_MODIFY utterances | +5 to ORDER | Fill semantic gap for cancel/change operations |
| 7 | Remove 15 near-duplicate ORDER_PLACE utterances | -15 from ORDER | Reduce noise, keep only structurally diverse samples |
| 8 | Add 3 PAYMENT-specific few-shots to router.json with "xem hóa đơn", "bao nhiêu tổng", split bill | +3 to router.json | Fix SLM router's SEARCH/PAYMENT confusion |

**Net effect:** Better balanced, less noisy, more diverse utterance space.

### P3: Model Test (1 Hour)

| Step | What | Effort |
|------|------|--------|
| 9 | Swap BAAI/bge-m3 → keepitreal/vietnamese-sbert | 1 line |
| 10 | Re-run eval suite, compare accuracy per intent | Run script |

If Vietnamese model improves accuracy by >2%, adopt it. Otherwise, keep bge-m3.

### P4: Eval Expansion (2 Hours)

| Step | What | Add |
|------|------|-----|
| 11 | Add 20 eval cases: split bill, e-wallet, teencode, code-switching, multi-turn context | +20 to router_eval.json |
| 12 | Split eval category from "hard" into "lexical_ambiguous" and "context_dependent" | Refactor difficulty labels |

---

## 7. Expected Post-Fix Architecture

```
Current:
  query → 1-NN cosine against 118 individual utterances → single global threshold 0.85 → intent

After Fix:
  query → cosine against 4 centroids (ORDER, SEARCH, PAYMENT, CHAT) → per-intent thresholds → intent
           ↓
  Centroids computed from:
    ORDER (35):  diverse place + modify utterances, NO confirmations
    SEARCH (34): menu/info only, NO facility queries
    PAYMENT (33): balanced: confirm + split + e-wallet + casual
    CHAT (19):  greetings + complaints + small talk
```

This gives the semantic router a fair fight: 4 centroids, each representing the clean semantic center of its intent, judged by intent-specific thresholds calibrated from eval data.

---

## References
- [ADR 0005: Comprehensive Review](file:///home/lequocthinh/Desktop/KNOWLEDGE_HUB/CODE/AI_Waiter/docs/0005-comprehensive-review-limitations-and-improvements.md) — Section A
- `semantic_router_node.py:31-47` — Current 1-NN implementation
- `utterances.json` — 118 training utterances
- `router.json` — 14 SLM few-shot examples
- `evals/data/router/router_eval.json` — 80 eval cases
