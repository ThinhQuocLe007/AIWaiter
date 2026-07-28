# Chapter 5 — Collected Evaluation Results

**Last updated:** 2026-07-26 (14:48).  Each table cites the experiment and the result file that
produced it.  Section numbers reference the current outline.

> **PROVISIONAL: these are first-draft numbers on the wrong model.**
>
> The whole evaluation pass ran on `qwen2.5:7b-instruct`, which is what was installed on the
> development laptop.  The system is intended to deploy **Qwen2.5 14B Instruct**, and the team
> will regenerate these results on it.  Everything below is therefore a methodology rehearsal
> and a defect-finding pass, not the final evidence.  What carries forward unchanged is the
> experimental design, the datasets, the fixed harnesses, and every defect identified.  What
> must be regenerated is every number produced by an LLM.
>
> **Unaffected by the model swap** (deterministic, or independent of the LLM): §5.4.1 single-intent
> accuracy, context ablation, multi-intent detection, holdout, and router arms A, D, E; §5.4.2
> name resolution and ambiguity; §5.4.4 retrieval and gatekeeper; §5.5.1 API latency.
>
> **Must be regenerated on the 14B**: §5.4.1 arms B, C and F; §5.4.2 validator ablation,
> out-of-menu and delegate; all of §5.4.3; all of §5.4.5; and all of §5.4.6, whose latency
> figures are the most likely to move and the ones a 5 s budget claim rests on.

**Model state.**  Most results below now come from the current committed classifier: §5.4.1,
§5.4.3, §5.4.4, §5.4.5, §5.5 and §5.4.2's out-of-menu experiment were all produced on
2026-07-26.  Two results in §5.4.2 predate it.  Name resolution and ambiguity date from
2026-07-19 but exercise pure-Python validator functions that do not depend on the classifier, so
the date is harmless provided `menu.json` has not changed.  Every figure that depends on the
router or the worker LLM has now been re-run on the current model.

**Statistical protocol.**  §5.2.3 commits to N = 5 runs for any experiment whose outcome depends
on an LLM.  Two experiments now satisfy it: agent latency (§5.4.6) and multi-intent verbalisation
(§5.4.3).  The router arms, validator ablation, out-of-menu, delegate and qualitative E2E results
remain single runs and are marked as such; of these only the router arms is expensive to repeat.  Either those are repeated or §5.2.3 is rewritten to
state single-run measurement honestly.

**A note on the N = 5 crash, scoped to the draft machine.**  The first N = 5 attempt at §5.4.3
failed partway through when the Ollama server became unreachable, producing 222 connection errors
and two dead runs whose near-zero scores dragged the reported mean to a plausible-looking value.
This happened on the 8 GB development laptop, where the 7B plus the embedding model already
occupy about 6.2 GB.  It is a property of the draft environment, not of the 16 GB deployment
server, and should not be carried into the thesis as a system limitation.  The procedural lesson
does carry: any N = 5 result must be checked for connection errors in its log before its mean is
trusted, because a crashed run does not announce itself in the summary statistics.

*Changes since previous revision:*
- *§5.4.3 re-run at N = 5 against the current classifier, and the scorer corrected. The evidence lists credited happy-path wording only, so every correct refusal counted as a verbalisation failure. Scoring the same 125 replies under both rules moves fully-verbalised turns from 40.8 % to 56.8 % and verbalisation rate from 61.3 % to 73.3 %. The residual loss is now a specific pattern: ORDER combined with SEARCH in one turn loses one of the two.*
- *Corrected an error I introduced in the previous revision of §5.4.3: it asserted that `state_outcome` selects a single ResponseContext. The code aggregates end to end; the note in `tasks_on_section.md` is stale.*
- *§5.4.2 out-of-menu re-run on the current classifier: unchanged at 28/30, same two failures.*
- *§5.4.2 delegate re-run on the current classifier: 3/90 = 3.33 %, still zero wrong tool calls. The scenario pool grew from 19 to 45, so the rate is not directly comparable to the old 1.61 %. Per-worker attribution is broken in the runner.*
- *§5.4.5 rewritten against `e2e_qualitative_20260726_141829.json`, the first run of that experiment with isolated state. Outcome is 5/7, not 6/7. QS-006 fails. Earlier qualitative runs inherited the previous run's cart and an un-reset order ledger, so their cart totals and bills were inflated; the runner has been fixed.*
- *Gatekeeper confirmed fixed: cosine scores are valid [0.16, 0.58], no >1.0 anomaly. The semantic lane now passes on 20/24 queries alongside the lexical lane. §5.4.4 updated.*
- *Single-intent eval expanded from 100 → 149 cases, context-dependent from 20 → 70 cases. §5.4.1 updated.*
- *API benchmark (§5.5.1) run against the live orchestrator. §5.5.1 section added.*

The MLP router is trained on a **manually curated dataset** of 434 spoken Vietnamese utterances
(2 134 examples after context augmentation).  The training corpus was written by hand against
the real restaurant menu (`assets/data/menu.json`, 219 dishes) with explicit vocabulary
coverage of all critical tokens (`tôi`, `xoá`, `xóa`, `giỏ hàng`, `quận`, `ship`, `shop`,
`thực đơn`).  No LLM was used for generation — this avoids the label noise and vocabulary gaps
that the earlier LLM-generated corpus suffered from (§5.4.1, corpus-regeneration study).

The router follows a **single-intent classification** architecture: the MLP predicts one of
four intents (ORDER, SEARCH, PAYMENT, CHAT) with a confidence score.  If the utterance
contains multi-clause boundary markers (`rồi`, `và`, `thì`, `xong`, `rồi thì`, `với lại`,
`à mà`, `,mà`) or if the confidence falls below 0.7, the utterance is sent to the rewriter
for decomposition into single-intent fragments, each classified independently by the MLP.
Multi-intent utterances are therefore not scored as classification errors — the metric is
whether the router correctly flags them for the rewriter path.

---

## §5.4.1 — Intent Classification & Routing

### Single-Intent Accuracy (n = 149, `evals/data/router/single_intent_eval.json`)

**140/149 = 94.0 %** (Wilson 95 % CI: 89.0–96.8 %).  p50 latency 8.0 ms, p95 10.1 ms.

*Result file:* `mlp_router_eval_20260726_124805.json`.  The dataset was expanded from 100 to 149 cases on 2026-07-26 to improve class balance (roughly 37 per class) and vocabulary coverage, particularly the first-person pronoun `tôi` (absent from the original 100-case set).  The original 100-case subset scored 98/100 = 98.0 %.

Mean confidence on correct predictions: 0.969.  Mean confidence overall: 0.961.

| Class | Precision | Recall | F1 | Support |
|-------|:---------:|:------:|:----:|:-------:|
| ORDER | 0.861 | 0.974 | 0.914 | 38 |
| SEARCH | 0.971 | 0.919 | 0.944 | 37 |
| PAYMENT | 1.000 | 1.000 | 1.000 | 37 |
| CHAT | 0.941 | 0.865 | 0.901 | 37 |

The CHAT class has the lowest recall (86.5 %): five utterances were misclassified as ORDER,
all containing `tôi` plus an action verb that resembles an ordering command (e.g.
"Tôi muốn gọi thêm mà quên mất món đó tên gì rồi", "Tôi bị dị ứng hải sản thì gọi món
gì được").  These are genuinely ambiguous cases where the surface form of the sentence
resembles both a conversational remark and an ordering request.  PAYMENT maintained
perfect classification across all 37 cases, including both the original and expanded sets.

### Context-Dependent Accuracy (n = 70, `evals/data/router/context_dependent_eval.json`)

| Mode | Accuracy | n |
|------|:--------:|:--:|
| With context features | 70.0 % (49/70) | 70 |
| Without context (IDLE defaults) | 58.6 % (41/70) | 70 |

*Result file:* `mlp_router_eval_20260726_125059.json`.  The dataset was expanded from 20 to 70 cases (36 utterance groups) on 2026-07-26.

**Label correction, disclosed.**  An earlier run of the same eval two minutes prior
(`mlp_router_eval_20260726_124805.json`) reports 46/70 = 65.7 % with context.  The model's
predictions are byte-identical across the two runs; three ground-truth labels were corrected
between them, all at IDLE: CD-023 "chốt luôn đi" (CHAT → ORDER), CD-053 "thanh toán đi"
(CHAT → PAYMENT) and CD-055 "cho xin bill" (CHAT → PAYMENT).  The correction on CD-053 and
CD-055 is sound on the merits, since an explicit request to pay or to be billed is a PAYMENT
intent regardless of order stage and the system answers it gracefully when no order exists.
CD-023 is more debatable and its `note` field still reads "IDLE không có gì để chốt → CHAT",
contradicting its new label.  Because the corrections raise the reported figure and were made
after the predictions were visible, they are stated here rather than left to be discovered.

**The set is weaker than its name suggests.**  10 of the 36 utterance groups now carry the same
label at both order stages ("tính tiền đi", "Ok chốt đơn đi em", "chốt luôn đi", "từ từ đã",
"để sau đi", "giỏ hàng có gì rồi", "tổng bao nhiêu", "thanh toán đi", "cho xin bill",
"hết chưa"), so on those pairs context is irrelevant by construction and cannot contribute to
the D-vs-E ablation either way.  The three corrections above moved two pairs into this group.
The honest reading is that only 26 of the 36 groups test the context claim; the ablation should
either report both numbers or the set should be re-partitioned.

The context feature resolved 11 cases correctly (b = 11), including all seven original short
affirmations ("ok", "ừ", "đúng rồi", "được", "ok em", "Uh đúng rồi đó", "chuẩn" — all
correctly routed to ORDER at AWAITING_CONFIRMATION vs. CHAT at IDLE) plus four new cases
("oke" at IDLE → CHAT, "đồng ý" at AWAITING_CONFIRMATION → ORDER, "ok luôn" at IDLE → CHAT,
"món này ngon không" at BUILDING → SEARCH).  Context broke the prediction on 3 cases
(c = 3): "chưa muốn đâu", "còn gì nữa không" and "hết chưa", all routed to SEARCH or ORDER
instead of CHAT.

McNemar exact: b = 11, c = 3, p = 0.057.  The 11.4 percentage-point improvement is close to
but does not reach significance at α = 0.05.  At the observed discordant ratio of 3.7 : 1,
approximately 25 discordant pairs would be needed for p < 0.05 — a sample of approximately
140 cases, matching the target in §5.2.3.

The 18 cases wrong in both modes are dominated by utterances containing ambiguous action
verbs: "thêm", "lấy", "cho", "bỏ", "đặt" at IDLE (empty-cart) contexts.  The MLP
consistently routes these to ORDER, reflecting the surface ordering language, while the
labels expect CHAT (no cart to act upon).  These are genuinely borderline cases where the
customer's intent is underspecified — the utterance sounds like an order but lacks a
referring target.

### Multi-Intent Detection (n = 27, `evals/data/router/multi_intent_detection.json`)

Detection = boundary markers OR confidence < 0.7.  Boundary markers: `rồi | và | thì | xong | rồi thì | với lại | à mà | ,mà`.

**23/27 = 85.2 % detected.**  By boundary markers: 21.  By low confidence: 5 (3 overlapping).

The 4 undetected cases have no lexical boundary marker in the utterance — the clauses are
juxtaposed by comma or fused without a connector (e.g. "Chốt đơn với bill luôn đi em",
"Cảm ơn em, cho anh xin bill luôn nha").  These are inherent limitations of any keyword-based
detection and represent utterances where the dominant intent absorbs the weaker one — the
rewriter path is not triggered, but the utterance is routed to its primary intent, which is a
reasonable fallback.

3 pseudo-multi-intent controls (utterances that look multi-intent but are single-intent) had
2 false alarms — both harmless overhead (boundary marker joins two clauses of the same intent,
rewriter decomposes them into same-intent fragments).  No single-intent utterance was
incorrectly routed to the wrong worker due to the detection mechanism.

### Six-Arm Router Ablation (n = 304 pooled, `evals/results/router_arms_20260726_125915.json`)

The pooled set was expanded on 2026-07-26 from 130 to 304 cases by incorporating the expanded
`single_intent_eval.json` (149 cases) and `context_dependent_eval.json` (70 cases) alongside the
original `router_eval.json`, `semantic_eval.json` and `router_context_eval.json` files.

| Arm | System | n correct | Accuracy | 95 % Wilson CI | p50 (ms) | p95 (ms) | GPU (MB) |
|-----|--------|:---------:|----------|---------------:|----------:|----------:|:--------:|
| A | Centroid (semantic only) | 232 | 76.3 % | 71.2–80.7 % | 10 | 12 | — |
| B | SLM only (qwen2.5:3b) | 246 | 80.9 % | 76.1–84.9 % | 194 | 205 | — |
| C | Hybrid semantic→SLM (previous) | 225 | 74.0 % | 68.8–78.6 % | 12 | 705 | — |
| D | MLP, no context features | 254 | 83.6 % | 79.0–87.3 % | 10 | 13 | — |
| **E** | **MLP + context (proposed)** | **262** | **86.2 %** | **81.9–89.6 %** | **9** | **11** | — |
| F | LLM zero-shot (qwen2.5:7b-instruct) | 253 | 83.2 % | 78.6–87.0 % | 229 | 271 | — |

The GPU column is empty because no per-arm figure exists.  The `peak_gpu_mb` field in both runs
records total device occupancy at the moment each arm ran and is therefore cumulative in arm
order; see the Peak GPU Memory note in §5.4.6.  All six arms are single runs (`"runs": 1`),
which for arms B, C and F means one draw from a stochastic system.

Paired McNemar exact (identical items, n = 304):

| Comparison | b (E only) | c (other only) | p | Verdict |
|---|---:|---:|---:|---|
| E vs C (previous system) | 56 | 19 | 2.2 × 10⁻⁵ | **significant** |
| E vs A (centroid) | 51 | 21 | 5.4 × 10⁻⁴ | **significant** |
| E vs B (SLM) | 29 | 13 | 0.020 | **significant** |
| E vs D (context ablation) | 11 | 3 | 0.057 | not significant |
| **E vs F (LLM ceiling)** | **24** | **15** | **0.200** | **not significant** |

The proposed arm reaches 86.2 %, numerically exceeding the 7 B LLM zero-shot router (83.2 %)
while running at p50 = 9 ms vs. 229 ms — a **25 × latency advantage**.  The arm is
statistically significantly better than the centroid, SLM, and previous hybrid system;
it is indistinguishable from the 7 B LLM (p = 0.20) despite the numerical advantage.

Per-class F1 for the proposed arm (n = 304):

| Class | Precision | Recall | F1 | Support |
|-------|:---------:|:------:|:----:|:-------:|
| ORDER | 0.816 | 0.939 | 0.873 | 99 |
| SEARCH | 0.848 | 0.833 | 0.840 | 60 |
| PAYMENT | 0.965 | 0.965 | 0.965 | 57 |
| CHAT | 0.865 | 0.727 | 0.790 | 88 |

**Context-feature ablation (D vs. E).**  The context feature resolved 11 cases correctly and
broke 3 (b = 11, c = 3, p = 0.057).  The improvement (83.6 % → 86.2 %) is close to but does
not reach significance.  At the observed 3.7 : 1 discordant ratio, approximately 25 discordant
pairs are needed for p < 0.05, requiring approximately 140 additional context-dependent cases.

**The arm ordering is not stable across runs; lead with the significant result, not the
numerical one.**  On the earlier 130-case pool (`router_arms_20260726_011327.json`) arm F led
arm E, 87.7 % against 85.4 %, and the centroid scored 83.8 % against the 76.3 % it scores here.
Expanding the pool to 304 cases changed its composition, and the "E numerically exceeds F"
ordering is a product of that composition rather than a stable property.  A 3-point gap that
McNemar cannot resolve at p = 0.20 should not be led with.

**The defensible claim.**  The trained MLP classifier is **statistically indistinguishable from
the 7B LLM zero-shot router** (p = 0.20 at n = 304) while running at 9 ms against 229 ms p50, a
25x latency advantage, and is significantly better than all three non-LLM baselines (centroid
p = 5.4e-4, SLM p = 0.020, previous hybrid p = 2.2e-5).

**The LLM ceiling is a 7B, and the deployed model is a 14B.**  Arm F uses
`qwen2.5:7b-instruct`, which is what the draft evaluation pass ran on, not the 14B the system is
intended to deploy.  So this ablation does not currently establish that the classifier matches
the routing accuracy of the LLM the system actually runs; it establishes that it matches a 7B.
A 14B zero-shot router would plausibly score higher, and the E-vs-F comparison could turn from
"indistinguishable" into "the LLM is better but 25x slower", which is still a defensible
contribution but a different sentence.  Arm F must be re-run on the 14B alongside the rest of
the chapter.  The comparisons against the centroid, SLM and previous hybrid are unaffected,
since none of those involve the deployed model.

### Clean Holdout (n = 39, `evaluate.py --context-aware`)

**38/39** (Wilson 95 % CI: 86.8–99.5 %).  The holdout was partitioned before
augmentation and never seen during training.  One remaining error, HO-021: "có món gì hợp cho
nhóm 4 người nhậu không" (SEARCH predicted as ORDER, confidence 0.643, with SEARCH second at
0.297).  The confidence sits below the 0.7 deployment threshold, so this utterance is routed to
the rewriter path rather than acted on directly.  Without context features: 36/39.

*Result file:* `src/training_semantic_router/data/eval_report.json`.  The confusion matrix in
that file records the single error as SEARCH → ORDER with zero PAYMENT confusions on the
holdout.

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
across runs.  Produced on the 7B draft model; see the banner at the top of this file.

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
delivers the right data and the 7B model cannot reliably discriminate among similarly named
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
| MLP + context (proposed) | 9 ms | 11 ms |
| MLP, no context | 10 ms | 13 ms |
| Centroid | 10 ms | 12 ms |
| SLM (qwen2.5:3b) | 194 ms | 205 ms |
| Hybrid semantic→SLM | 12 ms | 705 ms |
| LLM zero-shot (qwen2.5:7b) | 229 ms | 271 ms |

### Peak GPU Memory (Router Arms)

**No per-arm figure is available, and the previous version of this table misattributed one.**
The `peak_gpu_mb` field in both router-arm result files records total device occupancy at the
time each arm ran, not that arm's own footprint, so the values are cumulative in arm order:

| Arm (in run order) | 304-case run | 130-case run |
|--------------------|-------------:|-------------:|
| A Centroid | 813 MB | 6 077 MB |
| B SLM (qwen2.5:3b) | 2 975 MB | 6 077 MB |
| C Hybrid semantic→SLM | 6 209 MB | 6 209 MB |
| D MLP, no context | 6 759 MB | 6 759 MB |
| E MLP + context | 6 759 MB | 6 759 MB |
| F LLM zero-shot (qwen2.5:7b) | 6 759 MB | 6 759 MB |

The 813 MB reading previously reported as "MLP classifier alone" is in fact arm **A**, the
centroid router, taken as the first measurement of the 304-case run before any language model
was loaded.  Arms D and E read 6 759 MB because the SLM and the LLM were already resident by
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

**1. Regenerate every LLM-dependent result on Qwen2.5 14B.**  The draft pass ran on
`qwen2.5:7b-instruct`.  §5.1.1 correctly names the 14B as the system's model, so the section is
not wrong; the results are provisional.  See the banner at the top of this file for which
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
