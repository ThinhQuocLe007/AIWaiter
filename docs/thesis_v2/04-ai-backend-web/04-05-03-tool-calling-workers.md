## 4.5.3 Specialized Agents and Prompt Architecture

Section 4.5.1 established why the architecture deploys specialized agents rather than a single
monolithic model. This section details how each agent is built: what tools it is bound to, what
context it receives, how it recovers when an utterance falls outside its domain, and how the
shared language model is adapted to each role. That adaptation is carried entirely by prompting.
No fine-tuning is used anywhere in the agent, and the intent classifier is the one trained
component, training only a small head on top of a frozen embedding. The prompt architecture is
therefore a design element rather than an implementation detail. It is also where the survey's
one unclosed finding is absorbed rather than answered: §2.4.3 reports that function-calling
accuracy and Vietnamese language quality have only ever been measured apart, so no published
figure says how well a model does both at once on a task like this one. Nothing in the design
can supply that measurement. What it can do is reduce how much rests on it, by narrowing what
the model is asked to produce and checking what it produces afterwards.

All three language-model-calling stages, the rewriter, the two tool-calling workers, and
the response generator, share one model instance: Qwen2.5 14B Instruct, selected from
the survey of §2.4.3 for its Vietnamese-language capability and reliable function-calling
protocol. The model is served locally by Ollama with persistent keep-alive, so it remains
pinned in GPU memory and no loading overhead is incurred between stages. Each stage
configures the same model differently: temperature and tool-binding are set per call,
not per instance.

Which tools each agent may call is shown in Figure 4.3: the order agent holds the four
cart operations, the search agent holds retrieval, the payment dispatcher holds the single
payment call, and the chat agent holds none. The escape hatch is bound to the two agents
that call the model and to neither of the deterministic ones.

Table 4.8 gives what each agent receives, its dynamic context from the conversation
state, its system prompt, and its few-shot examples, and what it produces. The four
agents share no prompt between them; each is an independent module, and the only coupling
is through the agent state object they read and write. All system prompts are written in
Vietnamese, which produces more natural Vietnamese output than prompting in English.

*Table 4.8. What each agent receives and what it produces.*

| Agent | Dynamic context | System prompt | Few-shot | Produces |
|-------|----------------|---------------|----------|----------|
| Order agent | Active cart (items, quantities, prices); validator feedback on retry | `order_worker_agent.md`: cart rules, quantity patterns, modifier handling | `order_worker.json` (11 pairs) | One tool call: add\_cart, remove\_cart, clear\_cart, confirm\_order, or delegate |
| Search agent | Already-known items from prior search results and cart; validator feedback on retry | `search_agent.md`: rewriting instructions, delegation triggers | `search_worker.json` (11 pairs) | One tool call: search (with rewritten query terms), or delegate |
| Payment dispatch | Table identifier | None (deterministic) | None | One tool call: request\_payment |
| Chat worker | Full conversation history, cart with total, order stage, curated dishes from prior searches, delegate reason | None (deterministic) | None | Typed chat context (no tool call) |

The two language-model agents share two design choices that distinguish them from a
generic tool-calling setup. First, forced tool choice (`tool_choice="any"`) requires each
invocation to produce exactly one tool call; a single automatic retry recovers the
occasional failure where the model responds in Vietnamese text instead of calling a tool.
Second, the menu is deliberately excluded from every decision prompt: the model extracts
raw item strings and quantities, and the validator resolves names against the authoritative
menu.

The three stages that call the shared model use different runtime configurations.
The rewriter runs at temperature zero with output constrained to a list of fragments.
The workers run at 0.1 with forced tool choice, enough to tolerate Vietnamese
orthographic variation while keeping tool selection stable. The response node runs at 0.1
with free-form generation, low enough that the reply stays close to the pre-verified data
it is given.

The model's Vietnamese limitations, moderate diacritic accuracy and variable compound-word
handling, are absorbed by the surrounding design rather than by the prompt. Classification
does not depend on them, because the trained classifier decides the intent without a model
call. Orthographic errors do not reach the cart, because the validator normalizes diacritics
on both sides before matching a name. What the model is left to do is extraction and
paraphrasing: deciding which structured action to take, and how to say what has already been
verified.
