### 4.5.6 Response Generation

The final stage converts the result of the turn into spoken Vietnamese. Its input is not the raw
output of a tool but a typed response context, built by the state outcome or the chat worker and
carrying only values that have already been checked. Table 4.10 sets out the five subtypes, one
per kind of outcome a turn can reach.

*Table 4.10. The five response contexts, and what each carries into the reply stage.*

| Context | Built by | Carries | Produced when |
|---------|----------|---------|---------------|
| Order | State outcome | Cart, total, off-menu items, ambiguous items, stage, order identifier | A cart tool ran |
| Search | State outcome | Query, ranked results, dishes already shown in earlier turns | The search tool ran |
| Payment | State outcome | Amount, QR code address, table identifier, status | A payment tool ran |
| Chat | Chat agent | Utterance, cart, stage, history, up to five remembered dishes, delegate reason | No tool ran this turn |
| Retry | State outcome | Name of the failed tool, validator feedback | The circuit breaker tripped |

Most outcomes are formula-driven: a cart read back with its total, an order sent to the kitchen,
a dish reported as unavailable. These use pre-written Vietnamese templates filled with values
computed in Python, so the phrasing is identical on every occurrence and the numbers are
arithmetic rather than generation. Templates cost microseconds, need no inference, and were
written by a native speaker rather than translated from English.

Two kinds of content cannot be written in advance. A search that returned dishes has to become
something a waiter would say, selected and ordered against what the customer asked rather than
read out rank by rank. Open conversation has to follow whatever was actually said. Both go to the
model, and it receives more than a list of names: each dish carries its price, taste profile,
tags, and category, and on the conversational path the cart with its computed total, the order
stage, and the dishes discussed in earlier turns. All of it is read from the menu data, so the
model decides which dishes to raise and how to describe them, never what they are or what they
cost.

Within each context type an ordered set of conditions selects the path, listed in Table 4.11.
Of the nineteen paths a turn can reach, sixteen are assembled from templates and three call the
model: a search with results, and the two conversational paths, one with remembered dishes and
one without.

*Table 4.11. How a reply is chosen. Conditions are tested top to bottom within each context,
and the first one that matches wins.*

| Context | Condition | Reply |
|---------|-----------|-------|
| Order | Ambiguous items present | Template: ask which variant |
| | Off-menu item with a nearest match | Template: name it as unavailable, offer the match |
| | Off-menu item with no match | Template: plain rejection |
| | Tool reported an error | Template: convey the error |
| | Confirm order succeeded | Template: the order has gone to the kitchen |
| | Remove succeeded | Template: acknowledge, then echo the cart |
| | Clear succeeded | Template: acknowledge |
| | Otherwise, add succeeded | Template: echo the cart with prices and total |
| Search | Tool reported an error | Template: nothing suitable found |
| | No results | Template: not on the menu, offer to suggest something |
| | Results returned | **Model**, generated whole, checked against the retrieved dishes, then spoken sentence by sentence |
| Payment | Request without an amount, or an error | Template: apologise |
| | Request succeeded | Template: state the total, show the QR code |
| Chat | Delegated to review the cart | Template: echo the cart, or say it is empty |
| | Delegated as unclear | Template: ask the customer to repeat |
| | Greeting or thanks | Template: standard courtesy reply |
| | Dishes held in memory | **Model**, generated whole, checked, then spoken sentence by sentence |
| | Otherwise | **Model**, streamed token by token |

The three model paths pass a grounding check before anything is spoken. Given the retrieved
dishes and told to name only those, the model still invents plausible neighbours: "Ốc Luộc" and
"Ốc Hương nướng mỡ hành" both appeared during development on a menu carrying neither. Detecting
an invented name directly is not possible, since it matches nothing that could be compared
against the menu, and a Vietnamese reply is full of bare food words such as "món ốc" that any
pattern broad enough to catch would also catch in a correct sentence.

The check is therefore positive rather than negative. A reply that recommends dishes must name at
least one of the dishes actually retrieved, matched as whole words after normalising diacritics
on both sides. A reply naming none is discarded and replaced by a deterministic listing of the
real results with their prices. A reply given no dishes to check against, such as an answer to a
general question, passes untouched.

This catches the reply that has left the retrieved set altogether, where the customer would order
a dish the kitchen cannot cook and the tablet would show no card for it. It does not catch an
invented name standing beside a genuine one, since one real dish satisfies the test. That
residual case is the one place where model output reaches the customer without a deterministic
check, and Section 5.6.2 of Chapter 5 reports it as such.

Streaming differs by path. Open conversation is streamed token by token and split into sentences
at Vietnamese punctuation. Replies that name dishes cannot be: grounding can only be judged on
the finished text, and a spoken sentence cannot be recalled, so they are generated in full,
checked, and only then emitted sentence by sentence. Template responses are emitted as a single
event.
