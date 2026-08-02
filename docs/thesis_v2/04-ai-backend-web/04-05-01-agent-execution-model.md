## 4.5 Conversational Agent

The voice pipeline delivers transcribed Vietnamese text to the server. From there the system
must work out what the customer wants, choose an action, make sure that action is safe to
take, carry it out, and say something back. This section presents the conversational agent
that does that work.

### 4.5.1 Agent Architecture

The agent is a graph of ten nodes through which one customer sentence passes in five stages:
classify the intent, decide the action, validate it, execute it, and respond. Every node reads
and writes one shared state object and then hands control forward; no node calls another
directly. The idea the whole graph is arranged around is that the decisions the system depends
on are made in ordinary code, and the language model is asked only to propose which action
fits an utterance and to phrase what has already been decided. Figure 4.3 shows the topology,
and Table 4.2 names the nodes in the order an utterance meets them.

![Figure 4.3. Agent StateGraph Topology](../images/agent_graph.svg)

*Figure 4.3. Agent StateGraph Topology: an utterance enters at the router and is dispatched to
one of four workers. Every proposal from the three tool-calling workers passes through the
validator before the tool node runs it; the chat agent holds no tools and bypasses both. The
state updater merges results and returns the turn to the next worker while intents remain, the
state outcome finalizes the turn, and the response generator produces the spoken reply.
(drawn by the group)*

*Table 4.2. The nodes of the agent graph, in the order an utterance meets them.*

| Node | Stage | Kind | Responsibility |
|------|-------|------|----------------|
| Classifier router | Classify | Trained MLP, with LLM rewriter | Embeds the utterance and classifies it into one of four intents; calls the rewriter to split compound utterances |
| Order agent | Decide | LLM | Selects a cart operation and extracts item names, quantities, and special requests |
| Search agent | Decide | LLM | Rewrites the conversational request into concrete search terms and dispatches retrieval |
| Payment dispatch | Decide | Deterministic | Emits a request-payment call; no decision is left once the router has classified PAYMENT |
| Chat agent | Decide | Deterministic | Assembles conversation history, cart, and remembered dishes into a typed context for the response stage |
| Validator | Validate | Deterministic | Inspects every tool call argument against the menu and the current state; resolves dish names, flags ambiguity, rejects off-menu items |
| Tool node | Execute | Deterministic | Runs the approved tool calls: cart operations, search, or payment |
| State updater | Execute | Deterministic | Merges tool results into the state; pops the processed intent from the queue |
| State outcome | Respond | Deterministic | Builds a typed response context from the executed action; clears per-turn fields |
| Response generator | Respond | Templates and LLM | Converts the typed context into spoken Vietnamese, by template or by paraphrase |

A customer saying "Cho tôi 2 Ốc Hương" crosses all five stages. The classifier router labels
the sentence an ordering intent in about nine milliseconds, without calling the language model.
The order agent, which holds the cart tools and nothing else, proposes one call: add to cart,
name "Ốc Hương", quantity two. That name is only the string the customer said, because the
agent never receives the menu. The validator looks it up, finds that it identifies no single
dish, and refuses the call, so nothing enters the cart and the tool node does not run.

The turn still reaches the response generator, which asks the customer which dish they meant. When the
next turn names it in full, the call passes, the cart tool runs, and the price is read from the
menu file rather than produced by the model.

Three properties of that path belong to the graph rather than to any node in it. The first is
that the validator sits on every edge between a worker and the tool node, so no proposed call
reaches execution without being inspected, and it is the shape of the graph rather than an
instruction in a prompt that makes this true.

The second is that a turn carrying more than one
intent is served one worker at a time, in the order the customer spoke them: the state updater
pops the intent it has just finished and sends the turn back for the next one, so an order
followed by a request for the bill adds the items before the total is computed. The third is
that every path ends at the response generator, whether the turn succeeded, was refused, or
exhausted its retries, so the customer always hears a reply.

Of the ten nodes, six are ordinary Python, two call the language model, and two combine the
two. Routing, validation, cart arithmetic, state transitions, and per-turn cleanup are all code
whose behaviour can be read from the source and repeated. The language model is one component
inside a mostly deterministic machine, not the machine itself.

The subsections that follow take the five stages in the order an utterance meets them:
classification, action selection, validation, execution, and response.
