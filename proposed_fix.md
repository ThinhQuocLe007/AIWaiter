# Appendix G Fixes — Scrambled descriptions

## Background

The conversation transcripts themselves are correct and consistent with the
results in Section 5.4.5. The problems are in the prose descriptions above each
transcript:

1. **G.4 description is a copy-paste of G.3.** G.4's transcript is about cart
   mutation (removing, replacing, adding items), but the description talks about
   multi-intent decomposition with "rồi".

2. **G.6 description is wrong.** It says "The adversarial conversation. The
   customer orders two dishes that are not on the menu..." but G.6's transcript
   is a normal full sitting (best sellers, browsing, changing beer, checking
   cart). The "adversarial" text describes G.7.

3. **G.7 analysis text is placed before G.7.** The paragraph at line 63 about
   "Phở Bò Tái and Cơm Tấm Sườn" belongs after the G.7 transcript, not between
   G.6 and G.7.

4. **Line 7 is truncated.** The sentence ends mid-thought — "so no run inherits
   the previous one's cart" — missing a period and possibly the end of the
   sentence.

---

## Fix 1 — G.4: Rewrite description to match cart mutation transcript

The current G.4 description (lines 37–39) is an exact duplicate of G.3. The
transcript shows the customer ordering, then changing their mind — removing
Mực Cháy Tỏi and adding Cháo Hàu instead, then adding another dish later.
Replace with:

```
**G.4 Changing Your Mind Mid-Order (QS-004)**

The cart is mutated across three turns. The customer first places two items,
then removes one and replaces it, then adds a third before confirming. The
remove_cart and add_cart calls in the same turn are validated against
different references (remove against the cart, add against the menu), and the
cart total is recomputed from the authoritative menu prices after each
mutation. The confirm_order call carries the final three-item cart, and the
billed total matches exactly.
```

---

## Fix 2 — G.6: Rewrite description to match full sitting transcript

The current G.6 description (line 57) incorrectly says "The adversarial
conversation." The transcript is a seven-turn normal dining scenario.
Replace with:

```
**G.6 A Full Sitting (QS-006)**

A seven-turn conversation following a group of first-time customers. The
conversation spans browsing best sellers, ordering, asking for more
recommendations, checking the cart, substituting one beer for another, and
asking about a dish's spiciness. Throughout, the cart is mutated four times
while the order stage stays at AWAITING_CONFIRMATION, and the search context
accumulates across turns so later recommendations do not repeat earlier ones.
The request_payment call on turn 6 correctly returns an error (no confirmed
order yet), demonstrating that the workflow constraint holds.
```

---

## Fix 3 — G.7: Move analysis paragraph below transcript + rewrite description

The current G.7 heading (line 65) has no description text — only the
transcript table. The paragraph that describes the adversarial behavior
appears at line 63, between G.6 and G.7. Move it below the G.7 transcript,
and add a short description above the G.7 transcript.

**G.7 heading + new description** — replace the current G.7 heading-only with:

```
**G.7 Dishes That Do Not Exist (QS-007)**

The adversarial path. The customer orders two dishes this seafood restaurant
does not serve alongside one that is on the menu. The validator rejects the
off-menu items on the first turn, the correct dish is added to the cart, and
the turn reaches DRAFTING. On the second turn, the customer says "mấy món kia
bỏ" — referring to dishes that were refused a turn earlier and were therefore
never in the cart. Forced tool calling obliges the worker to propose removing
them; the gate resolves the remove_cart argument against the cart rather than
the menu, refuses both calls, and the duplicate add_cart is absorbed rather
than doubling the line. A turn carrying three wrong tool calls leaves the cart
unchanged.
```

**G.7 analysis paragraph (move from line 63 to after G.7 transcript):**

Keep the existing text:

```
Phở Bò Tái and Cơm Tấm Sườn are plausible Vietnamese dishes this seafood
restaurant does not serve. On turn 2 the model proposes removing them even
though they were refused a turn earlier and were therefore never in the cart.
The gate resolves a remove_cart argument against the cart rather than the
menu, refuses both calls and reports what the cart actually holds, and the
worker then abstains with delegate instead of attempting a third variation.
The cart stays correct throughout and the order confirms with the one valid
dish.
```

(This paragraph stays as-is; it is factually correct and well-written. Only
its position needs to move from before the G.7 heading to after the G.7
transcript.)

---

## Fix 4 — Line 7: Complete the truncated sentence

The current line 7 reads:

> `The pass rate over those five runs is 82.9 % [71.4 %–100 %]; the
>  transcripts below are one of them, the run in which all seven scenarios
>  passed their assertions. The runner derives a run-unique thread identifier
>  and clears both the checkpoint store and the transactional tables before
>  starting, so no run inherits the previous one's cart`

The sentence is cut off at "cart" with no period. Complete it:

```
find:    so no run inherits the previous one's cart

replace: so no run inherits the previous one's cart or session state.
```

---

## Summary

| # | Location | Change |
|---|----------|--------|
| 1 | Appendix G.4 description | Rewrite: copy-paste from G.3 → cart mutation description |
| 2 | Appendix G.6 description | Rewrite: "adversarial" → full sitting description |
| 3a | Appendix G.7 heading | Add description above transcript (moved from line 63) |
| 3b | Appendix G.7 analysis | Move paragraph about Phở Bò Tái/Cơm Tấm Sườn from before G.7 heading to after G.7 transcript |
| 4 | Appendix G, line 7 | Add period + "or session state" to truncated sentence |

All seven conversation transcripts themselves are correct — the tool calls,
cart totals, stage transitions, and validator/gate behaviour match the expected
system behaviour described in Sections 4.5 and 5.4.5.
