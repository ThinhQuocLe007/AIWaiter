"""Real-life scenario runner — traces the full agent pipeline per turn.

Runs realistic restaurant conversations through the AI Waiter agent graph
directly (no HTTP server needed for sync_cart/search). Produces a detailed
per-node trace for every turn including:
  - Router decisions (semantic vs SLM, confidences)
  - Worker outputs (tool calls)
  - Validator actions (item resolution, blocking, stripping)
  - Tool execution results
  - State transitions (cart, order_stage)
  - Response context construction
  - Final Vietnamese responses

Usage:
    PYTHONPATH=. uv run python evals/scripts/run_real_life.py
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv()

from src.agent_brain.agent.agent import get_agent_app
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

SCENARIOS_FILE = os.path.join(PROJECT_ROOT, "evals", "data", "e2e", "e2e_real_life.json")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "evals", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(RESULTS_DIR, f"real_life_{TS}.log")
REPORT_FILE = os.path.join(RESULTS_DIR, f"real_life_report_{TS}.json")


# ── Logging ──────────────────────────────────────────────────────────
def log(msg: str = ""):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] {msg}" if msg else ""
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ── Stream extractors ────────────────────────────────────────────────
def extract_routing_meta(stream: list) -> dict:
    for update in stream:
        if "router" in update:
            return update["router"].get("routing_meta", {})
    return {}


def extract_tool_calls(stream: list) -> list:
    calls = []
    for update in stream:
        for node in ["order_worker", "search_worker", "payment_dispatch",
                      "payment_worker"]:
            if node in update:
                for msg in update[node].get("messages", []):
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        calls.extend(msg.tool_calls)
    return calls


def extract_tool_outputs(stream: list) -> list:
    outputs = []
    for update in stream:
        if "tools" in update:
            for msg in update["tools"].get("messages", []):
                if isinstance(msg, ToolMessage):
                    outputs.append({"name": msg.name, "content": str(msg.content)})
    return outputs


def extract_final_response(stream: list) -> str:
    for update in reversed(stream):
        if "response_node" in update:
            for msg in reversed(update["response_node"].get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content:
                    return msg.content
        for node in ["order_worker", "search_worker", "payment_dispatch",
                      "payment_worker", "chat_worker"]:
            if node in update:
                for msg in reversed(update[node].get("messages", [])):
                    if (
                        isinstance(msg, AIMessage)
                        and msg.content
                        and isinstance(msg.content, str)
                        and not msg.tool_calls
                    ):
                        return msg.content
    return ""


def extract_validator_actions(stream: list) -> dict:
    """Extract what the validator did in this turn."""
    for update in stream:
        if "validator" in update:
            return update["validator"]
    return {}


def node_names_in_stream(stream: list) -> list:
    """Ordered list of node names that executed this turn."""
    names = []
    for update in stream:
        names.extend(update.keys())
    return names


# ── State helpers ─────────────────────────────────────────────────────
def fmt_vnd(amount) -> str:
    return f"{int(amount):,}".replace(",", ".")


def state_summary(state: dict) -> str:
    parts = []
    parts.append(f"order_stage={state.get('order_stage', 'IDLE')}")
    cart = state.get("active_cart")
    if cart:
        items = getattr(cart, "items", []) if hasattr(cart, "items") else []
        total = getattr(cart, "total_price", 0) if hasattr(cart, "total_price") else 0
        if items:
            parts.append(
                f"cart=[{', '.join(f'{i.name}×{i.quantity}' for i in items)}] "
                f"total={fmt_vnd(total)}₫"
            )
        else:
            parts.append("cart=(empty)")
    else:
        parts.append("cart=None")
    parts.append(f"is_valid={state.get('is_valid', True)}")
    parts.append(f"loop={state.get('loop_count', 0)}")
    fb = state.get("feedback")
    if fb:
        parts.append(f"feedback='{fb[:60]}'")
    return " | ".join(parts)


# ── Runner ────────────────────────────────────────────────────────────
def run_scenario(app, scenario: dict) -> dict:
    sid = scenario["id"]
    thread_id = f"real_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    log()
    log("═" * 70)
    log(f"  {sid}: {scenario['name']}")
    log(f"  {scenario['description']}")
    log("═" * 70)

    turns_log = []
    all_ok = True

    for turn_data in scenario["turns"]:
        t = turn_data["turn"]
        user_input = turn_data["content"]
        asserts = turn_data.get("assert", {})

        log()
        log(f"─── Turn {t} ───")
        log(f"  🧑 Khách: {user_input}")

        start = time.time()
        stream = []
        for chunk in app.stream(
            {"messages": [HumanMessage(content=user_input)],
             "table_id": scenario["table_id"]},
            config=config,
            stream_mode="updates",
        ):
            stream.append(chunk)
        latency = time.time() - start

        routing_meta = extract_routing_meta(stream)
        tool_calls = extract_tool_calls(stream)
        tool_outputs = extract_tool_outputs(stream)
        response = extract_final_response(stream)
        nodes = node_names_in_stream(stream)

        final_state = app.get_state(config)
        sv = final_state.values if final_state else {}

        # ── Trace each node ──
        log(f"  ⚙ Nodes executed: {nodes}")

        # Router
        decided_by = routing_meta.get("decided_by", "?")
        intent = routing_meta.get("semantic_intent", "NONE")
        conf = routing_meta.get("semantic_confidence", 0)
        slm = routing_meta.get("slm_intents")
        log(f"  🧭 Router: intent={intent} decided_by={decided_by} sem_conf={conf:.3f}")
        if slm:
            log(f"           slm_intents={slm}")
        all_sims = routing_meta.get("semantic_all_sims", {})
        if all_sims:
            sims = ", ".join(f"{k}={v:.3f}" for k, v in all_sims.items())
            log(f"           similarities: {{{sims}}}")

        # Tool calls
        if tool_calls:
            log(f"  🔧 Tool calls ({len(tool_calls)}):")
            for tc in tool_calls:
                name = tc.get("name", "?")
                args = tc.get("args", {})
                if name in ("add_cart", "sync_cart"):
                    items = args.get("items", [])
                    item_strs = [
                        f"  {i.get('name', '?')} ×{i.get('quantity', 1)}"
                        for i in items
                    ]
                    log(f"     {name}:")
                    for s in item_strs:
                        log(s)
                elif name == "remove_cart":
                    log(f"     remove_cart(name={args.get('name', '?')})")
                elif name == "clear_cart":
                    log(f"     clear_cart()")
                else:
                    log(f"     {name}({args})")
        else:
            log(f"  🔧 Tool calls: (none)")

        # Tool outputs
        if tool_outputs:
            log(f"  📦 Tool outputs:")
            for to in tool_outputs:
                content = to["content"][:150]
                log(f"     [{to['name']}] {content}")
        else:
            log(f"  📦 Tool outputs: (none)")

        # Validator
        validator = extract_validator_actions(stream)
        unavail = validator.get("unavailable_items") or []
        ambig = validator.get("ambiguous_items") or []
        if unavail:
            log(f"  🛡 Validator OFF-MENU: {[u['name'] for u in unavail]}")
        if ambig:
            log(f"  🛡 Validator AMBIGUOUS: {[a['name'] for a in ambig]}")
        if not unavail and not ambig and tool_calls:
            log(f"  🛡 Validator: all items valid")

        # Response
        if response:
            log(f"  🤖 Waiter:")
            for line in response.strip().split("\n"):
                log(f"     {line}")
        else:
            log(f"  🤖 Waiter: (empty)")

        # State
        log(f"  📊 State: {state_summary(sv)}")
        log(f"  ⏱ Latency: {latency:.2f}s")

        # Assertions
        if asserts:
            log(f"  ✅ Assertions:")
            tc_names = [tc.get("name") for tc in tool_calls]
            ok = True

            for check, expected in asserts.items():
                if check == "tool_called":
                    result = expected in tc_names
                    ok = ok and result
                    icon = "✓" if result else "✗"
                    log(f"     {icon} tool_called={expected} | actual={tc_names}")
                elif check == "tool_must_NOT_call":
                    result = expected not in tc_names
                    ok = ok and result
                    icon = "✓" if result else "✗"
                    if not result:
                        log(f"     {icon} tool_must_NOT_call={expected} BUT IT WAS CALLED")
                    else:
                        log(f"     {icon} tool_must_NOT_call={expected}")
                elif check == "tool_output_contains":
                    ok_ = any(expected.lower() in to["content"].lower() for to in tool_outputs)
                    ok = ok and ok_
                    icon = "✓" if ok_ else "✗"
                    log(f"     {icon} tool_output_contains='{expected}'")
                elif check == "response_should_contain_one_of":
                    ok_ = any(term.lower() in (response or "").lower() for term in expected)
                    ok = ok and ok_
                    icon = "✓" if ok_ else "✗"
                    log(f"     {icon} response_should_contain_one_of={expected}")
                elif check == "response_contains":
                    ok_ = expected.lower() in (response or "").lower()
                    ok = ok and ok_
                    icon = "✓" if ok_ else "✗"
                    log(f"     {icon} response_contains='{expected}'")
                elif check == "confirmed_items_must_contain":
                    confirm_tc = next((tc for tc in tool_calls if tc.get("name") == "confirm_order"), None)
                    if confirm_tc:
                        item_names = [i.get("name", "") for i in confirm_tc.get("args", {}).get("items", [])]
                        ok_ = any(expected.lower() in n.lower() for n in item_names)
                        ok = ok and ok_
                        icon = "✓" if ok_ else "✗"
                        log(f"     {icon} confirmed_items_must_contain='{expected}' | items={item_names}")
                    else:
                        log(f"     ✗ confirmed_items_must_contain='{expected}' | confirm_order NOT called")
                        ok = False
                elif check == "confirmed_items_must_NOT_contain":
                    confirm_tc = next((tc for tc in tool_calls if tc.get("name") == "confirm_order"), None)
                    if confirm_tc:
                        item_names = [i.get("name", "") for i in confirm_tc.get("args", {}).get("items", [])]
                        ok_ = not any(expected.lower() in n.lower() for n in item_names)
                        ok = ok and ok_
                        icon = "✓" if ok_ else "✗"
                        log(f"     {icon} confirmed_items_must_NOT_contain='{expected}' | items={item_names}")
                    else:
                        log(f"     ✗ confirmed_items_must_NOT_contain='{expected}' | confirm_order NOT called")
                        ok = False
                else:
                    log(f"     ? unknown assertion: {check}={expected}")
            all_ok = all_ok and ok
        else:
            log(f"  ✅ Assertions: (none)")

        turns_log.append(
            {
                "turn": t,
                "user": user_input,
                "routing": {
                    "intent": intent,
                    "decided_by": decided_by,
                    "semantic_confidence": round(conf, 4),
                    "slm_intents": slm,
                },
                "nodes": nodes,
                "tool_calls": [
                    {"name": tc.get("name"), "args": tc.get("args")}
                    for tc in tool_calls
                ],
                "tool_outputs": tool_outputs,
                "response": response,
                "state": {
                    "order_stage": sv.get("order_stage"),
                    "cart_items": [
                        {"name": i.name, "qty": i.quantity}
                        for i in (sv.get("active_cart").items if sv.get("active_cart") else [])
                    ],
                    "cart_total": getattr(sv.get("active_cart"), "total_price", 0) if sv.get("active_cart") else 0,
                    "is_valid": sv.get("is_valid"),
                    "loop_count": sv.get("loop_count"),
                },
                "validator": {
                    "off_menu": len(unavail),
                    "ambiguous": len(ambig),
                },
                "latency": round(latency, 2),
            }
        )

    return {"id": sid, "name": scenario["name"], "success": all_ok, "turns": turns_log}


# ── Main ─────────────────────────────────────────────────────────────
def main():
    log("REAL-LIFE SCENARIO EVALUATION")
    log(f"Scenarios: {SCENARIOS_FILE}")
    log()

    # Clear checkpoint DB for fresh state each run
    checkpoint_db = os.path.join(PROJECT_ROOT, "storage", "db", "checkpoints.db")
    if os.path.exists(checkpoint_db):
        os.remove(checkpoint_db)
        log("Cleared checkpoint DB")

    log("Loading agent (cold start includes model warmup)...")
    app = get_agent_app()
    warmup_cfg = {"configurable": {"thread_id": "warmup_real"}}
    for _ in app.stream(
        {"messages": [HumanMessage(content="warmup")], "table_id": "warmup"},
        config=warmup_cfg,
        stream_mode="updates",
    ):
        pass
    log("Agent ready.\n")

    with open(SCENARIOS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenarios = data["scenarios"]
    log(f"Loaded {len(scenarios)} real-life scenarios")

    results = []
    for sc in scenarios:
        r = run_scenario(app, sc)
        results.append(r)

    # ── Summary ──
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    rate = passed / total if total > 0 else 0

    log()
    log("═" * 70)
    log("  SUMMARY")
    log("═" * 70)
    log(f"  Scenarios: {total}")
    log(f"  Passed:    {passed}")
    log(f"  Failed:    {total - passed}")
    log(f"  Rate:      {rate:.1%}")
    log()

    # Per-scenario latency breakdown
    log("  Latency profile:")
    for r in results:
        avg_lat = sum(t["latency"] for t in r["turns"]) / max(len(r["turns"]), 1)
        status = "PASS" if r["success"] else "FAIL"
        semantic_turns = sum(
            1 for t in r["turns"] if t["routing"]["decided_by"] == "SEMANTIC"
        )
        slm_turns = sum(
            1 for t in r["turns"] if t["routing"]["decided_by"] == "SLM"
        )
        log(
            f"  [{status}] {r['id']}: {len(r['turns'])} turns, "
            f"avg {avg_lat:.1f}s, "
            f"semantic={semantic_turns}, slm={slm_turns}"
        )

    # Router decision breakdown
    all_decisions = [
        t["routing"]["decided_by"] for r in results for t in r["turns"]
    ]
    sem_count = all_decisions.count("SEMANTIC")
    slm_count = all_decisions.count("SLM")
    log()
    log(f"  Router: semantic={sem_count}, slm={slm_count} "
        f"({sem_count / max(len(all_decisions), 1):.0%} fast-tracked)")

    # Tool call breakdown
    all_tools = [
        tc["name"]
        for r in results
        for t in r["turns"]
        for tc in t["tool_calls"]
    ]
    from collections import Counter
    tool_counts = Counter(all_tools)
    log(f"  Tools executed: {dict(tool_counts)}")

    # Save report
    report = {
        "summary": {
            "timestamp": datetime.now().isoformat(),
            "pass_rate": rate,
            "total_scenarios": total,
            "passed": passed,
            "router_semantic_count": sem_count,
            "router_slm_count": slm_count,
            "tool_counts": dict(tool_counts),
        },
        "results": results,
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log(f"\nReport: {REPORT_FILE}")
    log(f"Log:    {LOG_FILE}")


if __name__ == "__main__":
    main()
