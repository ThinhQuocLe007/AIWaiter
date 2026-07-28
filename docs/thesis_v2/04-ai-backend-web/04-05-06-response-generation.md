## 4.5.6 Response Generation

The final stage converts the executed action's result into spoken Vietnamese. Every
utterance follows a guaranteed path: the state outcome always produces a typed response
context, and the response node always produces a spoken reply. The customer always hears
something, regardless of whether the turn succeeded, failed validation, or triggered the
circuit breaker.

The response architecture is shaped by the same consideration that shaped the workers. Because
the joint accuracy of function calling and Vietnamese phrasing is unmeasured in the literature
(§2.4.3), the design does not ask the model for more language than the outcome requires. The
approach is therefore hybrid: pre-written Vietnamese templates for formula-
driven outputs where speed, correctness, and consistency are paramount; language model
generation only for variable-content situations where the structured data the model receives
has already passed through the validator, eliminating the risk of hallucinated dish names,
prices, or quantities reaching the customer.

The response context, built by the state outcome or by the chat worker, is a discriminated union
of five subtypes, one for each kind of outcome a turn can reach. Each carries only data that has
already been verified, which is what makes the model safe to call on it. Table 4.12 sets out the
five.

*Table 4.12. The five response contexts, and what each carries into the reply stage.*

| Context | Built by | Carries | Produced when |
|---------|----------|---------|---------------|
| Order | State outcome | Cart, total, off-menu items, ambiguous items, stage, order identifier | A cart tool ran |
| Search | State outcome | Query, ranked results, dishes already shown in earlier turns | The search tool ran |
| Payment | State outcome | Amount, QR code address, table identifier, status | A payment tool ran |
| Chat | Chat agent | Utterance, cart, stage, history, up to five remembered dishes, delegate reason | No tool ran this turn |
| Retry | State outcome | Name of the failed tool, validator feedback | The circuit breaker tripped |

Template responses are pre-written Vietnamese strings assembled with string formatting, used
for deterministic outcomes where the content is formula-driven and the phrasing should be
predictable across every occurrence: order confirmation, cart echoing, ambiguity
clarification, off-menu rejection, removal and clearing acknowledgments, payment prompts,
greetings, thanks, and the circuit breaker apology. Templates are fast (microseconds, no
inference), correct (prices and quantities are computed, not hallucinated), consistent, and
written in natural Vietnamese by a native speaker rather than translated from English.

Two situations require language model generation because the content is too variable for
templates. Search results must be listed conversationally: the model receives the ranked
dish list with names, prices, and categories and paraphrases it into natural Vietnamese.
Free-form chat responses are grounded in the conversation history, the cart, and the
curated memory of previously discussed dishes. Every other outcome is assembled from a
template, because the dish names and prices come from the menu data and there is nothing
for the model to add beyond phrasing. The model receives only pre-verified structured data
and never invents content; it decides how to say what has already been verified.

Within each context type, an ordered set of conditions selects the path. Table 4.13 lists them
in the order they are tested; the first match produces the reply. Reading down the table shows
how narrow the model's role is: of the twenty outcomes a turn can reach, seventeen are
assembled from templates, and the model is called only for a search that returned dishes and
for open conversation. This hybrid approach, templates for deterministic outputs and the
language model for variable content, maximizes speed and correctness while maintaining
conversational flexibility where it is needed.

*Table 4.13. How a reply is chosen. Conditions are tested top to bottom within each context,
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
| | Verification succeeded | Template: confirm the bill is settled |
| Chat | Delegated to review the cart | Template: echo the cart, or say it is empty |
| | Delegated as unclear | Template: ask the customer to repeat |
| | Greeting or thanks | Template: standard courtesy reply |
| | Dishes held in memory | **Model**, generated whole, checked, then spoken sentence by sentence |
| | Otherwise | **Model**, streamed token by token |
| Retry | Always | Template: apologise, quoting the validator's feedback |

The response generator supports sentence-by-sentence streaming, but not every path streams
in the same way. Open conversation is streamed token by token and split into sentences
at Vietnamese punctuation boundaries. A reply that names dishes cannot be treated that
way: grounding can only be judged on the finished text, and a sentence already spoken
cannot be recalled. Those replies are therefore generated in full, checked against the
dishes actually retrieved, and only then emitted sentence by sentence. Template responses
are emitted as a single event.
