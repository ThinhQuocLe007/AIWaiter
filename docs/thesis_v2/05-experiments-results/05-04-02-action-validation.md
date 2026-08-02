### 5.4.2 Action Validation and Safety

Objective 3 requires that no item absent from the menu reach the customer's cart. It fails on either side:
a dish the kitchen cannot cook reaching the cart, or a gate strict enough to refuse valid orders, since a
validator that rejects everything satisfies the first half perfectly. The validator of §4.5.4 is the
component that lets a language model drive restaurant operations without being trusted to generate correct
arguments: the model proposes tool calls, and deterministic Python checks every argument before any tool
executes.

The gate resolves against two different references depending on the tool. An `add_cart` argument is
resolved against the menu, since the question is whether the kitchen can cook the dish. A `remove_cart`
argument is resolved against the current cart, since the question is whether the customer has that dish to
remove; when it does not resolve, the gate refuses the call and names what the cart actually holds. §5.4.5
shows that second check containing an unresolvable referring expression.

#### Name Resolution, Suggestion and Ambiguity

Resolution normalises both sides and compares for an exact match, a prefix, then a substring, rejecting a
name that matches nothing. Suggestion runs only after resolution has rejected a name, scoring token
overlap by Jaccard similarity, and cannot admit an item to the cart. Ambiguity detection handles the case
where a name is valid but underspecified. All three are deterministic Python over the menu file, so the
figures are exact fractions.

**Table 5.6.** Name resolution, suggestion and ambiguity detection by stage.
(`eval_name_resolution.py`, `eval_ambiguity.py`)

| Mechanism | Stage | Correct / Total |
|---|---|:---:|
| Resolution | Valid names matched (exact, diacritic-insensitive, prefix, substring) | 45 / 45 |
| Resolution | Misspelled names correctly rejected | 16 / 16 |
| Suggestion | Offered at Jaccard ≥ 0.3 | 5 / 5 |
| Suggestion | Withheld below Jaccard 0.3 | 4 / 4 |
| Ambiguity | Ambiguous prefix flagged for clarification | 15 / 15 |
| Ambiguity | Unambiguous full name resolved directly | 10 / 10 |

The rejection rows carry the result, not the matched ones. All 16 misspellings are rejected rather than
force-matched to a plausible neighbour, and the 4 names too unlike any dish receive no suggestion rather
than a barely related one. Neither mechanism guesses. The ambiguity rows test the same discipline on valid
input: "Ốc Hương" is a prefix of eleven sauce variants on the reference menu, and the validator flags
every such name for clarification instead of silently resolving to one of them, at no cost to the
unambiguous names. Appendix G.5 shows a live turn and the clarification the customer hears.

#### What the Gate Is Worth

The validator node was replaced by a pass-through and 41 scenarios run through both configurations.
Leakage is measured by resolving each item name in `add_cart` and `confirm_order` calls against the menu
file directly rather than by reading the validator's own validity flag, because the ablated arm has no
validator to set that flag and a measurement based on it would report zero by construction.

<!-- PENDING-14B: both arms run the worker language model. Re-run eval_validator_ablation.py. -->

**Table 5.7.** Validator ablation (n = 41 scenarios per arm). (`eval_validator_ablation.py`)

| Condition | Scenario pass rate | Off-menu items reaching cart tools | Bad `confirm_order` calls |
|---|:---:|:---:|:---:|
| Validator ON | 92.7 % | **0** | 0 |
| Validator OFF | 95.1 % | **32** | **7** |

The 32 leaked names originate in fourteen distinct scenarios. In a deployed restaurant they would be
dishes the kitchen cannot cook appearing on a customer's bill.

The pass rate is not where the validator shows up. It is no better with the gate than without it, and on
this run marginally worse. The turn-level assertions check tool selection
and conversational flow, which the validator does not affect; what it changes is the content of the
arguments, which is what the leakage columns measure and the pass rate does not. The validator is a
guarantee, not a correction the system visibly depends on to complete tasks.

#### Robustness and the Delegate Escape Hatch

<!-- PENDING-14B: single runs through the worker language model. Re-run eval_out_of_menu.py and
     eval_delegate.py. -->

Two further runs test the gate from the outside. Thirty adversarial scenarios across seven categories,
non-existent dishes, near-miss variants, mixed orders with one invalid item, hallucination bait quoting an
invented combo at a specific price, teencode, missing diacritics, and a negative control of entirely valid
items, all pass: 30 of 30, with no off-menu item admitted and no valid item wrongly refused.

The second run tests the escape hatch. Workers run under `tool_choice="any"`, so the model must emit a
tool call on every turn, and without an escape a worker receiving an utterance none of its tools fit would
be forced to invent one. Across 90 turns the `delegate` tool fired 3 times, all three correct abstentions
handed to the chat worker, and no worker produced a wrong tool call that the mechanism was needed to
prevent and failed to prevent. The zero is the important figure rather than the rate, which should be read
against a test set containing deliberate out-of-domain utterances.

**Objective 3 is met:** no off-menu item reached a cart tool in any validated run, against 32 with the
validator bypassed, and the gate achieved that without refusing valid work, since the negative control
passed, all 15 ambiguous names were flagged rather than resolved silently, and none of the 16 misspellings
was force-matched.
