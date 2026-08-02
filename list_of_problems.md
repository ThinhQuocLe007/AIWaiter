# Content Issues — Find & Replace

## Chapter 1: INTRODUCTION

### 1. Missing section number for Motivation
```
find: ## Motivation
replace: ## 1.1 Motivation
```

### 2. Missing section number for Objectives
```
find: ## Objectives
replace: ## 1.3 Objectives
```

### 3. Missing period at end of paragraph (WebSocket)
```
find: orchestrator that pushes order state, kitchen display and robot position to role-specific web interfaces over WebSocket
replace: orchestrator that pushes order state, kitchen display, and robot position to role-specific web interfaces over WebSocket.
```

### 4. Missing punctuation — "physical presence a waiter"
```
find: Joining them would give the conversation a physical presence a waiter that listens, answers, and acts, at the table, not behind a screen.
replace: Joining them would give the conversation a physical presence—a waiter that listens, answers, and acts, at the table, not behind a screen.
```

### 5. Missing em-dash — "separate systems the disconnect"
```
find: Interaction and navigation remain separate systems the disconnect described above, appearing in the Vietnamese market in operational form.
replace: Interaction and navigation remain separate systems—the disconnect described above, appearing in the Vietnamese market in operational form.
```

### 6. "a NVIDIA" → "an NVIDIA"
```
find: a NVIDIA GPU
replace: an NVIDIA GPU
```

### 7. Broken bold — "Agent **turns** latency"
```
find: Agent **turns** latency
replace: Agent turn latency
```

### 8. Objectives should be numbered (1 to 8)
The eight objectives (paragraphs 264–271) lack numbering, yet Chapter 5 references them as "Objective 1", "Objective 2", etc. Add numbering:

```
find: Intent classification accuracy.
replace: 1. Intent classification accuracy.

find: Routing without a language model in the loop.
replace: 2. Routing without a language model in the loop.

find: Deterministic action validation.
replace: 3. Deterministic action validation.

find: Knowledge retrieval quality.
replace: 4. Knowledge retrieval quality.

find: Agent turn latency.
replace: 5. Agent turn latency.

find: End-to-end ordering.
replace: 6. End-to-end ordering.

find: Map-based navigation.
replace: 7. Map-based navigation.

find: ArUco precision docking.
replace: 8. ArUco precision docking.
```

### 9. Roadmap omits Chapter 6 (paragraph [253])
The roadmap at the end of the Motivation section lists only Chapters 2–5, omitting Chapter 6 entirely. Section 1.5 correctly lists all six chapters.
```
find: Chapter 2 surveys prior work in each of these areas and identifies the gap it leaves. Chapters 3 and 4 present the proposed solutions. Chapter 5 reports what was measured.
replace: Chapter 2 surveys prior work in each of these areas and identifies the gap it leaves. Chapters 3 and 4 present the proposed solutions. Chapter 5 reports what was measured. Chapter 6 concludes with the contributions, limitations, and future work.
```

### 10. Grammar — parallel structure broken in 1.5 (paragraph [280])
```
find: surveys prior work in the areas the system draws on and identifying the gap each area leaves open.
replace: surveys prior work in the areas the system draws on and identifies the gap each area leaves open.
```

### 11. Comma splice (paragraph [248])
```
find: became controllers given a set of tools, a model can choose which one to call and with what arguments
replace: became controllers: given a set of tools, a model can choose which one to call and with what arguments
```

### 12. Wrong cross-reference — "in this chapter" should be "in Chapter 5" (paragraph [272])
The accuracy figures are reported in Chapter 5, not Chapter 1.
```
find: so the accuracy figures reported in this chapter describe typed input
replace: so the accuracy figures reported in Chapter 5 describe typed input
```

### 13. Broken parallel structure — "only" breaks "no X, no Y" pattern (paragraph [249])
```
find: no per-request cloud bill, no dependence on an external internet connection during service period, only the restaurant's own local network, and customer conversations that never leave the building.
replace: no per-request cloud bill, no dependence on an external internet connection during service, and customer conversations that never leave the building.
```

### 14. Run-on sentence — Out of Scope paragraph (paragraph [275])
Too many clauses joined by commas in one sentence. Split into two.
```
find: The robot platform is purchased, so the mechanical design, the chassis, the motors and the low-level motor control firmware are not part of this work, physical transport of food and drink is not addressed; the contribution begins at ROS 2 integration.
replace: The robot platform is purchased, so the mechanical design, the chassis, the motors, and the low-level motor control firmware are not part of this work. Physical transport of food and drink is not addressed. The contribution begins at ROS 2 integration.
```

### 15. Comma splice — missing colon (paragraph [260])
```
find: Each component was built for a different context, cloud chatbots for customer support, warehouse fleet managers for logistics, academic navigation stacks for controlled laboratory environments.
replace: Each component was built for a different context: cloud chatbots for customer support, warehouse fleet managers for logistics, and academic navigation stacks for controlled laboratory environments.
```

### 16. In-scope vs Out-of-scope tension about pedestrian avoidance
Paragraph [274] says "The lane is physically separated from the customers, so the robot does not navigate through dining areas and does not perform pedestrian avoidance." Paragraph [275] says "dynamic obstacle handling for pedestrians in the lane are not addressed." If the lane is physically separated, how can pedestrians be in it? Either clarify that "pedestrians" refers to staff who may enter the lane, or remove the contradiction.

```
Suggested fix for [275]:
find: dynamic obstacle handling for pedestrians in the lane are not addressed.
replace: dynamic obstacle handling for staff who may enter the lane is not addressed.
```

---

## Chapter 2: RELATED WORK

### 17. Redundant paragraphs — [405] and [408] say the same thing
Both paragraphs state that function calling does not guarantee correctness, with nearly identical phrasing:
- [405]: "Function calling guarantees syntactic structure, not correctness. An LLM can still hallucinate arguments, violate tool order, or break domain constraints."
- [408]: "Function calling provides the mechanism for action. It does not guarantee correctness. An LLM can invoke the right tool with hallucinated arguments, call tools in an invalid sequence, or produce parameter values that violate domain constraints."

Merge or remove one.
```
Replace [408] with a forward-looking transition sentence that does not repeat [405].
```

### 18. Grammar — "The four separates on where governance resides" (paragraph [414])
```
find: The four separates on where governance resides: developer, LLM, topology, or nowhere in particular.
replace: The four differ on where governance resides: developer, LLM, topology, or nowhere in particular.
```

### 19. Grammar — "SQLite is the option for limitations do not bind" (paragraph [478])
```
find: SQLite is the option for limitations do not bind.
replace: SQLite is the option whose limitations do not bind.
```

### 20. Grammar — "a screen a cook consult" (paragraph [482])
```
find: a screen a cook consult periodically
replace: a screen a cook consults periodically
```

### 21. Grammar — "benefit from" → "benefits from" (paragraph [483])
```
find: a browser panel showing a live map benefit from the same channel
replace: a browser panel showing a live map benefits from the same channel
```

### 22. Grammar — "searches for the static costmap for a path" (paragraph [351])
```
find: The global planner searches for the static costmap for a path
replace: The global planner searches the static costmap for a path
```

### 23. Unclear referent — "the cloud" (paragraph [345])
"the cloud" refers to the particle cloud from AMCL, but the word "particle" is two sentences back and easily missed.
```
find: in symmetric geometry the cloud can converge confidently on the wrong hypothesis.
replace: in symmetric geometry the particle cloud can converge confidently on the wrong hypothesis.
```

### 24. Colloquial word — "useless" (paragraph [382])
```
find: and useless for Vietnamese
replace: and unsuitable for Vietnamese
```

### 25. Run-on sentence — five routing approaches in one sentence (paragraph [428])
Five approaches described in a single 120-word sentence separated only by semicolons. Split into a bulleted list for readability.
```
find: Five approaches trade speed against flexibility [52]: rule/SVM and lightweight classifiers are fast and deterministic but fail on teencode and context-dependent turns; semantic centroids handle new vocabulary but not multi-intent blends; state-augmented classifiers need dialogue-state corpora that do not exist for Vietnamese; LLM routing handles teencode, context, and multi-intent at second-scale latency and non-deterministic sampling; LLM decomposition for a fast downstream classifier is untested on Vietnamese segmentation ambiguities.
replace: Five approaches, summarized in Table 2.10, trade speed against flexibility:
- Rule-based and lightweight classifiers: fast and deterministic, but fail on teencode and context-dependent turns.
- Semantic centroids: handle new vocabulary, but not multi-intent blends.
- State-augmented classifiers: require dialogue-state corpora that do not exist for Vietnamese.
- LLM routing: handles teencode, context, and multi-intent turns, at second-scale latency with non-deterministic sampling.
- LLM decomposition for a fast downstream classifier: untested on Vietnamese segmentation ambiguities.
```

### 26. Awkward phrasing — "Documented responses to argument-level error" (paragraph [434])
```
find: Documented responses to argument-level error intervene at different points:
replace: The literature addresses argument-level errors at different stages:
```

### 27. Reference [49] appears out of sequence (paragraph [298])
Reference [49] (Rasa) appears between references [14]–[18] and later numbers. IEEE style requires sequential numbering in order of first appearance. Renumber all references to sequential order.

### 28. "ROS2" vs "ROS 2" inconsistency throughout Chapter 2
The document uses both "ROS2" and "ROS 2" interchangeably. Decide on one convention (the official name is "ROS 2" with a space) and apply consistently.
```
Global find: ROS2
Global replace: ROS 2
```
*(Except in code identifiers like `robot_localization`, package names, or file paths.)*

### 29. Section 2.1.3 is too thin (paragraph [303])
Only two sentences + a fragment, then immediately transitions to 2.1.4. Consider merging 2.1.3 into 2.1.2 or 2.1.4, or expanding it with more survey content.

### 30. Reference [73] repeated 3 times in one sentence (paragraph [493])
```
find: Supporting choices follow established practice: data-dense component libraries for operations screens [73], Vite for fast native-ESM development and tree-shaken production builds [73], and multiple role apps over one backend with shared types and role-scoped subscriptions [73].
replace: Supporting choices follow established practice: data-dense component libraries for operations screens, Vite for fast native-ESM development and tree-shaken production builds, and multiple role apps over one backend with shared types and role-scoped subscriptions [73].
```

### 10. "These operate in isolated silos." — standalone orphan sentence (paragraph 301)
```
find: These operate in isolated silos. Without a shared real-time state, a
replace: These operate in isolated silos, and without a shared real-time state, a
```

---

## Chapter 3: PROPOSED METHOD (I): ROBOT CONTROL AND NAVIGATION ON ROS2

### 32. Possessive typo — "It's" → "Its" (paragraph [509])
```
find: It's one structural limit is that it sees only that horizontal plane
replace: Its one structural limit is that it sees only that horizontal plane
```

### 33. Factual error — "four drive motors" should be "two" (paragraph [513])
The robot has two DC motors (MC520P30 × 2) driving two wheels. The OpenCTR controller board has four motor ports, but only two are populated.
```
find: the four drive motors with their wheel encoders
replace: the two drive motors with their wheel encoders
```

### 34. Incomplete sentence — "standard transform chain" (paragraph [636])
The sentence ends with no period and no specification of the chain. Paragraph [637] (following) is empty — probably a formula was removed or never written.
```
find: The two layers feed Nav2 through the standard transform chain
replace: The two layers feed Nav2 through the standard transform chain map → odom → base_footprint.
```

### 35. Cross-reference too broad (paragraph [571])
Section 2.2 covers everything under "Autonomous Mobile Robot." The EKF is specifically in Section 2.2.2.
```
find: by the Extended Kalman Filter presented in Section 2.2
replace: by the Extended Kalman Filter presented in Section 2.2.2
```

### 36. Missing comma (paragraph [538])
```
find: adds new motion onto the previous estimate it can never correct a past mistake.
replace: adds new motion onto the previous estimate, it can never correct a past mistake.
```

### 37. Missing "that" (paragraph [560])
```
find: the scale factors the driver applies to every incoming sample
replace: the scale factors that the driver applies to every incoming sample
```

### 38. Pseudo-headings styled as Normal (paragraphs [653], [660], [677])
Three paragraphs serve as subsubsection headings but are styled as Normal text, not Heading 4:
- [653] "Global planning with A*."
- [660] "Local control with the Dynamic Window Approach."
- [677] "Output conditioning."

Apply **bold** to each, or change style to Heading 4.

### 39. Informal word — "lock onto" (paragraph [629])
```
find: scan matching alone can lock onto the wrong spot.
replace: scan matching alone can converge on the wrong spot.
```

### 40. Informal word — "jumping" (paragraph [635])
```
find: keep the robot from jumping to the wrong place
replace: keep the robot from localizing incorrectly
```

### 41. Informal word — "clean it up" (paragraph [677])
```
find: leaving the filter to clean it up afterwards.
replace: leaving the filter to compensate for it afterwards.
```

### 42. Informal word — "closes in" (paragraph [678])
```
find: as it closes in
replace: as it approaches
```

### 43. Serial comma missing (paragraph [497])
```
find: the LiDAR, the IMU, the wheel encoders and the RGB-D camera
replace: the LiDAR, the IMU, the wheel encoders, and the RGB-D camera
```

### 44. Table 3.3 — two P diagonal entries are blank
Two diagonal entries in the initial estimate covariance matrix P in Table 3.3 are empty cells. Fill them with the appropriate values from the EKF parameter file.

### 45. "on-board" vs "onboard" inconsistency
"onboard computer" is used in most places, but "on-board MPU6050" appears in paragraph [513]. Pick one convention.

---

## Chapter 4: PROPOSED METHOD (II): AI AND BACKEND SYSTEM

### 46. Duplicate sentence — copy-paste artifact + missing space (paragraph [882])
The last two sentences of the paragraph say the same thing. Also: `"matter.A menu"` — missing space.
```
find: where dense retrieval is expected to matter.A menu corpus represents a worst-case scenario for dense retrievers; keeping the semantic lane ensures the system can handle non-menu FAQ queries and generalize well to other domains with wider vocabulary gaps.
replace: where dense retrieval is expected to matter. A menu corpus represents the worst case for dense retrieval, and the performance gap observed here is therefore not expected to carry over to other domains.
```
*(Or simply delete the second sentence entirely.)*

### 47. Tool count inconsistency — text vs table title (paragraph [837], Table 4.9)
Paragraph [837] says "Six tools cover the agent's action space" and "A seventh callable, the delegate escape hatch, is absent from the table." But Table 4.9 is titled "The agent's seven tools." The table either shows 6 tools (correct per text) or 7 (correct per title). Fix the table title to match the text.
```
find (Table 4.9 caption): The agent's seven tools, what each touches, and whether its effect outlives the session.
replace: The agent's six tools, what each touches, and whether its effect outlives the session.
```

### 48. Word order — "clear completely" → "completely cleared" (paragraph [695])
```
find: Conversation state must be clear completely when a session ends
replace: Conversation state must be completely cleared when a session ends
```

### 49. Grammar — "All four places the agent calls" (paragraph [790])
```
find: All four places the agent calls a language model, the rewriter, the two tool-calling workers, and the response generator, share one model instance
replace: Whenever the agent calls a language model—the rewriter, the two tool-calling workers, and the response generator—all four uses share one model instance
```

### 50. Missing "that" — "the one callable the tool node never runs" (paragraph [793])
```
find: it is the one callable the tool node never runs.
replace: it is the one callable that the tool node never runs.
```

### 51. Garbled sentence — "are measured against sit in" (paragraph [914])
```
find: Both the robot positions and the table are measured against sit in the saved SLAM map frame
replace: Both the robot positions and the table coordinates sit in the saved SLAM map frame
```

### 52. Subject-verb agreement — "sits" → "sit" (paragraph [694])
The subject is plural: "detection, recognition and synthesis."
```
find: The voice activity detection, recognition and synthesis contributed by the edge device sits outside this budget
replace: The voice activity detection, recognition, and synthesis contributed by the edge device sit outside this budget
```

### 53. Factual contradiction — "is not measured" vs Section 5.4.7 (paragraph [694])
Paragraph [694] says voice pipeline latency "is not measured in this work." But Section 5.4.7 explicitly measures voice pipeline latency (VAD, STT, TTS) on the Jetson. Clarify or remove the claim.
```
find: sits outside this budget and is not measured in this work.
replace: sits outside this budget and is measured separately in Section 5.4.7.
```

### 54. Logical ordering confusion — gate "before fusion" but fusion section comes first (paragraph [885] vs [883])
Section 4.6.2 describes fusion, then Section 4.6.3 describes the gatekeeper which "runs before fusion." The section ordering (4.6.2 Fusion → 4.6.3 Gatekeeper) contradicts the stated execution order (Gate → Fusion). Either reorder the sections or rephrase [885] to clarify that the gate runs between retrieval and fusion, and is described after fusion for exposition.
```
Suggested: Move gatekeeper subsection before fusion subsection, OR add a sentence at the start of 4.6.3 clarifying "The gatekeeper runs between retrieval and fusion; it is described after the fusion mechanism for clarity."
```

### 55. Grammar — "turn finish" → "turn finishes" (paragraph [793])
```
find: lets the turn finish with no tool executing
replace: lets the turn finish with no tool executing
```
*(Re-read context: actually "lets the turn finish" is correct — "finish" is the bare infinitive after "lets". No issue here. Removed.)*

Wait — re-examining: "lets the turn finish" is correct. But the original text at [793] shows: "lets the turn finish with no tool executing" — this IS grammatically correct ("lets" + object + bare infinitive). So this was a false alarm. Skip this item.

### 56. Informal word — "fell out" → "ended" (paragraph [828])
```
find: before the turn fell out with an apology.
replace: before the turn ended with an apology.
```

### 57. Informal word — "the SEARCH bar" (paragraph [785])
```
find: Raising the SEARCH bar sends borderline dish-name utterances
replace: Raising the SEARCH threshold sends borderline dish-name utterances
```

### 58. Number formatting — "220 thousand" (paragraph [770])
```
find: approximately 220 thousand parameters
replace: approximately 220,000 parameters
```

### 59. Informal word — "roughly" (paragraph [739])
```
find: until it detects roughly 1.5 seconds of silence
replace: until it detects approximately 1.5 seconds of silence
```

### 60. Missing hyphens — "first come first served" (paragraph [914])
```
find: is served first come first served by creation time.
replace: is served first-come, first-served by creation time.
```

### 61. Inconsistent naming — "manager's tablet" vs "management panel" (paragraph [905])
The same interface is called "manager's tablet" at [905] but "management panel" at [932] and throughout section 4.8.3. Use one name consistently.
```
find: the manager's tablet
replace: the management panel
```

### 62. Vague quantity — "five of those updates a second" (paragraph [915])
```
find: fed five of those updates a second
replace: fed at 5 Hz
```

### 63. Section heading trailing periods (paragraphs [899], [900])
```
find: 4.7. Backend Orchestrator
replace: 4.7 Backend Orchestrator

find: 4.7.1. Where This Layer Sits
replace: 4.7.1 Where This Layer Sits
```

### 64. Informal phrase — "move under them" (paragraph [926])
```
find: still sees the same screens move under them.
replace: still sees the same screens respond in sequence.
```

---

## Chapter 5: EXPERIMENTAL RESULTS

### 65. Seven AI requirements lack numbering (paragraphs [688]–[695])
Same issue as Chapter 1 objectives — the requirements are listed as plain paragraphs. Number them 1–7 for traceability, since they map to the design sections (4.4–4.8) and the evaluation in Chapter 5.

### 66. Wrong heading level — subsections of 5.3 use Heading 2 instead of Heading 3
All subsections 5.3.1 through 5.3.7 currently use Heading 2 style. They should use Heading 3 to be consistent with 5.4.1–5.4.8 which correctly use Heading 3.

In the docx, change the style of the following headings from **Heading 2** to **Heading 3**:
- 5.3.1 Simulation Environment
- 5.3.2 Real-life Testbed Setup
- 5.3.3 Odometry Accuracy Test
- 5.3.4 Map Building and Localization Test
- 5.3.5 Navigation and Docking Test
- 5.3.6 Dynamic Obstacle Avoidance Demonstration
- 5.3.7 Summary and Discussion

### 67. Factual contradiction — "Nothing was measured in simulation" (paragraph [945])
Paragraph [945] claims "Nothing was measured in simulation or on a different machine." But Section 5.3.1 explicitly describes simulation-based validation, and 5.3.3–5.3.5 report simulation results.
```
find: Nothing was measured in simulation or on a different machine.
replace: The AI agent experiments in Sections 5.4 and 5.5 were measured on the hardware described below. Navigation experiments in Section 5.3 were validated in simulation before physical deployment.
```

### 68. Factual contradiction — "no quantitative measurement of it was taken" (paragraph [1170])
Paragraph [1170] says "no quantitative measurement of it was taken" about the speech pipeline. But Section 5.4.7 quantitatively measures VAD, STT, and TTS latency. Narrow to recognition accuracy.
```
find: no quantitative measurement of it was taken
replace: its recognition accuracy was not quantitatively benchmarked (latency is measured separately in Section 5.4.7)
```

### 69. Confusing paragraph — "five of eight" misaligned with objectives (paragraph [1171])
Paragraph [1170] discusses 6 software objectives, then [1171] abruptly says "five of eight needs identified in Chapter 2" without transition. These "eight needs" aren't the same as the 8 objectives from Section 1.3 (all 8 of which were evaluated). Clarify or rewrite.
```
Replace or clarify: what are the "eight needs" from Chapter 2? Why were two "not evaluated" when all 8 objectives have results?
```

### 70. Double period — "neither significant.." (paragraph [1054])
```
find: neither significant.. On accuracy
replace: neither significant. On accuracy
```

### 71. Made-up word — "unvindicated" (paragraph [1170])
"Unvindicated" is not standard English.
```
find: leaving the hybrid design unvindicated on this corpus.
replace: leaving the hybrid design unsupported on this corpus.
```

### 72. Section 5.4.6 contradicts itself with Section 5.4.7 (paragraph [1133])
Para [1133] says voice pipeline latency "is part of the budget this chapter does not measure." But 5.4.7 measures it.
```
find: and the distance between them is part of the budget this chapter does not measure.
replace: and the distance between them is measured separately in Section 5.4.7.
```

### 73. Unclear referents — "second group" and "unwritten section" (paragraph [1107])
"The second group" references Table 5.19 but the groups aren't described in prose. "The unwritten section is a content gap of the same kind, closed by writing the section" — what section? Cryptic and incomplete.
```
Rewrite paragraph [1107] to name the groups explicitly; clarify or remove the "unwritten section" sentence.
```

### 74. Duplicate explanation in gatekeeper paragraph (paragraph [1113])
The same reasoning (why pizza/sushi/motorbike pass the gate) is stated twice in one paragraph.
```
Delete the duplicate second half: "The gate correctly rejects 2 of the 5 queries... 'sushi' clear the semantic lane...".
```

### 75. Grammar — "fall" → "falls" (paragraph [1139])
```
find: One figure fall outside the budget.
replace: One figure falls outside the budget.
```

### 76. Inconsistent spelling — "verbalisation" vs "verbalization"
Table 5.16 uses British "verbalisation"; text at [1080] uses American "verbalization." Pick one convention.

### 77. First-person "we" breaks thesis voice (paragraph [1083])
```
find: When we exclude these execution-only failures
replace: When excluding these execution-only failures
```

### 78. Grammar — "41 scenarios run" → "were run" (paragraph [1068])
```
find: 41 scenarios run through both configurations
replace: 41 scenarios were run through both configurations
```

### 79. Informal phrase — "clocks in at" (paragraph [1163])
```
find: the system clocks in at 4.84 s.
replace: the system reaches 4.84 s.
```

### 80. Ambiguous — "v1 context block" never defined (paragraph [1051])
```
find: Dropping the v1 context block is reported here as a design decision
replace: Dropping the conversation-context block from the previous router version is reported here as a design decision
```

### 81. Pseudo-headings styled as Normal (9 occurrences)
The following labels serve as subsection headings but are styled Normal, not Heading 4:
- [1038] "Single-Intent Accuracy"
- [1045] "Multi-Intent Detection"
- [1049] "Router Ablation"
- [1062] "Name Resolution, Suggestion and Ambiguity"
- [1067] "What the Gate Is Worth"
- [1072] "Robustness and the Delegate Escape Hatch"
- [1089] "Retrieval Quality and the Fusion Ablation"
- [1095] "The Effect of Query Rewriting"
- [1109] "Dual-Lane Gatekeeper"

Apply **bold** or change to Heading 4 style.

### 82. Space before percent sign throughout
```
Global find:  %
Global replace: %
```
*(Only for measurement values, e.g., "90 %" → "90%". Leave "per cent" in prose.)*

### 83. "31 %" → "31%" (specific instance)
```
find: 31 %
replace: 31%
```

### 84. CLIFFHANGER sentence — "as the physical testbed" (paragraph [1193])
The sentence appears truncated. Complete it.

### 85. Missing numeric values throughout Chapter 5 (equation fields)
Blank spaces where measurement values should appear (e.g., "within ██ laterally", "reduced to ██"). Convert equation fields to plain text numbers. Affected: 5.3.3, 5.3.5, 5.3.7, Table 5.23.

### 86. Menu: 22 supporting documents never fully specified
Paragraph [875] mentions "22 supporting documents (e.g., best sellers, restaurant information, and customer policies)" but never lists them definitively, making the retrieval index irreproducible.

---

## Chapter 6: CONCLUSION

### 87. Missing colon in chapter title (paragraph [1178])
Chapters 1–5 all use `"CHAPTER N: TITLE"`. Chapter 6 omits the colon.
```
find: CHAPTER 6 CONCLUSION
replace: CHAPTER 6: CONCLUSION
```

### 88. Spurious colon — "Management Panel: alongside" (paragraph [1184])
```
find: Management Panel: alongside an automated fleet dispatcher
replace: Management Panel, alongside an automated fleet dispatcher
```

### 89. Inconsistent tense in Contribution 1 (paragraph [1182])
Contribution 1 uses present tense ("inspects", "strips", "resolves"); contributions 2–5 use past tense.
```
find: The validator inspects every tool argument against the authoritative menu, strips off-menu items, resolves ambiguous dish references, and enforces strict ordering workflow constraints.
replace: The validator inspected every tool argument against the authoritative menu, stripped off-menu items, resolved ambiguous dish references, and enforced strict ordering workflow constraints.
```

### 90. First-person "we" throughout Chapter 6 — inconsistent with Chapters 1–5
Chapters 1–5 avoid first-person (one slip at [1083]). Chapter 6 uses "we" in nearly every paragraph. Either keep "we" in Ch.6 (conclusion is conventionally more personal) or convert to impersonal for consistency.

### 91. "0.30 degrees" → degree symbol (paragraph [1185])
```
find: 0.30 degrees in heading
replace: 0.30° in heading
```

### 92. Contributions lack cross-references to implementation chapters
Section 6.1 lists five contributions without citing where each is described. Add references:
- Contribution 1 (validator) → Section 4.5.4
- Contribution 2 (routing/retrieval) → Sections 4.5.2 and 4.6
- Contribution 3 (graph agent/backend) → Sections 4.5.1 and 4.7
- Contribution 4 (navigation/docking) → Sections 3.4–3.6
- Contribution 5 (edge memory) → Section 4.3.1

### 93. Repeated word "Overall" in consecutive sentences (paragraph [1188])
```
find: validates the overall system design against the core objectives. Overall, the quantitative findings confirm
replace: validates the system design against the core objectives. The quantitative findings confirm
```

---

## Cross-Chapter Issues

### 94. "we" inconsistency — Chapter 6 vs Chapters 1–5
Same as #90. Chapters 1–5 avoid first-person; Chapter 6 uses "we" throughout.

### 95. "verbalisation" (British) vs "verbalization" (American) across chapters
Table 5.16 uses British spelling; prose at [1080] and [1084] uses American. Pick one. (Also #76.)

### 96. Simulation scope vs physical validation mismatch
Scope says "six dining tables / restaurant environment." Physical testbed is 2 stations in a stockroom. Acknowledged in Ch.1 [274] and Ch.6 [1193], but readers may miss the qualification.

### 97. Chapter 1 roadmap [253] vs Section 1.5 [284] discrepancy
Roadmap at end of Motivation lists Ch.2–5 only, omitting Ch.6. Section 1.5 correctly lists all six. (Also #9.)

### 98. Redundancy between 5.5 Results Summary and 6.2 Summary of Empirical Validation
Section 5.5 already provides a results summary with objective scorecard (Table 5.23). Section 6.2 restates the same conclusions. Ensure prose is not duplicated.

---

## Summary

| Priority | Count | Areas |
|----------|-------|-------|
| Critical | 9 | Wrong heading levels (5.3.x), Appendix G scrambled, incomplete sentence [636], "four motors"→"two", "It's"→"Its", duplicate sentence [882], tool count Table 4.9, garbled sentence [914], "nothing measured in simulation" [945], "no measurement taken" [1170] |
| High | 23 | Missing section numbers, wrong cross-references, roadmap omits Ch.6, in/out-of-scope contradiction, ref [49] sequence, ROS2 inconsistency, redundant paras, pseudo-headings (Ch.3+Ch.5), gate/fusion ordering [885], "five of eight" confusion [1171], double period [1054], "unvindicated" [1170], self-contradiction [1133], missing colon Ch.6 title [1178], inconsistent tense [1182], "we" inconsistency [90/94], contributions lack cross-refs [92] |
| Medium | 29 | Grammar/punctuation, informal words, Table 3.3 blank cells, thin 2.1.3, number formatting, naming inconsistency, unclear referents [1107], duplicate gate [1113], spelling inconsistency, missing menu docs [86], redundancy 5.5/6.2 [98], simulation/physical mismatch [96] |
| Low | 8 | Minor wording, consistency nits, percent spacing |
