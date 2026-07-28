## 4.5.4 Deterministic Validator

The validator addresses the gap identified in §2.4.5: no autonomous, deterministic,
post-generation validator that inspects every tool call argument and blocks invalid calls has
been demonstrated. The survey found that existing approaches all operate at generation time.
Constrained decoding enforces schema syntax but performs no semantic check: "Cơm Tấm" is
valid JSON but not a valid dish. RAG grounding reduces the probability of error by injecting
authoritative data into the prompt, but provides no detection mechanism for the errors that
still occur. Human-in-the-loop eliminates all errors at the cost of full autonomy. The
validator presented here is a pure-rules layer positioned after the language model proposes
an action but before that action executes, inspecting every argument against the authoritative
menu and current conversation state.

A language model's output is probabilistic regardless of temperature. It can hallucinate a
dish name that does not exist on the menu, produce a nonsensical quantity, or attempt to
confirm an order with invalid items. The validator cannot prevent the language model from
hallucinating, but it can detect hallucinated output before it reaches the cart, the kitchen,
or the payment system. This architecture, in which the language model proposes, the validator
inspects, and tools execute only if approved, is the central safety invariant of the system.
Figure 4.5 shows the validator's control flow.

![Figure 4.5. Validator Control Flow](../images/validator_flow.svg)

*Figure 4.5. Validator Control Flow: a proposed tool call enters, its arguments are checked
against the menu and the current state, and it either reaches the tool node or returns to the
worker as corrective feedback. The name resolution invoked by the cart tools is expanded in
Figure 4.6. Three consecutive failures trip the circuit breaker. (drawn by the group)*

The core validation logic is menu name resolution: determining whether each item name the
language model produced actually exists on the restaurant's menu, whose 234 entries each carry
a distinct dish name, many of them sharing a leading word across a family of variants.
Figure 4.6 illustrates the resolution cascade, ordered from the most reliable form of evidence
to the least.

![Figure 4.6. Menu Name Resolution Cascade](../images/name_resolution.svg)

*Figure 4.6. Menu Name Resolution Cascade: resolution of a customer-spoken dish name, applied
to each item requested by a cart tool. A name that matches one menu entry is accepted, a name
that matches several produces a clarifying question rather than a guess, and a name that
matches none is reported as unavailable with the nearest suggestion. (drawn by the group)*

Resolution begins with diacritic-insensitive normalisation: both sides are lowercased,
stripped of Vietnamese diacritics through Unicode decomposition, the letter đ folded to d,
and whitespace collapsed. "Oc Huong Xot Trung Muoi" and "Ốc Hương Xốt Trứng Muối" become
the same string before any matching is attempted.

Two matching stages then run on the normalised forms. First, exact comparison: if the
input equals a menu name, resolution stops and the item is accepted. Second, partial
matching: menu names beginning with the input are collected first, since a prefix is the
most intuitive abbreviation; only if none begin with the input does the validator fall back
to names containing it anywhere. The number of surviving candidates determines the outcome:
exactly one is accepted as an unambiguous match, several are reported as ambiguous, and
none means the item is not on the menu. Nothing further is attempted to force a name into
the cart; token similarity plays no part in the decision and is used only afterwards, to
suggest an alternative for a name already ruled off-menu.

Generic names that match multiple menu items are flagged as ambiguous, never auto-resolved:
a dish family like "Ốc Hương" appears in eleven sauce variants, and choosing one for the
customer would be incorrect. The system instead asks the customer which variant they want.

Items that resolve to nothing are captured as off-menu, each carrying a suggested
alternative. The suggestion is the best-scoring menu name by Jaccard token similarity, offered
only if the score reaches 0.3. Below that floor, no suggestion is made; an apology is more
useful than a barely related dish. Because similarity scoring runs after the item has been
ruled off-menu, it can never put a dish in the cart. The validator never auto-corrects or
substitutes; it only flags and suggests, and the customer decides whether to accept.

Vietnamese customers frequently append special requests directly to dish names: "Lẩu Thái,
ít cay," "Ốc Hương Xốt Trứng Muối, thêm hành," "Cơm Chiên (không hành)." The validator
extracts these modifiers by matching common delimiters (parentheses, commas, dashes) in
priority order. If a pattern matches, the modifier text is stripped, the cleaned name is
re-resolved against the menu, and, if valid, the modifier is stored in the item's special
requests field. "Lẩu Thái, ít cay" is stored as the dish "Lẩu Thái" with the modifier
"ít cay", separating the customer's preference from the dish name.

Beyond menu validation, the validator enforces three state consistency rules. First,
simultaneous add-and-confirm is rejected: if the model emits both an add-to-cart and a
confirm-order call in the same turn, the confirm-order call is stripped, because the
cart state machine requires the customer to explicitly confirm after seeing the updated
cart. Second, additive-turn detection restores the existing cart when the utterance
contains markers like "thêm" or "nữa" and the model accidentally produced a replacement
rather than an addition; if a destructive marker ("bỏ," "xóa," "đổi") is also present,
restoration is suppressed. Third, cart deduplication strips items the model re-added
from context that the customer did not mention in the current utterance.

Each tool type receives specific additional validations, listed in Table 4.9. For confirming
an order, the validator requires that the cart is non-empty and that the order stage is
awaiting confirmation; an order cannot be confirmed before the cart has been drafted and echoed
to the customer. For clearing the cart, the validator rejects the operation if the cart is
already empty. For payment and confirmation tools, the validator automatically injects the
table identifier into the tool call arguments; these tools call the backend orchestrator, which
requires the table identifier, but the language model operates on session-scoped state and
does not know the identifier.

*Table 4.9. What the validator checks before each tool, and what happens when a check fails.*

| Tool | Checks applied | On failure |
|------|----------------|------------|
| Add to cart | Every item name resolves against the menu; quantity is greater than zero | The item is dropped and recorded as off-menu or ambiguous |
| Remove from cart | The name resolves against the cart in three stages: exact, substring, then menu resolution plus cart lookup; if no quantity is specified or the quantity exceeds the cart count, the entire item is removed; otherwise only the specified quantity is subtracted | Rejected with feedback, worker retries |
| Clear cart | The cart is not already empty | Rejected with feedback, worker retries |
| Confirm order | Stage is awaiting confirmation; cart is non-empty; the item list is replaced with the server-side cart | Rejected with feedback, worker retries |
| Request payment, verify payment | The table identifier is injected from session state | Rejected with feedback, worker retries |

When the validator finds errors, it constructs per-tool feedback in Vietnamese naming the
exact problem and the nearest valid suggestion. The feedback is appended to the conversation
history so the worker, on retry, sees its own failed attempt alongside the corrective
instructions. A loop counter tracks retry attempts; at three consecutive failures, the
circuit breaker routes to the state outcome, which produces a spoken apology. The customer
always hears a reply, even after repeated language model failures.

The validator's effectiveness is evaluated in §5.4.2.
