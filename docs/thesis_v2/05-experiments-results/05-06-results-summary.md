## 5.6 Results Summary

### 5.6.1 Objective Scorecard

Each measurable target from §1.3 is set against its measured result. Targets that were not met, and
targets that could not be measured, appear with the same prominence as those that were.

<!-- PENDING-14B: this table is the one place in the chapter where results are quoted a second time.
     After a re-run, update the source table or figure first, then bring the matching row here into
     line with it. Rows 1 and 4 are deterministic; rows 2, 3, 5, 6 and 7 are not. -->

**Table 5.11.** Objectives against measured results.

| # | Objective | Target | § | Result | Verdict |
|---|---|---|---|---|---|
| 1 | Intent router accuracy | ≥ 90 % | 5.4.1 | 94.0 % single-intent (140/149); 38/39 on the clean holdout | **met** |
| 2 | Router latency advantage over an LLM | qualitative | 5.4.1 | 8 ms against 195 ms p50, at significantly higher accuracy | **met** |
| 3 | Off-menu items reaching the cart | 0 | 5.4.2 | 0 with the validator enabled, against 32 with it bypassed | **met** |
| 4 | Retrieval quality | recall-oriented | 5.4.4 | relevant dish found for 23 of 24 queries; fusion does not beat the lexical lane | **partially met** |
| 5 | Voice turn latency | < 5 s | 5.4.6 | p50 1.74 s, p95 3.62 s | **met** |
| 6 | End-to-end ordering completion | qualitative | 5.4.5 | five of six conversations complete correctly over five runs | **partially met** |
| 7 | Multi-intent verbalisation completeness | not targeted | 5.4.3 | 57.6 % of multi-intent turns fully verbalised | **not met** |
| 8–10 | EKF odometry error, navigation success, ArUco docking error | ≤ target | 5.3 | robot hardware time unavailable | **not evaluated** |
| 11 | Speech recognition accuracy in the deployed pipeline | not targeted | — | pipeline never exercised end to end | **not evaluated** |

Four of the seven software objectives are met outright. Retrieval meets its recall-oriented target while
leaving the hybrid design unvindicated on this corpus. One of the six end-to-end conversations falls
short, in the language model's judgement rather than in the deterministic layers. Multi-intent turns tell
the customer the complete story on 57.6 % of occasions. Four further objectives could not be evaluated,
three because the navigation experiments require robot hardware time that was not available and one
because the speech pipeline was never exercised end to end.

Against the needs identified in Chapter 2, five of eight are supported by evidence here, one only in part,
§2.5's requirement that sensory descriptions reach relevant dishes, and two are not evaluated because they
depend on physical hardware, §2.2's dynamically assigned navigation goals and §2.3's Vietnamese voice
understanding.

---

### 5.6.2 Where the Failures Fall

**Table 5.12.** Failures by responsible component. The experiments have different sample sizes and are not
commensurable, so the purpose is to locate the weakest link rather than to total the errors.

| Component | Observed failures | Character |
|---|---|---|
| Intent classifier (§4.5.2) | 9 of 149 single-intent; 1 of 39 holdout; 7 misroutes in multi-intent turns | mostly CHAT pulled toward ORDER; recoverable downstream |
| Rewriter and model judgement | wrong dish chosen among similar names; removals proposed for items never in the cart | contained by the gate, but the reply is still wrong |
| Response generation (§4.5.6) | 41 of 53 residual verbalisation losses | actions executed but not spoken |
| Retrieval (§4.6) | 1 of 7 hard queries returns nothing relevant | corpus ceiling rather than retriever weakness |
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
  menu, so none is an independent benchmark. Familiarity with the menu may flatter retrieval and name
  resolution in particular. The perfect scores in Table 5.6 show those mechanisms behaving as designed,
  not surviving vocabulary the designer did not anticipate.

- **Single runs of a stochastic system.** The latency, verbalisation and qualitative experiments were
  repeated five times as §5.2.2 requires; the validator ablation, the out-of-menu test, the delegate
  measurement and the language-model router arms were not. This is not hypothetical: the out-of-menu pass
  rate moved from 28/30 to 30/30 between two runs of the same scenarios against the same unchanged
  validator, purely because the model proposed different arguments.

- **Paths the evaluation sets could not exercise.** The retrieval gate's rejection path saw no query the
  menu cannot answer, so §5.4.4 measures only its false-positive half. The context-feature ablation in
  Table 5.4 does not reach significance and would need roughly twice its case count, and ten of its
  thirty-six utterance groups carry the same label at both order stages and cannot contribute at all. The
  latency percentiles rest on twelve distinct utterances repeated five times rather than sixty different
  ones.

- **Decisions informed by the data that reports them.** The fusion lane weighting of 3 : 1 was selected on
  the same 24 queries §5.4.4 reports it over. The language-model arm of the router ablation uses the
  deployed model zero-shot rather than prompted or tuned for routing, so that comparison is with the model
  this system runs rather than with language-model routing in general.

- **Single deployment, and infrastructure left unmeasured.** One restaurant, one menu, one robot, one
  network, one server, so nothing here establishes behaviour at multi-restaurant or multi-robot scale, and
  the retrieval results depend on a corpus in which customers and documents share vocabulary. On the
  backend side, event propagation latency on the push path, session isolation under concurrent load, the
  fleet failure and requeue path, and browser-visible update latency were designed and not run, so §5.5
  validates the happy path only.
