"""Expand retrieval eval expected_relevant lists using menu.json group fields.

When a dish name in expected_relevant matches a menu item's group field,
all sibling dishes in that group are added as also-relevant.  This prevents
FAISS from being penalised for returning semantically correct variant names
that were not in the original narrow expected list.

Usage:
    PYTHONPATH=. uv run python evals/scripts/expand_retrieval_eval.py
    PYTHONPATH=. uv run python evals/scripts/expand_retrieval_eval.py --dry-run
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

MENU_PATH = PROJECT_ROOT / "assets" / "data" / "menu.json"
EVAL_PATH = PROJECT_ROOT / "evals" / "data" / "retrieval" / "retrieval_eval.json"
OUT_PATH = PROJECT_ROOT / "evals" / "data" / "retrieval" / "retrieval_eval.json"


def load_menu():
    with open(MENU_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_group_index(menu):
    """Build a dict mapping group name -> list of dish names in that group."""
    idx = {}
    for item in menu:
        group = item.get("group")
        name = item["name"]
        if group:
            idx.setdefault(group, set()).add(name)
        # Also index dish names themselves as singletons
        idx.setdefault(name, set()).add(name)
    return idx


def main():
    dry_run = "--dry-run" in sys.argv

    menu = load_menu()
    group_idx = build_group_index(menu)
    print(f"Loaded {len(menu)} dishes, {len(group_idx)} groups/dishes indexed")

    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        eval_data = json.load(f)

    changes = []
    for case in eval_data["cases"]:
        case_id = case["id"]
        original = set(case["expected_relevant"])
        expanded = set(original)

        for name in original:
            if name in group_idx:
                siblings = group_idx[name]
                added = siblings - original
                if added:
                    expanded.update(siblings)
                    changes.append({
                        "case": case_id,
                        "query": case["query"],
                        "name": name,
                        "added": sorted(added),
                    })

        case["expected_relevant"] = sorted(expanded)

    if not changes:
        print("\nNo changes needed — all expected lists already include full groups.")
        return

    print(f"\n{len(changes)} expansions across {len(set(c['case'] for c in changes))} cases:\n")
    for c in changes:
        print(f"  [{c['case']}] '{c['query']}'")
        print(f"    '{c['name']}' -> +{len(c['added'])} siblings: {c['added']}\n")

    if dry_run:
        print("DRY RUN — no changes written.")
        return

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)
    print(f"Written to {OUT_PATH}")


if __name__ == "__main__":
    main()
