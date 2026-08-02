# Chapter 5 — Collected Evaluation Results

**Last updated:** 2026-07-30.  Each table cites the experiment and the result file that
produced it.  Section numbers reference the current outline.

> **PENDING-14B:** the router LLM arms (B, C, F) and all agent-level experiments (§5.4.3, §5.4.5,
> §5.4.6) are awaiting their run on the deployment server. What is final below and needs no re-run:
> the MLP classifier results (§5.4.1 arms A and D), name resolution and ambiguity (§5.4.2), and
> retrieval (§5.4.4), which are deterministic or independent of the language model.

**Model state — v2 classifier (2026-07-30).**  The MLP router was retrained as a text-only
model on 1 639 hand-written utterances (`corpus_v2.json`), with no context features and no
context augmentation.  The earlier 778-dim context-augmented model was discarded.  All
deterministic router experiments were re-run on the v2 checkpoint at
`src/training_semantic_router/classifier/saved_v2/model.pt`.

The MLP router is trained on a **manually curated dataset** of 1 639 spoken Vietnamese
utterances against the real restaurant menu (`assets/data/menu.json`, 234 dishes).  No
LLM was used for generation.  The corpus is text-only — no context features, no
augmentation — and the training split is grouped by utterance (`GroupShuffleSplit`) to
prevent leakage.

The router follows a **single-intent classification** architecture: the MLP predicts one of
four intents (ORDER, SEARCH, PAYMENT, CHAT) with a confidence score.  If the utterance
contains multi-clause boundary markers (`rồi`, `và`, `thì`, `xong`, `rồi thì`, `với lại`,
`à mà`, `,mà`) or if the confidence falls below 0.7, the utterance is sent to the rewriter
for decomposition into single-intent fragments, each classified independently by the MLP.

---

## §5.4.1 — Intent Classification & Routing

### Single-Intent Accuracy (n = 149, `evals/data/router/single_intent_eval.json`)

**142/149 = 95.3 %** (Wilson 95 % CI: 90.6–97.8 %).  p50 latency 8.2 ms, p95 11.4 ms.

*Result file:* `mlp_router_eval_20260730_001724.json`.  Re-run on the v2 text-only classifier
(2026-07-30).  The previous v1 context-feature classifier scored 140/149 (94.0 %); the v2
improvement of 2 points comes from the cleaner text-only corpus with no context-induced label
noise.

Mean confidence on correct predictions: 0.975.  Mean confidence overall: 0.969.

| Class | Precision | Recall | F1 | Support |
|-------|:---------:|:------:|:----:|:-------:|
| ORDER | 0.950 | 1.000 | 0.974 | 38 |
| SEARCH | 0.881 | 1.000 | 0.937 | 37 |
| PAYMENT | 1.000 | 1.000 | 1.000 | 37 |
| CHAT | 1.000 | 0.811 | 0.896 | 37 |

The CHAT class has the lowest recall (81.1 %): 7 utterances were misclassified, 5 toward SEARCH
and 2 toward ORDER. Five of the seven errors are sentences where the customer uses restaurant
vocabulary in a conversational context ("Quán này mới mở hả em" → SEARCH, "Tôi có con nhỏ, quán
có ghế em bé không" → SEARCH). The text-only model has no stage awareness to distinguish
conversational uses of restaurant terms from transactional ones, and these errors will route
through the rewriter path.  PAYMENT maintained perfect classification across all 37 cases.
ORDER and SEARCH both achieved perfect recall (1.000).

### Context-Dependent Accuracy (n = 123, `evals/data/router/context_dependent_eval.json`)

| Measure | Accuracy | n |
|------|:--------:|:--:|
| Text-only accuracy on context-dependent utterances | 48.0 % (59/123) | 123 |

*Result file:* `mlp_router_eval_20260730_001724.json`.  The dataset was expanded from 70 to
123 cases (38 utterance groups) on 2026-07-30 to cover a broader range of context-dependent
utterances.  The 64 errors are dominated by ambiguous affirmations ("ok", "ừ", "chuẩn") at
IDLE routing to ORDER instead of CHAT, or postponement utterances ("thôi", "để lát đi",
"khoan đã") at AWAITING_CONFIRMATION routing to CHAT instead of ORDER.

**DO NOT report this as a with/without-context ablation.**  Earlier runs printed a
"with context" and a "without context" row and they were identical, but that was an artifact,
not a finding: `predict.classify()` accepts a `state` argument and ignores it, so both rows
executed the same text-only code path and could not have differed.  The comparison was removed
from `eval_mlp_router.py` on 2026-07-30.  Whether context features would help here is
**unmeasured**; answering it needs a model retrained with the context block on this corpus.

### Multi-Intent Detection (n = 27, `evals/data/router/multi_intent_detection.json`)

**24/27 = 88.9 % detected.**  By boundary markers: 22.  By low confidence: 4.

The 3 undetected cases have no lexical boundary marker ("Chốt đơn với bill luôn đi em",
"Cảm ơn em, cho anh xin bill luôn nha", "Gọi 1 lẩu thái nha, trời mưa ăn lẩu là đúng bài").
2 false alarms on 3 pseudo-multi-intent controls — both harmless overhead.

### Router Ablation (n = 360 pooled, `evals/results/router_arms_20260730_002059.json`)

**Only arm F is defective in this run.**  Its 113/360 = 31.4 % is exactly the number of CHAT
items in the pool (113), which is the signature of the harness recording a fallback label on
every call rather than a measurement.  F is excluded from the chapter.

Arms B and C are weak but valid, and must not be described as broken: B scores 167/360 and C
246/360, both above the 113 a single-label CHAT guess would produce, and C at 68.3 % sits where
a hybrid inheriting the semantic stage should, next to arm A at 69.7 %.  This matters because
§5.4.1 uses C as the baseline for the chapter's headline claim (McNemar p = 0.001); if C were
defective that claim would collapse, and it is not.

Arms A (centroid) and D (MLP) are deterministic.  The proposed arm D is significantly above the
centroid baseline at 77.2 % vs 69.7 %, with comparable latency (~9 ms p50).

Arm E has been **removed** from `eval_router_arms.py` (2026-07-30).  It was billed as "MLP +
context" but loaded the same `saved_v2` text-only model as arm D through a `state` argument
`predict.classify()` ignores, so its byte-identical result was guaranteed by construction and
measured nothing.  Any older result file still carrying an arm E should be read as a duplicate
of arm D.

| Arm | System | n correct | Accuracy | 95 % Wilson CI | p50 (ms) | p95 (ms) |
|-----|--------|:---------:|----------|---------------:|---------:|---------:|
| A | Centroid (semantic only) | 251 | 69.7 % | 64.8–74.2 % | 10.2 | 12.1 |
| B | SLM only (qwen2.5:3b) | 167 | 46.4 % | 41.3–51.6 % | 194.4 | 211.0 |
| C | Hybrid semantic→SLM (previous production router) | 246 | 68.3 % | 63.4–72.9 % | 11.2 | 716.6 |
| **D** | **MLP, text-only (proposed)** | **278** | **77.2 %** | **72.6–81.2 %** | **9.2** | **11.0** |
| ~~F~~ | ~~LLM zero-shot~~ | ~~113~~ | ~~31.4 %~~ | excluded, fallback artifact | 2 | 3 |

### Clean Holdout (n = 39)

**38/39** (Wilson 95 % CI: 86.8–99.5 %).  The holdout was partitioned before any training.
One remaining error, HO-021: "có món gì hợp cho nhóm 4 người nhậu không" (SEARCH predicted as
ORDER, confidence 0.643, below the 0.7 deployment threshold — routes to rewriter).

*Result file:* `src/training_semantic_router/data/eval_report.json`.

---

## §5.4.2 — Action Validation & Safety

### Name Resolution by Stage (n = 70 pairs)

*Result file:* `name_resolution_20260719_000825.json` (2026-07-19).  A run 67 seconds earlier
(`..._000718.json`) reports 14/70; the harness was corrected between the two and only the later
run measures the resolver.  These are pure-Python validator functions and do not depend on the
classifier, so the 2026-07-19 date does not invalidate them, but they should be re-run if
`menu.json` changes.

| Resolution stage | Correct | Total | Accuracy |
|------------------|:-------:|:-----:|:--------:|
| Exact match | 15 | 15 | 100 % |
| Diacritic-insensitive | 10 | 10 | 100 % |
| Prefix match | 10 | 10 | 100 % |
| Substring match | 10 | 10 | 100 % |
| Token-Jaccard (match) | 5 | 5 | 100 % |
| Token-Jaccard (reject) | 4 | 4 | 100 % |
| Misspelled (correctly rejected) | 16 | 16 | 100 % |
| **Total** | **70** | **70** | **100 %** |

### Ambiguity Detection (n = 25 cases)

| Metric | Value |
|--------|-------|
| Accuracy | 100 % (25/25) |
| True positives | 15 |
| False positives | 0 |
| False negatives | 0 |

All 15 ambiguous prefixes (e.g. "Ốc Hương" matching 11 sauce variants) correctly flagged for
clarification.  All 10 unambiguous full names correctly resolved.  QS-005 in §5.4.5 shows this
behaviour end to end on a live turn.

*Result file:* `ambiguity_20260719_000719.json` (2026-07-19, deterministic validator function).

### Validator Ablation — ON vs. OFF (n = 41 scenarios each)

| Condition | Pass rate | Off-menu items in cart tools | Bad confirm_order calls |
|-----------|:---------:|:---------------------------:|:-----------------------:|
| Validator ON | 92.7 % (38/41) | **0** | 1 |
| Validator OFF | 92.7 % (38/41) | **31** | **8** |

*Result files:* `validator_ablation_validator_on_20260726_005518.json`, `validator_ablation_validator_off_20260726_010039.json`.

Off-menu items are detected by resolving each item name in `add_cart` and `confirm_order`
tool calls against `menu.json`, not by reading the validator's `is_valid` flag — the OFF arm
has no validator to set the flag, and a measurement based on it would report zero by
construction.  With the validator bypassed, 31 hallucinated dish names from 14 distinct
scenarios reach cart tools, and 8 `confirm_order` calls contain at least one off-menu item.
The validator blocks all of them — the ON arm has zero off-menu items in any cart tool.

The 1 bad `confirm_order` in the ON arm is a `confirm_order` call with an empty item list or
a tool call produced at the wrong order stage; the validator catches the anomaly but the
response node still verbalises a confirmation.  This is a distinct failure mode from a bad
tool call — the validator protects state but the response layer can still fabricate text.

Both arms are single runs.  The scope of the safety claim is stated precisely by QS-007 in
§5.4.5: the validator gates dish names against `menu.json`, so it blocks off-menu names, but it
does not verify that a named item is present in the cart, and a `remove_cart` naming a valid
menu item the customer never ordered passes through unchallenged.

### Out-of-Menu Robustness (n = 30 scenarios, 7 categories)

**Pass rate: 93.3 %** (28/30).  Two failures: OOM-008 (off-menu item entered as false-positive
near-match) and OOM-016 (all 3 items entered cart including one invalid).

*Result file:* `e2e_out_of_menu_report.json`, re-run 2026-07-26 against the current classifier.
The outcome is unchanged from the 2026-07-23 run, same pass rate and the same two failing
scenarios, which is what one would expect since off-menu rejection is decided by the
deterministic validator rather than by the router.  The earlier run is preserved as
`e2e_out_of_menu_report_20260723_232041.json`.  Note that this script writes to a fixed filename
rather than a timestamped one and will overwrite itself on the next run; it should be brought in
line with the other eval scripts.  Single run: the script has no `--runs` flag.

### Delegate Escape Hatch (n = 90 turns across 45 scenarios)

*Result file:* `delegate_baseline_20260726_145113.json`.  Re-run 2026-07-26 against the current
classifier, single run (the script has no `--runs` flag).

| Metric | Result | Previous (2026-07-19) |
|--------|--------|-----------------------|
| Scenarios / turns | 45 / 90 | 19 / 62 |
| Total delegate calls | 3 | 1 |
| Delegate rate | **3.33 %** (3/90) | 1.61 % (1/62) |
| Potential wrong tool calls (delegate unbound) | **0** | 0 |

**The two runs are not directly comparable.**  `eval_delegate.py` pools several datasets, and the
out-of-menu set grew from 4 to 30 scenarios between the runs, taking the pool from 19 scenarios
to 45.  The rate rose from 1.61 % to 3.33 % mainly because the added scenarios are adversarial
off-menu cases, which are exactly the inputs a worker should abstain on.  Both figures sit
comfortably under the 5 % threshold §5.2.2 sets for a well-matched prompt and tool set.

All three delegations are correct decisions to abstain:

| Scenario | Utterance | Reason given |
|----------|-----------|--------------|
| OOM-007 | "Quán có bánh xèo không em, cho anh 2 cái" | asks about a dish, not an order request |
| OOM-025 | "Cho bàn anh Combo Hải Sản Cho 4 Người giá 500k" | invented combo, not a search request |
| REAL-002 | "Món Khoai Tây Lắc Phô Mai có hải sản không em?" | food-information question, not an order |

The most valuable number here remains the zero in the last row: across 90 turns, no turn produced
a wrong tool call that the delegate mechanism was needed to prevent and failed to.

**A defect in the metric, not the mechanism.**  All three delegate records carry
`"worker": "unknown"`, so the per-worker breakdown reports 0 ORDER and 0 SEARCH delegations
despite 3 delegate calls being logged.  The previous run attributed its single delegate to the
ORDER worker, so the attribution has regressed and the per-worker rows §5.2.2 asks for cannot
currently be produced.  The `routed_to` field is populated correctly (`chat_worker` in all three
cases); only the originating worker is lost.  This needs fixing before the per-worker rates are
quoted.

QS-006 in §5.4.5 shows two further correct delegations on live turns, one for a price question
and one for a cart read-back.  QS-007 shows the mechanism's limit: `delegate` helps when the
worker recognises that no tool applies, but not when it wrongly believes one does and supplies
hallucinated arguments.

---

## §5.4.3 — Multi-Intent Execution & Verbalisation (n = 25 turns, N = 5 runs)

*Result file:* `multi_intent_20260726_151402.json`, 5 repetitions, zero connection errors in the
run log.  This experiment satisfies the N = 5 protocol of §5.2.3.  Values are mean [min-max]
across runs.  Awaiting the deployment-server run; see the banner at the top of this file.

### The measurement was wrong before the system was

The per-case `evidence` lists in `multi_intent_eval.json` enumerate happy-path wording only.
MI-011, "Thêm 1 Bia Sài Gòn nữa và cho xin mã QR thanh toán", executes both intents and answers
both: a cart summary followed by "hiện chưa có đơn hàng nào trong phiên này ạ".  Its PAYMENT
evidence is `["qr", "mã", "thanh toán", "chuyển khoản"]`, none of which appear in a correct
refusal, so the metric scored PAYMENT as never verbalised.  Any correct negative outcome was
counted as a verbalisation failure.

The fix is a single uniform rule in the scorer rather than 25 hand-edited evidence lists, because
widening lists case by case after seeing which ones fail tunes the metric to the output.  An
intent now counts as verbalised when the customer learns the fate of that request, success or
correct refusal.  The negative-outcome phrasings are copied from the agent's own response
templates, not written to fit observed failures:

| Intent | Negative-outcome evidence | Source |
|--------|---------------------------|--------|
| PAYMENT | `chưa có đơn hàng` | `response_node.py`, request_payment with no order in session |
| ORDER, SEARCH | `không có trong thực đơn` | `response_template.py`, off-menu rejection (3 call sites) |

The generic failure string `có lỗi khi xử lý đơn` is **deliberately excluded**: it tells the
customer that something went wrong without saying which request it concerns, so it is not
evidence that any particular intent was verbalised.  The script computes and reports both rules.

### Results under both rules

| Rule | Verbalisation rate | Fully verbalised turns |
|------|--------------------|------------------------|
| Strict (happy-path evidence only) | 0.625 [0.567-0.667] | 0.456 [0.400-0.520] |
| **Corrected (+ contentful negative outcomes)** | **0.725** [0.667-0.767] | **0.576** [0.520-0.640] |

Coverage of what the customer asked: **0.747** [0.700-0.780].  Router queued all expected
intents: **60.0 %** (15/25, identical in every run, as expected for a deterministic classifier).

**An independent check that isolates the rule from sampling.**  Re-scoring the previous run's
125 stored replies under both rules gives 0.613 strict against 0.733 corrected for verbalisation,
and 0.408 against 0.568 for fully-verbalised turns.  Because the replies are identical in that
comparison, the roughly 12-point and 16-point gaps are attributable to the measurement rule
alone.  The fresh run above reproduces both the levels and the size of the gap, with wider
intervals as expected from a new sample.

### Against the previous router

| Metric | Now (current router, corrected rule) | 2026-07-23 (old router, strict rule) |
|--------|--------------------------------------|--------------------------------------|
| Router queued all expected intents | **60.0 %** | 44.0 % |
| Coverage of what the customer asked | **74.7 %** [70.0-78.0] | 51.3 % |
| Mean verbalisation rate | **72.5 %** [66.7-76.7] | 47.3 % |
| Fully verbalised turns | **57.6 %** [52.0-64.0] | 40.0 % |

Two changes are compounded here and must not be attributed to one cause: the hand-curated
training corpus improved routing, and the corrected rule stopped penalising correct refusals.
The strict column in the previous table separates them.  Under the strict rule alone, the corpus
change moved fully-verbalised turns from 40.0 % to 45.6 %; the measurement fix carried the rest
of the way to 57.6 %.

### What remains is specific

Across all 5 runs there are 53 turns carrying at least one executed-but-unspoken intent, and they
are not scattered:

| Pattern | Losses (of 53) | Which side is lost |
|---------|:--------------:|--------------------|
| ORDER + SEARCH in one turn | 26 | the SEARCH result |
| ORDER + PAYMENT in one turn | 15 | the ORDER acknowledgement |
| Router misrouted a single-intent turn | 7 | not a response-layer failure |
| Other | 5 | |

**The defensible statement is therefore not "the response layer drops intents".**  It is that
when an ordering action is combined with a second intent in the same turn, one of the two
consistently goes unspoken, and which one is lost depends on the pairing: SEARCH loses to ORDER,
and ORDER loses to PAYMENT.  41 of 53 losses, roughly 77 %, have that shape.  This is narrow
enough to diagnose rather than merely report.

**The previously suspected mechanism is not the cause.**  `state_outcome._pick_tool_messages`
already returns every `ToolMessage` since the last user turn and builds one `ResponseContext` per
tool, and `response_node` iterates the list and joins all replies.  Aggregation is implemented end
to end; the note in `tasks_on_section.md` describing a single-context selection has been corrected.
QS-003 in §5.4.5 confirms aggregation working on a live two-intent turn.

**One caution on reading the table.**  The per-intent-count breakdown that earlier revisions
reported has been dropped.  Both the old 11.1 %-at-three-intents figure and its replacement rest
on two or three turns, so neither carries useful precision and neither should be presented as a
trend.  The only well-populated case is the two-intent turn, at 19 of 25 cases.

## §5.4.4 — Knowledge Retrieval (n = 24 queries)

### Retrieval Quality — BM25 / FAISS / RRF

*Result file:* `retrieval_full_20260726_004318.json`.

| Mode | P@5 | R@5 | MRR | Hit Rate | Latency p50 |
|------|:----:|:----:|:----:|:--------:|:-----------:|
| BM25 only | 0.367 | 0.719 | 0.720 | 0.875 | 8.8 ms |
| FAISS only | 0.315 | 0.523 | 0.663 | 0.792 | 422 ms |
| **RRF fusion** | **0.400** | **0.743** | **0.751** | **0.917** | 9.7 ms |

### Per-Difficulty (RRF)

| Difficulty | n | P@5 | R@5 | MRR | Hit Rate |
|------------|:--:|:----:|:----:|:----:|:--------:|
| Easy | 8 | 0.425 | 0.865 | 1.000 | 1.000 |
| Medium | 9 | 0.444 | 0.907 | 0.722 | 1.000 |
| Hard | 7 | 0.314 | 0.391 | 0.505 | 0.714 |

### Dual-Lane Gatekeeper (n = 24 queries)

| Category | Count |
|----------|:-----:|
| Both lanes pass | 20 |
| Lexical-only pass | 3 |
| Semantic-only pass | 0 |
| Correctly rejected | 1 |
| Total passed | 23 (95.8 %) |

*Result file:* `retrieval_full_20260726_004318.json`.

The gatekeeper correctly rejects one query ("có gì cho nhóm đông người chia sẻ") where
neither the semantic lane (cos = 0.195) nor the lexical lane found a keyword match.
Top-1 cosine scores range from 0.165 to 0.581 across the 24 queries, all within the valid
[0, 1] interval — the earlier cos > 1.0 anomaly was caused by an embedding-model
configuration mismatch resolved by the float32 pinning and model-name fix in commit
`f308a1a`.  The semantic lane never passes independently because the lexical lane is strong
on nearly all menu queries; on 20 of 24 queries both lanes agree to admit the query.
The 3 lexical-only passes occur on queries where the semantic similarity is low
(cos = 0.165–0.278) but a keyword match in the top-ranked document confirms relevance.

---

## §5.4.5 — End-to-End System Evaluation (Qualitative)

Rather than aggregate a pass rate across many scenarios, which at a sample of 20 yields a
Wilson CI too wide for a decisive claim, this section reports a **qualitative case study**
of seven curated scenarios, each exercising a distinct architectural claim.  Every turn is
shown with the tool calls produced, the agent's spoken reply, the committed order stage and
the assertion outcome.

*Result file:* `e2e_qualitative_20260726_141829.json` (30 turns, single run).

**Run hygiene.**  This run is the first with isolated state.  Earlier runs of this experiment
used a fixed `thread_id` per scenario, so each run resumed the previous run's conversation and
inherited its cart, while the orchestrator's order ledger accumulated across runs.  Cart totals
and bills in any earlier qualitative result file are inflated by whatever ran before them and
must not be quoted.  The runner now derives a run-unique thread id and clears both the
checkpoint store and the transactional tables before starting, matching `eval_e2e.py`.
The order stage and validity fields reported below are read from committed graph state; in
earlier runs they were scraped from a node key that did not exist and serialised as null
throughout.

### Scenario Inventory

| ID | Category | Claim Tested | Outcome |
|----|----------|-------------|:-------:|
| QS-001 | Happy path | Complete order→confirm→pay pipeline | **PASS** |
| QS-002 | Search→order | SEARCH worker, search_context persistence, referential ordering | **PASS** |
| QS-003 | Multi-intent | Boundary marker `rồi` triggers rewriter, ORDER+PAYMENT split | **PASS** |
| QS-004 | Modification | Remove, add, incremental build; cart integrity after mutation | **PASS** |
| QS-005 | Ambiguity | Validator flags `Ốc Hương` (11 variants), clarifies, customer selects | **PASS** |
| QS-006 | Long conversation | 12-turn state integrity: browse→order→recommend→modify→confirm→pay | **FAIL** |
| QS-007 | Off-menu | Validator rejects `Phở Bò Tái` & `Cơm Tấm Sườn`; LLM fails vague removal | **FAIL** |

**5 of 7 scenarios pass.**  Both failures are analysed below; each isolates a distinct boundary
of the architecture rather than a random defect.

### QS-001 — Happy Path (PASS)

```
[Khách]    Cho mình 2 Ốc Hương Xốt Trứng Muối với 1 Lẩu Thái nha
[Tools]    add_cart(Ốc Hương Xốt Trứng Muối ×2, Lẩu Thái ×1)
[Stage]    AWAITING_CONFIRMATION   cart 425.000₫
[AI Waiter] Dạ, giỏ hàng của anh/chị hiện có:
            - Ốc Hương Xốt Trứng Muối ×2 (85.000₫/phần)
            - Lẩu Thái ×1 (255.000₫/phần)
            Tổng tạm tính 425.000. Anh/chị xác nhận đặt hàng chưa ạ?

[Khách]    Ok chốt đơn đi em
[Tools]    confirm_order(items=[Ốc Hương Xốt Trứng Muối ×2, Lẩu Thái ×1])
[Stage]    CONFIRMED
[AI Waiter] Dạ, em đã xác nhận đơn hàng 14 ạ. Món đang được chuẩn bị,
            anh/chị chờ một chút nhé.

[Khách]    Tính tiền giùm mình
[Tools]    request_payment(table_id=T_qs_1)
[AI Waiter] Dạ, tổng hóa đơn của anh/chị là 425.000₫ ạ.
            Anh/chị vui lòng quét mã QR để thanh toán nhé.
```

The complete pipeline executes without error.  The router classifies all three turns correctly,
the validator confirms both item names against the menu, and the order stage advances
IDLE → AWAITING_CONFIRMATION → CONFIRMED.  The billed total matches the cart exactly, which is
the check that state and ledger agree.

### QS-002 — Search Then Order (PASS)

```
[Khách]    Có món gì cay cay ăn nhậu không em
[Tools]    search(query="món cay, đồ cay, ốc cay, tôm cay")
[AI Waiter] Dạ, anh/chị có muốn thử Tôm Thẻ Xốt Thái Siêu Cay ạ?
            Món này rất cay và ngon, chắc chắn sẽ thích hợp với khẩu vị
            của anh/chị.

[Khách]    Vậy cho mình 1 phần món đó đi
[Tools]    add_cart(Tôm Thẻ Xốt Thái Siêu Cay ×1)
[Stage]    AWAITING_CONFIRMATION   cart 115.000₫

[Khách]    Chốt đơn luôn nha
[Tools]    confirm_order(items=[Tôm Thẻ Xốt Thái Siêu Cay ×1])
[Stage]    CONFIRMED
```

The referential phrase "món đó" resolves against the prior search context.  The
`search_context` → `curated_memory` → cart bridge functions correctly.

### QS-003 — Multi-Intent Rewriter (PASS)

```
[Khách]    Cho 2 Hàu Nướng Phô Mai rồi tính tiền luôn nha em
[Tools]    add_cart(Hàu Nướng Phô Mai ×2)
[Tools]    request_payment(table_id=T_qs_3)
[Stage]    AWAITING_CONFIRMATION   cart 78.000₫
[AI Waiter] Dạ, giỏ hàng của anh/chị hiện có:
            - Hàu Nướng Phô Mai ×2 (39.000₫/phần)
            Tổng tạm tính 78.000. Anh/chị xác nhận đặt hàng chưa ạ?
            Dạ, hiện chưa có đơn hàng nào trong phiên này ạ.

[Khách]    Xác nhận đơn rồi bill luôn
[Tools]    confirm_order(items=[Hàu Nướng Phô Mai ×2])
[Tools]    request_payment(table_id=T_qs_3)
[Stage]    CONFIRMED
[AI Waiter] Dạ, em đã xác nhận đơn hàng 16 ạ. Món đang được chuẩn bị,
            anh/chị chờ một chút nhé. Dạ, tổng hóa đơn của anh/chị
            là 78.000₫ ạ. Anh/chị vui lòng quét mã QR để thanh toán nhé.
```

Both turns are multi-intent and both decompose correctly.  Turn 1: the boundary marker `rồi`
triggers the rewriter, which splits the utterance into ORDER and PAYMENT fragments; both
execute.  Turn 2: ORDER_CONFIRM and PAYMENT, both tools called, and the bill of 78.000₫ matches
the confirmed order.  This is the core architectural claim: a single-intent MLP classifier
combined with a deterministic boundary-marker rewriter handles multi-intent utterances without
being trained on them.

Turn 1 also shows the ordering constraint honestly.  The payment fragment executes before the
order is confirmed, so the system correctly reports that no order exists yet rather than
inventing a total.  The two intents are executed in the order spoken, not reordered to make
sense; the customer hears a cart summary followed by a refusal to bill.

### QS-004 — Modification and Recovery (PASS)

```
[Khách]    Cho mình 1 Mực Cháy Tỏi với 2 Bia Sài Gòn
[Tools]    add_cart(Mực Cháy Tỏi ×1, Bia Sài Gòn ×2)
[Stage]    AWAITING_CONFIRMATION   cart 165.000₫

[Khách]    Thôi bỏ Mực Cháy Tỏi đi, đổi qua Cháo Hàu 1 phần
[Tools]    remove_cart("Mực Cháy Tỏi"), add_cart(Cháo Hàu ×1)
[Stage]    AWAITING_CONFIRMATION   cart 125.000₫
[AI Waiter] Dạ, em đã bỏ món khỏi giỏ hàng ạ. Giỏ hàng của anh/chị hiện có:
            - Bia Sài Gòn ×2 (15.000₫/phần)
            - Cháo Hàu ×1 (95.000₫/phần)
            Tổng tạm tính 125.000. Anh/chị xác nhận đặt hàng chưa ạ?

[Khách]    Thêm 1 Khoai Tây Lắc Phô Mai nữa
[Tools]    add_cart(Khoai Tây Lắc Phô Mai ×1)
[Stage]    AWAITING_CONFIRMATION   cart 174.000₫

[Khách]    Ok chốt đơn đi
[Tools]    confirm_order(items=[Bia Sài Gòn ×2, Cháo Hàu ×1,
            Khoai Tây Lắc Phô Mai ×1])   Mực Cháy Tỏi correctly absent
[Stage]    CONFIRMED
```

Cart state evolves correctly across four turns.  The substitution pattern
("bỏ...đổi qua...") is handled as a paired `remove_cart` and `add_cart`, the incremental
addition preserves existing items, and the final `confirm_order` contains exactly the three
items the customer settled on with no trace of the removed Mực Cháy Tỏi.

One cosmetic defect: the reply on turn 2 repeats the cart summary twice, once for the
`remove_cart` outcome and once for the `add_cart` outcome.  The state is correct, but the
verbalisation duplicates.

### QS-005 — Ambiguity Clarification (PASS)

```
[Khách]    Cho mình 2 phần Ốc Hương
[Tools]    add_cart(items=[])   validator blocks: "Ốc Hương" matches 11 variants
[Stage]    IDLE   cart unchanged
[AI Waiter] Dạ, món Ốc Hương bên em có nhiều loại ạ, anh/chị muốn chọn
            loại nào ạ?
            - Ốc Hương Xốt Trứng Muối
            - Ốc Hương Xốt Phô Mai
            - Ốc Hương Xốt Me
            - Ốc Hương Xốt Muối Tắc
            - Ốc Hương Xốt Bơ Cay
            - Ốc Hương Xốt Bơ Tỏi Cay
            - Ốc Hương Xốt Thái Siêu Cay
            - Ốc Hương Xốt Sa Tế
            - Ốc Hương Rang Muối
            - Ốc Hương Cháy Tỏi
            - Ốc Hương Hấp Sả

[Khách]    Ốc Hương Xốt Bơ Cay ấy
[Tools]    add_cart(Ốc Hương Xốt Bơ Cay ×2)
[Stage]    AWAITING_CONFIRMATION   cart 170.000₫

[Khách]    Chốt đơn đi em
[Tools]    confirm_order(items=[Ốc Hương Xốt Bơ Cay ×2])
[Stage]    CONFIRMED
```

The validator detects that "Ốc Hương" is an ambiguous short name matching 11 menu items.  It
empties the item list, lists all 11 variants and asks for clarification, leaving the order stage
at IDLE.  On the next turn the customer selects a specific variant, which is accepted and
confirmed.  The system never silently auto-selects from ambiguous input.

### QS-006 — Long Conversation (12 turns, FAIL)

```
[Khách]  1  Quán mình có món nào bán chạy nhất không em,
            tụi mình lần đầu tới quán
[Tools]     search(query="món bán chạy, best seller")
[AI]        Dạ, anh/chị có muốn thử món tôm thẻ nướng muối ớt không?
            Đây là một trong những best seller của chúng em ạ.

[Khách]  2  Ốc Hương Xốt Trứng Muối giá bao nhiêu vậy em
[Tools]     delegate(reason="khách hỏi về giá món ăn, không phải yêu cầu CRUD")
[AI]        Dạ, Ốc Hương Xốt Trứng Muối là một best seller của chúng em,
            giá là 85.000₫ ạ. Anh/chị có muốn thử món này không?
            ✗ assertion expected search

[Khách]  3  Ok cho 2 phần Ốc Hương Xốt Trứng Muối với 4 Bia Sài Gòn nha
[Tools]     add_cart(Ốc Hương Xốt Trứng Muối ×2, Bia Sài Gòn ×4)
[Stage]     AWAITING_CONFIRMATION   cart 230.000₫

[Khách]  4  Có món nào ăn nhậu lai rai không em, gợi ý thêm vài món đi
[Tools]     search(query="món nhậu, đồ nướng")
[AI]        Dạ, chị/chị có thể thử Sò Điệp Nướng Phô Mai ạ.

[Khách]  5  Vậy cho thêm 1 Mực Cháy Tỏi với 1 Khoai Tây Lắc Phô Mai nữa
[Tools]     add_cart(Mực Cháy Tỏi ×1, Khoai Tây Lắc Phô Mai ×1)
[Stage]     AWAITING_CONFIRMATION   cart 414.000₫

[Khách]  6  Cho mình xem lại giỏ hàng đang có gì
[Tools]     delegate(reason="khách hỏi xem lại giỏ hàng, không phải yêu cầu CRUD")
[AI]        (reads back all four lines and the running total)

[Khách]  7  Thôi bỏ Bia Sài Gòn đi, đổi qua 4 Bia Heineken
[Tools]     remove_cart("Bia Sài Gòn"), add_cart(Bia Heineken ×4)
[Stage]     AWAITING_CONFIRMATION   cart 454.000₫

[Khách]  8  Mực Cháy Tỏi ăn có cay không em?
            Tụi mình có đứa không ăn cay được
[Tools]     search(query="Mực Cháy Tỏi, cay")
[AI]        Dạ chị/chị có muốn thử ốc bulot cháy tỏi ạ? Món này rất ngon
            và cay vừa miệng, phù hợp với khẩu vị của chị/chị.

[Khách]  9  Thôi đổi Mực Cháy Tỏi qua Cháo Hàu đi, ăn Cháo Hàu cho lành
[Tools]     remove_cart("Mực Cháy Tỏi"), add_cart(Cháo Hàu ×1)
[Stage]     AWAITING_CONFIRMATION   cart 414.000₫

[Khách] 10  Tổng cộng hết bao nhiêu rồi em
[Tools]     request_payment(table_id=T_qs_6)
[AI]        Dạ, hiện chưa có đơn hàng nào trong phiên này ạ.

[Khách] 11  Ok chốt đơn đi em, đúng hết rồi đó
[Tools]     confirm_order(items=[Ốc Hương Xốt Trứng Muối ×2,
            Khoai Tây Lắc Phô Mai ×1, Bia Heineken ×4, Cháo Hàu ×1])
            no Bia Sài Gòn, no Mực Cháy Tỏi
[Stage]     CONFIRMED

[Khách] 12  Tính tiền giùm tụi mình luôn nha em
[Tools]     request_payment(table_id=T_qs_6)
[AI]        Dạ, tổng hóa đơn của anh/chị là 414.000₫ ạ.
            Anh/chị vui lòng quét mã QR để thanh toán nhé.
```

**Assessment.**  Eleven of twelve turns are correct, and the state-integrity claim holds.  The
order stage is held at AWAITING_CONFIRMATION across turns 3 to 10 while the cart is mutated four
times, then advances to CONFIRMED on turn 11.  Both substitutions execute correctly: Bia Sài Gòn
to Bia Heineken on turn 7, Mực Cháy Tỏi to Cháo Hàu on turn 9.  The final `confirm_order`
contains exactly the four items the group settled on with zero trace of either removed item, and
the billed 414.000₫ equals the cart total (170.000 + 100.000 + 49.000 + 95.000).

The scenario nonetheless fails, on one assertion and two unasserted defects worth reporting.

*Turn 2, the assertion failure.*  The price question is answered correctly (85.000₫) from
`curated_memory` via `delegate` rather than through `search`.  The behaviour is right and the
assertion is too strict: it demands a specific tool where the architecture deliberately allows
the worker to abstain and let the chat path answer from memory.  This is an assertion defect,
not a system defect, and the assertion should be relaxed to accept either path.

*Turn 8, the rewriter selecting the wrong near-name.*  The retriever behaves correctly, returning
Mực Cháy Tỏi as the top BM25 hit with `taste="cay thơm"`, but the rewriter, facing several
"cháy tỏi" variants in the result set, answers about "ốc bulot cháy tỏi" instead.  The retriever
delivers the right data and the model cannot reliably discriminate among similarly named
dishes.  This reproduced in all three runs of this experiment and is therefore a stable
limitation, not sampling noise.  It feeds §6.2.

*Turn 10, a running-total question routed to payment.*  "Tổng cộng hết bao nhiêu rồi em" asks what
the cart currently comes to.  The utterance routes to PAYMENT, `request_payment` queries the order
ledger, finds no confirmed order in the session and answers "hiện chưa có đơn hàng nào trong phiên
này ạ".  The refusal is graceful and no wrong number is invented, but the answer the customer
wanted (414.000₫) was sitting in cart state.  The failure is one of intent granularity: the router
has no class distinguishing "what does my cart come to" from "bill me".

### QS-007 — Off-Menu Handling (FAIL)

```
[Khách]  1  Cho mình 1 tô Phở Bò Tái, 2 Ốc Hương Xốt Me với
            1 dĩa Cơm Tấm Sườn
[Tools]     add_cart(Ốc Hương Xốt Me ×2)
[Stage]     AWAITING_CONFIRMATION   cart 170.000₫
[AI]        Dạ, món Phở Bò Tái, Cơm Tấm Sườn hiện không có trong thực đơn ạ.
            Anh/chị muốn chọn món khác không ạ?

[Khách]  2  Vậy thôi cho mình Ốc Hương Xốt Me đi, mấy món kia bỏ
[Tools]     remove_cart("Cơm Tấm Sườn")
            remove_cart("Lẩu Thái")
            remove_cart("Bia Sài Gòn")
            remove_cart("Trà Đào Cam Sả")
            add_cart(Ốc Hương Xốt Me ×1)
            remove_cart("Ốc Hương Xốt Me")
[Stage]     IDLE   cart (trống)
[AI]        Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn. Anh/chị thử lại
            giúp em nhé ạ.  (repeated three times)

[Khách]  3  Chốt đơn đi
[Tools]     clear_cart()
[Stage]     IDLE   is_valid=False
[AI]        Dạ, xin lỗi anh/chị, có lỗi khi xử lý đơn.
            ✗ assertion expected confirm_order
```

**Assessment.**  Turn 1 is the validator working exactly as designed.  Two off-menu names are
rejected before any tool executes, the one valid item enters the cart, and the reply names both
rejected dishes without inventing substitutes.

Turn 2 is where the design reaches its boundary.  The vague reference "mấy món kia bỏ" (remove
those other ones) has no resolvable antecedent in the cart, which contains a single item.  The
order worker, obliged by `tool_choice="any"` to emit a tool call, produces six: four
`remove_cart` calls naming dishes the customer never mentioned and which were never in the cart
(Lẩu Thái, Bia Sài Gòn, Trà Đào Cam Sả are hallucinated outright), then an `add_cart` and an
immediate `remove_cart` for the one item that was there.  The cart goes from correct to empty and
the customer receives three stacked error messages.  Turn 3 then calls `clear_cart` where
`confirm_order` was expected, and the turn ends with `is_valid=False`.

**This scopes the validator claim precisely.**  The validator resolves every dish name against
`menu.json`, so it blocks off-menu *names*, as turn 1 demonstrates.  It does not check whether a
named item is actually *in the cart*, because a `remove_cart` for a valid menu item that the
customer never ordered is not a menu-validity error.  The guarantee is over menu membership, not
over referential correctness.  Vague anaphora with no resolvable antecedent is the failure mode
that gets past it, and the escape hatch does not help here: `delegate` exists for the case where
no tool applies, but the model judged that a tool did apply and simply chose the wrong arguments.

### Summary

Five of seven scenarios pass.  The happy path, referential ordering after search, multi-intent
decomposition, cart modification and ambiguity clarification all behave as designed, and in every
passing scenario the billed total equals the cart total, which is the check that graph state and
the orchestrator ledger agree.

QS-006 demonstrates state integrity across a full 12-turn service interaction, holding the order
stage steady through four cart mutations and confirming exactly the right four items, while
exposing three separable weaknesses: an over-strict assertion, a rewriter that cannot
discriminate among similarly named dishes, and a router with no class for "what does my cart come
to".  QS-007 exposes the genuine boundary of the validation design: it guarantees menu membership
but not referential correctness, so an unresolvable vague reference under forced tool calling
produces hallucinated removals that the validator has no basis to block.

The qualitative approach reveals *what breaks* and *why*, which is more informative for a defence
than a single pass-rate number at n = 7.  One caveat applies to all of it: this is a single run
of a stochastic system.  QS-006 turn 1 called `delegate` in one run and `search` in the next on
identical input, which is the concrete reason the N = 5 protocol in §5.2.3 exists and the reason
the 5/7 figure should be read as one draw rather than a system constant.

---

## §5.4.6 — Agent Latency & Cost (n = 60 measurements)

*Result file:* `latency_20260726_003314.json`.

**What n = 60 means here.**  The file holds **12 distinct utterances at 5 runs each**
(`n_runs_per_utterance = 5`), so the per-intent rows below rest on 2 or 3 utterances repeated,
not on 10 to 15 different ones.  This is the one experiment in the chapter that satisfies the
N = 5 protocol of §5.2.3, and the repetition is what gives the percentiles their stability, but
the utterance diversity is low and the table should be read as 12 utterances characterised well
rather than 60 turns sampled broadly.

**Two gaps against what §5.4.6 asks for.**  `cold_start_s` is null, so the cold-versus-warm
comparison was not captured.  More importantly there is **no per-node breakdown**: the outline's
central question for this section is where the turn budget goes and which stage dominates, and
only whole-turn latency was instrumented.  The deployment argument (LLM on the server, not the
robot) currently rests on turn totals alone.

### Per-Intent Turn Latency

| Intent | p50 | p95 | n |
|--------|:-----:|:-----:|:--:|
| ORDER | 1.36 s | 2.29 s | 10 |
| ORDER_CONFIRM | 3.22 s | 4.89 s | 5 |
| SEARCH | 2.19 s | 2.86 s | 15 |
| PAYMENT | 0.94 s | 3.66 s | 10 |
| CHAT | 1.22 s | 2.83 s | 10 |
| MULTI | 2.36 s | 4.21 s | 10 |
| **Global** | **2.15 s** | **3.40 s** | **60** |

Global p50 of 2.15 s and p95 of 3.40 s are both well within the 5 s voice-interaction
latency budget set in §4.1.  The ORDER_CONFIRM path has the highest tail (p95 = 4.89 s),
driven by the confirm_order tool call which involves a database write and kitchen-display
push.

### Router Latency per Arm (n = 304)

*Result file:* `router_arms_20260726_125915.json`.

| Arm | p50 | p95 |
|-----|:-----:|:-----:|
| MLP, text-only (proposed) | 9 ms | 11 ms |
| Centroid | 10 ms | 12 ms |
| SLM (qwen2.5:3b) | 194 ms | 205 ms |
| Hybrid semantic→SLM | 12 ms | 705 ms |
| LLM zero-shot | 229 ms | 271 ms |

*Superseded: this table is from an earlier run that still carried the removed arm E and a
draft model tag on arm F. Regenerate with the rest of the router arms.*

### Peak GPU Memory (Router Arms)

**No per-arm figure is available, and the previous version of this table misattributed one.**
The `peak_gpu_mb` field in both router-arm result files records total device occupancy at the
time each arm ran, not that arm's own footprint, so the values are cumulative in arm order:

| Arm (in run order) | 304-case run | 130-case run |
|--------------------|-------------:|-------------:|
| A Centroid | 813 MB | 6 077 MB |
| B SLM (qwen2.5:3b) | 2 975 MB | 6 077 MB |
| C Hybrid semantic→SLM | 6 209 MB | 6 209 MB |
| D MLP, text-only | 6 759 MB | 6 759 MB |
| F LLM zero-shot | 6 759 MB | 6 759 MB |

The 813 MB reading previously reported as "MLP classifier alone" is in fact arm **A**, the
centroid router, taken as the first measurement of the 304-case run before any language model
was loaded.  Arm D reads 6 759 MB because the SLM and the LLM were already resident by
then.  The same arm reads 6 077 MB in one run and 813 MB in the other, which is itself proof
that the figure tracks device state rather than the arm.

§5.2.2 promises peak memory "measured per arm".  Delivering that requires either a separate
single-arm process per arm or an allocator-level measurement scoped to the arm.  Until then the
memory column should be dropped from the ablation table, and the deployability argument for the
MLP should rest on its parameter count and the fact that it reuses the embedding model already
loaded for retrieval, both of which are defensible without a GPU measurement.

---

## §5.5.1 — API Benchmark

*Result file:* `bench_api_20260726_124543.json`.  All 12 REST endpoints were exercised with
n = 10 samples each after 2 warmup requests, against the live orchestrator on port 8000.

| Endpoint | p50 (ms) | p95 (ms) | p99 (ms) |
|----------|:---:|:---:|:---:|
| GET /menu | 2.2 | 3.1 | 3.1 |
| GET /tables | 2.2 | 3.0 | 3.0 |
| GET /tables/{id} | 2.5 | 2.9 | 2.9 |
| POST /seatings | 2.0 | 2.6 | 2.6 |
| GET /orders | 2.8 | 3.6 | 3.6 |
| POST /orders | 1.3 | 2.3 | 2.3 |
| GET /payments | 1.6 | 2.8 | 2.8 |
| GET /robots | 2.0 | 2.9 | 2.9 |
| GET /tasks | 1.8 | 3.0 | 3.0 |
| GET /layout | 1.4 | 2.0 | 2.0 |
| POST /voice/event | 1.3 | 1.7 | 1.7 |
| POST /voice/listen | 1.4 | 2.3 | 2.3 |

All endpoints respond within 4 ms at p99.  The FastAPI + SQLite design meets the real-time
requirement — push-based WebSocket events replace the 5–10 s polling cycle of traditional
KDS systems (§2.6.4).

The benchmark also issued 2 and then 4 simultaneous requests, all of which succeeded
(`concurrent.2_tables.n_ok = 2`, `4_tables.n_ok = 4`) at a p95 of 2.9 and 3.4 ms.  This measures
concurrent HTTP handling only.  It is **not** the session-isolation experiment §5.5.2 calls for,
which requires concurrent conversations at different tables ordering overlapping dishes and a
cross-session leakage count.  That experiment has not been run.

### WebSocket Event Propagation

The WebSocket benchmark (`bench_ws_20260726_124544.json`) connected successfully as `panel`
and `customer` roles but collected no events — the orchestrator was idle during the
measurement window.  Event propagation latency requires active agent-driven traffic
(e.g. order creation, robot status updates) and remains unevaluated pending a
multi-component integration test.  This limitation is noted in §5.6.4.

---

## §5.5.3 — Fleet Management & Robot Task Lifecycle

*Result file:* `bench_fleet_20260726_135111.json`.

A mock robot connects via WebSocket (`role=robot`), the backend creates a call task, the
dispatcher assigns it, and the robot completes the lifecycle:

| Step | Robot status | Activity |
|------|-------------|----------|
| Before connection | `offline` | — |
| WS connect + heartbeat | `idle` | `Đang ở dock` |
| Task created (call, table 1) | `busy` | `Đang tới bàn 1 (gọi phục vụ)` |
| `task_done` message | `returning` | `Đang về dock` |
| `at_dock` message | `idle` | `Đang ở dock` |

The task progressed through the full state machine: PENDING → ASSIGNED → DONE.  This
validates the dispatcher's `create_task` → `try_assign` → `on_task_done` pipeline and
the robot lifecycle tracking described in §4.7.3.

**Fault recovery was not measured.**  The result file records
`fault_recovery.validated_by_inspection = true` with the note that the watchdog test requires
killing the WebSocket mid-task and verifying task requeue, and that this is instead argued
structurally from `try_assign()` requeuing all PENDING tasks on each connect and disconnect
event.  The outline's §5.5.3 asks for watchdog detection time, task requeue latency, voice
rebind correctness and whether a customer-visible interruption occurs.  None of those are
measured.  This is the happy path of the lifecycle only, and §5.6.4 must say so.

## §5.5.4 — Multi-Role State Consistency

*Result file:* `bench_fleet_20260726_135111.json`.

A seating event (kiosk role) followed by an order creation (agent role) was driven through
the REST API, and the three role views were polled to verify convergence:

| Role | Endpoint | Before | After |
|------|----------|--------|-------|
| Kiosk (seating) | `POST /seatings` → table 3 | `TRONG` | `DANG_PHUC_VU`, party_size=4 |
| Agent (order) | `POST /orders` → table 3 | 0 orders | 2 orders, latest 245,000 ₫ |
| Panel (monitor) | `GET /orders` | 0 orders | 2 orders visible |
| Customer (tablet) | `GET /tables/3` | `TRONG` | `DANG_PHUC_VU`, current_order_id set |
| Admin | `POST /admin/reset` | — | All tables freed ✓ |

All three role views (kiosk, panel, customer tablet) reflect the same backend state within
a single HTTP request-response cycle — there are no stale views or polling delays.  The
FastAPI + SQLite backend serves as a single source of truth.

The result file records `orders_before = 0`, `orders_after = 2` and `tasks_before = 1`,
`tasks_after = 2`; the second order and the pre-existing task are residue from the fleet
lifecycle test that ran immediately before in the same process.  Convergence across roles is
what this experiment establishes, and that holds; the absolute counts are not a clean baseline
and the benchmark should reset between the two phases.  Note also that this measures REST
polling convergence, not the WebSocket push latency §5.5.4 asks for, which remains unmeasured
for the same reason as §5.5.1.


---

## Open Items Before This Becomes Chapter Prose

Ordered by how much damage each does if it reaches a defence unaddressed.

**1. Regenerate every LLM-dependent result on the deployment server.**  The drafting pass was run
locally, so those results are provisional; §5.1 names Qwen2.5 14B as the system's model and stands.
See the banner at the top of this file for which
experiments carry forward and which must be re-run.  Two consequences deserve attention rather
than a simple re-run: §5.4.6's turn latency (p50 2.15 s, p95 3.40 s against a 5 s budget) will
grow on a larger model and is the claim most at risk, and §5.4.1's arm F becomes a genuine LLM
ceiling only once it uses the deployed model.

**1b. Correct §5.1.1's hardware table.**  It currently describes the development laptop
(RTX 3070 Laptop, 8 GB), not the 16 GB deployment server the 14B will run on.  The GPU model,
CPU and system RAM of the server are still needed.  The GPU-memory discussion in §5.4.6 was also
measured on the laptop and must be re-scoped or re-measured.

**2. §5.2 no longer describes the experiments that were run.**  The dataset table still says
single-intent 100 cases, context-dependent 20, E2E 20 scenarios and a 50-scenario safety pool;
the actual figures are 149, 70, 7 and 41.  The §5.2.4 status column still marks the validator
ablation "invalid", the retriever ablation "not implemented" and `bench_api` "never run", all of
which are now done, and it omits `eval_qualitative.py`, `eval_router_arms.py` and
`bench_fleet.py` entirely.

**3. §5.2.3's N = 5 protocol is not met by anything except the latency experiment.**  Decide
between re-running the cheap stochastic experiments and rewriting the protocol.  The concrete
evidence that it matters: QS-006 turn 1 called `delegate` in one run and `search` in the next on
identical input, flipping the scenario's assertion outcome.

**4. Three metrics are defined in §5.2.2 and never reported.**  Accuracy-per-cost, which §5.2.2
promises as the final column of the router ablation table; circuit-breaker rate; and validator
false-positive rate.  The confusion matrix is defined at length but only per-class precision,
recall and F1 appear.  Compute them or cut the definitions.

**5. Experiments the outline asks for that have no data.**  The rewriter ablation in §5.4.4 (with
and without query rewriting).  Session isolation with a cross-session leakage count (§5.5.2).
Watchdog, requeue and voice-rebind measurement (§5.5.3).  WebSocket propagation latency (§5.5.1
and §5.5.4).  All of §5.3.  The §5.4.1 vocabulary-coverage diagnostic is now stale in a different
way: the LLM-generated corpus it measured has been replaced by the hand-curated one, so either
re-measure OOV on the new corpus or rewrite that bullet as the corpus-replacement narrative,
which is the better story.

**6. §5.6 cannot be written yet.**  The objective scorecard needs the §1.3 targets, which are
still placeholders (`X cm`, `X %`).
