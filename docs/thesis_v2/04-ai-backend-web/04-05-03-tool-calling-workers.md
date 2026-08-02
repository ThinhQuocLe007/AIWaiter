### 4.5.3 Action Selection

Once the router has fixed the intent, one of four workers decides what to do about it. The
order agent turns "Cho tôi 2 Ốc Hương" into a call to add to cart carrying a name and a
quantity. The search agent turns "món gì ấm bụng" into concrete search terms. The payment
dispatcher emits the one call its intent allows. The chat agent produces no call at all. This
section describes what each worker is bound to, what it is told, and what it does when the
utterance in front of it does not fit.

None of the four is fine-tuned. The one trained component in the agent is the intent
classifier, and even that trains a small head on a frozen embedding. Everything that adapts
the shared language model to these four roles is carried by the prompt, which makes the prompt
a design element here rather than an implementation detail.

All four places the agent calls a language model, the rewriter, the two tool-calling workers,
and the response generator, share one model instance: Qwen2.5 14B Instruct. The survey of
Section 2.4.3 of Chapter 2 groups Vietnamese-capable models into three categories, and this
one comes from the open-weight multilingual group, the only category that offers documented
function-calling support, Vietnamese good enough to speak to a customer, and weights that can
be held on the restaurant's own server.

The model is served locally by Ollama with persistent keep-alive, so it remains pinned in GPU
memory and no loading overhead is incurred between stages. Each stage configures the same
model differently: temperature and tool-binding are set per call, not per instance.

Which tools each agent may call is shown in Figure 4.3: the order agent holds the four
cart operations, the search agent holds retrieval, the payment dispatcher holds the single
payment call, and the chat agent holds none. The escape hatch is bound to the two agents
that call the model and to neither of the deterministic ones.

That escape hatch is the delegate tool, and it is the one callable the tool node never runs.
A worker calls it when the utterance in front of it fits none of its tools, passing a short
reason in Vietnamese. The graph reads the call as the worker giving up the turn: it keeps the
reason, drops the intent from the queue, and lets the turn finish with no tool executing, so
the reply is assembled from the conversation rather than from an action. A question about
opening hours reaching the search agent is not a search the menu can answer, and the worker
can say so instead of running one. Without this, forced tool choice would leave it nothing to
do but invent a call for the validator to reject.

Table 4.6 gives what each agent receives, its dynamic context from the conversation
state, its system prompt, and its few-shot examples, and what it produces. The four
agents share no prompt between them; each is an independent module, and the only coupling
is through the agent state object they read and write. All system prompts are written in
Vietnamese, which produces more natural Vietnamese output than prompting in English.

*Table 4.6. What each agent receives and what it produces.*

| Agent | Dynamic context | System prompt | Few-shot | Produces |
|-------|----------------|---------------|----------|----------|
| Order agent | Active cart (items, quantities, prices); dishes returned by a recent search, under their menu names; validator feedback on retry | `order_worker_agent.md`: cart rules, quantity patterns, modifier handling | `order_worker.json` (11 pairs) | One tool call: add\_cart, remove\_cart, clear\_cart, confirm\_order, or delegate |
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

The second choice is where the one thing the design cannot establish is absorbed. Function
calling and Vietnamese have only ever been benchmarked apart, tool-invocation suites running
in English and Vietnamese suites measuring generated text rather than structured actions
(§2.4.3), so no published figure says how accurately any model calls a function while working
in Vietnamese, where the arguments are compound dish names carrying tonal diacritics. Nothing
here can supply that figure.

What the design can do is give the model less to get wrong. Keeping the menu out of the prompt
means it is never asked to decide whether a dish exists, only to repeat the string the customer
said and attach a number to it. Whether "Ốc Hương Xốt Trứng Muối" is spelled correctly, is on
this menu, or names one dish rather than eleven is settled afterwards, in Python, against the
menu file.

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
