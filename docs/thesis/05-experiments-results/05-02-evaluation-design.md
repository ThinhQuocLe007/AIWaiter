## 5.2 Evaluation Design

With the system described, this section fixes what will be measured, against what data, by
what standard, and under what statistical protocol. It closes with an inventory of every
experiment so that any number reported in this chapter can be regenerated from the repository.

### 5.2.1 Datasets

All evaluation data was authored against the menu of a single reference restaurant, *Ốc Quậy*,
a Vietnamese seafood establishment. Every dish name in every dataset resolves against
`assets/data/menu.json`, so the same 219-entry menu is the ground truth for retrieval, name
resolution and out-of-menu rejection alike. This is deliberate: a real restaurant has one menu,
and a system that performs differently on different menus has a domain-adaptation problem, not
a core accuracy problem. Evaluating against one menu tests the architecture; evaluating against
several would test the menu-authoring process.

Sample sizes were chosen so that the Wilson 95 % confidence interval on an accuracy near 0.95
is narrower than the effect each experiment must detect. Where a comparison remains
underpowered at the available sample size, the experiment states the size it would need rather
than over-reading the point estimate.

| Dataset | File | Size | Purpose | Validates Need |
|---------|------|------|---------|---------------|
| Router single-intent accuracy | `evals/data/router/single_intent_eval.json` | 149 cases (~37 per class) | MLP classification accuracy on self-contained single-intent utterances. No context features. Balanced difficulty: ~⅓ easy, ⅓ medium, ⅓ hard. | §2.4 |
| Router multi-intent detection | `evals/data/router/multi_intent_detection.json` | 30 cases (27 true multi, 3 pseudo) | Whether the router correctly flags multi-intent utterances for the rewriter path. | §2.4 |
| Router context-dependent | `evals/data/router/context_dependent_eval.json` | 70 cases (36 utterance groups) | Context-feature ablation: same utterance evaluated with and without order_stage context. | §2.4 |
| Retrieval evaluation | `evals/data/retrieval/retrieval_eval.json` | 24 queries | Menu search relevance with graded judgements | §2.5 |
| E2E qualitative case studies | `evals/data/e2e/e2e_qualitative.json` | 7 conversations, 30 turns; 6 reported | Full-pipeline behaviour: happy path, search-then-order, multi-intent rewriter, modification, ambiguity, a 12-turn sitting, and off-menu handling. Reported as transcripts rather than a pass rate; the modification conversation is subsumed by the 12-turn sitting and is not reproduced in §5.4.5. | §2.4 |
| Out-of-menu robustness | `evals/data/e2e/e2e_out_of_menu_test.json` | 30 scenarios, 7 categories | Off-menu rejection; includes a negative control | §2.4 |
| **Safety pool** | *(E2E + out-of-menu scenarios)* | **41 scenarios** | Paired set both validator ablation arms run on | §2.4 |
| Multi-intent completeness | `evals/data/e2e/multi_intent_eval.json` | 25 turns | Intents executed vs. intents verbalised | §2.4 |
| Validator name resolution | `evals/data/validator/name_resolution_eval.json` | 70 pairs | Per-stage name resolution accuracy | §2.4 |
| Validator ambiguity | `evals/data/validator/ambiguity_eval.json` | 25 cases | Generic-name ambiguity detection | §2.4 |

Every dataset was written by hand rather than generated. The three router sets were assembled by
`evals/data/router/build_eval_datasets.py` from curated test cases held out from the training
distribution, and each targets a different question, which is why they are not pooled by default:
the single-intent set asks whether an utterance can be classified from its text alone, the
context-dependent set asks whether conversation state changes the answer, and the multi-intent
set asks whether the router recognises an utterance it should not try to classify at all.

---

### 5.2.2 Metrics

Every metric used in this chapter is defined here. The standard ones are listed below without
further comment. After them come three choices of measure that are not obvious and that the
results depend on, followed by the four metrics specific to this system.

*Standard metrics, with the experiment each appears in.*

| Metric | Definition | Used in |
|--------|-----------|---------|
| Accuracy | $N_{\text{correct}} / N_{\text{total}}$ | §5.4.1 |
| Per-class precision, recall, F1 | Standard definitions, reported beside accuracy | §5.4.1 |
| Confusion matrix | Rows are the true intent, columns the predicted intent; the diagonal is correct classifications | §5.4.1 |
| Precision at rank k | $\text{P@}k = \lvert R \cap D_k \rvert / k$ | §5.4.4 |
| Recall at rank k | $\text{R@}k = \lvert R \cap D_k \rvert / \lvert R \rvert$ | §5.4.4 |
| Mean reciprocal rank | Mean of $1 / \text{rank}$ of the first relevant document | §5.4.4 |
| Hit rate | Fraction of queries with at least one relevant document in the top k | §5.4.4 |
| Pass rate | Fraction of scenarios in which every turn's assertions hold | §5.4.2 |

Three of those choices are not obvious.

**Recall and hit rate over precision.** The agent speaks a paraphrase of the top results rather
than showing a list, so the response generator can filter noise but cannot recover a dish the
retriever missed. A low hit rate means whole query categories return nothing. An MRR below 0.5
puts the first useful dish outside the top two, and only about three are ever spoken.

**Pass rate is all-or-nothing per scenario.** One failed turn fails the scenario, because one
wrong tool call puts a wrong item on the bill. It is a lower bound on real reliability: the
scenarios were written by the system's author.

**Latency as percentiles, never as a mean.** The model stages are right-skewed, so a mean
describes a turn nobody experiences. p50 is a typical turn, p95 the worst common one. Turn
latency is transcript to reply; stage latency is per graph node.

Four metrics are specific to this system.

**Multi-intent detection rate.** Fraction of multi-intent utterances the router flags for
decomposition, a flag being a confidence below 0.7 or the presence of a boundary marker. This is
not a classification score, since no single label is correct for a two-intent utterance.
Pseudo-multi-intent controls, which carry a boundary marker but one intent, give the false-alarm
rate; a false alarm costs one rewriter call and still returns the right answer.

**Validator catch rate and false positive rate.** Blocked hallucinated calls over hallucinated
calls, and wrongly blocked valid calls over valid calls. Read as a pair, since rejecting
everything gives a perfect catch rate. §5.4.2 reports counts instead of rates, because the
denominator is however many hallucinations the model produced on that run, a property of the
model rather than of the validator.

**Delegate rate.** Fraction of tool-calling turns on which a worker calls `delegate` rather than
a domain tool. An abstention, not an error. Read against the test set, since one containing
deliberate out-of-domain utterances should produce a higher rate.

**Multi-intent verbalisation rate.** Fraction of executed intents the spoken reply mentions. It
catches actions taken but not reported, which the customer cannot detect and the bill will.
§5.4.3 counts an intent as verbalised when the customer learns its fate, success or correct
refusal, and reports both that rule and the narrower one it replaced.

---

### 5.2.3 Statistical Protocol

Several components of this system are stochastic. The tool-calling language model, the
small-model router arm and the language-model router arm all sample from a distribution, so a
single run reports one draw rather than the system's mean behaviour.

Some components are deterministic given fixed weights and a fixed index: the MLP classifier, the
centroid router, BM25, FAISS and the deterministic validator. These are run once and reported as
exact fractions.

The protocol for anything involving a language model is N = 5 runs, reported as `mean
[min–max]`, with the sampling temperature fixed at its deployment value and stated per
experiment, and the random seed varied deliberately across runs so that the spread reflects
genuine sampling variance rather than one lucky trajectory.

**What meets that protocol, and what does not.** Two experiments meet it: the turn-latency
measurement in §5.4.6 and the multi-intent verbalisation experiment in §5.4.3. Five do not, and
are single runs: the validator ablation, the out-of-menu robustness test, the delegate
measurement, the qualitative conversations, and the three language-model arms of the router
ablation. Each of those reports one draw from a distribution rather than an estimate of its mean,
and the sections concerned repeat the qualification where the figures appear. This is not a
hypothetical concern: the same conversation has been observed to call a different tool on
identical input across runs, which changes whether a scenario's assertions hold. The protocol
stated above is therefore the standard this chapter was designed against and met in part, not a
description of how every figure in it was produced.

Accuracies and pass rates are proportions estimated from small samples, where the normal
approximation is unreliable near 1.0. All such quantities are reported with a **Wilson 95 %
confidence interval**, which stays inside [0, 1] and remains well-behaved for p̂ near the
boundary. Sample sizes in §5.2.1 were chosen so that this interval is narrower than the effect
the experiment must resolve.

Router arms are evaluated on **identical items**, so comparisons are paired and use **McNemar's
exact test** on the discordant pairs, the cases where one arm is correct and the other is not.
Concordant cases carry no information about which arm is better and are excluded. This is
substantially more powerful than comparing two independent accuracy figures, which is what makes
a decisive comparison possible at the sample sizes available here. Differences are reported with
the discordant counts (b, c) and the exact p-value.

No proportion is reported to more significant figures than its sample size supports. With n = 39,
an accuracy is quoted as a fraction (37/39) with its Wilson interval, not as `94.87 %`.

---

### 5.2.4 Experiment Inventory and Reproduction

Every experiment in this chapter is listed here with the script that produces it, so that any
number reported can be regenerated from the repository.

| § | Experiment | Script |
|---|-----------|--------|
| 5.4.1 | Single-intent accuracy and confusion matrix | `eval_mlp_router.py --datasets single` |
| 5.4.1 | Context-feature ablation | `eval_mlp_router.py --datasets context` |
| 5.4.1 | Multi-intent detection | `eval_mlp_router.py --datasets multi` |
| 5.4.1 | Six-arm router ablation with latency | `eval_router_arms.py` |
| 5.4.1 | Clean holdout | `evaluate.py --context-aware` |
| 5.4.2 | Name resolution and suggestion | `eval_name_resolution.py` |
| 5.4.2 | Ambiguity detection | `eval_ambiguity.py` |
| 5.4.2 | Validator ON / OFF ablation | `eval_validator_ablation.py` |
| 5.4.2 | Out-of-menu robustness | `eval_out_of_menu.py` |
| 5.4.2 | Delegate escape hatch | `eval_delegate.py` |
| 5.4.3 | Multi-intent execution and verbalisation | `eval_multi_intent.py --runs 5` |
| 5.4.4 | Retrieval quality, fusion ablation, gatekeeper | `eval_retrieval_full.py` |
| 5.4.5 | End-to-end qualitative conversations | `eval_qualitative.py` |
| 5.4.6 | Turn latency by intent class | `eval_latency.py` |
| 5.5.1 | API responsiveness | `bench_api.py`, `bench_ws.py` |
| 5.5.2–5.5.3 | Fleet lifecycle and multi-role convergence | `bench_fleet.py` |

Every script is invoked as `PYTHONPATH=. uv run python evals/scripts/<script>.py`, writes a
timestamped JSON result file to `evals/results/`, and is deterministic given a fixed model, index
and seed except where the experiment involves a language model. The result file backing each
table is cited in the text so that a reader can trace any number to the run that produced it.
