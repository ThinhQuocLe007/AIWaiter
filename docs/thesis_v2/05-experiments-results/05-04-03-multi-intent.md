### 5.4.3 Multi-Intent Execution and Verbalisation

No numbered objective covers this property. It is reported because the experiments identified it as the
system's weakest point. Executing every intent in a turn is necessary but not sufficient: if the agent
adds two dishes and requests the bill but tells the customer about only one of the three actions, the
state is correct and the customer's understanding of it is not. Execution and verbalisation are therefore
counted separately over 25 multi-intent turns with per-intent lexical evidence, run five times because the
response layer is stochastic.

<!-- PENDING-14B: every row but the router row depends on the response language model.
     Re-run eval_multi_intent.py --runs 5. -->

**Table 5.8.** Multi-intent execution and verbalisation (25 turns, mean over 5 runs, observed range in
brackets). An intent counts as verbalised when the customer learns its fate, success or correct refusal
alike. (`eval_multi_intent.py --runs 5`)

| Measure | Result |
|---|---|
| Verbalisation rate | 0.725 [0.667–0.767] |
| Turns fully verbalised | **0.576** [0.520–0.640] |
| Coverage of what the customer asked for | 0.747 [0.700–0.780] |
| Turns where the router queued every expected intent | 0.600 (identical in all 5 runs) |

The router figure is identical across all five runs, as expected for a deterministic classifier, so every
point of variance in this table originates in the language model rather than in routing.

The scoring rule matters more than most effects in this chapter. A stricter rule counting only successful
outcomes drops the full verbalisation figure to 0.456, but it is the wrong rule: case MI-011 executes both
intents and answers both, the payment half with "hiện chưa có đơn hàng nào trong phiên này ạ", which
contains none of that intent's evidence terms and so scores as never verbalised despite the customer
having been told exactly what happened.

Across the five runs, 53 turns carry at least one executed but unspoken intent, and they are not evenly
distributed. Twenty-six occur when ORDER and SEARCH share a turn, where the search result is lost, and
fifteen when ORDER and PAYMENT share one, where the order acknowledgement is lost. A further seven are
router misroutes on single-intent turns and so are not response-layer failures at all. Roughly three
quarters of the loss therefore falls on two specific intent pairings rather than on a general tendency to
drop intents, which makes it a diagnosable defect.

The cause is not a failure to aggregate. The outcome node returns every tool message produced since the
last customer utterance and builds one response context per tool, and the response node joins all of the
resulting replies; scenario QS-003 in §5.4.5 shows a two-intent turn verbalising both halves. The loss
occurs earlier, in that certain pairings do not produce the second context at all.

**This property is not met**, and §5.6.1 records it as such. The system tells the customer the complete
story on 57.6 % of multi-intent turns and conveys 74.7 % of what was asked. What makes the result usable
rather than merely disappointing is its shape, a specific pairing defect located upstream of the response
layer, with roughly a seventh of it belonging to the router rather than to verbalisation at all.
