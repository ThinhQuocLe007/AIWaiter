## 4.5.5 Tool Execution and State Management

The state management architecture addresses the gap identified in §2.4.6: no prior work
characterizes a memory architecture for Vietnamese conversations combining conversation
history, persistent state, session isolation, and context window allocation. The survey
found that general-purpose agent frameworks do not natively separate conversation history
from application state — the cart, order stage, and search context that define the
customer's current position in the ordering workflow — and that dialogue state tracking
is not integrated with session-scoped persistence for restaurant use. The architecture
presented here combines a typed state object with five categories of fields organized by
lifecycle, SQLite-backed checkpointing keyed to the restaurant's session lifecycle
(§4.7.2), and a cart state machine that enforces the ordering workflow through guarded
transitions.

The agent's shared state is a typed object — not a plain dictionary — carrying all
information that must persist across turns and flow between nodes. Fields are organized into
five categories by lifecycle, ensuring each node knows which fields it can read, which it
must write, and which will be cleared before the next turn.

Conversation history accumulates user messages, assistant responses, and tool results across
turns using append semantics. This is the only field that grows monotonically within a
session; all other fields are overwritten or reset per turn. Task state persists across turns
and drives context-dependent behavior: the table identifier links the agent to the physical
table and its active session; the active cart holds the in-progress order as a structured
record with item names, quantities, unit prices, and special requests; the order stage
tracks the customer's position in the ordering workflow — idle, drafting, awaiting
confirmation, or confirmed; the search context retains results from the most recent menu
search so follow-up questions ("món đó có cay không?") can be answered without re-querying.

Routing state is populated by the router at the start of each turn and consumed as workers
process their assigned intents. The intent queue is a first-in-first-out list of intents to
process in sequence. Routing metadata records which classification path was taken, the
confidence score, and the per-intent sub-queries extracted from compound utterances for
multi-intent turns. Inter-node contract fields carry information between specific node pairs
within a single turn. The validator writes validity flags and corrective feedback that the
routing function reads to decide whether to proceed, retry, or trip the circuit breaker; a
loop counter tracks retry attempts. The validator also captures off-menu items — dish names
the model produced that do not exist on the menu, each with its nearest valid suggestion —
and ambiguous items — generic names matching multiple menu variants — for the response node
to communicate to the customer. Output fields are populated at the end of each turn and
consumed by the response node and the tablet. The typed response context carries the
structured data needed to generate the appropriate reply — order, search, payment, chat, or
retry. The UI action command tells the tablet which screen to navigate to. The order
confirmation flag and cart-touched flag signal one-shot state changes that the tablet uses
to transition its display exactly once.

The state is persisted between turns by a SQLite-backed checkpointer that saves the full
state after every node execution. The critical design decision ties the conversation thread
identifier to the restaurant's session identifier (§4.7.2): a session begins when a party
is seated and ends when payment is verified. Within a visit, all turns share the same thread
and the checkpointer restores the full state before each turn. Between visits, payment
closes the session, the next seating creates a new session — and therefore a new thread —
with a blank state. No manual cleanup is needed; the session lifecycle naturally partitions
conversation memory.

The cart is additionally synchronized bidirectionally between the agent and the tablet. When
the customer edits the cart by touch on the tablet, the tablet pushes its complete draft
into the agent's state. The cart-touched flag, set only on turns where a cart tool actually
modified the cart, prevents the agent from overwriting a hand-edited cart with a stale voice
draft on subsequent turns that do not involve ordering.

Execution proceeds in two phases once the validator approves a tool call. In the first
phase, the ToolNode executes the approved tool. In the second phase, the state updater
merges the result into the agent's state. This two-phase design — execute then update —
ensures that tool execution failures, such as network errors or database constraint
violations, leave no residue in the agent's state. Only successful tool calls modify the
state.

### 4.5.5.1 Tool Architecture

Seven tools cover the agent's action space, falling into three architectural categories.

Three in-memory cart tools operate entirely on the agent's state with no network calls,
no database writes, and no external service dependencies. The add-to-cart tool accepts a
list of items with names, quantities, and optional special requests; same-name items merge
by incrementing quantity rather than creating duplicate entries. The remove-from-cart tool
removes one item by exact name from the cart. The clear-cart tool empties all items. All
three tools recompute prices from the authoritative menu data, never from the language
model — the language model might hallucinate a price, but the cart always reflects the
restaurant's actual pricing.

Three orchestrator API tools bridge the stateless agent to the persistent restaurant
ledger. The confirm-order tool serializes the cart and sends it to the backend, which
inserts the order into the database, links it to the active session, verifies prices
against the menu, and emits a real-time event to the kitchen display. The request-payment
tool triggers the backend to compute the session total — the sum of all confirmed orders
— and generate a payment QR code. The verify-payment tool marks the session as closed and
the table as paid. The agent does not write to the database directly; it only proposes
that an action should happen, and the backend enforces the business rules.

The search tool wraps the hybrid retrieval pipeline described in §4.6. When the search
worker calls it with a rewritten query, the tool tokenizes the query for Vietnamese,
executes two parallel retrievals — BM25 for sparse lexical matching and FAISS for dense
semantic matching with the Vietnamese bi-encoder — fuses the results via Reciprocal Rank
Fusion, and applies a dual-lane relevance gate. The tool returns a list of structured
search results, each carrying the dish name, price, category, tags, and taste profile.

### 4.5.5.2 Tool Execution

The ToolNode iterates over all approved tool calls in the language model's output and
calls each tool function with the arguments the language model provided. Each tool
execution produces a result — either a success with structured data or an error with a
diagnostic message — that is appended to the conversation history. When the language
model emits multiple tool calls in a single message, such as adding two different items
in one utterance, each call executes independently and produces its own result.

### 4.5.5.3 State Merging

The state updater runs after the ToolNode and processes all tool results from the current
turn. Each tool type has a dedicated handler. For cart additions, the handler merges new
items into the existing cart additively and recalculates the total. For removals, the
handler filters the named item from the cart and recalculates. For clearing, the handler
replaces the cart with an empty one. For order confirmation, the handler advances the
order stage to confirmed and sets a per-turn flag that the tablet uses to transition its
display from cart to ordered state. For search, the handler stores the results in the
search context field so follow-up questions can be answered without re-searching. For
payment, the handler sets a UI action command that causes the customer's tablet to
navigate to the payment screen.

After processing all tool results, the state updater performs two housekeeping tasks.
It recomputes the cart total from the authoritative menu data, ensuring prices are always
sourced from the menu rather than the language model. It pops the first intent from the
intent queue. If more intents remain, the routing function dispatches the next worker;
if the queue is empty, execution proceeds to finalize the turn.

### 4.5.5.4 Cart State Machine

The ordering workflow is governed by a finite state machine with four states, illustrated
in Figure 9. The states are enforced by the state updater through guarded transitions.

In the idle state, no cart exists and no order is in progress. The only allowed action is
adding items, which transitions to the drafting state. In the drafting state, the cart is
being built; items can be added, removed, or cleared. When the cart has items and the agent
echoes the cart to the customer, the state advances to awaiting confirmation — the customer
has seen what they are about to order and must explicitly confirm. In the awaiting
confirmation state, the customer can still modify the cart — any addition or removal loops
back to drafting, and the cart is re-echoed — or can confirm, which transitions to
confirmed and sends the order to the kitchen. In the confirmed state, the order is in the
kitchen; the payment flow proceeds, and a new add-to-cart action starts a fresh drafting
cycle for a new order.

The critical rule is that any cart modification at the awaiting confirmation stage loops
back to drafting and re-echoes the cart. This prevents the language model from silently
adding items and confirming without the customer seeing the updated cart. The customer
always sees what they are about to order before the confirmation call is made.

### 4.5.5.5 Multi-Intent Iteration

The intent queue is a first-in-first-out queue processed sequentially. When the router
classifies multiple intents — for example, the utterance "Cho 2 Ốc Hương rồi tính tiền
luôn" produces the queue [ORDER, PAYMENT] — each intent is dispatched to its worker in
order, and the state updater merges the result before the next intent is processed.

Sequential execution is essential for correctness. In the example above, the ORDER worker
runs first, adding two Ốc Hương to the cart and advancing the order stage to awaiting
confirmation. The state updater pops ORDER from the queue, leaving [PAYMENT]. The payment
dispatch runs next, requesting the bill — and because ORDER has already updated the cart,
the payment total reflects the just-added items. If the two intents ran in parallel, the
payment total would miss the new items.

### 4.5.5.6 Turn Finalization

The state outcome node is the penultimate stage before response generation. It runs after
all intents have been processed and builds a typed response context from the tool execution
results. The dispatch logic handles five cases. If a response context is already set — by
the chat worker for the CHAT path — the node skips building and only performs cleanup. If
the circuit breaker triggered, the node builds a retry response context with the feedback
and failed tool name. If the last message is a tool result, the node dispatches to a
per-tool context builder that maps the structured tool output to the appropriate response
context subtype — order, search, payment, or a generic chat context for defensive fallback.

Each response context subtype carries the structured data the response node needs to
generate the appropriate reply. An order response context carries the cart contents,
total, off-menu items with suggestions, ambiguous items needing clarification, and the
order stage. A search response context carries the rewritten query and the ranked results
with metadata. A payment response context carries the amount, the QR code URL, the table
identifier, and the payment status.

The state outcome performs per-turn cleanup, resetting ephemeral fields that must not
persist to the next turn: off-menu items, ambiguous items, validator feedback, the
delegate reason, and per-intent sub-queries. This is the only place these fields are
cleared — all nodes safely assume they exist for the duration of a single turn.
