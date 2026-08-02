# CHAPTER 6 CONCLUSION

Chapter này cần viết lại

## 6.1 Contributions

This thesis presented an autonomous AI waiter system that integrates spoken Vietnamese interaction, conversational AI, real-time restaurant backend operations, and robot delivery on a two-wheel differential-drive platform. The main contributions are:

- A deterministic safety layer around probabilistic generation. A rule-based validator inspects every tool call argument before execution, resolving dish names against the authoritative menu, detecting ambiguous references, stripping off-menu items, and enforcing ordering workflow constraints. Across 41 evaluation scenarios, the validator prevented 32 invalid items from reaching the cart,  items that would have become wrong orders in a deployed restaurant ,  without refusing any valid request.
A text-only intent classifier for informal Vietnamese. A lightweight MLP over a frozen Vietnamese bi-encoder embedding classifies restaurant utterances into four intent classes at 95.3 % accuracy and 7.2 ms median latency, a factor of twenty-four below prompting the same language model the system already runs, at accuracy statistically indistinguishable from it. The classifier sees the utterance and nothing else; short answers whose meaning depends on the order stage are settled after routing by the deterministic validator rather than inside the classifier, which keeps routing reproducible. A dedicated rewriter decomposes multi-intent utterances before classification rather than training the model to emit multi-label outputs.

- A hybrid knowledge retrieval pipeline with a relevance gate. A BM25–FAISS retriever over 234 menu entries, preceded by LLM-based query rewriting that translates sensory Vietnamese descriptions ("ấm bụng", "giải nhiệt") into concrete search terms. A deterministic dual-lane gatekeeper between retrieval and generation withholds queries the menu cannot answer cleanly rather than passing noise to the language model. Retrieval places a relevant dish in the top five for 42 of the 47 queries the menu can answer. The ablation reported in section 5.4.4 is itself a finding: on a menu corpus, where customers name dishes in the words printed on the menu, the lexical lane carries the result and the dense lane earns its place only on the sensory queries the rewrite is built for, where it moves one benchmark query from a recall of 0.000 to 1.000
- A graph-based agent architecture with specialized workers. Ten nodes organized into five stages (classify, decide, validate, execute, respond) replace a monolithic agent with domain-specialized workers, each bound only to the tools of its intent class. A delegate escape hatch lets the model abstain rather than hallucinate, and a circuit breaker guarantees a spoken reply after three consecutive failures. Median turn latency is 1.74 s, within the five-second target.
- ROS 2 autonomous navigation with ArUco precision docking. An EKF fusing wheel odometry and IMU, RTAB-Map SLAM with LiDAR–RGB-D–ArUco sensor fusion, and Nav2 with A* global planning and DWB local control drive a purchased two-wheel differential-drive platform from kitchen to table. ArUco visual alignment reduces terminal docking error from 47.77 cm to 1.57 cm laterally and to 0.30 degrees in heading, at the cost of 1.1 additional seconds per delivery.
- An integrated real-time backend. A FastAPI orchestrator with SQLite persistence, WebSocket push to three role-specific web interfaces (customer tablet, entrance kiosk, management panel with kitchen board and fleet minimap), and a dispatcher that assigns navigation tasks to the nearest idle robot above battery threshold. All components run on local hardware with no cloud dependency in normal operation.
## 6.2 Summary of Measured Results ( Nên bỏ phần này )

Table đâu ?  (

| Objective | Target | Result | Status |
| --- | --- | --- | --- |
| Intent classification accuracy | ≥ 90% | 94.0% (140/149) | ✓ Met |
| Router latency vs LLM | 1 order of magnitude lower | 8 ms vs 195 ms | ✓ Met |
| Off-menu item prevention | Zero leakage | 0 leaked vs 32 bypassed | ✓ Met |
| Knowledge retrieval (hit rate @ 5) | , | 0.958 | Partial |
| Agent turn latency | < 5 s median | 1.74 s | ✓ Met |
| End-to-end ordering | Complete scenarios | 5/6 conversations pass | Met |
| Map-based navigation | ≥ 90% success | 100.0% success (5/5 runs pass) | ✓ Met |
| ArUco docking | ≤ 10 cm, ≤ 8° | 1.57 cm lateral, 0.30° heading with visual align on | ✓ Met |

## 6.3 Limitations

Speech pipeline demonstrated but not quantified. The voice pipeline (Silero VAD, PhoWhisper medium under the faster-whisper runtime, Piper TTS) was selected, integrated and deployed on the Jetson edge computer, and the complete spoken path from a customer's utterance to the robot's reply is demonstrated in the accompanying recording, which covers an ordering conversation carried out entirely by voice. What is missing is measurement rather than function: word error rate under restaurant noise, voice activity detection boundary accuracy, and the drop in routing accuracy on real transcripts against typed input were not measured, because doing so requires a spoken Vietnamese restaurant corpus that was outside the time available. Every agent figure reported in Chapter 5 is therefore an upper bound on what a speaking customer would experience.

Single restaurant, single menu. Retrieval and name resolution were evaluated against one 234-entry seafood restaurant menu.. The results establish that the architecture works on this menu; they do not establish how it generalizes to different cuisines, larger menus, or menus in other languages.

Language model judgement remains the weakest link. The deterministic layers (validator, cart arithmetic, state machine, name resolver) behaved correctly in every experiment. Failures concentrated in two places: the LLM answering about a different dish from the one asked about (response layer), and the LLM dropping one intent in a multi-intent turn (verbalisation). Only 57.6% of multi-intent turns told the customer the complete story. No deterministic check currently sits between the response generator and the customer.

Unmeasured infrastructure. Event propagation latency on the push path, session isolation under concurrent load, the fleet failure and requeue path, and navigation success rate across all six tables were designed but not quantitatively measured.

Scope exclusions. The robot does not navigate through dining areas, avoids only static obstacles in the service lane, and operates in a single mapped environment. Pedestrian avoidance, multi-floor operation, and dynamic re-planning around moving obstacles are not addressed.

## 6.4 Future Work

Speech pipeline end-to-end evaluation. The immediate gap. Measure WER of PhoWhisper on restaurant-domain utterances under realistic noise, evaluate VAD boundary accuracy, and quantify the degradation of intent classification accuracy on transcript vs. typed input. This determines how much of the reported agent performance survives the full spoken path.

Response grounding for multi-turn safety. The validator guarantees correct state but not correct speech, and the two are the same problem approached from opposite ends: the validator checks the model's output into the system, and nothing yet checks its output to the customer. The check does not require constraining generation, which would be unreliable, only inspecting what generation produced. Every reply is generated from a response context the system assembled deterministically, so three assertions are available over the finished text before it reaches speech synthesis. Every dish name the reply mentions must resolve to a dish present in that turn's context, using the same resolver §4.5.4 already applies to tool arguments. Every price and quantity the reply states must appear in the context, since the cart arithmetic that produced them runs in Python. And each tool result in the context must be mentioned at least once, which is the completeness property §5.4.3 measures, evaluated at run time rather than after the fact. A reply failing any assertion is discarded in favour of the templated reply for that outcome, a path §4.5.6 already implements for the sixteen templated cases and which costs microseconds. The check is deterministic in the sense that matters: it is a pure function of the reply text and the verified context, so the same pair always yields the same verdict however the model varies between runs.

Expanded retrieval evaluation. Add queries the menu genuinely cannot answer to quantify the gatekeeper's rejection rate. Extend the retrieval benchmark beyond one restaurant to measure corpus-dependence of the hybrid design.

Pedestrian-aware navigation in the dining area. Extend Nav2 with a human-aware local planner operating in the table zones, using the RealSense depth camera for real-time person detection, to enable the robot to approach occupied tables through the dining room rather than only via the dedicated lane.

Multi-language support. The agent architecture is language-agnostic in design; only the Vietnamese-specific components (bi-encoder, classifier training data, prompts, TTS) lock it to one language. Extending to English or other languages requires replacing those components while keeping the graph, validator, retriever, and backend unchanged.


