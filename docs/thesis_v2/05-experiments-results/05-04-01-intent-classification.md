### 5.4.1 Intent Classification and Routing

Objectives 1 and 2 require Vietnamese restaurant utterances to be classified into ordering, menu search,
payment or general conversation at 90 % or better, and require that accuracy to come from a trained
classifier rather than a language model, at a median latency an order of magnitude lower. It is a joint
claim: accuracy alone would not justify the component, since a language model was already available, and
latency alone would not either, since a keyword matcher is faster still.

The classifier is the text-only multi-layer perceptron of §4.5.2, a 768-dimensional sentence embedding
with no context features, trained on 1 639 hand-written spoken Vietnamese utterances.

#### Single-Intent Accuracy

On 149 cases balanced at roughly 37 per class and classifiable from the text alone, the classifier is
correct on 142, 95.3 %, Wilson 90.6–97.8 %, at a median inference latency of 8.2 ms.

**Table 5.3.** Confusion matrix on the single-intent set (n = 149). Rows are the true intent.
(`eval_mlp_router.py --datasets single`)

| True \ Predicted | ORDER | SEARCH | PAYMENT | CHAT | Total |
|---|:---:|:---:|:---:|:---:|:---:|
| **ORDER** | **38** | 0 | 0 | 0 | 38 |
| **SEARCH** | 0 | **37** | 0 | 0 | 37 |
| **PAYMENT** | 0 | 0 | **37** | 0 | 37 |
| **CHAT** | 2 | 5 | 0 | **30** | 37 |

The matrix matters more than the accuracy figure, because it shows which confusions occur. The dangerous
cell is empty: the entire PAYMENT row and column are clean, giving that class an F1 of 1.000, so no
utterance was routed into or out of billing. A misrouting there would either bill a customer who did not
ask or fail to bill one who did, and neither error is recoverable downstream.

All seven errors fall on CHAT, and five are pulled toward SEARCH. The text-only model has no stage
awareness to distinguish conversational uses of restaurant vocabulary from transactional ones. Example
misroutes: "Tôi thấy trên mạng review quán mình ngon lắm" and "Tôi có con nhỏ, quán có ghế em bé không"
both route to SEARCH. These errors will travel through the rewriter path at deployment, since their
confidence sits near the 0.7 threshold. ORDER and SEARCH both achieved perfect recall (1.000).

A 39-case holdout partitioned before any training gives 38 of 39, Wilson 86.8–99.5 %. Its single error
is SEARCH predicted as ORDER at confidence 0.643, below the 0.7 deployment threshold, so the utterance
routes to the rewriter rather than being acted upon.

#### Context-Dependent Utterances and Multi-Intent Detection

Two secondary properties are measured. The first is accuracy on utterances whose intent depends on
the conversation state rather than on their words, 123 variants across 38 groups placed at two order
stages. The router is text-only by design, so it cannot see the stage, and this set quantifies what
that costs. The second tests whether the router flags an utterance carrying two intents for
decomposition. Detection fires on a boundary marker (`rồi`, `và`, `thì`, `xong`, `với lại`, `à mà`)
or on confidence below 0.7.

**Table 5.4.** Context-dependent accuracy and multi-intent detection.
(`eval_mlp_router.py --datasets context,multi`)

| Measure | Result |
|---|---|
| Context-dependent utterances (n = 123) | 59 / 123, 48.0 % |
| Multi-intent utterances detected (n = 27) | 24 / 27, 88.9 % |
| False alarms on 3 pseudo-multi-intent controls | 2 |

Fewer than half of the context-dependent utterances are routed correctly, and this is the
classifier's clearest weakness. The 64 errors are dominated by ambiguous short affirmations ("ok",
"ừ", "chuẩn", "dạ") at IDLE routing to ORDER, and postponement utterances ("thôi", "để lát đi",
"khoan đã") at AWAITING_CONFIRMATION routing to CHAT. The words alone do not carry the answer, so no
text-only model can resolve them, and the design absorbs the loss downstream: the deterministic
validator refuses an action the stage does not permit, and low-confidence cases route to the rewriter
rather than being acted upon.

The three undetected multi-intent cases contain no lexical boundary marker, their clauses fused without a
connector as in "Chốt đơn với bill luôn đi em". This is an inherent limit of keyword-based segmentation,
and the failure is graceful: the utterance routes to its dominant intent and the weaker one is absorbed.
The two false alarms cost one extra rewriter call and still return the right answer.

#### Router Ablation

Five routing systems were evaluated on one identical pooled set of 360 cases. Four are reported below.
The fifth, arm F, is a zero-shot pass through the deployment language model, and its run did not
complete: every one of its 360 calls raised and the harness recorded the fallback label. Its apparent
accuracy of 31.4 % is exactly the share of CHAT in the pool (113 of 360), the signature of that
fallback rather than a measurement of anything. It is excluded rather than reported as a weak
baseline, and §5.6.3 records the comparison it leaves open.

There is deliberately no arm pairing the classifier with and against conversation context. The
deployed router takes a sentence embedding and nothing else, so such a pair would run identical code
on identical inputs. Dropping the v1 context block is reported here as a design decision, not as a
measured result.

**Table 5.5.** Accuracy and latency of the router arms (n = 360 pooled, identical items).
(`eval_router_arms.py`)

| Arm | System | Accuracy | 95 % Wilson CI | p50 (ms) | p95 (ms) |
|---|--------|----------|---------------:|:------:|:------:|
| A | Centroid (semantic only) | 251/360, 69.7 % | 64.8–74.2 % | 10.2 | 12.1 |
| B | SLM only (Qwen2.5 3B) | 167/360, 46.4 % | 41.3–51.6 % | 194.4 | 211.0 |
| C | Hybrid semantic → SLM (previous production router) | 246/360, 68.3 % | 63.4–72.9 % | 11.2 | 716.6 |
| **D** | **MLP, text-only (proposed)** | **278/360, 77.2 %** | **72.6–81.2 %** | **9.2** | **11.0** |

![Figure 5.1. Router Ablation](../images/ch5_router_ablation.svg)

*Figure 5.1. Router Ablation: accuracy and latency of the routing arms on the pooled 360-case set.
(`render_ch5_figures.py`)*

Because the arms ran on identical items, the comparisons are paired and use McNemar's exact test as
§5.2.2 requires. Against the centroid the MLP wins 59 discordant cases and loses 32 (p = 0.006); against
the previous hybrid router it wins 62 and loses 30 (p = 0.001); against the SLM alone it wins 141 and
loses 30 (p < 10⁻¹⁷). The MLP's advantage over both deterministic baselines is therefore significant on
the test the protocol specifies, not only on non-overlapping confidence intervals.

The latency columns carry the second half of the objective. The MLP is the fastest arm and also the most
stable one: its 95th percentile sits 1.8 ms above its median, where the previous hybrid router's sits
705 ms above its own. That gap is the deployment argument for replacing it, and §5.4.6 returns to it.

**Objectives 1 and 2 are met:** 95.3 % (142/149) against a 90 % target, repeated at 38 of 39 on a set
partitioned before training, and significantly above both deterministic baselines under McNemar
(p = 0.006 against the centroid, p = 0.001 against the previous hybrid router) at 9.2 ms median on the
pooled set.

<!-- PENDING-14B: arm F needs `ollama pull qwen2.5:14b-instruct-q6_K` and a re-run. It is the ceiling
     comparison against a language-model router, and it is currently missing rather than weak. -->
