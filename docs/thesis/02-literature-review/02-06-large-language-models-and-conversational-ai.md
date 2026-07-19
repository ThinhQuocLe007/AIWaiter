# 2.6 Large Language Models and Conversational AI

While the preceding sections covered the perception, state-estimation, and navigation theory that allows a mobile robot to move autonomously, a service robot that interacts with customers also requires a "brain" capable of understanding natural language, retrieving factual knowledge, and carrying out multi-step tasks such as taking an order. This section presents the theoretical background of that language layer: large language models (2.6.1), prompt engineering techniques for steering them (2.6.2), intent routing with semantic embeddings (2.6.3), Retrieval-Augmented Generation and its agentic extension (2.6.4), and LLM agents together with the LangGraph orchestration framework (2.6.5).

### 2.6.1 Large Language Models

A Large Language Model (LLM) is a deep neural network trained on very large text corpora to predict the next token in a sequence. Modern LLMs are based on the Transformer architecture [n], whose central building block is self-attention: every token in the input produces a query, key, and value vector (through learned linear projections of its embedding), and each token attends to every other token by comparing its query against all keys. Packing the queries, keys, and values into matrices , , , the attention operation is:

where contains the dot-product similarity between every query-key pair,  is the key dimension (the scaling  keeps the values numerically stable), and the softmax turns each row of similarities into weights summing to one, so each token's output is a weighted combination of all value vectors. In practice a Transformer runs several such attention operations in parallel (multi-head attention, each head with its own projections, able to capture a different kind of relationship) and stacks many such layers, each followed by a feed-forward sub-layer with residual connections and layer normalization, as shown in Figure 2.12. Because all token pairs are compared in a single matrix product, this design parallelizes efficiently on GPUs and can relate distant words in one step - the properties that made training models with billions of parameters practical.

> Figure 2.12 — Conceptual structure of a Transformer block: multi-head self-attention followed by the feed-forward sub-layer, with residual connections and layer normalization (redrawn from [n]).

Text generation and temperature. At inference time an LLM generates text autoregressively: given the prompt and all previously generated tokens, it outputs a probability distribution over the vocabulary and one token is sampled from it. The temperature parameter  divides the logits before the softmax and thereby controls the randomness of this sampling: a near-zero temperature makes the model almost always pick the most likely token, yielding deterministic, consistent output, while a higher temperature produces more varied text. A conversational agent therefore uses a near-zero temperature for decision-making steps - intent classification and structured tool calls, where consistency matters - and only slightly higher values for free-form response generation.

SLM versus LLM. Model capability grows with parameter count, but so do memory footprint and latency. This has led to a useful distinction between Small Language Models (SLMs roughly 1-3 billion parameters) and full-size LLMs. An SLM cannot match a large model in open-ended reasoning, but for narrow, well-defined tasks, such as classifying an utterance into one of a handful of intents when guided by a few examples. It achieves comparable accuracy at a fraction of the inference cost. A common design pattern in production dialogue systems is therefore to use a small, fast model as a router and reserve larger models for the steps that genuinely require generation. Locally hosted runtimes such as Ollama [n] make this pattern practical by serving multiple quantized open-weight models behind one API and keeping them resident in memory to avoid reload overhead.

### 2.6.2 Prompt Engineering

Because an LLM is controlled entirely through its input text, the way a task is phrased has a direct effect on output quality. Prompt engineering is the practice of designing that input - the instructions, examples, and context supplied to the model, so that a general-purpose model performs a specific task reliably, without modifying its weights [n]. It is the primary adaptation method used in this work; no model is fine-tuned. Four techniques are relevant here.

System prompt and role prompting. Chat-oriented LLMs distinguish the system prompt - persistent instructions defining the model's role, permitted behavior, and output format - from the user messages of the conversation. Assigning an explicit role and boundaries ("you are a waiter of restaurant X; you may only discuss items on the provided menu") narrows the space of responses and is the first line of defense against off-topic or fabricated answers.

Zero-shot and Few-shot prompting (in-context learning). In zero-shot prompting the model receives an instruction alone; this suffices for common tasks but is unreliable when the task involves domain-specific conventions or a strict output format. Few-shot prompting adds a small number of worked input -> output example pairs to the prompt, and the model infers the pattern from them, a phenomenon known as in-context learning [n]. It markedly improves accuracy in classification tasks and is the standard way to enforce an exact output convention, at the cost of a longer prompt on every call.

Structured output. When the model's answer is consumed by a program rather than a person, free-form text is fragile. The prompt therefore specifies a machine-readable schema, typically a JSON object with declared fields and allowed values and constrained decoding can enforce it at the decoder level, so the output is syntactically valid by construction. Structured output is what turns an LLM from a text generator into a usable software component, and it underlies the tool-calling mechanism.

Prompt structure and prefix caching. Inference servers cache the attention computation (the key - value cache) of a prompt prefix and reuse it when the same prefix appears again. Structuring every prompt as static part first, dynamic part last, the fixed system prompt and few-shot examples at the beginning, the changing conversation context appended at the end. Let’s most of the prompt be served from cache on every turn, reducing latency at no cost in quality.

> Figure 2.13 — Zero-shot versus few-shot prompting on the same classification task (drawn by the group, adapted from [n]).

### 2.6.3 Intent Routing and the Semantic Router

A task-oriented dialogue system must first determine what the user wants before deciding how to respond. This classification step is called intent routing: each utterance is assigned to one of a predefined set of intents (placing an order, searching the menu, requesting payment, casual chat), and dispatched to the sub-system responsible for it. The naive solution is letting an LLM classify every utterance is accurate but adds a full LLM inference of latency to every turn. A much faster alternative is the semantic router, which classifies purely with vector arithmetic in an embedding space.

Sentence embeddings. An embedding model maps a sentence to a fixed-length vector such that semantically similar sentences lie close together. Embedding inference takes milliseconds - orders of magnitude cheaper than LLM generation.

Per-intent centroids. For each intent , a small set of representative example utterances is embedded, and their mean forms the intent's centroid:

where  is the embedding of the -th of the  examples of intent . The centroid acts as a prototype of that intent in the embedding space and is precomputed offline, so at runtime only the incoming utterance must be embedded.

Cosine similarity. The incoming utterance's embedding  is compared against each centroid with the cosine of the angle between them:

where  is the similarity score between the utterance and intent ;  is the embedding vector of the incoming utterance;  is the centroid of intent  from Equation (2.x);  is the dot product of the two vectors; and ,  are their Euclidean norms (lengths), so that dividing by them removes the effect of vector magnitude. Cosine similarity is preferred over Euclidean distance because it depends only on the direction of the vectors, which is what encodes semantic content and not on their magnitude.

Softmax and gap gating. Raw similarities are hard to threshold directly, because their absolute values depend on the embedding model. The scores are therefore first converted into a probability distribution with a temperature-scaled softmax:

where  is the resulting probability assigned to intent ;  is that intent's cosine score from Equation (2.x); the sum in the denominator runs over all intents , so that the probabilities sum to one;  is the exponential function; and  is the temperature, which controls how sharply differences between the scores are amplified — a smaller  produces a more peaked distribution. Let  and  denote the largest and second-largest of these probabilities. The router accepts the top intent only if two conditions hold simultaneously:

where  is the probability of the winning intent;  is the probability of the runner-up;  is the probability threshold, the minimum probability the winner must reach in absolute terms; and  is the gap threshold, the minimum margin by which the winner must dominate the runner-up. This combined rule is called gap gating. If either condition fails, the utterance is treated as ambiguous and deferred to a fallback classifier, an SLM prompted with few-shot examples and constrained to return a structured prediction, which can also recognize multiple intents in one utterance. Figure 2.14 illustrates the decision geometrically.

> Figure 2.14 — Semantic routing in a 2-D sketch of the embedding space: utterance embedding, per-intent centroids, and the gap-gating decision (drawn by the group).

### 2.6.4 Retrieval-Augmented Generation (RAG) and Agentic RAG

The hallucination problem. An LLM stores knowledge implicitly in its weights, frozen at training time. Asked about facts it was never trained on, a specific restaurant's menu, prices, promotions. It does not abstain but produces fluent, fabricated text, a failure mode known as hallucination [n].

Retrieval-Augmented Generation. RAG [n] addresses hallucination by separating knowledge from language ability: relevant documents are retrieved from an external, curated knowledge base at query time and injected into the prompt, so the LLM only needs to read and rephrase verified information. The pipeline has three stages:

(1) Indexing (offline): The knowledge sources are split into retrieval units, embedded, and stored in a vector database supporting fast similarity search (e.g., FAISS [n]); the unit granularity is a design choice, and for structured data such as a menu, one record per document is more effective than fixed-size text chunking.

(2) Retrieval (online): The query is embedded with the same model and the top- most similar documents are fetched;

(3) Generation: The retrieved documents are placed in the LLM prompt together with the query, and the model answers grounded in that context.

Hybrid retrieval: keyword + semantic. Dense vector search captures meaning ("something sour and spicy" matches dishes whose descriptions convey that flavor), but can miss exact terms — proper names and rare dish names. Sparse keyword retrieval has the opposite profile. The classical sparse method is BM25 [n], which scores a document  against query terms as:

where  is how often term  occurs in ;  weights rare, informative terms above common ones;  is the document's length relative to the collection average; and the constants (term-frequency saturation) and  (length-normalization strength) tune the formula, with typical defaults , . For Vietnamese, whose lexical units are multi-syllable compounds (e.g., "bún bò Huế"), BM25 requires a word segmentation step so that tokens correspond to meaningful words rather than isolated syllables.

Hybrid retrieval runs both retrievers in parallel on the same query and merges their ranked lists with Reciprocal Rank Fusion (RRF) [n]:

where  is the position of document  in retriever 's list and is a smoothing constant (standard value ). RRF needs only ranks, not comparable scores, which makes it well suited to fusing BM25 with cosine similarities; documents ranked highly by both retrievers accumulate the largest fused scores. A gatekeeper rule can additionally be applied after fusion: if even the best result is weakly relevant (low top vector similarity and no literal keyword overlap), the system returns an empty result rather than feeding misleading context to the LLM, abstaining is safer than hallucinating.

Agentic RAG. In the classical pipeline, retrieval is unconditional and fixed: every query triggers exactly one retrieval with the raw query text, and the result is always injected into the prompt. This wastes computation on turns needing no knowledge (greetings, confirmations) and gives the model no influence over what is searched. Agentic RAG [n] removes both limitations by exposing retrieval to the model as a tool: the model itself decides whether to invoke the search and with which arguments, acting as a query rewriter that turns a vague request ("cái gì đó nóng cho ngày lạnh") into an explicit call with concrete keywords and structured filters (category, price range, dietary type). In its simplest and most widely used practical form, adopted in this work, the agent issues at most one retrieval call per user turn; more elaborate variants let the agent inspect the results and search again in a multi-step loop, trading latency for answer quality. Figure 2.15 contrasts the two paradigms.

> Figure 2.15 — Plain RAG (retrieval hard-wired into a fixed pipeline) versus Agentic RAG (retrieval exposed as a tool the agent decides when and how to call) (drawn by the group, adapted from [n]).

### 2.6.5 LLM Agents and the LangGraph Framework

From single prompts to agents. In its basic use, an LLM maps one prompt to one answer. An LLM agent goes further: the model is placed inside a control loop in which it repeatedly observes the current situation (the conversation so far and any task state), decides on an action — reply to the user, call a tool, or ask a clarifying question — and receives the result of that action as new context for the next decision [n]. The mechanism that makes this possible is tool calling (also called function calling): the operations available to the agent (searching a knowledge base, creating an order, requesting a payment) are described to the model as functions with typed parameters, and the model may output, instead of prose, a structured request to invoke one of these functions with concrete arguments. The application executes the call, appends the result to the context, and the model continues from there. Tool calling is a direct application of the structured-output techniques of Section 2.6.2, and it is what allows a language model to act on external systems rather than merely talk about them.

Why an orchestration framework. The simplest way to build an agent is a single monolithic prompt containing all instructions and all tool definitions, with the LLM deciding everything in one place. This approach scales poorly: as the number of tasks grows, the prompt becomes long and self-contradictory, a single misbehavior is hard to localize and test, and nothing structurally prevents the model from looping forever or calling tools in an invalid order. The established remedy is to decompose the agent into an explicit graph of smaller, specialized steps, in which each LLM call has one narrow job, deterministic program code can be inserted between LLM calls, and the possible control flow is declared up front. This makes the system's behavior inspectable, testable node by node, and bounded in its failure modes.

LangGraph. LangGraph [n] is an open-source framework for building such stateful, graph-structured LLM applications. An application is declared as a StateGraph consisting of three elements:

State: a typed, shared data structure (the message history plus task-specific fields such as a shopping cart or a dialogue stage) that flows through the graph. Each node receives the current state and returns an update, which the framework merges using declared reducer functions — for example, appending new messages to the history rather than overwriting it.

Nodes: the units of computation. A node may invoke an LLM, execute a tool, or run ordinary deterministic Python code, the framework treats all three identically, which is precisely what allows cheap rule-based checks to be interleaved between expensive LLM calls.

Edges: the transitions between nodes. A normal edge always routes to the same successor, while a conditional edge evaluates a function of the current state and routes dynamically. Conditional edges are how branching (dispatching to different nodes depending on the classified intent), looping (retrying a step after a failed check, bounded by a counter in the state so that termination is guaranteed), and early exits are expressed.

> Figure 2.16 — A LangGraph StateGraph: a shared typed state flowing through nodes (LLM calls, tools, and plain code), with normal edges, a conditional branch, and a bounded loop (drawn by the group).

Persistence and conversation memory. LangGraph provides a checkpointer that saves the graph state after every step, keyed by a thread identifier. When the next user utterance arrives with the same thread ID, the graph resumes from the saved state — this is what gives the agent memory of the dialogue history and task progress across turns. Assigning one thread per user session also yields clean isolation: closing a session and starting a new thread guarantees that no context leaks from one customer's conversation into the next.

Typed tool schemas. For tool calling to be reliable, every tool must expose a machine-checkable interface. In the Python ecosystem this is typically declared with Pydantic [n]: a tool's arguments are defined as a typed schema (field names, types, allowed literal values, required/optional status), which serves three purposes at once — the schema is rendered into the LLM prompt so the model knows the exact calling convention; it validates the model's output automatically, rejecting malformed calls before they reach any backend; and it documents the agent's action space explicitly. Beyond schema validation, an additional validation node of plain deterministic code can be placed between the LLM and the tool execution, checking each proposed call against business rules and looping back to the model with corrective feedback when a check fails.

Together, these mechanisms address the central weakness of LLM-based systems, their probabilistic, occasionally erroneous output. By wrapping every generative step in deterministic structure: typed schemas constrain what the model can emit, validation checks it before it takes effect, and the explicit graph bounds where the computation can go.

