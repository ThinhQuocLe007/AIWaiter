## 4.5.3 Specialized Agents and Prompt Architecture

Section 4.5.1 established why the architecture deploys specialized agents rather than a single
monolithic model. This section details how each agent is built: what tools it is bound to, what
context it receives, how it recovers when an utterance falls outside its domain, and how the
shared language model is adapted to each role. That adaptation is carried entirely by prompting.
No fine-tuning is used anywhere in the agent, and the intent classifier is the one trained
component, training only a small head on top of a frozen embedding. The prompt architecture is
therefore a design element rather than an implementation detail, which is the gap §2.4.3
identified: prompt engineering for domain adaptation is documented in the literature but untested
on Vietnamese restaurant ordering.

Table 4.8 sets out the four agents and the tools each is permitted to call.

*Table 4.8. The four agents, the tools each is allowed to call, and its model setting.*

| Agent | Intent | Bound Tools | Uses LLM | Temperature |
|-------|--------|-------------|----------|-------------|
| Order agent | ORDER, ORDER\_CONFIRM | add\_cart, remove\_cart, clear\_cart, confirm\_order, delegate | Yes | 0.1 |
| Search agent | SEARCH | search, delegate | Yes | 0.1 |
| Payment dispatch | PAYMENT | request\_payment | No | N/A |
| Chat worker | CHAT | none | No | N/A |

Each agent receives a specific set of dynamic context injected into its prompt at runtime. What
an agent sees determines what it can decide: the order agent cannot confirm an order if it does
not know the cart contents, and the search agent cannot avoid redundant queries if it does not
know what has already been retrieved. Table 4.9 lists what each one receives.

*Table 4.9. What each agent is told about the current situation, and why it needs it.*

| Agent | Dynamic Context | Purpose |
|-------|----------------|---------|
| Order agent | Cart contents (items, quantities, prices) | Enables additive decisions, prevents re-adding items already present |
| Order agent | Validator feedback (on retry) | Names the exact problem and nearest valid menu item for correction |
| Search agent | Already-known items (prior search results and cart contents) | Prevents re-searching topics already discussed; triggers delegation for follow-up questions |
| Search agent | Validator feedback (on retry) | Corrective instructions for invalid search queries |
| Payment dispatch | Table identifier (injected by validator) | Required by the backend orchestrator for session-scoped payment requests |
| Chat worker | Conversation history, cart with total, order stage, curated dishes from search, delegate reason | Enables memory-grounded and stage-appropriate conversational replies |

The two language-model-based agents share three design patterns that distinguish them from a
generic tool-calling setup. The first is forced tool choice: each agent always produces exactly
one tool call per invocation. Without this constraint the model can answer in text instead of
acting, saying "Dạ, em sẽ thêm món đó vào giỏ hàng" without calling the add-to-cart tool, so the
system appears to acknowledge the request while doing nothing.

The second is temperature 0.1 rather than zero. Zero would reject variant phrasings of Vietnamese
tool arguments, such as "ít cay" against "it cay", making the system brittle to informal spelling
while buying no real determinism, because tool selection is already near-deterministic at this
setting. The slightly-above-zero value allows orthographic variation in argument values while
keeping the choice of which tool to call stable across invocations.

The third is the deliberate exclusion of the menu from every decision prompt. The model does not
need the 219-entry menu to decide which tool to call or to extract names and quantities: when a
customer says "Cho 2 Ốc Hương Xốt Trứng Muối," it only has to recognize an ordering action and
extract the raw item string. Resolving that string against the menu belongs to the validator
(§4.5.4). Excluding the menu keeps prompts compact, cuts per-turn latency, and removes the risk
of the model inventing an item it believes it saw in the prompt.

The order agent is bound to five tools. Three are cart operations: add items with names,
quantities, and optional special requests; remove a named item; and clear the cart. One sends the
composed order to the kitchen. The fifth, delegate, is the escape hatch for an utterance that
maps to no cart action. Each tool has a structured argument schema enforced by the model's
function-calling mechanism: "Cho 2 Ốc Hương" becomes a record with name "Ốc Hương" and quantity
2; "Lấy 1 phần Lẩu Thái, ít cay" carries "ít cay" as a special request; "Thêm 1 Bia Sài Gòn và 1
Nước Suối" produces two items in a single call. The model's job is extraction, not validation.
Its dynamic context is the current cart, which lets it add to an existing cart rather than
replace it, and on a retry the validator's feedback, which names the exact problem so the model
can fix its output without re-reasoning the whole utterance.

The search agent is bound to two tools: the search tool, which runs a retrieval query over the
menu and knowledge base through the hybrid pipeline of §4.6, and delegate. Its primary work is
rewriting a conversational request into concrete search terms, which §4.6.1 describes in full.
Its system prompt names what falls outside its domain, restaurant hours, parking availability,
WiFi passwords, music requests, and complaints, and requires the model to call delegate with an
explanatory reason rather than search for a dish that cannot exist.

The payment dispatch is deterministic: no language model, no keyword matching, no ambiguity. The
router has already classified the intent as PAYMENT, and there is only one payment action the
agent can initiate. It always emits a request-payment tool call with the table identifier.
Computing the session total from all confirmed orders, generating the payment QR code, and
verifying payment completion are handled by the backend orchestrator (§4.7), not the agent.

The chat worker is a pure function with no language model and no tools. It reads the current
conversation state and assembles a structured context for the response generator: the customer's
utterance, the active cart and its total, the current order stage, the conversation history, and
up to five dishes from the most recent search converted into structured objects. If the chat
worker was reached via delegation, the delegate reason explains why the domain agent passed
control, for example "restaurant info query, not menu search." No validation occurs because
there are no tool calls to validate; its responsibility is assembly, not generation.

The delegate tool, bound to both language-model-based agents, is what stops forced tool choice
from forcing a wrong action. Some utterances genuinely fall outside an agent's domain: if the
search agent receives "mấy giờ đóng cửa?" (what time do you close?), no menu item matches "đóng
cửa" and a search call would return noise. Delegate provides a non-destructive way out. The
model calls it with a reason, and the graph's routing function dispatches the utterance to the
chat worker for a conversational response. The model is never forced to guess; when it is
uncertain about its domain, it admits it.

Domain adaptation, meaning Vietnamese restaurant vocabulary, the ordering workflow, and the
hospitality tone, is carried by prompt files loaded at agent startup: five system prompts and
three few-shot example sets, stored as editable text. A menu change or a tone adjustment needs
only a file edit and a restart, with no retraining and no code change. Table 4.10 lists them and
the node that reads each.

*Table 4.10. The prompt resources, and the node that loads each at startup.*

| File | Kind | Loaded by |
|------|------|-----------|
| `order_worker_agent.md` | System prompt | Order agent |
| `search_agent.md` | System prompt | Search agent |
| `rewriter_agent.md` | System prompt | Rewriter, called inside the classifier router |
| `response_rewriter.md` | System prompt | Response generator, waiter voice |
| `chat_rewriter.md` | System prompt | Response generator, conversational voice |
| `order_worker.json` | Few-shot, 11 pairs | Order agent |
| `search_worker.json` | Few-shot, 11 pairs | Search agent |
| `rewriter.json` | Few-shot, 12 examples | Rewriter |
| `utterances.json` | Few-shot | The rollback router only |

Every node that calls the model has its own system prompt defining its role, reasoning protocol,
output format, and constraints. The router has none, because it is the trained classifier and
calls no model; the prompt serving that stage belongs to the rewriter, the fallback call for a
compound utterance, which is told to split the sentence into single-intent Vietnamese fragments
and to resolve references such as "phần này" against the preceding turns. The order worker prompt
defines cart rules, Vietnamese quantity patterns ("2 phần", "1 dĩa"), and modifier handling ("ít
cay", "thêm hành"). The search worker prompt carries the rewriting instructions and the
delegation triggers. The response node uses two prompts, one for the waiter persona when
paraphrasing search results and one for open-ended conversation.

All system prompts are written in Vietnamese, because prompting the model in Vietnamese produces
more natural Vietnamese output than prompting in English and requesting Vietnamese output.

The few-shot sets are static lists of utterance-to-action pairs injected into prompts at runtime.
The twelve rewriter examples each pair a compound Vietnamese utterance with the fragments it
should be split into, along with a short line of reasoning; they cover single-intent utterances
that must pass through untouched, compound sentences such as "Cho 2 Ốc Hương rồi tính tiền
luôn," and cases where a fragment makes sense only once a reference like "phần này" has been
resolved from the previous turn. The order worker examples cover single-item and multi-item
additions, modifiers and quantities, removals, clearing, confirmation, and delegation. The search
worker examples cover keyword search, attribute-based search such as "món chay," price-based
search, recommendation requests, and delegation for non-search queries. Every example was chosen
to cover a failure mode observed in zero-shot testing rather than sampled at random; each one
teaches a specific skill the model lacked.

Static prompts define behaviour; dynamic context supplies the situation the model must act on.
Conversation history is injected at three different depths, matched to what each stage needs. The
rewriter receives the last five exchanges, which is what lets it resolve a reference in one clause
against a dish named in an earlier turn. The workers receive the last three turns, including error
messages from validation retries, so the model sees its own prior failed attempt beside the
corrective feedback. The response node, on the chat path, receives the full conversation history.
The classifier reads no history at all: it sees the conversation state through its context
features instead, which is what allows it to separate "ok" at awaiting confirmation from "ok" at
idle without a model call. The order stage is injected into the worker prompts as a plain string,
and validator feedback is injected on retry behind a header marking it as mandatory corrective
information.

The order of the prompt is chosen to exploit Ollama's attention key-value caching. All static
content, the system prompt and the few-shot examples, sits at the front; all dynamic content,
conversation history and cart state and validation feedback, sits at the end. Because the static
prefix is identical across turns for a given worker, its attention keys and values are cached and
only the dynamic suffix is computed fresh. Interleaving the two, for instance injecting cart
state between few-shot examples, would invalidate the cache for every token after it.

All three language-model-calling stages share one model instance, Qwen2.5 14B Instruct served
locally by Ollama, configured differently per stage. Because the model runs on the server rather
than on the robot, the choice is not constrained by a memory ceiling. Based on the survey of
language models in Section 2.4.3 of Chapter 2, the 13 to 14 billion class was taken rather than
the smaller class that would also have followed the tool protocol, because the larger model
handles Vietnamese diacritics and compound words more accurately, and that accuracy matters most
at the response stage, where the reply is spoken to the customer. The rewriter runs at temperature
zero with output constrained to a list of fragments. The workers run at 0.1 with forced tool choice. The response node runs at 0.1 with
free-form generation, low enough that the reply stays close to the pre-verified data it is given.
A single Ollama instance pins the model in GPU memory with persistent keep-alive, so there is no
model-switching overhead between stages: the same loaded model handles the routing fallback, the
decision, and the response.

The model's Vietnamese limitations, moderate diacritic accuracy and variable compound-word
handling, are absorbed by the surrounding design rather than by the prompt. Classification does
not depend on them, because the trained classifier decides the intent without a model call.
Orthographic errors do not reach the cart, because the validator normalizes diacritics on both
sides before matching a name. What the model is left to do is extraction and paraphrasing:
deciding which structured action to take, and how to say what has already been verified.
