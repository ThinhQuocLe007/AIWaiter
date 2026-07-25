## 4.5.3 Tool-Calling Workers

The workers select Qwen2.5 7B as the reasoning engine from the three categories of
Vietnamese-capable LLMs surveyed in §2.4.3. The survey found that Vietnamese-specific models
provide excellent language quality but no function calling, commercial API models offer the
best quality but are cloud-dependent, and open-weight multilingual models provide function
calling and local deployment — but the three properties of function calling, Vietnamese
quality, and context window capacity had never been evaluated jointly for a task-oriented
dialogue system. Qwen2.5 7B was selected as the smallest model capable of reliable Vietnamese
tool calling within a 16-thousand-token context window, served locally by Ollama to eliminate
cloud dependency.

Each worker receives the customer's utterance, the current conversation state, and a set of
bound tools, and must produce either a tool call specifying the action to take or a delegation
indicating that the utterance falls outside its domain. The four workers form a symmetric
design: every intent has exactly one worker, and every worker knows how to handle its domain.

### 4.5.3.1 Worker Taxonomy

| Worker | Intent(s) | Bound Tools | LLM Called? | Temperature |
|--------|-----------|-------------|-------------|-------------|
| Order worker | ORDER, ORDER\_CONFIRM | add\_cart, remove\_cart, clear\_cart, confirm\_order, delegate | Yes | 0.1 |
| Search worker | SEARCH | search, delegate | Yes | 0.1 |
| Payment dispatch | PAYMENT | request\_payment | No (deterministic) | N/A |
| Chat worker | CHAT | (none) | No (pure function) | N/A |

### 4.5.3.2 Shared LLM Worker Design

The two LLM-based workers — order and search — share an identical architectural pattern,
differing only in their bound tools, system prompts, and few-shot examples.

Tool choice is forced: the model is configured to always produce exactly one tool call per
invocation. This eliminates the failure mode where the LLM produces a text response instead
of a tool call — for example, saying "Dạ, em sẽ thêm món đó vào giỏ hàng" without actually
calling the add-to-cart tool. With forced tool choice, a tool call is guaranteed in every
response.

The temperature is set to 0.1 rather than zero. A temperature of zero would reject all
variant phrasings of Vietnamese tool arguments — "ít cay" versus "it cay" for "less spicy"
— making the system brittle to informal spelling. The slightly-above-zero setting allows
minor orthographic variation while keeping tool selection near-deterministic.

The menu is deliberately excluded from the worker prompts. The language model does not need
to know the full 217-item menu to decide which tool to call. When a customer says "Cho 2 Ốc
Hương Xốt Trứng Muối," the LLM only needs to recognize this as an ordering action and
extract the raw item name — the validator (§4.5.4) resolves the name against the actual menu.
Excluding the menu keeps the prompt context compact, reduces latency, and eliminates the
risk of the LLM hallucinating menu items it believes it has seen in the prompt.

The prompt sequence is ordered to maximize Ollama's prefix caching. System prompts and
few-shot examples — which are identical across all turns for the same worker — are placed at
the beginning of the sequence. Dynamic content such as cart state, validation feedback, and
conversation history is appended at the end. Ollama caches the attention key-value pairs for
the static prefix, so only the dynamic suffix requires fresh computation each turn.

### 4.5.3.3 Order Worker

The order worker handles cart CRUD operations and order confirmation. It is bound to five
tools. The add-to-cart tool adds items to the cart with the names, quantities, and special
requests extracted from the utterance. The remove-from-cart tool removes a named item. The
clear-cart tool empties the entire cart. The confirm-order tool sends the composed order to
the kitchen. The delegate tool provides an escape hatch when the utterance cannot be mapped
to any cart action.

Each tool has a structured schema defining its expected arguments. For adding items, the
LLM must extract structured information from natural Vietnamese: "Cho 2 Ốc Hương" becomes
a structured record with name "Ốc Hương" and quantity 2; "Lấy 1 phần Lẩu Thái, ít cay"
adds the special request "ít cay" as a modifier; "Thêm 1 Bia Sài Gòn và 1 Nước Suối"
produces two items in a single tool call. The LLM's job is extraction, not validation —
the validator checks every extracted name against the menu.

The order worker receives two forms of dynamic context. The current cart contents — with
quantities and prices — enable the LLM to make additive decisions, adding to an existing
cart rather than replacing it, and to avoid re-adding items already present. The validator
feedback, injected on retry, carries corrective instructions naming the exact problem and
the nearest valid menu item, enabling the LLM to fix its output without re-reasoning from
scratch.

### 4.5.3.4 Search Worker

The search worker handles menu queries, restaurant information lookups, and recommendations.
It is bound to two tools: a search tool that executes a retrieval query over the menu and
knowledge base, and a delegate tool for utterances that fall outside the search domain.

The LLM's primary job is query rewriting — translating conversational Vietnamese into
concrete search keywords. A customer might say "món gì ấm bụng cho ngày lạnh?" and the LLM
translates this into search terms like "lẩu súp nóng" that the hybrid retrieval pipeline
can match against the menu index. The rewritten query is placed in the search tool's
arguments.

The search worker injects a list of already-known items, drawn from both the current search
context — results from prior searches within the same session — and the active cart. This
prevents the LLM from re-searching topics the customer has already discussed. If the
customer asks "món đó có cay không?" and the item was returned in a prior search, the
already-known list includes it, and the LLM should delegate to the chat worker rather than
re-search.

The search worker's system prompt includes explicit instructions for what falls outside the
search domain: restaurant hours, parking availability, WiFi passwords, music requests, and
complaints. The LLM must recognize these as non-search queries and call the delegate tool
with an explanatory reason.

### 4.5.3.5 Payment Dispatch

The payment dispatch node is the simplest worker: it always emits a request-payment tool
call with the table identifier. No language model is called. The router has already
classified the intent as PAYMENT, and there is only one payment action the agent can
initiate — requesting the bill. Additional payment logic — computing the session total
from all confirmed orders, generating the payment QR code, verifying payment completion —
is handled by the backend orchestrator, not the agent. The agent's responsibility is
simply to initiate the request.

### 4.5.3.6 Chat Worker

The chat worker is a pure function that builds a typed context for the response generator.
It reads the current conversation state and assembles a structured record containing the
customer's utterance, the active cart and its total, the current order stage, the full
conversation history, up to five dishes from the most recent search converted into
structured objects with name, price, tags, and taste profile, and — if reached via
delegation — the reason the domain worker passed control to the chat path.

The chat worker is a leaf node in the graph. It connects directly to the state outcome
node. No validation occurs because there are no tool calls to validate. No language model
is called because the chat worker's responsibility is assembly, not generation —
generation is deferred to the response node, which receives the structured context and
produces the spoken reply.

### 4.5.3.7 Robustness Mechanisms

Three mechanisms prevent language model errors from corrupting system state.

The delegate escape hatch is bound alongside domain tools in both LLM-based workers.
With forced tool choice, the LLM must always produce a tool call — but some utterances
genuinely fall outside the worker's domain. If the search worker receives "mấy giờ đóng
cửa?" (what time do you close?), the correct action is not to search for a menu item
matching "đóng cửa" — there is none, and forcing a search call would return irrelevant
results that confuse the customer. The delegate tool provides a non-destructive way out:
the LLM calls it with a reason, and the routing function sends the utterance to the chat
worker for a conversational response. The principle is that the language model is never
forced to produce a wrong action; when uncertain about its domain, it admits it rather
than guessing.

The retry-with-corrective-feedback mechanism activates when the validator rejects a tool
call. The validator returns specific feedback — naming the exact problem and the nearest
valid menu item — and the routing function returns the utterance to the same worker. The
worker sees its own prior failed attempt followed by the validator's error feedback as the
full failure context, and must produce a corrected tool call on retry.

The circuit breaker guarantees bounded execution. A loop counter tracks retry attempts.
After each failed validation, the counter increments. At three failed attempts, the
circuit breaker triggers: the validator returns with the counter at the threshold, the
routing function sends the utterance directly to the state outcome instead of returning
to the worker, and the response node generates an apology. Even if the language model
repeatedly produces invalid output — due to hallucination, prompt confusion, or model
error — the graph terminates after at most three retries with a graceful fallback rather
than looping indefinitely.
