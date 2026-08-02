## 5.6 Results Summary

### 5.6.1 Objective Scorecard

Each measurable target from §1.3 is set against its measured result. Targets that were not met, and
targets that could not be measured, appear with the same prominence as those that were.

<!-- PENDING-14B: this table is the one place in the chapter where results are quoted a second time.
     After a re-run, update the source table or figure first, then bring the matching row here into
     line with it. Rows 1 and 4 are deterministic; rows 2, 3, 5, 6 and 7 are not. -->

**Table 5.13.** Objectives against measured results.

| # | Objective | Target | § | Result | Verdict |
|---|---|---|---|---|---|
| 1 | Intent router accuracy | ≥ 90 % | 5.4.1 | 95.3 % single-intent (142/149); 38/39 on the clean holdout; 48.0 % on context-dependent utterances | **met** |
| 2 | Router latency advantage over an LLM | qualitative | 5.4.1 | 9.2 ms p50 and 11.0 ms p95, deterministic; significantly above the centroid (p = 0.006) and the previous hybrid router (p = 0.001) under McNemar | **met** |
| 3 | Off-menu items reaching the cart | 0 | 5.4.2 | 0 with the validator enabled, against 32 with it bypassed | **met** |
| 4 | Retrieval quality | recall-oriented | 5.4.4 | relevant dish found for 42 of 50 queries; fusion does not beat the lexical lane | **partially met** |
| 5 | Voice turn latency | < 5 s | 5.4.6 | p50 1.61 s, p95 4.13 s; every intent class inside the budget at its median | **met** |
| 6 | End-to-end ordering completion | qualitative | 5.4.5 | 82.9 % [71.4 %–100 %] of seven conversations over five runs; no incorrect state written in any run | **partially met** |
| 7 | Multi-intent verbalisation completeness | not targeted | 5.4.3 | 57.6 % of multi-intent turns fully verbalised | **not met** |
| 8–10 | EKF odometry error, navigation success, ArUco docking error | ≤ target | 5.3 | robot hardware time unavailable | **not evaluated** |
| 11 | Speech recognition accuracy in the deployed pipeline | not targeted | n/a | pipeline never exercised end to end | **not evaluated** |

Four of the seven software objectives are met outright. The v2 text-only classifier at 95.3 % exceeds
the 90 % target on utterances classifiable from their words, while reaching only 48.0 % on the 123
utterances whose intent depends on the conversation stage, which the validator is there to absorb.
Retrieval meets its recall-oriented target while leaving the
hybrid design unvindicated on this corpus. The end-to-end conversations complete on 82.9 % of runs, and
what varies is the language model's judgement rather than the deterministic layers, which wrote nothing
incorrect in any run. Multi-intent turns tell the customer
the complete story on 57.6 % of occasions. Four further objectives could not be evaluated, three
because the navigation experiments require robot hardware time that was not available and one because
the speech pipeline was never exercised end to end.

Against the needs identified in Chapter 2, five of eight are supported by evidence here, one only in part,
§2.5's requirement that sensory descriptions reach relevant dishes, and two are not evaluated because they
depend on physical hardware, §2.2's dynamically assigned navigation goals and §2.3's Vietnamese voice
understanding.

---

### 5.6.2 Where the Failures Fall

**Table 5.14.** Failures by responsible component. The experiments have different sample sizes and are not
commensurable, so the purpose is to locate the weakest link rather than to total the errors.

| Component | Observed failures | Character |
|---|---|---|
| Intent classifier (§4.5.2) | 7 of 149 single-intent (all CHAT); 1 of 39 holdout; 3 undetected multi-intent | CHAT pulled toward SEARCH/ORDER; text-only model lacks stage awareness, addressed by downstream validator |
| Rewriter and model judgement | wrong dish chosen among similar names, which is what makes the referring-expression scenario vary run to run; removals proposed for items never in the cart | contained by the gate, but the conversation may not complete |
| Response generation (§4.5.6) | 41 of 53 residual verbalisation losses | actions executed but not spoken |
| Retrieval (§4.6) | 4 of 13 hard queries return nothing relevant | corpus ceiling rather than retriever weakness |
| Deterministic validator (§4.5.4) | 0 off-menu items reaching cart tools | no failure observed |
| Orchestrator | none observed | |

The deterministic components are not where the failures are. The validator, the name resolver, the cart
arithmetic and the backend behaved correctly in every experiment, and none produced an incorrect cart
total, an incorrect bill, or an inconsistency between roles.

The failures concentrate in the language model's judgement, and they divide into two kinds. The first is a
wrong tool call on wrong arguments, which the gate refuses and the delegate mechanism lets the worker
abandon. The second is wrong content generated confidently inside a reply, such as answering about a
different dish from the one asked about, and no deterministic check stands between that and the customer.
The architecture was designed on the assumption that both exist and must be contained rather than
prevented, and the results are consistent with it: no bad data reached the ledger in any experiment, while
the text the customer heard was sometimes still wrong. The weakest link is therefore the response and
rewriting layer, the one place where model output reaches the customer without passing a deterministic
check.

---

### 5.6.3 Threats to Validity

- **Typed text rather than speech.** Every experiment in §5.4 feeds the agent clean text. Speech
  recognition word error rate, voice activity boundary accuracy and the degradation of routing accuracy on
  a transcript rather than typed text are all unmeasured, so every result in §5.4 is an upper bound on
  what a customer speaking to the deployed system would experience, and the size of the gap is unknown.

- **Self-authored evaluation data.** Every dataset was written by the author against a single restaurant's
  menu, so none is an independent benchmark. Relevance judgements were re-checked against `menu.json`
  before the reported runs, but familiarity with the menu may flatter retrieval and name resolution in
  particular. The perfect scores in Table 5.6 show those mechanisms behaving as designed,
  not surviving vocabulary the designer did not anticipate.

- **Single runs of a stochastic system.** The latency, verbalisation and qualitative experiments were
  repeated five times as §5.2.2 requires; the validator ablation, the out-of-menu test, the delegate
  measurement and the small-language-model router arms were not. This is not hypothetical: the out-of-menu pass
  rate moved from 28/30 to 30/30 between two runs of the same scenarios against the same unchanged
  validator, purely because the model proposed different arguments.

- **Paths the evaluation sets barely exercise.** The retrieval gate's rejection half rests on the five
  queries in the set that the menu genuinely cannot answer, of which it turns away two, so that half of
  the requirement is measured on a sample too small to carry a rate. The latency percentiles rest on
  twelve distinct utterances repeated five times rather than sixty different ones.

- **Removing the context features is a design decision, not a measured one.** The v1 router carried ten
  conversation-state features and the v2 router does not. No experiment in this chapter compares the two:
  the deployed classifier takes a sentence embedding and nothing else, so an arm differing only in a
  context argument would run identical code. Whether those features would have helped on the 123
  context-dependent utterances of Table 5.4, where accuracy is 48.0 %, is therefore open. Answering it
  needs a second model trained with the context block on the same corpus, which was not done.

- **Decisions informed by the data that reports them.** The fusion lane weighting of 3 : 1 was selected on
  the same 50 queries §5.4.4 reports it over.

- **No language-model router baseline.** The router ablation compares the classifier against a centroid
  router, a 3B small language model and the previous hybrid production router, but not against the 14B
  model the system actually deploys: that arm did not execute, because the model was absent from the local
  Ollama instance and every call fell back to a default label. The claim that a trained classifier beats a
  language-model router at this task therefore rests on the 3B arm and on published latency, not on a
  measured comparison with the deployed model. It is the single most important missing measurement in this
  chapter, and it needs only the model to be pulled and the script re-run.

- **Single deployment, and infrastructure left unmeasured.** One restaurant, one menu, one robot, one
  network, one server, so nothing here establishes behaviour at multi-restaurant or multi-robot scale, and
  the retrieval results depend on a corpus in which customers and documents share vocabulary. On the
  backend side, event propagation latency on the push path, session isolation under concurrent load, the
  fleet failure and requeue path, and browser-visible update latency were designed and not run, so §5.5
  validates the happy path only.
