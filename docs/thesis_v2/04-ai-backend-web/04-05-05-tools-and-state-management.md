### 4.5.5 State Management

The agent has to carry two different things from one turn to the next, and they do not
tolerate the same treatment. One is the conversation: what the customer said and what the
robot answered. The other is the transaction: which dishes are in the cart, how many of each,
what they cost, and how far the order has got. A summarized turn of dialogue still conveys
what was said, so the conversation survives lossy compression. An itemized selection
compressed to a phrase can no longer be priced, confirmed, or billed.

General-purpose agent
frameworks keep both in the message list and manage it with a sliding window and periodic
summarization, and no evaluation separates the two or measures the effect of holding each
under a policy of its own (§2.4.6). What follows is a typed state object kept apart from the
message history, persistence keyed to the restaurant's own session, and a state machine that
governs the ordering workflow.

The agent's shared state is a typed object carrying all information that must persist across
turns and flow between nodes. Its fields divide into five categories by lifecycle, so each node
knows which it may read, which it must write, and which are cleared before the next turn.
Conversation history is the only field that grows monotonically within a session; everything else
is overwritten or reset per turn. Table 4.8 sets out the categories.

*Table 4.8. The five categories of state field, by lifecycle.*

| Category | Fields | Lifetime |
|----------|--------|----------|
| Conversation history | User messages, assistant replies, tool results | Appends for the whole session |
| Task state | Table identifier, active cart (names, quantities, unit prices, special requests), order stage, search context | Persists across turns within the session |
| Routing state | Intent queue in first-in-first-out order, classification path taken, confidence score, per-intent sub-queries | Written by the router each turn, consumed as workers drain the queue |
| Inter-node contract | Validity flag, validator feedback, retry counter, off-menu items, ambiguous items | One turn only, cleared at the end of it |
| Output | Typed response context, UI action command, order-confirmed flag, cart-touched flag | One turn only, read by the response stage and the tablet |

The two one-shot flags in the output category earn their place: they let the tablet transition its
display exactly once, which is what stops the agent from overwriting a hand-edited cart on a turn
that had nothing to do with ordering.

The state persists between turns through a SQLite-backed checkpointer that saves after every
node execution. The critical design decision ties the conversation thread identifier to the
restaurant's session identifier: a session begins when a party is seated and ends
when payment is verified. Within a visit, all turns share the same thread and the
checkpointer restores the full state before each turn. Between visits, payment closes the
session, the next seating creates a new session with a new identifier, the checkpointer sees
a fresh thread, and all state is blank. No manual cleanup is needed; the session lifecycle
naturally partitions conversation memory.

Six tools cover the agent's action space across three architectural categories, shown
in Table 4.9. Three in-memory cart tools operate with no network calls or external
dependencies and recompute prices from the authoritative menu data, never from the
language model. Two orchestrator API tools bridge the agent to the persistent
restaurant ledger. The search tool wraps the hybrid retrieval pipeline (§4.6). A seventh
callable, the delegate escape hatch, is absent from the table because it touches no state and
never runs; it belongs to the workers rather than to the action space, and is described with
them in §4.5.3.

Settling the bill is not among them. The agent asks for payment and states the amount, and
the settlement itself is recorded through the management panel, which closes the session and
frees the table. Nothing a customer says can mark their own bill as paid.

*Table 4.9. The agent's six tools, what each touches, and whether its effect outlives the
session.*

| Tool | Category | Effect | Permanent |
|------|----------|--------|-----------|
| Search | Retrieval | Reads the menu index and returns ranked dishes | No, read-only |
| Add to cart | In-memory | Adds items, merging quantities for a dish already present | No |
| Remove from cart | In-memory | Removes a line, or reduces its quantity | No |
| Clear cart | In-memory | Empties the cart | No |
| Confirm order | Backend | Writes the order to the ledger and returns its identifier | Yes |
| Request payment | Backend | Totals the session and returns the amount and QR code | Yes |

The ordering workflow is governed by a finite state machine over four stages, illustrated in
Figure 4.7: `IDLE`, `DRAFTING`, `AWAITING_CONFIRMATION`, and `CONFIRMED`. One node computes the
stage from the outcome of the turn, so no worker can write it directly.

![Figure 4.7. Cart and Order Stage Machine](../images/cart_state_machine.svg)

*Figure 4.7. Cart and Order Stage Machine: the stages a cart passes through and the event that
causes each transition. The dashed edge is the one the validator refuses: a confirmation is
accepted from awaiting confirmation and from nowhere else, and that edge is the only way into
the confirmed stage, so the property that the customer saw the cart before being billed
belongs to the graph rather than to a prompt. (drawn by the group)*

A cart starts idle, with nothing in it. Two kinds of event put items there, and they do not land
in the same stage. When the customer orders by voice, the turn that adds the item also reads the
cart back, so the cart moves straight to awaiting confirmation: there is no moment at which
items sit in the cart unseen. When the customer edits the cart by hand on the tablet, the
synchronised draft enters the graph as `DRAFTING` instead, because the system has not yet read
the updated cart back to the guest. A chat turn, or a cart operation that failed, also settles at
`DRAFTING`, which is what separates a silent cart from one the system has just echoed. A search or
a payment question does not: with the cart already awaiting confirmation, the stage is left where
it is, since the guest has seen the cart and only asked something in between. Without that rule a
guest who checks a price between ordering and confirming would find the confirmation refused.

From either stage the cart can grow or shrink. A successful addition or removal always re-reads
the cart, so it arrives at awaiting confirmation whichever stage it started from, and clearing
the cart empties it back to idle. Only an explicit confirmation moves the cart to confirmed and
sends the order to the kitchen, and that transition starts at awaiting confirmation and nowhere
else: the validator refuses `confirm_order` from any other stage, so a cart sitting in drafting
cannot reach the kitchen until it has been read back to the guest. The critical rule is that no
modification proceeds silently to confirmation. In the confirmed state the cart is emptied,
payment proceeds, and a new addition opens a fresh cycle.

Two further protections guard the destructive transitions. Both are enforced by the validator
and are described with the rest of its rules in §4.5.4: a first `clear_cart` on a non-empty
cart is refused pending confirmation, and a `confirm_order` sharing a turn with any cart change
is stripped and re-queued, so the guest always sees the final cart before confirming it.

The tablet and the agent keep a bidirectional cart synchronisation. When the agent mutates the
cart, it sets a per-turn `cart_touched` flag, and the tablet reads the flag to mirror the
change into its own cart UI. When the guest edits the cart by hand on the tablet, the tablet
pushes the full draft to the agent, which overwrites the checkpoint. The two converge on last
writer wins, so a quantity changed by hand is not silently undone by the next voice turn.

The `order_confirmed` flag serves the same one-shot purpose for the confirmation step: it is set on
the turn `confirm_order` succeeds and lets the tablet move its draft items into the ordered list
exactly once, since `order_stage` alone cannot tell "just confirmed" from "still CONFIRMED from
an earlier cycle."
