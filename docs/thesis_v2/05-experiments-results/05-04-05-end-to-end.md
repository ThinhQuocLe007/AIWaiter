### 5.4.5 End-to-End System Evaluation

Objective 6 requires the system to complete full ordering scenarios, from a customer request through a
confirmed order to the kitchen display, across conversations containing ambiguous dish names, off-menu
items and changes of mind, with the session lifecycle enforced and the cart consistent throughout.
Component-level accuracy establishes none of this: a router that classifies correctly, a validator that
blocks hallucinations and a retriever that finds the right dishes can still combine into a system that
fails to complete an order.

Seven conversations were authored and six reported, the seventh being a modification scenario subsumed by
the twelve-turn sitting. This section reports conversations rather than a pass rate, because a pass rate
over six scenarios would carry an interval too wide to support any claim. Unlike the other language-model
experiments here, this one meets the N = 5 protocol of §5.2.2: the six conversations were run five times
and every run produced the same per-scenario outcome. Full transcripts are in Appendix G.

<!-- PENDING-14B: run through the worker and response language models. Re-run
     eval_qualitative.py --runs 5 and refresh Appendix G. The findings below are stated as mechanisms
     rather than as turn numbers so that a re-run does not invalidate the prose. -->

**Table 5.10.** The six conversations, the claim each exercises, and the outcome. (`eval_qualitative.py`)

| Conversation | What it exercises | Outcome | Transcript |
|---|---|---|---|
| Ordering, confirming, paying | The baseline path, with colloquial phrasings for closing an order | complete; billed total equals cart total | G.1 |
| Referring back to a search result | Resolving "món đó" against the previous turn's search | complete; the full dish name reaches `add_cart` | G.2 |
| An ambiguous dish name | A prefix matching eleven menu variants | complete; the validator blocks and the agent asks rather than guessing | G.3 |
| Two intents in one utterance | Boundary-marker detection and rewriter decomposition | complete; fragments execute in the order spoken | G.4 |
| A full sitting | State integrity across twelve turns, four cart mutations, two substitutions | two turns short of complete | G.5 |
| Dishes that do not exist | Off-menu rejection, then a referring expression with no antecedent | complete; the cart survives both | G.6 |

Three findings follow, each stated as a property of the architecture rather than of one transcript,
because the turn at which a behaviour appears is not stable across runs even when the outcome is.

**Decomposition happens before classification.** A boundary marker triggers the rewriter, which splits the
utterance into single-intent fragments that the classifier then labels independently. This is the central
claim of the routing design in operation: a classifier trained only on single-intent utterances handles
multi-intent speech because decomposition precedes classification rather than sitting inside it. Fragments
execute in the order spoken, so an utterance asking for payment before confirming attempts payment first,
and the agent answers truthfully that no order exists rather than inventing a total or silently reordering
the request.

**The deterministic layer holds across a long sitting.** In G.5 the order stage stays at
AWAITING_CONFIRMATION while the cart is mutated four times, then advances on confirmation. Both
substitutions execute correctly and the confirmed order carries exactly the items the group settled on,
with neither removed dish in it. Cart arithmetic is performed in Python throughout, recomputed from the
menu price map after each mutation, which is why the running totals are correct at every step rather than
approximately correct and why the final bill equals the sum of the confirmed lines.

Two turns fall short, and neither is a failure of that layer. Asked whether a dish is spicy, the retriever
returns the right dish carrying the relevant taste attribute and the rewriter, presented with several
dishes whose names share a substring, answers about a different one; this reproduced in every run, so it
is a stable model-capability limit rather than sampling variance. Asked what the cart comes to so far, the
turn routes to PAYMENT, which queries the order ledger, finds no confirmed order and says so. No wrong
figure is produced, but the answer the customer wanted was sitting in cart state: the four-class scheme
has no label separating a request for the running total from a request to be billed.

**Two deterministic checks contain an unresolvable reference.** G.6 exercises the validation layer twice
against two different references. Its first turn is menu validation: the model proposes three dishes, two
of which this seafood restaurant does not serve, and the gate resolves each against the menu, rejects two
and allows one, naming both rejected dishes in the reply. Its second turn is the harder case. "Mấy món
kia bỏ" has no resolvable antecedent, because those dishes were refused a turn earlier and were never in
the cart, yet forced tool calling obliges the worker to propose removing them. The gate resolves a
`remove_cart` argument against the cart rather than the menu, finds neither dish, refuses both calls and
returns what the cart holds; the worker then calls `delegate` rather than inventing a third attempt. The
guarantee is therefore not scoped to menu membership: the gate checks a tool's arguments against whichever
reference that tool acts on, and that plus the escape hatch is what keeps a turn the model got wrong from
reaching state.

What the layer does not protect is the reply. Each refused argument produces its own error message and the
response node joins them, so the customer hears an apology repeated once per refusal. The state is right
and the wording is poor, which is the same boundary §5.4.3 measures: the deterministic layer governs what
is done, not what is said.

**Objective 6 is partially met:** five of six conversations complete correctly end to end, including both
built to break the system, with identical outcomes across five runs. In all six the gate, the name
resolver, the cart arithmetic and the state machine behave correctly, and every conversation reaching
payment bills exactly what the cart contained. What falls short is the language model's judgement in two
situations, both contained rather than propagated.
