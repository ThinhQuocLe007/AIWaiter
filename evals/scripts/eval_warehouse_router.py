"""Evaluate the LIVE warehouse intent router end-to-end.

Unlike the dead `evals/scripts/eval_router.py` (which imported a non-existent restaurant
`hybrid_router_node`), this script exercises the router that is actually wired into the brain:
`src.agent_brain.warehouse.nodes.mlp_router_node.route()`.

It reports:
  * end-to-end accuracy over `evals/data/router/warehouse_eval.json` (all 6 intents, including
    rule-resolved control/motion and LLM-escalated plan),
  * a confusion matrix,
  * the per-example misroutes,
  * a separate MLP-only report (`classify()`) on the rows the rule layer would forward to the
    model, so you can see the trained classifier's quality in isolation.

Run: `uv run python evals/scripts/eval_warehouse_router.py`
(requires the router to be trained first: `make train-router`)
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from sklearn.metrics import classification_report, confusion_matrix

from src.agent_brain.warehouse.nodes.mlp_router_node import route
from src.agent_brain.warehouse.types import Intent

EVAL_JSON = Path(__file__).resolve().parent.parent / "data" / "router" / "warehouse_eval.json"

# Intents the rule layer resolves before the MLP ever sees the text.
RULE_INTENTS = {Intent.CONTROL, Intent.MOTION, Intent.PLAN}


def _load() -> list[dict]:
    return json.loads(EVAL_JSON.read_text(encoding="utf-8"))


def main() -> None:
    rows = _load()
    y_true, y_pred = [], []
    mlp_true, mlp_pred = [], []  # only rows the MLP actually classifies
    misroutes: list[tuple[str, str, str, float, bool]] = []

    for r in rows:
        text = r["text"]
        expected = r["intent"]
        intent, conf, escalate = route(text)
        predicted = Intent.PLAN.value if escalate else intent.value
        y_true.append(expected)
        y_pred.append(predicted)
        if predicted != expected:
            misroutes.append((text, expected, predicted, round(conf, 3), escalate))
        # MLP-only view: the rule layer forwards control/motion/plan away, so exclude them
        if intent not in RULE_INTENTS and not escalate:
            mlp_true.append(expected)
            mlp_pred.append(intent.value)

    labels = sorted({*y_true, *y_pred})
    print("=== End-to-end router accuracy (route) ===")
    print(classification_report(y_true, y_pred, labels=labels, zero_division=0))
    print("confusion rows=true, cols=pred:", labels)
    print(confusion_matrix(y_true, y_pred, labels=labels))
    print(f"overall accuracy: {sum(t == p for t, p in zip(y_true, y_pred))}/{len(y_true)}")

    if mlp_true:
        mlp_labels = sorted(set(mlp_true) | set(mlp_pred))
        print("\n=== MLP-only accuracy (classify, rule-resolved rows excluded) ===")
        print(classification_report(mlp_true, mlp_pred, labels=mlp_labels, zero_division=0))

    if misroutes:
        print("\n=== Misroutes ===")
        for text, exp, pred, conf, esc in misroutes:
            tag = "escalated->plan" if esc else f"conf={conf}"
            print(f"  [{exp} -> {pred} | {tag}] {text}")
    else:
        print("\nNo misroutes.")


if __name__ == "__main__":
    main()
