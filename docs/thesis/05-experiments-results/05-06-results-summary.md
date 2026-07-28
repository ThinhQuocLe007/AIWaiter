## 5.6 Results Summary

This section draws the individual experiments together: what was achieved against what was
targeted, where the system's failures concentrate, how each result traces back to a need
identified in Chapter 2, and what the results do not establish.

---

### 5.6.1 Objective Scorecard

Each measurable target from §1.3 is set against its measured result and the experiment that
produced it. Targets that were not met, and targets that could not be measured, appear with the
same prominence as those that were.

**Table 5.19.** Objectives against measured results.

| # | Objective | Target | Experiment | Result | Verdict |
|---|-----------|--------|-----------|--------|---------|
| 1 | Intent router accuracy | ≥ 90 % | §5.4.1 | 94.0 % single-intent (140/149); 38/39 on the clean holdout | **met** |
| 2 | Router latency advantage over an LLM | qualitative | §5.4.1, §5.4.6 | 9 ms against 229 ms p50, at statistically indistinguishable accuracy | **met** |
| 3 | Off-menu items reaching the cart | 0 | §5.4.2 | 0 with the validator enabled, against 31 with it bypassed | **met** |
| 4 | Retrieval quality | recall-oriented | §5.4.4 | R@5 0.743, hit rate 0.917, MRR 0.751 with fusion | **met** |
| 5 | Voice turn latency | < 5 s | §5.4.6 | p50 2.15 s, p95 3.40 s | **met** |
| 6 | End-to-end ordering completion | qualitative | §5.4.5 | four of six conversations complete correctly; two expose model-judgement failures | **partially met** |
| 7 | Multi-intent verbalisation completeness | not targeted | §5.4.3 | 57.6 % of multi-intent turns fully verbalised | **not met** |
| 8 | EKF-fused odometry error | ≤ target | §5.3 | not measured | **not evaluated** |
| 9 | Navigation success rate | ≥ target | §5.3 | not measured | **not evaluated** |
| 10 | ArUco docking error | < target | §5.3 | not measured | **not evaluated** |
| 11 | Speech recognition accuracy in the deployed pipeline | not targeted | none | not measured | **not evaluated** |

Five of the seven software objectives are met outright. The two that are not are stated plainly:
multi-intent turns tell the customer the complete story on 57.6 % of occasions, and two of the
seven end-to-end conversations expose failures in the language model's judgement rather than in
the deterministic layers. Four further objectives could not be evaluated, three of them because
the navigation experiments require robot hardware time that was not available, and one because
the speech pipeline was never exercised end to end.

---

### 5.6.2 Failure Budget Allocation

Every failure observed across the experiments in this chapter, categorised by the component
responsible. The purpose is to identify the system's weakest link rather than to total the
errors, since the experiments have different sample sizes and are not commensurable.

**Table 5.20.** Failures by responsible component.

| Component | Observed failures | Where measured | Character |
|-----------|-------------------|----------------|-----------|
| Intent classifier (§4.5.2) | 9 of 149 single-intent; 1 of 39 holdout; 7 misroutes in multi-intent turns | §5.4.1, §5.4.3 | mostly CHAT pulled toward ORDER; recoverable downstream |
| Rewriter and language model judgement | wrong dish selected among similar names; hallucinated removals on an unresolvable reference | §5.4.5 | not recoverable; produces wrong content |
| Response generation (§4.5.6) | 41 of 53 residual verbalisation losses | §5.4.3 | actions executed but not spoken |
| Retrieval (§4.6) | 2 of 7 hard queries return nothing relevant | §5.4.4 | correctly reported as empty, not fabricated |
| Deterministic validator (§4.5.4) | 2 of 30 off-menu scenarios; 0 off-menu items reaching cart tools | §5.4.2 | false negatives on the rejection path |
| Orchestrator (§4.7) | none observed | §5.5 | |

Two observations follow. The deterministic components are not where the failures are. The
validator, the name resolver, the cart arithmetic and the backend behaved correctly in every
experiment except two out-of-menu near-miss cases, and no experiment produced an incorrect cart
total, an incorrect bill, or an inconsistency between roles.

The failures concentrate in the language model's judgement, and they divide into two kinds. The
recoverable kind is misrouting, where an utterance reaches the wrong worker and the validator or
the delegate mechanism catches it, and the customer experiences an awkward turn. The
unrecoverable kind is wrong content generated confidently: selecting the wrong dish among
similarly named ones, or inventing removals for items that were never ordered. The architecture
was designed on the assumption that the second kind exists and must be contained rather than
prevented, and the results are consistent with that assumption: the containment held, in the
sense that no bad data reached the ledger, but the text the customer heard was still wrong.

The weakest link is therefore the response and rewriting layer, which is the one place where the
language model's output reaches the customer without passing through a deterministic check.

---

### 5.6.3 Need to Requirement to Experiment Traceability

**Table 5.21.** Each need identified in Chapter 2 against the experiment that tests it.

| Need (Chapter 2) | Requirement | Experiment | Key result |
|------------------|-------------|------------|------------|
| §2.4 Informal Vietnamese speech to action | classification, validation, agent | §5.4.1, §5.4.2, §5.4.5 | 94.0 % routing; zero off-menu leakage; four of six conversations complete |
| §2.4.4 Routing without an LLM in the loop | R(classification) | §5.4.1 | indistinguishable from the deployed 14B LLM at 25× lower latency |
| §2.4.5 Autonomous post-generation validation | R(validation) | §5.4.2 | 31 hallucinated items blocked; guarantee scoped to menu membership |
| §2.5 Sensory description to relevant dishes | R(retrieval) | §5.4.4 | fusion improves on both retrievers on all four metrics |
| §2.6 Service events to synchronized operations | R(concurrency, fleet) | §5.5.1, §5.5.2 | sub-4 ms endpoints; full task lifecycle |
| §2.6 Multi-role interfaces on one truth | R(web) | §5.5.3 | all roles reflect agent-driven change within one request cycle |
| §2.2 Dynamically assigned navigation goals | R(odometry, navigation, docking) | §5.3 | not evaluated |
| §2.3 Vietnamese voice understanding | R(voice) | none | not evaluated |

Six of the eight needs identified in Chapter 2 have experimental evidence in this chapter. Two do
not, and they are the two that depend on physical hardware.

---

### 5.6.4 Threats to Validity

**Typed text rather than speech.** Every experiment in §5.4 feeds the agent clean text. The voice
pipeline described in §4.4 is architecturally specified and its components selected against the
Chapter 2 survey, but speech recognition word error rate, voice activity boundary accuracy, and
the degradation of routing accuracy when the classifier receives a transcript rather than typed
text are all unmeasured. The results in §5.4 are upper bounds on what a customer speaking to the
deployed system would experience, and the size of the gap between the two is unknown.

**Self-authored evaluation data.** Every dataset was written by the author against a single
restaurant's menu. They are not an independent benchmark. Familiarity with the menu may flatter
both retrieval and name resolution in particular, since the queries were written by someone who
knew what the corpus contained. The perfect scores on name resolution, suggestion and ambiguity
detection should be read as evidence that those mechanisms behave as designed, not that they
survive vocabulary the designer did not anticipate.

**Single runs of a stochastic system.** Only the latency measurement and the multi-intent
verbalisation experiment were repeated five times as the protocol in §5.2.3 requires. The
validator ablation, the out-of-menu robustness test, the delegate measurement, the qualitative
conversations, and the three language-model arms of the router ablation are single runs, and each
therefore reports one draw from a distribution. This is not a hypothetical concern: the same
conversation has been observed to call a different tool on identical input across runs, changing
whether a scenario's assertions hold.

**Underpowered comparisons.** The context-feature ablation, which is the comparison that
distinguishes the proposed classifier from an ordinary one, does not reach significance
(p = 0.057). Roughly 140 context-dependent cases would be needed rather than 70, and 10 of the
36 utterance groups in the current set carry the same label at both order stages and therefore
cannot contribute to the comparison at all. The effect is reported with its interval rather than
claimed as established.

**Model configuration.** The router ablation's language-model arm uses the deployed model
zero-shot rather than prompted or tuned for routing, so the parity it establishes is with the
language model this system runs rather than with language-model routing in general.

**The scope of the validation guarantee.** §5.4.2 establishes that no off-menu item reaches a cart
tool, and that is the whole of it. The validator resolves dish names against the menu; it does not
check whether a named item is present in the cart, so a `remove_cart` naming a genuine menu item
the customer never ordered passes through, which is the failure the final conversation of §5.4.5
exhibits. It also protects state rather than speech: the single bad `confirm_order` in the
validated arm was caught before the ledger while the response node still verbalised a
confirmation. Two of the thirty adversarial scenarios in Table 5.7 were false negatives on the
rejection path.

**The weight of the qualitative evidence.** Six conversations support a pattern, not a rate, and
none is quoted as one. The absence of failure in the four complete conversations is weaker evidence
than the presence of failure in the other two, and only the turn 8 error is known to be stable,
having reproduced in every run of that conversation. The latency percentiles rest on twelve
distinct utterances repeated five times rather than sixty different ones, so they are stable with
respect to model sampling but characterise a narrow set of inputs.

**Measurements that were designed but not taken.** WebSocket event propagation latency was not
captured because the orchestrator was idle during the benchmark window. Session isolation under
deliberate concurrent load was not tested, and is argued from the session-keyed memory design.
The fleet failure path, watchdog detection, task requeue and voice rebinding, was not exercised.
A per-node latency breakdown, which would identify which stage of the agent graph dominates the
turn budget, was not instrumented.

**Single deployment.** One restaurant, one menu, one robot, one network, one server. Nothing here
establishes behaviour at multi-restaurant or multi-robot scale, and the retrieval results in
particular depend on a corpus in which customers and documents share vocabulary, which is a
property of menus rather than a property of the retriever.
