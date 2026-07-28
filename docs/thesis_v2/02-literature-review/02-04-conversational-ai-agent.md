## 2.4 Conversational AI Agent

### 2.4.1 From General-Purpose LLM to Task-Oriented Agent

Large language models (LLMs) possess strong emergent reasoning capabilities but remain strictly text-in-text-out systems, fundamentally unable to modify databases or command external devices directly. Historically, bridging this gap required brittle post-hoc parsing, such as regex or keyword matching, to extract structured intents from the model's free-text outputs. Because these downstream parsers had to anticipate every possible natural language phrasing, any conversational variation frequently broke the extraction pipeline.

Function calling resolved this fragility by establishing structured JSON invocation as a native LLM capability. Instead of relying on text parsing, the LLM receives a typed JSON Schema of available tools and generates a strictly formatted invocation object, for example `{"name": "search_items", "arguments": {"query": "..."}}`. The serving framework intercepts this output, executes the corresponding function against live systems, and feeds the return value back into the LLM for the next reasoning step.

[Figure 2.4a. Function calling mechanism: the LLM receives a tool schema alongside the conversation and produces a structured JSON invocation rather than a free-text description; the framework executes the tool and feeds the result back.]

However, while function calling provides a reliable mechanism for action, it does not guarantee correctness. An LLM can successfully format a JSON object but still hallucinate arguments, execute tools in an invalid sequence, or violate domain constraints. The subsections below survey the literature that addresses this residual risk from four directions: the architecture that governs when tools may be invoked, the model that proposes them, the routing that selects a subsystem, and the checks that may be applied to a proposal before it executes.

### 2.4.2 Agent Architectures

The architecture surrounding the LLM determines when tools can be invoked, what happens between invocations, and what the system guarantees about correctness and termination. The agent development literature has studied four architectural patterns, each governing LLM-tool interaction differently.

The simplest is the chain, in which the developer declares a fixed linear sequence of steps (classify the utterance, extract parameters, call a tool, generate a response) with no branching. As implemented in LangChain's LCEL [2.4.7], each utterance type follows its own predetermined chain, so the control flow is explicit and the execution trace is fully auditable. Prior work on chain-based task-oriented dialogue [2.4.8] reports reliable execution for narrow domains with predefined workflows. What the chain buys is deterministic governance: the developer hard-codes every step, transition, and termination condition. What it costs is rigidity. A routing error at step one is unrecoverable, because no architectural component inspects the utterance mid-chain and redirects it, and error recovery means enumerating every possible failure mode at every step, which becomes combinatorial once the input space is open-ended natural language.

The autonomous reasoning loop, introduced by the ReAct pattern [2.4.9], addresses the chain's inability to adapt to conversational variation by delegating governance to the LLM itself. On each iteration the model receives the current state (conversation history, tool definitions, and prior tool results) and produces either a reasoning trace, a tool call, or a final answer. The framework executes any tool call, feeds the result back into the loop, and the next iteration begins. AutoGPT [2.4.10] extended the pattern with internet access, file system operations, and long-term memory, which let agents pursue open-ended goals across dozens of iterations without human intervention. The loop is conversationally flexible: the LLM chooses its next action from what it observes, and the developer never enumerates dialogue paths.

That flexibility is bought by giving up the deterministic governance a chain provides. Termination is not guaranteed. The loop ends when the LLM decides to stop, and if the model enters a reasoning cycle, producing neither a tool call nor a final answer, the turn blocks indefinitely [2.4.11]. Nothing in the architecture enforces a valid tool sequence or checks tool arguments before execution. ReAct has been evaluated on knowledge-intensive benchmarks such as HotpotQA and FEVER [2.4.9], where it improved task completion rates over chain-based baselines. Its published limitations note that the architecture cannot guarantee bounded execution or action correctness, because governance and proposal reside in the same probabilistic component.

Graph-based architectures, as implemented in LangGraph [2.4.12], encode the state machine in the topology of the architecture rather than in prompt instructions. The developer declares a directed graph: a typed, shared state object flows through nodes (LLM calls, tool executions, or deterministic functions) connected by conditional edges that inspect the state and determine which node executes next. Unlike a chain, the graph can branch on runtime conditions. Unlike a loop, termination is structural, following from the graph topology rather than from the LLM. Three primitives are documented: a checkpointer that serializes state after each node execution for session-scoped persistence [2.4.13], conditional edges that can place a deterministic node on any path between an LLM call and a tool execution, and circuit breakers that bound execution by capping retry iterations before routing to a fallback. LangGraph has been evaluated primarily on code generation and multi-step reasoning tasks [2.4.12]; its applicability to task-oriented dialogue in Vietnamese has not been assessed.

Multi-agent architectures such as AutoGen [2.4.14], CrewAI [2.4.15], and CAMEL [2.4.16] distribute tools, prompts, and responsibilities across independent LLM instances that communicate through structured messages. The argument for the decomposition is specialization: each agent operates with a narrower scope and a more focused prompt than a single agent handling all tools [2.4.14]. Three limitations are documented. Attention dilution [2.4.17]: each agent's context window accumulates every peer agent's reasoning traces, tool outputs, and coordination instructions alongside the user utterance, and benchmarks record accuracy regression once the agent count passes two or three. Coordination is entirely LLM-mediated, since routing to a worker and handing off to a peer are themselves LLM calls, which leaves no deterministic coordination layer. And ownership of the business process is diffused across agents, with no single component structurally responsible for the correctness of the overall tool sequence.

Figure 2.4b illustrates the control flow of these four architectures.

**[Figure 2.4b. Four agent architecture patterns: (a) chain, a fixed linear sequence of steps; (b) autonomous loop, LLM-governed iteration without structural termination; (c) graph, a topology-encoded state machine with conditional edges and a circuit breaker; (d) multi-agent, LLM-mediated coordination between specialized agents.]**

**Table 2.4a.** Documented properties of the four agent architectures.

| Property | Chain | Loop (ReAct) | Graph (LangGraph) | Multi-agent |
|----------|:---:|:---:|:---:|:---:|
| Termination condition | Fixed length | LLM decides | Graph topology | Emergent; inter-agent loops reported |
| Deterministic step between proposal and execution | ✗ (no inter-step check) | ✗ (LLM validates itself) | Available (node placeable on any edge) | ✗ (responsibility diffused) |
| Tool ordering fixed by | Developer, before run time | LLM, at run time | Topology, conditional on state | Negotiation between agents |
| Adaptation to unanticipated utterances | ✗ (fixed paths) | ✓ (LLM-driven) | ✓ (conditional edges) | ✓ (specialized agents) |
| Coordination overhead | None (single path) | None (single agent) | None (single agent) | LLM-mediated per handoff |

The four separate on where governance resides. In a chain the developer holds it, fixed before any utterance arrives. In a loop the LLM holds it, exercised at run time. A graph moves it into the topology, fixed before run time but conditional on state. In a multi-agent system it is distributed across LLM instances and held completely by none of them. The properties reported for each follow from that placement rather than from implementation detail.

What none of the four has been evaluated on is task-oriented dialogue in which every proposed action is inspected before it executes. LangGraph's published results cover code generation and multi-step reasoning [2.4.12], ReAct's cover knowledge-intensive question answering [2.4.9], and the multi-agent frameworks report on collaborative task completion [2.4.14]. Whether the primitives any of them supplies are sufficient in a transactional domain, in Vietnamese or in any other language, is a question the surveyed work does not take up.

The architecture also determines how several tool calls compose into a valid sequence. ReAct [2.4.9] established sequential execution, where each call consumes the output of the previous one; Toolformer [2.4.52] demonstrated that LLMs learn to insert appropriate tool calls through self-supervised training on API documentation; Gorilla [2.4.53] showed accurate tool selection from large API collections after fine-tuning on synthetic tool-call data. Across these systems tool selection accuracy is well characterized. Compositional correctness is not, meaning whether the sequence of calls produces the intended final state independently of whether each individual call was correct.

Three composition patterns are documented. Sequential composition executes tools one after another, each consuming the previous output, which is simple to debug but cannot branch on a result. Parallel composition executes independent tools concurrently, which matters when an utterance carries several unrelated intents. Conditional composition routes to a second tool after a deterministic evaluation of the first tool's output: once a search returns results, the system has to determine whether the top match is exact enough to proceed, ambiguous enough to require clarification, or empty. Only the third requires a deterministic component sitting between two LLM-proposed calls, which makes it a property of the orchestration layer rather than of the model. Prior benchmarks have measured per-call accuracy, how often the correct tool is selected, rather than compositional correctness [2.4.54]. Under per-call metrics a system that issues a confirmation call before the items it confirms have been recorded scores correctly on both calls while producing an empty confirmed transaction, so documented agent accuracy may overstate reliability in domains where the calls share state. Figure 2.4c contrasts the three patterns.

**[Figure 2.4c. Tool composition patterns: (a) sequential, tools execute one after another; (b) parallel, independent tools execute concurrently; (c) conditional, tool B is selected from a deterministic evaluation of tool A's result.]**

### 2.4.3 Vietnamese-Capable Language Models

The model is the component that reads the utterance, the conversation history, and the system prompt, and produces the tool call. The literature categorizes Vietnamese-capable LLMs into three groups, each trading language quality against function-calling reliability and deployment constraints:
- Vietnamese-Native Models (e.g., PhoGPT): Offer excellent native fluency, tonal accuracy, and polite conversational registers (dạ, ạ). However, they lack native function-calling API support, so integrating them means reverting to the brittle post-hoc text parsing described in §2.4.1.
- Open-Weight Multilingual Models (e.g., Qwen2.5, Llama 3, Gemma 2): Provide strong, benchmark-validated function-calling capabilities and allow for self-hosted, offline deployment. The trade-off is language quality; their Vietnamese output is functional but occasionally stilted, tending toward a neutral register with occasional diacritic errors.
- Commercial APIs (e.g., GPT-4o, Claude 3.5 Sonnet): Deliver the highest documented performance in both Vietnamese fluency and structured tool invocation. However, they impose a strictly cloud-dependent deployment model, where every inference requires network connectivity and incurs per-token costs.

**Table 2.4b.** Function-calling support, Vietnamese quality, and context capacity across the three model categories, as documented in the literature.

| Category | Representative models | Open weights | Tool calling | Vietnamese quality | Context window |
|----------|----------------------|:---:|:---:|-------------------|:---:|
| Vietnamese-native | PhoGPT 7B, ViSoBERT | ✓ | ✗ (no API support) | Excellent (native speaker) | 4K |
| Open-weight multilingual | Qwen2.5 7B–72B, Llama 3 8B, Gemma 2 9B | ✓ | ✓, BFCL-reported; improves with scale | Moderate to good | 8K–128K |
| Commercial API | GPT-4o, Claude 3.5 Sonnet, Gemini 2.0 Flash | ✗ (API-only) | ✓, BFCL-reported | Excellent | 128K–1M |

Regardless of total context capacity, models universally suffer from the "lost in the middle" phenomenon, where attention mechanisms strongly favor information at the boundaries of the prompt. For task-oriented dialogue in Vietnamese, this architectural limitation is compounded by a tokenization penalty. Because multilingual subword tokenizers are optimized for high-resource languages, they over-segment Vietnamese diacritics and compound words. A Vietnamese conversation therefore consumes more of the context window than an English equivalent, reducing the budget available for system prompts, tool schemas, and few-shot examples. The size of that penalty is tokenizer-specific and is not reported for the models surveyed here.

Serving open-weight models on edge hardware often requires integer quantization (e.g., GGUF via llama.cpp) to reduce memory footprint. Documented evidence shows that quantization noise disproportionately degrades performance on languages underrepresented in the training data, which bears directly on fine-grained Vietnamese tonal distinctions. Prompt engineering (system instructions, few-shot examples, dynamic context injection) is the standard method for domain adaptation without fine-tuning, and all of these techniques draw on the same penalized context budget.

The two properties this domain requires together, function-calling accuracy and Vietnamese language quality, have only been evaluated apart. Benchmarks such as the Berkeley Function Calling Leaderboard (BFCL) test tool invocation exclusively in English, while Vietnamese NLU benchmarks measure text generation rather than structured actions. No published benchmark assesses domain-specific function calling in Vietnamese, where tool arguments carry compound proper nouns and tonal diacritics, so joint performance is unmeasured.

### 2.4.4 Intent Classification

Before an agent can invoke a tool, it must determine which subsystem the utterance addresses. A routing error, such as sending a catalogue query to a checkout subsystem, produces an incorrect system action regardless of how well the rest of the pipeline performs. The task-oriented dialogue literature documents five routing approaches, which trade execution speed against conversational flexibility:
- Rule-based and Lightweight Classifiers (e.g., SVMs, Rasa, fastText): Rely on n-gram features or keyword matching. Extremely fast, but they classify utterances in isolation, so they cannot distinguish a context-dependent confirmation from a greeting, and they rely on formal vocabularies, so they fail on informal Vietnamese teencode.
- Semantic Centroid Routing: Classifies inputs by cosine similarity to intent embeddings. It handles new vocabulary without retraining, but fails on multi-intent utterances, which produce blended and unmatchable embeddings, and on heavily distorted informal variants.
- State-Augmented Classification: Addresses context-blindness by concatenating dialogue state features with the text representation, at millisecond latency. It requires corpora annotated with dialogue states, which do not exist for Vietnamese.
- LLM-based Routing: Passes the utterance and conversation history to the LLM. It handles teencode, context-dependence, and multi-intent compounding. The cost is three orders of magnitude in routing latency (1.5 to 2.0 seconds per call), and temperature sampling makes the outcome non-deterministic.
- LLM-based Decomposition: A hybrid variant using the LLM only to split complex utterances into fragments for a fast downstream classifier. It is untested on Vietnamese, where teencode compounding and missing punctuation create ambiguous segmentation boundaries.

<!-- SOURCE NEEDED [2.4.42]: a paper defining state-augmented / context-aware intent classification, where dialogue-state features are concatenated with the utterance representation as classifier input. -->
<!-- SOURCE NEEDED [2.4.63]: an evaluation of that approach on English task-oriented dialogue, reporting the accuracy gain from the state features. -->

Figure 2.4d compares these approaches.

**[Figure 2.4d. Five intent routing approaches: architecture and data flow for each, annotated with latency and determinism properties.]**

**Table 2.4c.** The five routing approaches against criteria documented in the routing literature.

| Approach | Informal language | Context-aware | Multi-intent | Domain vocabulary | Inference cost | Deterministic |
|----------|:---:|:---:|:---:|:---:|---|:---:|
| Rule/SVM (Rasa, Dialogflow) | ✗ | ✗ | ✗ | ✗ | Milliseconds | ✓ |
| Lightweight (fastText, SetFit) | Partial (subwords) | ✗ | ✗ | ✗ | Milliseconds | ✓ |
| Semantic centroid | ✗ (informal distant from centroids) | ✗ | ✗ | ✓ | Milliseconds, after one embedding pass | ✓ |
| LLM-based | ✓ (seen in pretraining) | ✓ | ✓ | ✓ | Seconds | ✗ |
| State-augmented classifier | Depends on the embedding model | ✓ | ✗ | Depends on the embedding model | Milliseconds, after one embedding pass | ✓ |

The surveyed literature positions these approaches on a single axis running from cheap and brittle to expensive and flexible, and reports a system's position on that axis as a property fixed at design time: an evaluation states one approach's accuracy and latency averaged over a whole test set. No surveyed evaluation varies the routing mechanism within a session according to a property of the individual utterance, so the published results cannot distinguish whether the trade-off belongs to the approaches themselves or to the decision to apply one of them uniformly. Separately, no approach has been evaluated on Vietnamese task-oriented speech, where compound dish names, tonal diacritics, and teencode abbreviations exercise the documented weakness of every method at once.

### 2.4.5 Action Validation

Correct routing ensures the right tool is invoked, but it does not guarantee correct arguments. An LLM can emit a syntactically valid call whose arguments name an entity that does not exist in the database the tool writes to. Function calling guarantees syntactic structure; semantic correctness requires a separate mechanism.

The literature documents three approaches to argument-level errors, intervening at different points:
- Constrained Decoding: Intervenes during token generation to enforce JSON schema compliance. It guarantees syntactic validity, for instance that a quantity field holds an integer, but it is blind to fact: the schema knows types, not whether a string value corresponds to a real record.
- Retrieval-Augmented Generation (RAG) Grounding: Injects authoritative domain data into the prompt to lower the probability of a hallucinated argument. It reduces error rates but enforces nothing, and provides no signal when the model ignores the injected context and fabricates a value anyway.
- Human-in-the-Loop: Intervenes after generation, requiring an operator to review each tool call before execution. It achieves semantic accuracy at the cost of autonomy, which rules it out for unattended operation.

**[Figure 2.4e. Where documented validation approaches intervene: constrained decoding and RAG grounding act during generation; human review acts after generation but requires an operator. The interval between a fully formed tool call and its execution is unoccupied by any autonomous approach in the surveyed work.]**

**Table 2.4d.** Where each documented validation approach intervenes, and what it checks.

| Approach | Syntax check | Semantic check | Autonomous | Operates at |
|----------|:---:|:---:|:---:|---|
| Constrained decoding | ✓ | ✗ (schema knows types, not facts) | ✓ | Generation time |
| RAG grounding | ✗ (no enforcement) | Partial (reduces probability) | ✓ | Generation time |
| Human-in-the-loop | ✓ | ✓ (human verifies) | ✗ (requires operator) | Post-generation |

A propose-and-verify pattern, in which a probabilistic model proposes an action and a deterministic environment checks it, is documented in domains that supply an automatic oracle: code generation, where a test suite decides, and clinical decision support, where a drug interaction database decides. It remains largely uncharacterized in conversational agents, where the corresponding oracle would have to be the domain's own operational records.

The three approaches above act either during generation, by making a wrong argument less likely, or after generation through a person. The interval between the point at which a tool call is fully formed and the point at which it executes is occupied by no autonomous mechanism in the surveyed work, and no published evaluation reports what an agent's argument error rate would be if one were placed there.

### 2.4.6 Memory and State Management in Conversational Agents

A transactional interaction spans multiple turns, and resolving references across them requires the agent to carry information forward. The literature documents four strategies for maintaining dialogue history within an LLM's context:
- Sliding Window: Retains the most recent N messages. Cheap and predictable, but blind to early-turn context.
- Periodic Summarization: Uses an LLM to compress older turns. Saves tokens at the cost of lossy compression.
- Vector Retrieval: Embeds past turns and retrieves them by semantic similarity, allowing targeted recall without flooding the prompt.
- Hybrid Approaches: Combine summarization for broad context with vector retrieval for specific historical detail.

All four are bounded by the context window. They are subject to the "lost in the middle" effect and, in Vietnamese, to the tokenization overhead described in §2.4.3, which competes with system prompts and tool schemas for the same budget.

**[Figure 2.4f. Memory strategies in conversational agents: (a) sliding window discards older turns; (b) periodic summarization compresses history; (c) vector retrieval selects relevant past turns; (d) hybrid combines summary with retrieval. Below: application state (cart, stage, search context) maintained as structured fields alongside conversation text.]**

General-purpose memory frameworks store conversation history and application state through the same mechanism, and the two do not tolerate the same treatment. A summarized turn still conveys the flow of a dialogue, so history survives lossy compression. A structured record of what was decided does not: compressing an itemized selection to "the customer ordered some seafood" removes the ability to price, confirm, or bill it. Serialization tools exist, LangGraph's SQLite checkpointer among them [2.4.13], but the surveyed memory literature reports no evaluation that separates the two kinds of content or measures the effect of retaining them under different policies.

### 2.4.7 Identified Literature Gaps

The components surveyed above have been studied separately and, more consequentially, evaluated separately. Architectures are assessed on code generation and multi-step reasoning, models on either function-calling benchmarks or Vietnamese language benchmarks but not both, routing approaches on English task-oriented corpora, validation approaches on the domains that happen to supply an automatic oracle, and memory strategies on the retention of conversation text. Three absences follow from that separation.

The first is joint measurement (§2.4.3). Function-calling accuracy and Vietnamese language quality are the two properties a Vietnamese task-oriented agent needs at the same time, and no published benchmark reports them for the same model on the same task. The tokenization penalty Vietnamese imposes on the context budget is likewise unquantified for the models surveyed, although it constrains every technique competing for that budget, from system prompts to few-shot examples to dialogue history.

The second is the unoccupied interval in the action path (§2.4.5). Validation in the surveyed work happens during generation or through a human. The propose-and-verify pattern that would occupy the space between them is documented in code generation and clinical decision support, where an automatic oracle exists, and has not been characterized for conversational agents, where the oracle would have to be the domain's own records. The architectures of §2.4.2 supply primitives capable of hosting such a step, but no evaluation reports one in place or measures its effect.

The third is the treatment of state (§2.4.6). Memory research measures the retention of conversation text, whereas the deterministic records a transaction produces are governed by different requirements, and no surveyed evaluation distinguishes the two.

Each absence has been recorded here against a single component. What the surveyed work does not report is a system in which they are addressed together, for Vietnamese or for any other language.
