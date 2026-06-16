# Collaborator Task — Eval Dataset Bias Audit

> **Goal**: Audit all 3 eval datasets for author bias, add adversarial cases that expose weaknesses, re-run all 3 scripts, and report what the system actually fails at.
>
> **The 66.67% → 100% jump on e2e part1 across identical back-to-back runs was LLM model variance (temperature > 0), not code changes.** You need adversarial cases that produce *stable* failures.

---

## 1. Datasets to Audit

| File | What it tests | Cases | Expected accuracy (last report) |
|---|---|---|---|
| `evals/data/router/router_eval.json` | Hybrid router → correct intent | 80 | **90.00%** (72/80) |
| `evals/data/retrieval/retrieval_eval.json` | RAG (BM25 + FAISS) → relevant dishes | 25 | **RRF 88% hit rate**, Weighted 64% |
| `evals/data/e2e/e2e_conversations_part1.json` | Full graph pipeline, short | 6 scenarios | **100%** (part1 only, model variance inflated) |
| `evals/data/e2e/e2e_conversations_part2.json` | Full graph pipeline, long | 5 scenarios | **63.64%** (combined 11 scenarios) |

**Reference past reports** (read only):
- `evals/results/router_eval_report_20260610.md`
- `evals/results/retrieval_eval_report_20260611.md`
- `evals/results/e2e_eval_report_20260611_11scenarios.md`

---

## 2. Bias Hypotheses Per Dataset

### Router — 8 known failures + add adversarial cases

| ID | Hypothesis | How to test |
|---|---|---|
| H1 | No standalone ORDER requests (all reference prior context) | Add `"Cho tôi đặt 1 Phở Bò"` as first utterance |
| H2 | COMPLEX only tests SEARCH+ORDER, missing PAYMENT+SEARCH, CHAT+ORDER | Add `"Cho xem menu rồi tính tiền luôn"` |
| H3 | No Vietnamese teencode, dialect, or code-switching | Add `"oke chốt đơn dùm tui"`, `"xog chưa?"`, `"check bill gium m` |
| H4 | Cases written backwards (note telegraphs label) | Reverse-engineer: cover note with hand, guess label |

Add **at least 5 new cases**. Update `total_cases` and `cases_per_route` in header.

### Retrieval — 25 cases, 3 chronic misses

| ID | Hypothesis | How to test |
|---|---|---|
| H5 | All queries are 1–3 words. Real queries are longer. | Add `"có món gì cho người ăn chay ít ngọt không?"` |
| H6 | `expected_relevant` matches exact menu names. Real users misspell. | Add `"phở bò tái"` (menu has `"Phở Bò Đặc Biệt"`) |
| H7 | Easy/medium are well-known categories. Hard cases model already fails. | Add concept queries the model should handle but might not |
| H8 | No multi-criteria (price + diet + category) | Add `"món chay dưới 100k cho 2 người"` |

Add **10–15 new cases**. Update `total_cases` and `difficulty_distribution`.

### E2E — 4 failed scenarios out of 11

Bias hypotheses from the current dataset:

| ID | Hypothesis | How to test |
|---|---|---|
| H9 | All scenarios end with "xác nhận". Real users say "ok", "ừ", "đặt đi". | Create teencode confirm scenario |
| H10 | Cart always starts empty. No "confirm empty cart" or "cart has items from before" | Create scenario where cart has pre-existing items |
| H11 | Assertions too loose — wrong args still pass | Create scenario with wrong item in sync_cart args |
| H12 | All users cooperative. No undo / mid-conversation change. | Create scenario with undo ("bỏ món đó đi") |

Add **3–4 new scenarios** to `e2e_conversations_part2.json`. Update `total_scenarios`.

---

## 3. How Each Eval Script Works

### `eval_router.py`
- Reads `router_eval.json` (80 labeled cases with `input` + `expected_route`)
- For each case: calls `hybrid_router_node(state)`, compares predicted intent to expected
- Outputs: accuracy per route, latency, SLM vs semantic split
- **Run**: `python evals/scripts/eval_router.py`

### `eval_retrieval.py`
- Reads `retrieval_eval.json` (25 queries with `expected_relevant` + `expected_irrelevant`)
- Runs query through BM25+FAISS with RRF and Weighted fusion modes
- Computes Precision@3, Recall@3, MRR, Hit Rate
- **Run**: `python evals/scripts/eval_retrieval.py`

### `eval_e2e.py`
- Reads scenarios from JSON files in `evals/data/e2e/`
- Each scenario = multi-turn conversation with per-turn `assert` blocks
- Runs each turn through `app.stream()`, checks tool calls + response text + state
- **Run**: 
  ```bash
  # Default (part1 only)
  python evals/scripts/eval_e2e.py

  # Both parts
  python evals/scripts/eval_e2e.py --datasets e2e_conversations_part1.json e2e_conversations_part2.json

  # Part2 only (new scenarios)
  python evals/scripts/eval_e2e.py --datasets e2e_conversations_part2.json
  ```

---

## 4. Example — Adding an E2E Scenario

Add to `e2e_conversations_part2.json` under `"scenarios"`:

```json
{
  "id": "E2E-012",
  "name": "teencode_short_confirm",
  "description": "Bias-target: khách dùng teencode ('oke', 'xog'), không nói 'xác nhận' rõ ràng.",
  "table_id": "T_eval_11",
  "difficulty": "hard",
  "expected_outcome": "order_placed",
  "turns": [
    {
      "turn": 1,
      "role": "user",
      "content": "1 ly Trà Đào Cam Sả",
      "assert": {
        "tool_called": "sync_cart",
        "tool_output_contains": "Đã cập nhật"
      }
    },
    {
      "turn": 2,
      "role": "user",
      "content": "xog chốt đơn đi oke",
      "assert": {
        "tool_called": "confirm_order",
        "response_contains": "đơn hàng"
      }
    }
  ]
}
```

Then update `"total_scenarios"` from `5` to `6`.

---

## 5. What to Do

1. **Audit** — read all 3 datasets. Which biases from H1–H12 do you confirm?
2. **Add cases** — modify each dataset file:
   - `router_eval.json`: +5 cases, update `total_cases` + `cases_per_route`
   - `retrieval_eval.json`: +10–15 cases, update `total_cases` + `difficulty_distribution`
   - `e2e_conversations_part2.json`: +3–4 scenarios, update `total_scenarios`
3. **Run all 3 evals**:
   ```bash
   python evals/scripts/eval_router.py
   python evals/scripts/eval_retrieval.py
   python evals/scripts/eval_e2e.py --datasets e2e_conversations_part1.json e2e_conversations_part2.json
   ```
4. **Analyze** — compare against the past reports. Where did accuracy drop? That's where the real bias was.

---

## 6. What to Report Back

Write `evals/results/bias_audit_report_<date>.md` with:
1. **Hypotheses confirmed/refuted** per dataset (H1–H12)
2. **New cases added** — table with IDs, bias target, difficult
3. **Before/after metrics** — old vs new accuracy per dataset
4. **Failure analysis** — top 3 most revealing new failures with root cause
5. **Recommendation** — which adversarial cases should stay permanently

---

## 7. Out of Scope

- The eval scripts themselves — only modify the **datasets**
- Model code (`agent/`, `services/`, `perception/`, `output/`)
- Past eval results — read but don't overwrite
