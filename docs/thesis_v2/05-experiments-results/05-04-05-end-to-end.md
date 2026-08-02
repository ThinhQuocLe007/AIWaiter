### 5.4.5 End-to-End System Evaluation

Objective 6 requires the system to complete full ordering scenarios, from a customer request through a
confirmed order to the kitchen display, across conversations containing ambiguous dish names, off-menu
items and changes of mind, with the session lifecycle enforced and the cart consistent throughout.
Component-level accuracy establishes none of this: a router that classifies correctly, a validator that
blocks hallucinations and a retriever that finds the right dishes can still combine into a system that
fails to complete an order.

Seven conversations spanning thirty turns were authored and all seven are reported. The experiment meets
the N = 5 protocol of §5.2.2, and unlike the deterministic experiments its outcome varies between runs:
the per-run pass rate is 82.9 % [71.4 %–100 %], with one run in five passing every scenario. Full
transcripts are in Appendix G.

<!-- PENDING-14B: run through the worker and response language models. Re-run
     eval_qualitative.py --runs 5 and refresh Appendix G. The findings below are stated as mechanisms
     rather than as turn numbers so that a re-run does not invalidate the prose. -->

**Table 5.12.** The seven conversations, the claim each exercises, and the outcome. (`eval_qualitative.py`)

| Conversation | What it exercises | Outcome | Transcript |
|---|---|---|---|
| Ordering, confirming, paying | The baseline path, with colloquial phrasings for closing an order | complete; billed total equals cart total | G.1 |
| Referring back to a search result | Resolving "món đó" against the previous turn's search | varies between runs; completes when the reference resolves | G.2 |
| Two intents in one utterance | Boundary-marker detection and rewriter decomposition | complete; fragments execute in the order spoken | G.3 |
| Changing your mind mid-order | A substitution and an incremental addition inside one cart | complete; totals recomputed after each mutation | G.4 |
| An ambiguous dish name | A prefix matching eleven menu variants | complete; the validator blocks and the agent asks rather than guessing | G.5 |
| A full sitting | State integrity across twelve turns, four cart mutations, two substitutions | complete; two turns answer a question the customer did not ask | G.6 |
| Dishes that do not exist | Off-menu rejection, then a referring expression with no antecedent | cart stays correct; one turn short of a confirmed order | G.7 |

Four findings follow, each stated as a property of the architecture rather than of one transcript,
because the turn at which a behaviour appears is not stable across runs even when the outcome is.

**Decomposition happens before classification.** A boundary marker triggers the rewriter, which splits the
utterance into single-intent fragments that the classifier then labels independently. This is the central
claim of the routing design in operation: a classifier trained only on single-intent utterances handles
multi-intent speech because decomposition precedes classification rather than sitting inside it. Fragments
execute in the order spoken, so an utterance asking for payment before confirming attempts payment first,
and the agent answers truthfully that no order exists rather than inventing a total or silently reordering
the request.

**The deterministic layer holds across a long sitting.** In G.6 the order stage holds at
AWAITING_CONFIRMATION from turn 3 to turn 11 while the cart is mutated four times and five non-ordering
turns pass between them. Both substitutions execute correctly and the confirmed order carries exactly the
items the group settled on, with neither removed dish in it. Cart arithmetic is performed in Python
throughout, recomputed from the menu price map after each mutation, which is why the running totals are
correct at every step rather than approximately correct and why the final bill equals the sum of the
confirmed lines. That the stage survives the intervening search and payment turns is what allows turn 11
to confirm at all, and the rule producing that is described with the cart state machine in §4.5.5.

Two of those intervening turns still fall short of what the customer asked. Both ask for the running
total, both route to PAYMENT, and the payment tool finds no confirmed order and errors, so the reply
states that the session holds no order. No wrong figure is produced, but the answer the customer wanted
was sitting in cart state: the four-class scheme has no label separating a request for the running total
from a request to be billed.

**Two deterministic checks contain an unresolvable reference.** G.7 exercises the validation layer twice
against two different references. Its first turn is menu validation: the model proposes three dishes, two
of which this seafood restaurant does not serve, and the gate resolves each against the menu, rejects two
and allows one, naming both rejected dishes in the reply. Its second turn is the harder case. "Mấy món
kia bỏ" has no resolvable antecedent, because those dishes were refused a turn earlier and were never in
the cart, yet forced tool calling obliges the worker to propose removing them. The gate resolves a
`remove_cart` argument against the cart rather than the menu and refuses both calls, and the duplicate
`add_cart` in the same turn is absorbed rather than doubling the line, so a turn carrying three wrong tool
calls leaves the cart unchanged. The guarantee is therefore not scoped to menu membership: the gate checks
a tool's arguments against whichever reference that tool acts on.

The cost is that those refusals leave the stage at DRAFTING, so the confirmation on the next turn is
correctly refused and the conversation ends one turn short of a confirmed order. The scenario's assertions
treat that as a pass because no incorrect state was written, which is a limitation of the assertion set:
they check that nothing wrong happens, not that the ordering path completes.

**What the layer does not protect is the reply.** Each tool that runs produces its own response context
and the response node joins them, so a turn that removes one dish and adds another reads the cart back
twice, and a turn whose arguments are refused apologises once per refusal. The state is right and the
wording is poor, which is the same boundary §5.4.3 measures: the deterministic layer governs what is
done, not what is said.

The one scenario whose outcome varies is G.2, and the variance is instructive. A search returns two
dishes whose names differ by three syllables, and the customer then says "món đó". Which one is meant is
a judgement no deterministic layer makes, so the worker either picks one and the conversation completes,
or asks which was meant and the following confirmation meets an empty cart. Neither path writes anything
incorrect; the difference is whether the order gets placed.

**Objective 6 is partially met:** every scenario completes in the best of five runs and five of seven in
the worst, including both conversations built to break the system. In all seven the gate, the name
resolver, the cart arithmetic and the state machine behave correctly, no incorrect item reached a cart or
a ledger in any run, and every conversation reaching payment bills exactly what the cart contained. What
varies is whether the language model's judgement carries a conversation to completion, and what falls
short is the wording of the reply rather than the state behind it.
