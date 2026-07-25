## 4.5.4 Deterministic Validator

The validator addresses the gap identified in §2.4.5: no autonomous, deterministic,
post-generation validator that inspects every tool call argument and blocks invalid calls
has been demonstrated. The survey found that existing approaches all operate at generation
time — constrained decoding enforces schema syntax but performs no semantic check, RAG
grounding reduces error probability but provides no detection mechanism for the errors that
remain, and human-in-the-loop eliminates errors at the cost of full autonomy. The validator
presented here is a pure-rules layer positioned after the language model proposes an action
but before that action executes, inspecting every argument against the authoritative menu
and current conversation state.

A language model's output is probabilistic regardless of temperature. It can hallucinate a
dish name that does not exist on the menu, produce a nonsensical quantity, or attempt to
confirm an order with invalid items. The validator cannot prevent the language model from
hallucinating, but it can detect hallucinated output before it reaches the cart, the
kitchen, or the payment system. This architecture — language model proposes, validator
inspects, tools execute only if approved — is the central safety invariant of the system.

### 4.5.4.1 Menu Name Resolution

The core validation logic is menu name resolution: determining whether each item name the
language model produced actually exists on the restaurant's 217-item menu. Figure 5b
illustrates the five-level cascade, ordered from fastest and most reliable to slowest and
least reliable.

Level one performs exact string comparison against all 217 dish names. This catches the
common case — the validator-normalized output usually matches a menu item directly — and
costs virtually nothing. Level two performs diacritic-insensitive matching via Unicode
decomposition: the diacritics are stripped from both strings and the resulting ASCII forms
are compared. This catches the common Vietnamese typing pattern where customers and language
models omit diacritics — "Oc Huong Xot Trung Muoi" matches "Ốc Hương Xốt Trứng Muối." Level
three checks whether any menu item starts with the input string — a prefix match that catches
cases where the customer or language model uses a shortened name like "Ốc Hương" to refer
to "Ốc Hương Xốt Trứng Muối." Level four performs substring matching, finding the
input anywhere within a menu item name. Level five, the Jaccard fallback, tokenizes both
strings and computes token-level Jaccard similarity with a threshold of 0.3 — catching
cases where the input is close but not identical, such as "Lau Thai Hai San" matching
"Lẩu Thái Hải Sản."

Each level is tried in sequence. The first match stops the cascade and returns the resolved
name along with a match kind — exact, single unambiguous match, ambiguous, or none. This
priority ordering means the fast, reliable levels handle the majority of cases, and the
slower fallback activates only for genuinely difficult inputs.

### 4.5.4.2 Ambiguity and Off-Menu Handling

Generic names that match multiple menu items are flagged as ambiguous, never auto-resolved.
This is a critical Vietnamese restaurant-specific challenge: a dish family like "Ốc Hương"
(sea snails) appears in eleven sauce variants on the menu — trứng muối, me, tỏi, bơ, rang
muối, and others. When a customer says "Cho 1 Ốc Hương," the prefix match resolves to all
variants, none uniquely. The validator flags this ambiguity, and the response node asks for
clarification: "Dạ, Ốc Hương có nhiều loại sốt: trứng muối, me, tỏi, bơ... anh/chị muốn
loại nào ạ?" Choosing a specific variant for the customer would be incorrect and frustrating
if the wrong sauce arrives — the system forces the customer to disambiguate.

Items that fail all five resolution levels are captured as off-menu, each carrying the raw
language-model-produced name and, where possible, the nearest valid menu item found through
the same token Jaccard fallback. The validator never auto-corrects or substitutes. It only
flags and suggests. The decision to accept the suggestion or choose something else remains
with the customer. This design principle — flag but do not substitute — prevents the system
from ordering the wrong dish on the customer's behalf.

### 4.5.4.3 Modifier Stripping

Vietnamese customers frequently append special requests directly to dish names: "Lẩu Thái,
ít cay," "Ốc Hương Xốt Trứng Muối — thêm hành," "Cơm Chiên (không hành)." The validator
extracts these modifiers by matching common delimiters — parentheses, commas, and dashes —
in priority order. If a pattern matches, the modifier text is extracted, the cleaned name
is re-resolved against the menu, and — if the cleaned name resolves to a valid item — the
modifier is stored in the item's special requests field rather than the name. This means
"Lẩu Thái, ít cay" is stored as the dish "Lẩu Thái" with the modifier "ít cay" — the
kitchen sees the correct dish with the customer's preference separated from the name.

### 4.5.4.4 State Consistency Checks

Beyond menu validation, the validator enforces three state consistency rules.

Simultaneous add-and-confirm is rejected. If the language model emits both an add-to-cart
and a confirm-order tool call in the same turn, the confirm-order call is stripped and
an error is added to the feedback. The cart state machine requires the customer to explicitly
confirm after seeing the updated cart. A simultaneous add-and-confirm would send items to
the kitchen that the customer never saw.

Additive-turn detection prevents a statelessness problem. Language models are stateless per
call — they receive the prompt, produce a response, and have no memory of prior turns. If
the customer says "thêm 1 Bia Sài Gòn" and the prompt accidentally omits the existing cart
contents, the language model might produce an add-to-cart call that overwrites a cart
previously containing three items. The validator detects additive markers in the utterance
— "thêm," "nữa," "lấy thêm," "gọi thêm," "cho thêm" — and, if the proposed cart does not
include the existing items, automatically restores them. The existing items are prepended
to the new items, ensuring the cart accumulates rather than replaces.

Cart deduplication prevents the language model from re-adding the entire cart from context.
If the cart contains Ốc Hương and Lẩu Thái and the customer says "thêm 1 Bia," the language
model might re-add all existing items plus the new one. The validator checks each item in the
proposed tool call against the current cart and strips items already present that the
customer did not mention in the current utterance.

For removal operations, the validator resolves the raw item name against the current cart
contents. If the language model says "bỏ Ốc Hương" but the cart contains "Ốc Hương Xốt Trứng
Muối," a prefix match resolves the vague name to the full cart entry. If the name cannot be
matched to any cart item, an error is returned.

### 4.5.4.5 Per-Tool Validation

Each tool type receives specific additional validations. For confirming an order, the
validator requires that the cart is non-empty and that the order stage is awaiting
confirmation — an order cannot be confirmed before the cart has been drafted and echoed
to the customer. For clearing the cart, the validator rejects the operation if the cart
is already empty. For payment and confirmation tools, the validator automatically injects
the table identifier into the tool call arguments — these tools call the backend
orchestrator, which requires the table identifier, but the language model operates on
session-scoped state and does not know the identifier.

### 4.5.4.6 Retry and Circuit Breaker

Figure 5a shows the validator's control flow. When the validator finds errors, it
constructs per-tool error messages with formatted feedback in Vietnamese — naming the
exact problem, the affected item, and the nearest valid suggestion where applicable. These
error messages are appended to the conversation history. When the worker is invoked for
retry, it sees its own prior failed tool call followed by the validator's error feedback
as the full failure context.

The loop counter is incremented with each failed validation. At three failed attempts,
the circuit breaker engages: the validator returns a rejection flag with the counter at
the threshold, but the routing function sends the utterance to the state outcome instead
of returning to the worker. The state outcome builds a retry response context with an
apology, and the response node verbalizes it: "Dạ, em xin lỗi anh/chị, em xử lý thông
tin bị lỗi. Anh/chị kiểm tra lại giúp em nhé ạ."

The system always produces a response — even after repeated language model failures, the
customer hears an apology rather than silence.

### 4.5.4.7 Design Principles

The validator is deterministic — every check is a hand-written predicate with a definitive
yes-or-no answer, with no machine learning and no randomness. It rejects but does not
substitute — off-menu items are flagged with suggestions, never auto-corrected, and
ambiguous items ask for clarification. It acts as a firewall — positioned after the
language model proposes but before tools execute, ensuring that failed tool calls never
reach the execution layer. Its execution is bounded — the circuit breaker at three retries
guarantees termination regardless of language model behavior. Its feedback is specific —
error messages name the exact problem and the affected item, enabling the language model
to fix its output on retry without re-reasoning from scratch. Its false positive rate on
the known menu is zero at the first four resolution levels; only the Jaccard fallback at
level five involves a similarity threshold that could produce a false match, and it is
gated conservatively at 0.3.

The validator's effectiveness is quantified in §5.3.2: across adversarial out-of-menu
scenarios, the validator caught all off-menu items, and zero invalid items reached the
order confirmation stage.
