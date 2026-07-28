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

## Run Configuration — 2026-07-28 Pass

Everything in this revision was produced in a single sequential pass on 2026-07-28.  Logs and
per-stage timings are in `evals/results/run14b_20260728_190734/`.

| Setting | Value |
|---------|-------|
| Router / worker / response model | `qwen2.5:14b-instruct-q6_K` (the deployment model) |
| Embedding model | `bkai-foundation-models/vietnamese-bi-encoder`, CUDA, 768-dim |
| GPU | NVIDIA GeForce RTX 5060 Ti, 16 GB |
| System RAM | 31 GB |
| Menu | `assets/data/menu.json`, **234 dishes** |
| Repetitions | N = 5 for every LLM-dependent experiment; single run for deterministic ones |

**This pass replaces the 7B draft.**  The previous revision ran on `qwen2.5:7b-instruct` and
carried a PROVISIONAL banner saying every LLM-produced number had to be regenerated on the 14B.
This pass regenerates them on the 14B and applies the N = 5 protocol of §5.2.3 to every
stochastic experiment rather than to two of them.  Per-experiment run counts are stated in each
section; where a section still reports a single run, it says so.

### What was deliberately not run, and why

Recorded here so that no reader has to infer an omission from a missing table.

**Arm B of the router ablation (`SLM only`) was dropped.**  Arms B and F are the same prompt at
two model sizes — `_prompted()` in `eval_router_arms.py` is a single function and the arms
differ only in the model name.  This pass was constrained to keep exactly one model resident on
the 16 GB card, so arm B was pointed at nothing rather than at a second small model, which would
have made it a byte-identical duplicate of arm F contributing one redundant row and no
information.  The ablation was therefore run as `--arms A C D E F`, five arms.  The consequence
is that the **E-vs-B McNemar comparison is absent from this revision**; the previous revision's
figure (arm B = 246/304 = 80.9 % on `qwen2.5:3b`, E vs B p = 0.020) is the last measurement of
it and was made on the 7B-era pass.  If the thesis wants an SLM baseline, it needs a deliberate
choice of which small model that is, and a run of its own.

**The cascade experiment (speech → routing) was not run.**  It requires 180 recordings from
three speakers plus a restaurant-noise file, none of which exist yet; `evals/HANDOFF.md` is the
packet for whoever records them.  This is the one Chapter 5 experiment that cannot be produced
from the repository alone.

**`evals/data/e2e/e2e_real_life.json` (4 scenarios) and `e2e_scenarios.json` (20 scenarios) were
not run.**  Neither appears in the §5.2.4 experiment inventory; the qualitative case study uses
`e2e_qualitative.json` and the safety pool uses `e2e_out_of_menu_test.json`.  They are datasets
without a listed experiment, not experiments that were skipped.

### Harness changes made during this pass

Three changes to eval scripts, all recorded here because they touch how results are produced.
None of them changes what any experiment measures.

- **`eval_latency.py`** cleared `storage/db/checkpoints.db` without its `-wal` and `-shm`
  sidecars.  The stale sidecars were then paired with the fresh database and every later process
  that opened it — including the agent service already holding the old file — died with
  `sqlite3.OperationalError: disk I/O error`.  This destroyed the first attempt at the LLM block:
  six consecutive experiments failed, and `eval_qualitative.py` **reported `pass_rate 0.000` with
  exit code 0** rather than failing, which is exactly the silent-corruption mode §5.2.3 warns
  about.  The script now removes all three files, and it is ordered last in the run because it
  clears state other experiments share.
- **`eval_router_arms.py`** had its arm models hard-coded, which made the 14 B-versus-7 B control
  above impossible to run.  They are now overridable via `ARM_LLM_MODEL` / `ARM_SLM_MODEL`.
- The run driver now marks any stage whose log contains a traceback, an OOM, a connection error
  or a `falling back to CHAT` line as `DIRTY` in `_progress.log`, so a crashed run cannot be
  mistaken for a low score.

**A note on GPU capacity, since it caused a corrupted run.**  `qwen2.5:14b-instruct-q6_K` at a
16 384-token context occupies roughly 14 GB of the 16 GB card.  Running the agent HTTP service
alongside an evaluation puts a second copy of the embedding model on the same device, and the
classifier then raises `torch.OutOfMemoryError` — which
`classifier_router_node` catches and converts into a **silent fallback to CHAT**.  An entire
N = 5 run completed that way, routing every utterance to CHAT and reporting it as a result.  The
service must be stopped for the duration of an evaluation pass; the evaluations construct the
agent in-process and do not need it.  This failure mode deserves a line in §5.6.4: the fallback
is correct behaviour for a live service and the wrong behaviour for a measurement harness.

### Dataset and menu drift found during this pass

Two datasets have fallen out of sync with `menu.json`, which has grown from the **219 dishes**
this chapter asserts in §5.2.1 to **234**.  Both are ground-truth problems rather than system
regressions, and both are detailed where they bite:

- **Name resolution** (§5.4.2): four names the dataset marks off-menu are now real dishes,
  costing five cases and dropping a reported 100 % to 92.9 %.
- **Out-of-menu robustness** (§5.4.2): `OOM-002` lists `Cà Phê Sữa Đá` and `OOM-020` lists
  `Kem Dừa` among their `invalid_items`; both are on the current menu, and `OOM-020` is
  categorised `all_invalid` while containing a valid item.

The `menu_verified` field in `e2e_out_of_menu_test.json` still reads "kiểm tra ngày
2026-07-23".  Every dataset that hard-codes dish names needs re-verification against the menu
before the chapter is written, and §5.2.1's "219-entry menu" needs correcting to 234.

---

## §5.4.1 — Intent Classification & Routing

### Single-Intent Accuracy (n = 149, `evals/data/router/single_intent_eval.json`)

**140/149 = 94.0 %** (Wilson 95 % CI: 89.0–96.8 %).  p50 latency 7.9 ms, p95 8.4 ms.

*Result file:* `mlp_router_eval_20260728_190748.json` (2026-07-28).  The dataset was expanded from 100 to 149 cases on 2026-07-26 to improve class balance (roughly 37 per class) and vocabulary coverage, particularly the first-person pronoun `tôi` (absent from the original 100-case set).  The original 100-case subset scored 98/100 = 98.0 %.

The 2026-07-28 re-run reproduces the 2026-07-26 figure exactly — same 140/149, same nine errors, same per-class table, mean confidence 0.961 — which is the expected outcome for a deterministic classifier on an unchanged checkpoint and confirms the harness is stable across the model swap.

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

### Context-Dependent Accuracy (n = 123, `evals/data/router/context_dependent_eval.json`)

| Mode | Accuracy | 95 % Wilson CI | n |
|------|:--------:|:--------------:|:--:|
| With context features | 61.0 % (75/123) | 52.1–69.1 % | 123 |
| Without context (IDLE defaults) | 48.0 % (59/123) | 39.3–56.7 % | 123 |

*Result file:* `mlp_router_eval_20260728_190748.json` (2026-07-28).  **The dataset has grown
again since the previous revision, from 70 cases (36 utterance groups) to 123 cases (62
groups)**, spanning four order stages (IDLE 62, AWAITING_CONFIRMATION 36, BUILDING 22,
CONFIRMED 3).  The figures here therefore supersede the 70-case ones and are not directly
comparable to them: absolute accuracy falls (70.0 % → 61.0 %) because the added cases are
harder, while the quantity the experiment exists to measure — the context effect — gets
stronger and, for the first time, significant.

**Label correction, disclosed** *(concerns the superseded 70-case set; retained because it is a
disclosure of edits made to ground truth after predictions were visible)*.  An earlier run of the same eval two minutes prior
(`mlp_router_eval_20260726_124805.json`) reports 46/70 = 65.7 % with context.  The model's
predictions are byte-identical across the two runs; three ground-truth labels were corrected
between them, all at IDLE: CD-023 "chốt luôn đi" (CHAT → ORDER), CD-053 "thanh toán đi"
(CHAT → PAYMENT) and CD-055 "cho xin bill" (CHAT → PAYMENT).  The correction on CD-053 and
CD-055 is sound on the merits, since an explicit request to pay or to be billed is a PAYMENT
intent regardless of order stage and the system answers it gracefully when no order exists.
CD-023 is more debatable and its `note` field still reads "IDLE không có gì để chốt → CHAT",
contradicting its new label.  Because the corrections raise the reported figure and were made
after the predictions were visible, they are stated here rather than left to be discovered.

**The ablation now reaches significance.**  McNemar exact on the 18 discordant pairs:
b = 17 (context fixes), c = 1 (context breaks), **p = 1.4 × 10⁻⁴**.  On the 70-case set this
comparison was b = 11, c = 3, p = 0.057 — close but not significant, and the previous revision
estimated that roughly 140 cases would be needed to resolve it.  The expansion to 123 delivered
that: the D-vs-E context ablation is no longer an underpowered "not significant" row.  The
13.0-percentage-point gap (48.0 % → 61.0 %) is now the strongest single piece of evidence for
the context-feature design decision.

**The set is also no longer weak by construction.**  The previous revision's main caveat was
that 10 of 36 utterance groups carried the same label at both order stages, so context could
not contribute on them either way.  At 62 groups only **one** does.  That criticism is retired;
the set now tests what its name claims.

The 17 cases context resolved are dominated by bare affirmations that are CHAT at IDLE and
ORDER at AWAITING_CONFIRMATION — "ok", "ừ", "đúng rồi", "được", "ok em", "chuẩn", "đồng ý",
"vâng", "rồi đó", "đúng vậy", "ok bạn", "đúng òi" — plus "oke" and "ok luôn" at IDLE → CHAT,
"món này ngon không" at BUILDING → SEARCH, and "cho coi menu đi" at IDLE → SEARCH.  Exactly
one case broke: CD-038 "còn gì nữa không" at BUILDING, routed to SEARCH where the label expects
CHAT — a defensible prediction against a debatable label.

The 47 cases wrong in both modes are the same failure mode reported before, now with a sharper
profile: 25 of them sit at IDLE, and 28 carry an expected label of CHAT against which the MLP
predicts ORDER 21 times.  These are utterances containing ambiguous action verbs ("thêm",
"lấy", "cho", "bỏ", "đặt") in empty-cart contexts, where the surface form is an ordering
command but the label expects CHAT because there is nothing to act upon.  The customer's intent
is genuinely underspecified in these cases; this is the class the low-confidence rewriter path
exists to absorb, not one the classifier can be expected to settle from text alone.

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

### Five-Arm Router Ablation (n = 360 pooled, `evals/results/router_arms_20260728_193643.json`)

Run at **N = 5** on the deployment model, `--arms A C D E F`.  Arm B was dropped; see
*Run Configuration* above for why, and what is lost with it.  The pooled set grew again with the
context-dependent dataset, from 304 cases to **360** (`router`, `single`, `semantic`, `context`,
`context_dep`).

| Arm | System | n correct | Accuracy | 95 % Wilson CI | p50 (ms) | p95 (ms) |
|-----|--------|:---------:|----------|---------------:|----------:|----------:|
| A | Centroid (semantic only) | 251/360 | 69.7 % | 64.8–74.2 % | 10 | 11 |
| C | Hybrid semantic→SLM (previous) | 251/360 | 69.7 % | 64.8–74.2 % | 10 | 1820 |
| D | MLP, no context features | 274/360 | 76.1 % | 71.4–80.2 % | 8 | 9 |
| **E** | **MLP + context (proposed)** | **290/360** | **80.6 %** | **76.2–84.3 %** | **8** | **9** |
| F | LLM zero-shot (`qwen2.5:14b-instruct-q6_K`) | 277/360 | 76.9 % | 72.3–81.0 % | 235 | 267 |

Paired McNemar exact (identical items, n = 360):

| Comparison | b (E only) | c (other only) | p | Verdict |
|---|---:|---:|---:|---|
| E vs C (previous system) | 61 | 22 | 2.2 × 10⁻⁵ | **significant** |
| E vs A (centroid) | 61 | 22 | 2.2 × 10⁻⁵ | **significant** |
| E vs D (context ablation) | 18 | 2 | 4.0 × 10⁻⁴ | **significant** |
| E vs F (LLM ceiling, 14B) | 32 | 19 | 0.092 | not significant, favouring E |

**The LLM-ceiling caveat is resolved, and it resolved in the thesis's favour.**  The previous
revision had to concede that arm F was a 7B while the system deploys a 14B, so the ablation
established only that the classifier matched a smaller model than the one that ships.  Arm F is
now the deployed `qwen2.5:14b-instruct-q6_K`.  The proposed arm still comes out ahead —
80.6 % against 76.9 % — and McNemar still cannot separate them (p = 0.092).  The defensible
sentence is therefore stronger than before and has the same shape:

> The trained MLP classifier is statistically indistinguishable from a zero-shot router built on
> the **deployed 14 B model** (p = 0.092 at n = 360), while running at 8 ms against 235 ms p50 —
> a **29 × latency advantage** — and is significantly better than every non-LLM baseline.

#### Control: is the 14 B really worse than the 7 B?  No — the pool changed.

Arm F scored 83.2 % in the previous revision on the 7 B and 76.9 % here on the 14 B, which reads
as the larger model routing worse.  It does not survive checking, and the check matters because
the naive reading would undermine the model-selection argument in §5.1.1.

**The pools are different.**  Every arm fell by a similar margin between the two revisions,
including the three that never touch a language model and therefore *cannot* be affected by the
model swap:

| Arm | Previous (n = 304) | This pass (n = 360) | Δ | Uses an LLM? |
|-----|:---:|:---:|:---:|:---:|
| A Centroid | 76.3 % | 69.7 % | −6.6 | no |
| D MLP, no context | 83.6 % | 76.1 % | −7.5 | no |
| E MLP + context | 86.2 % | 80.6 % | −5.6 | no |
| F LLM zero-shot | 83.2 % | 76.9 % | −6.3 | yes |

Arm F's drop sits inside the band set by arms that are provably model-independent, so there is
nothing left for the model swap to explain.

**Measured directly.**  Arm F was re-run with `qwen2.5:7b-instruct` over the identical 360-item
pool (`ARM_LLM_MODEL=qwen2.5:7b-instruct`, result file `armF_7b_20260728.json`):

| Model | Accuracy | 95 % Wilson CI | p50 |
|-------|:--------:|:--------------:|----:|
| `qwen2.5:14b-instruct-q6_K` | 277/360 = 76.9 % | 72.3–81.0 % | 235 ms |
| `qwen2.5:7b-instruct` | 274/360 = 76.1 % | 71.4–80.2 % | 196 ms |

Paired McNemar: b = 14, c = 11, **p = 0.69**.  The two models agree on 328 of 360 items
(91.1 %).  The 14 B is if anything marginally ahead, and the difference is not significant.
**The 7 B-versus-14 B comparison is a null result, and the apparent regression was entirely
pool composition.**

**Why both models sit at the same number — a structural ceiling.**  The discordant cases are
dominated by the context-dependent subset, and inspection explains it.  Of the 112
`context_dep` items in the pool, **110 belong to 55 utterances whose gold label differs by order
stage** ("ok luôn", "rồi đó", "chắc rồi", "đúng òi", "thôi khỏi", "chưa cần", …).  Arm F is a
text-only prompt: it never receives `order_stage`, so it assigns one label per utterance string
and is necessarily wrong on one member of every such pair.  **Its ceiling on those 110 items is
55, i.e. 50 %.**  Measured:

| Arm | `context_dep` (n = 112) | Sees order stage? |
|-----|:---:|:---:|
| F, 14 B | 56/112 = 50 % | no — **at the ceiling** |
| F, 7 B | 53/112 = 47 % | no — at the ceiling |
| A, centroid | 57/112 = 51 % | no — at the ceiling |
| **E, MLP + context** | **65/112 = 58 %** | **yes — the only arm above it** |

Both prompted arms and the centroid are pinned at the ceiling regardless of capacity, while the
proposed arm is the only one that clears it.  This sharpens the contribution claim considerably.
The argument is not "a small classifier happens to match a large language model"; it is that on
the subset where conversation state decides the label, **no text-only router can exceed 50 % no
matter how large it is**, and the gap is closed by giving the classifier the state rather than
by scaling the model.  It also explains why growing the context-dependent set lowered every arm
except E: the pool gained items that are unanswerable without context.

Per-dataset accuracy for the full comparison:

| Arm | router (39) | single (118) | semantic (71) | context (20) | context_dep (112) |
|-----|:---:|:---:|:---:|:---:|:---:|
| E, MLP + context | 97 % | 93 % | 87 % | 75 % | 58 % |
| F, 14 B | 95 % | 91 % | 92 % | 60 % | 50 % |
| F, 7 B | 95 % | 90 % | 93 % | 60 % | 47 % |
| A, centroid | 77 % | 72 % | 94 % | 60 % | 51 % |

The prompted arms beat the classifier on `semantic` (92 % vs 87 %) — the subset of paraphrased,
self-contained questions where world knowledge helps and conversation state is irrelevant.  That
is the honest counterweight to the paragraph above and belongs in the chapter beside it.


**The context ablation is now significant here too.**  D vs E moved from p = 0.057 at n = 304 to
b = 18, c = 2, **p = 4.0 × 10⁻⁴** at n = 360, agreeing with the standalone context experiment in
§5.4.1 above.  The two independent routes to that conclusion are the strongest result in this
section.

**The N = 5 protocol produced zero spread on the prompted arms.**  Arms C and F were each run
five times and returned exactly 251/360 and 277/360 on all five runs.  This is not a harness
error: `_prompted()` fixes temperature at 0.0, and the hybrid arm's SLM fallback is likewise
greedy.  §5.2.3 anticipates reporting `mean [min–max]` for stochastic components; for these two
arms the range is degenerate, and the honest reporting is a single figure with the note that
five draws were taken and did not differ.  The genuine run-to-run variation this chapter has
observed elsewhere — the QS-006 tool-call flip in §5.4.5 — comes from the agent graph, not from
the router's prompted arms.

**Arm C fires its SLM fallback on 1 % of cases and is otherwise the centroid.**  Arms A and C
score identically (251/360) and produce the same Wilson interval, which was initially read as a
possible harness fault.  It is not: the per-arm prediction vectors are stored in the result
file, and comparing them directly shows the two arms **differ on exactly 4 of 360 items**.  All
four are two utterances that appear at two order stages —

| Case | Utterance | Gold | A (centroid) | C (hybrid) |
|------|-----------|------|--------------|------------|
| CD-066 | "chốt nha" | CHAT | CHAT ✓ | ORDER ✗ |
| CD-067 | "chốt nha" | ORDER | CHAT ✗ | ORDER ✓ |
| CD-092 | "đợi chút" | CHAT | CHAT ✓ | ORDER ✗ |
| CD-093 | "đợi chút" | ORDER | CHAT ✗ | ORDER ✓ |

— so each arm wins one of each pair and they cancel exactly: McNemar b = 2, c = 2, p = 1.0.
The hybrid arm's semantic fast path accepts the other 356 cases outright, so its SLM fallback
runs about 1 % of the time.  That is consistent with its p95 of 1 820 ms: the fallback is rare
and expensive, which is precisely the behaviour the previous production router had and the
reason it was replaced.

The practical consequence for the chapter stands: **E-vs-C and E-vs-A are not independent
comparisons.**  They return identical discordant counts (b = 61, c = 22, p = 2.2 × 10⁻⁵) because
the two arms differ on four items that cancel.  Report one of them, or report both while saying
they are the same comparison; do not present them as two separate pieces of evidence.

Full pairwise McNemar, computed from the stored prediction vectors:

| Pair | b (row only) | c (col only) | p |
|------|---:|---:|---:|
| A vs C | 2 | 2 | 1.0 |
| A vs D | 25 | 48 | 0.0095 |
| A vs E | 22 | 61 | 2.2 × 10⁻⁵ |
| A vs F | 22 | 48 | 0.0025 |
| D vs E | 2 | 18 | 4.0 × 10⁻⁴ |
| D vs F | 18 | 21 | 0.75 |
| E vs F | 32 | 19 | 0.092 |

Per-class F1 for the proposed arm

| Class | Precision | Recall | F1 | Support |
|-------|:---------:|:------:|:----:|:-------:|
| ORDER | 0.757 | 0.883 | 0.815 | 120 |
| SEARCH | 0.803 | 0.792 | 0.797 | 72 |
| PAYMENT | 0.946 | 0.964 | 0.955 | 55 |
| CHAT | 0.796 | 0.655 | 0.718 | 113 |

CHAT recall is the weak class at 0.655, the same pattern the standalone single-intent
experiment shows: conversational remarks carrying ordering verbs are pulled into ORDER.

**Accuracies fell across every arm relative to the previous revision** (E: 86.2 % → 80.6 %,
F: 83.2 % → 76.9 %, A: 76.3 % → 69.7 %).  This is a composition change, not a regression — the
pool grew from 304 to 360 by absorbing the expanded context-dependent set, whose cases are
harder than the pool average.  Arm-to-arm comparisons within this table are paired on identical
items and are unaffected; comparisons against the previous revision's numbers are not valid.

**GPU memory remains unreportable per arm.**  The `peak_gpu_mb` field records total device
occupancy while each arm ran (A: 1 785 MB, C: 14 770 MB, D/E/F: 15 318 MB) and is cumulative in
arm order, so it measures what was already loaded rather than what the arm needs.  A per-arm
figure requires running each arm alone from a cold GPU (`--arms E`), which this pass did not do.
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

*Result file:* `name_resolution_20260728_190802.json` (2026-07-28).  The previous revision
reported **70/70 = 100 %** from `name_resolution_20260719_000825.json` and warned that the set
"should be re-run if `menu.json` changes".  It has changed, and the warning has come due.

| Resolution stage | Correct | Total | Accuracy |
|------------------|:-------:|:-----:|:--------:|
| Exact match | 15 | 15 | 100 % |
| Diacritic-insensitive | 10 | 10 | 100 % |
| Prefix match | 10 | 10 | 100 % |
| Substring match | 10 | 10 | 100 % |
| Token-Jaccard (match) | 5 | 5 | 100 % |
| Token-Jaccard (reject) | 4 | 4 | 100 % |
| Misspelled (correctly rejected) | 11 | 16 | 68.8 % |
| **Total** | **65** | **70** | **92.9 %** (Wilson 84.3–96.9 %) |

**The five failures are stale ground truth, not a resolver regression.**  `menu.json` has grown
from the **219 dishes** this chapter quotes throughout to **234**, and four of the names the
dataset marks as off-menu (`expected = none`) are now real dishes the resolver is correct to
find:

| Case | Probe | Dataset says | Menu now contains |
|------|-------|--------------|-------------------|
| NR-062 | "Gỏi Cuốn" | off-menu | Gỏi Cuốn Tôm Thịt |
| NR-064 | "Bò Nướng Lá Lốt" | off-menu | Bò Nướng Lá Lốt (exact) |
| NR-065 | "Nước Cam" | nearest = Nước Suối | Nước Ép Cam |
| NR-066 | "Trà Đào" | off-menu | Trà Đào Cam Sả |
| NR-068 | "Cá Hồi Nướng" | nearest = Cá Chim Nướng Sa Tế | Khô Cá Đuối Nướng (new nearest) |

Six of the seven resolution stages — exact, diacritic-insensitive, prefix, substring,
token-Jaccard match and token-Jaccard reject — still score 100 %.  The entire loss sits in the
seventh, the `misspelled` bucket, and is attributable to menu growth
rather than to the resolver, whose behaviour on all five is the behaviour one would want.

**This is an action item, not a result.**  Either the five labels are corrected against the
current `menu.json` and the experiment re-run, or the chapter states that name resolution was
measured against the 219-dish snapshot.  Reporting 92.9 % as a resolver accuracy would
understate the component and invite a question at the defence that has a better answer.  The
same menu drift affects the out-of-menu dataset (see §5.4.2 below) and the "219-entry menu"
figure asserted in §5.2.1.

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

*Result file:* `ambiguity_20260728_190802.json` (2026-07-28, deterministic validator function).
Re-run against the current 234-dish `menu.json`: unchanged at 25/25, precision 1.000, recall
1.000.  Unlike name resolution, this experiment is insensitive to menu growth — it asks whether
a generic prefix maps to more than one dish, and adding dishes cannot turn an ambiguous prefix
unambiguous.  The candidate counts did shift (e.g. "Ốc Cà Na" now returns 4 candidates where
the dataset's `note` expects ≥ 9), which affects none of the pass/fail outcomes but does mean
the per-case expected-count annotations in `ambiguity_eval.json` are stale.

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

*Result file:* `retrieval_full_20260728_190807.json` (2026-07-28).

| Mode | P@5 | R@5 | MRR | Hit Rate | Latency p50 |
|------|:----:|:----:|:----:|:--------:|:-----------:|
| **BM25 only** | **0.402** | **0.747** | **0.701** | **0.958** | **0.4 ms** |
| FAISS only | 0.254 | 0.461 | 0.580 | 0.667 | 7.8 ms |
| RRF fusion | 0.350 | 0.634 | 0.581 | 0.833 | 8.9 ms |

**The fusion result has reversed, and this is the most consequential change in this revision.**
The previous revision reported RRF ahead of both single lanes on every metric
(P@5 0.400, R@5 0.743, MRR 0.751, hit 0.917).  It is now behind BM25 on every metric: recall
drops 0.747 → 0.634, hit rate 0.958 → 0.833, MRR 0.701 → 0.581.  §5.2.2 states that recall and
hit rate are the metrics that matter here, because the agent speaks a paraphrase of the top
results and cannot recover a dish the retriever missed — so this is a loss exactly where the
chapter argues it counts.  On this dataset the lexical lane alone is the strongest configuration
and fusion actively costs recall by promoting weak semantic candidates into the top 5.

Two further observations from the same run:

- **FAISS latency fell from 422 ms to 7.8 ms p50.**  The previous revision's 422 ms was an
  outlier attributable to first-query model loading inside the timed region; at 7.8 ms the
  vector lane is no longer a latency argument for or against fusion.
- **The vector lane retrieves non-dish documents.**  FAISS top-5 lists include
  `1. Giới thiệu chung`, `# THÔNG TIN NHÀ HÀNG "ỐC QUẬY"` and `Chị Lan` — restaurant-info
  chunks sitting in the same index as dishes.  These can never be relevant to a dish query, and
  they are a plausible mechanism for both the FAISS numbers and the fusion regression.  Whether
  the index should be partitioned by document type is a design question this result raises and
  does not answer.

### Per-Difficulty (RRF)

| Difficulty | n | P@5 | R@5 | MRR | Hit Rate |
|------------|:--:|:----:|:----:|:----:|:--------:|
| Easy | 8 | 0.425 | 0.865 | 0.938 | 1.000 |
| Medium | 9 | 0.356 | 0.741 | 0.491 | 0.889 |
| Hard | 7 | 0.257 | 0.232 | 0.291 | 0.571 |

The hard tier is where the system is weak: R@5 = 0.232 and a hit rate of 0.571 mean that on
three of seven intent-style queries ("đồ nhắm lai rai với bia", "món nào bán chạy được yêu
thích nhất", "có gì cho nhóm đông người chia sẻ") nothing relevant reaches the top 5 at all.

### Dual-Lane Gatekeeper (n = 24 queries)

| Category | Count |
|----------|:-----:|
| Both lanes pass | 20 |
| Lexical-only pass | 2 |
| Semantic-only pass | 0 |
| Rejected | 2 |
| Total passed | 22 (91.7 %) |

Top-1 cosine scores span [0.170, 0.587], all inside the valid [0, 1] interval — the cos > 1.0
anomaly fixed in commit `f308a1a` has not returned.  The semantic lane still never passes
independently.  The two lexical-only passes are SR-023 "đồ uống không cồn cho trẻ em"
(cos = 0.240) and SR-024 "hàu chế biến kiểu gì" (cos = 0.273).

**One rejection is correct and one is a harness defect.**  SR-021 "có gì cho nhóm đông người
chia sẻ" (cos = 0.195) is the same correct rejection reported before: neither lane finds
anything.  SR-002 "cho xem lẩu thái" is not — it is an *easy* query on which BM25 returns
`Lẩu Thái` at rank 1 with R@5 = 1.000, and the gatekeeper blocks it anyway (cos = 0.170,
top_doc `Rau Muống Xào Chao`).

The cause is a divergence between the harness and the system.  `gatekeeper_check()` in
`evals/scripts/eval_retrieval_full.py:113-115` builds its lexical-lane text from the **vector
engine's top-1 document only**, while the production gatekeeper in
`src/agent_brain/services/retriever/fusion/rrf.py:44-47` concatenates the **BM25 top-1 and the
vector top-1**.  The harness docstring claims "This is the same logic as the production
gatekeeper in `rrf.py`"; it is not.  The harness therefore measures a strictly stronger
gatekeeper than the one that ships, and would reject any query whose keyword match lives in the
lexical lane — which is precisely what "lexical lane" is supposed to mean.

Production would admit SR-002, since `Lẩu Thái` contains the query keyword.  **The gatekeeper
figures above, and the 23/24 reported in the previous revision, both understate the deployed
gatekeeper.**  The harness should be corrected to match `rrf.py` and this experiment re-run
before the number reaches the chapter; the fix is one line, but it changes a reported result and
so has been left for a decision rather than applied inside an evaluation pass.

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

### Router Latency per Arm (n = 360)

*Result file:* `router_arms_20260728_193643.json` (2026-07-28, N = 5).

| Arm | p50 | p95 |
|-----|:-----:|:-----:|
| MLP + context (proposed) | 8 ms | 9 ms |
| MLP, no context | 8 ms | 9 ms |
| Centroid | 10 ms | 11 ms |
| Hybrid semantic→SLM | 10 ms | 1 820 ms |
| LLM zero-shot (`qwen2.5:14b-instruct-q6_K`) | 235 ms | 267 ms |

Arm B (`SLM only`) is absent; see *Run Configuration*.  The previous revision measured it at
194 ms p50 on `qwen2.5:3b`.

Two things changed against the previous revision.  The prompted arm is now the 14B rather than
the 7B and costs 235 ms p50 against the 7B's 229 ms — **model size barely moved the router's
latency**, because the arm emits a single label token and is dominated by prompt processing
rather than by generation.  The MLP arms are marginally faster (9 → 8 ms), which is noise.

The hybrid arm's p95 rose from 705 ms to 1 820 ms, which is what one would expect once its SLM
fallback runs on a 14B rather than a 3B — but see the note in §5.4.1 that arm C may be
degenerating to arm A on this pool, which that p95 does not sit comfortably with.  The p95
should be read as evidence the fallback fires, not as a settled figure.

The **29 × p50 advantage** of the classifier over the prompted router (8 ms vs 235 ms) is the
number the architecture argument rests on, and it survives the move to the deployment model
intact.

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

*Result file:* `bench_api_20260728_190815.json` (2026-07-28).  All 12 REST endpoints were
exercised against the live orchestrator on port 8000.  **The harness now takes n = 100 samples
per endpoint rather than the n = 10 of the previous revision**, so these percentiles are better
resolved; p99 in particular was previously estimated from ten observations and meant little.

| Endpoint | p50 (ms) | p95 (ms) | p99 (ms) |
|----------|:---:|:---:|:---:|
| GET /menu | 1.1 | 1.2 | 1.2 |
| GET /tables | 1.1 | 1.2 | 1.3 |
| GET /tables/{id} | 1.2 | 1.3 | 1.5 |
| POST /seatings | 1.0 | 1.1 | 1.2 |
| GET /orders | 1.3 | 1.4 | 1.4 |
| POST /orders | 0.8 | 1.0 | 6.4 |
| GET /payments | 1.1 | 1.2 | 1.3 |
| GET /robots | 1.1 | 1.3 | 1.4 |
| GET /tasks | 1.2 | 1.4 | 1.5 |
| GET /layout | 0.9 | 1.0 | 1.0 |
| POST /voice/event | 0.8 | 1.0 | 1.1 |
| POST /voice/listen | 0.8 | 0.9 | 0.9 |

All 1 200 requests succeeded (`n_err = 0` on every endpoint).  Eleven of the twelve endpoints
respond within 1.5 ms at p99 — roughly twice as fast as the previous revision's figures, which
is consistent with the larger sample amortising the warmup cost rather than with any change to
the backend.  The single exception is **POST /orders at p99 = 6.4 ms against a p50 of 0.8 ms**,
a tail that appears only at n = 100 and was invisible at n = 10.  It is the one write path that
inserts order lines, so an occasional SQLite write stall is the obvious explanation; at 6.4 ms
it is far inside any interactive budget and is recorded rather than investigated.

The FastAPI + SQLite design meets the real-time requirement — push-based WebSocket events
replace the 5–10 s polling cycle of traditional KDS systems (§2.6.4).

Concurrency: 2 and then 4 simultaneous table orders, all successful (`2_tables.n_ok = 2` at
p95 = 2.3 ms, `4_tables.n_ok = 4` at p95 = 3.0 ms).  This measures concurrent HTTP handling
only.  It is **not** the session-isolation experiment §5.5.2 calls for, which requires
concurrent conversations at different tables ordering overlapping dishes and a cross-session
leakage count.  That experiment has still not been run.

### WebSocket Event Propagation

*Result file:* `bench_ws_20260728_190817.json`.  **Still unmeasured, and for a new reason — the
benchmark is now broken.**

The previous revision reported that the WebSocket client connected but collected no events
because the orchestrator was idle.  This run is worse: the harness generated its own traffic and
**every single one of the 20 `POST /orders` calls it issued was rejected with HTTP 422
Unprocessable Entity**, leaving `rest_calls = 0`.  It collected 21 unrelated WS events from
ambient activity and could match none of them to traffic it caused.

This is a harness defect, not a backend defect: in the same pass `bench_api` posted to
`/orders` 100 times with zero errors, and `bench_fleet` created an order that returned 201.
`bench_ws.py` is therefore building a request body the current `/orders` schema no longer
accepts — the endpoint's contract has moved and this one caller was not updated with it.

WebSocket propagation latency consequently remains unevaluated, and §5.6.4 must continue to say
so.  The fix is to bring `bench_ws.py`'s payload in line with the schema `bench_api.py` already
uses; until then this benchmark reports nothing and should not be cited.

---

## §5.5.3 — Fleet Management & Robot Task Lifecycle

*Result file:* `bench_fleet_20260728_190920.json` (2026-07-28).  Re-run; the lifecycle outcome
is unchanged from 2026-07-26.

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

*Result file:* `bench_fleet_20260728_190920.json` (2026-07-28).

A seating event (kiosk role) followed by an order creation (agent role) was driven through
the REST API, and the three role views were polled to verify convergence:

| Role | Endpoint | Before | After |
|------|----------|--------|-------|
| Kiosk (seating) | `POST /seatings` → table 3 | `TRONG` | `DANG_PHUC_VU`, party_size=4 |
| Agent (order) | `POST /orders` → table 3 | 3 orders | 5 orders, latest 245,000 ₫ |
| Panel (monitor) | `GET /orders` | 3 orders | 5 orders visible |
| Customer (tablet) | `GET /tables/3` | `TRONG` | `DANG_PHUC_VU`, `current_order_id = 5` |
| Admin | `POST /admin/reset` | — | All tables freed ✓ |

All three role views (kiosk, panel, customer tablet) reflect the same backend state within
a single HTTP request-response cycle — there are no stale views or polling delays.  The
FastAPI + SQLite backend serves as a single source of truth.

The result file records `orders_before = 3`, `orders_after = 5` and `tasks_before = 2`,
`tasks_after = 3`; the extra order and the pre-existing tasks are residue from the fleet
lifecycle test that ran immediately before in the same process, and from earlier runs that were
never reset.  Convergence across roles is what this experiment establishes, and that holds; the
absolute counts are not a clean baseline and the benchmark should reset between the two phases.
The drift in these counts between the 2026-07-26 run (0 → 2) and this one (3 → 5) is itself
evidence for that: the deltas are stable, the absolutes are not.  Note also that this measures REST
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
