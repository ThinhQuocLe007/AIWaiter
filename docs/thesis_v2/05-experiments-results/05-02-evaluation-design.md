## 5.2 Evaluation Design

### 5.2.1 Datasets

All evaluation data was written by hand against the menu of a single reference restaurant, *Ốc Quậy*, a
Vietnamese seafood establishment. Every dish name in every dataset resolves against
`assets/data/menu.json`, so the same 219-entry menu is ground truth for retrieval, name resolution and
out-of-menu rejection alike. Evaluating against one menu tests the architecture; evaluating against
several would test the menu-authoring process.

**Table 5.2.** Evaluation datasets, held under `evals/data/`.

| Dataset | Size | Purpose |
|---|---|---|
| Router: single-intent, context-dependent, multi-intent | 149 + 70 + 30 cases | Classification from text alone, context ablation at two order stages, decomposition trigger |
| Retrieval | 24 queries, graded judgements | Menu search relevance across three difficulty levels |
| Safety pool (E2E + out-of-menu) | 41 scenarios | Paired set both validator ablation arms run on |
| Out-of-menu robustness | 30 scenarios, 7 categories | Off-menu rejection, with a negative control |
| Multi-intent completeness | 25 turns | Intents executed against intents verbalised |
| Validator name resolution and ambiguity | 70 pairs + 25 cases | Per-stage resolution accuracy, generic-name ambiguity |
| E2E qualitative | 7 conversations, 30 turns; 6 reported | Full-pipeline behaviour, reported as transcripts |

The three router sets are kept separate rather than pooled because each asks a different question: whether
an utterance can be classified from its text alone, whether conversation state changes the answer, and
whether the router recognises an utterance it should not try to classify at all.

---

### 5.2.2 Metrics and Statistical Protocol

Classification is reported as accuracy with per-class precision, recall and F1 beside a confusion matrix;
retrieval as precision, recall, mean reciprocal rank and hit rate at rank five; end-to-end behaviour as a
pass rate, the fraction of scenarios in which every turn's assertions hold. Three choices among them are
not obvious. Recall and hit rate are weighted above precision because the agent speaks a paraphrase of the
top results rather than showing a list, so it can filter noise but cannot recover a dish the retriever
missed. Pass rate is all-or-nothing per scenario, since one wrong tool call puts a wrong item on the bill.
Latency is always reported as percentiles and never as a mean, because the model stages are right-skewed
and a mean describes a turn nobody experiences.

Components that are deterministic given fixed weights and a fixed index, the MLP classifier, BM25, FAISS
and the validator, are run once and reported as exact fractions. Anything involving a language model is
specified as N = 5 runs at the deployment temperature with the seed varied across runs, reported as `mean
[min–max]`. Three experiments meet that standard, the turn-latency measurement, the verbalisation
experiment and the qualitative conversations. Four do not and are single runs, the validator ablation, the
out-of-menu test, the delegate measurement and the language-model arms of the router ablation, and each
reports one draw rather than an estimate of a mean. This is not a hypothetical concern: the same
conversation has been observed to call a different tool on identical input across runs.

Proportions are reported with a **Wilson 95 % confidence interval**, which stays inside [0, 1] and remains
well-behaved for p̂ near the boundary, where the normal approximation is unreliable. Router arms are
evaluated on **identical items**, so comparisons are paired and use **McNemar's exact test** on the
discordant pairs, reported as the counts (b, c) with the exact p-value. No proportion is reported to more
significant figures than its sample size supports, so an accuracy over 39 items is quoted as 38/39 rather
than as a percentage.

Every experiment is produced by a script under `evals/scripts/`, named in the caption of the table or
figure it feeds and invoked as `PYTHONPATH=. uv run python evals/scripts/<script>.py`. Each writes a
timestamped JSON file to `evals/results/`, from which `render_ch5_figures.py` draws every figure in this
chapter along with the numbers behind it, so a re-run reaches the text as a copy rather than as a
transcription.
