"""Scenario test: "ask info → go to Khu B → ask about Khu B WHILE moving".

Why this works headlessly: the three turns only exercise the MLP router (intent), the
RAG retriever (resolve item / section), the navigation worker (emit token) and the
*deterministic* response node — none of which need the LLM. The graph is identical to
the one `make agent` serves; we just call it directly and inspect state.

This also models the real system's key property: conversation (voice device) and motion
(robot client) are DECOUPLED. A "move to Khu B" turn dispatches a navigate task and
returns immediately; the next "tell me about Khu B" turn is a fresh /chat that the agent
handles while the robot keeps driving its already-assigned task.

Run (after `make reindex` once, so the RAG index + router weights exist):
    uv run python tests/scripts/test_move_while_talking.py
Exit 0 = scenario behaves correctly, non-zero = a check failed.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.agent_brain.warehouse.graph import build_graph
from src.agent_brain.warehouse.memory.checkpointer import get_checkpointer


def run():
    table_id = "T_TEST_MOVE"
    graph = build_graph(get_checkpointer())

    # Force a clean thread so the run is repeatable.
    try:
        graph.checkpointer.delete_thread(table_id)
    except Exception:
        pass

    cfg = {"configurable": {"thread_id": table_id}}

    print("=" * 72)
    print("SCENARIO: info → move to Khu B → info about Khu B (while moving)")
    print("=" * 72)

    def turn(text: str, note: str):
        print(f"\n--- USER: {text}  ({note})")
        res = graph.invoke({"user_text": text, "session_id": table_id}, cfg)
        print(f"    intent        : {res.get('intent')}")
        print(f"    reply         : {res.get('reply')}")
        action = res.get("action")
        print(f"    action        : {action}")
        print(f"    navigated_place: {res.get('navigated_place')}")
        print(f"    current_section: {res.get('current_section')}")
        return res

    failures = []

    # 1) Ask for information about a real item.
    r1 = turn("bột mì để ở đâu", "ask info")
    if r1.get("intent") != "answer":
        failures.append(f"T1: expected intent=answer, got {r1.get('intent')!r}")
    if r1.get("action") is not None:
        failures.append(f"T1: expected NO action, got {r1.get('action')!r}")

    # 2) Ask to move to Khu B.
    r2 = turn("đưa tôi đến khu B", "move to Khu B")
    if r2.get("intent") != "navigate":
        failures.append(f"T2: expected intent=navigate, got {r2.get('intent')!r}")
    act2 = r2.get("action") or {}
    if act2.get("type") != "navigate":
        failures.append(f"T2: expected action.type=navigate, got {act2!r}")
    pos = act2.get("position") or {}
    if pos.get("token") != "B":
        failures.append(f"T2: expected navigate token 'B', got {pos.get('token')!r}")
    # Context memory must remember we're heading to B (so follow-ups resolve).
    if r2.get("current_section") != "B":
        failures.append(f"T2: expected current_section='B', got {r2.get('current_section')!r}")

    # 3) WHILE moving, ask more info about Khu B (the robot keeps its task;
    #    this is a fresh /chat and must NOT spawn a second navigate, just answer).
    r3 = turn("khu B có những gì", "info about Khu B while moving")
    if r3.get("intent") != "answer":
        failures.append(f"T3: expected intent=answer, got {r3.get('intent')!r}")
    if r3.get("action") is not None:
        failures.append(f"T3: must NOT dispatch a 2nd navigation; got action={r3.get('action')!r}")
    if "Khu B" not in (r3.get("reply") or ""):
        failures.append(f"T3: reply should describe Khu B, got {r3.get('reply')!r}")

    print("\n" + "=" * 72)
    if failures:
        print("FAILED CHECKS:")
        for f in failures:
            print(f"  ✗ {f}")
        print("=" * 72)
        return 1
    print("✓ ALL CHECKS PASSED")
    print("  - T1 info → answer, no motion")
    print("  - T2 'đến khu B' → navigate token 'B', context remembers section=B")
    print("  - T3 'khu B có gì' while moving → answer only, no 2nd navigation")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(run())
