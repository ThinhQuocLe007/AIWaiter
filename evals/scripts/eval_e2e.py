import json
import os
import sys
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

from dotenv import load_dotenv
load_dotenv()

from src.agent_brain.agent.agent import get_agent_app
from src.agent_brain.config import settings
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

E2E_DATA_DIR = os.path.join(PROJECT_ROOT, "evals", "data", "e2e")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "evals", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(RESULTS_DIR, f"e2e_eval_{timestamp}.log")
REPORT_FILE = os.path.join(RESULTS_DIR, "e2e_report.json")


def log(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def extract_routing_meta(stream_updates: List[Dict]) -> Dict[str, Any]:
    """Extract routing metadata from stream updates."""
    for update in stream_updates:
        if "router" in update:
            router_output = update["router"]
            return router_output.get("routing_meta", {})
    return {}


def extract_tool_calls_from_stream(stream_updates: List[Dict]) -> List[Dict]:
    """Extract all tool calls from stream updates."""
    tool_calls = []
    for update in stream_updates:
        for node_name in ["order_worker", "search_worker", "payment_worker"]:
            if node_name in update:
                messages = update[node_name].get("messages", [])
                for msg in messages:
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        tool_calls.extend(msg.tool_calls)
    return tool_calls


def extract_tool_outputs_from_stream(stream_updates: List[Dict]) -> List[Dict]:
    """Extract all tool outputs from stream updates."""
    tool_outputs = []
    for update in stream_updates:
        if "tools" in update:
            messages = update["tools"].get("messages", [])
            for msg in messages:
                if isinstance(msg, ToolMessage):
                    tool_outputs.append({
                        "name": msg.name,
                        "content": str(msg.content),
                    })
    return tool_outputs


def extract_ai_response_from_stream(stream_updates: List[Dict]) -> str:
    """Extract the final AI response from stream updates."""
    for update in reversed(stream_updates):
        if "response_node" in update:
            messages = update["response_node"].get("messages", [])
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and msg.content:
                    return msg.content
        for node_name in ["order_worker", "search_worker", "payment_worker"]:
            if node_name in update:
                messages = update[node_name].get("messages", [])
                for msg in reversed(messages):
                    if isinstance(msg, AIMessage) and msg.content and isinstance(msg.content, str):
                        return msg.content
    return ""


def format_tool_call(tc: Dict) -> str:
    """Format a tool call for logging."""
    name = tc.get("name", "unknown")
    args = tc.get("args", {})
    if name == "sync_cart":
        items = args.get("items", [])
        item_strs = [f"{{name: {i.get('name')}, qty: {i.get('quantity')}}}" for i in items]
        return f"sync_cart(items=[{', '.join(item_strs)}])"
    elif name == "confirm_order":
        return f"confirm_order(table_id={args.get('table_id')}, items={len(args.get('items', []))} items)"
    elif name == "search":
        return f"search(query={args.get('query')})"
    elif name == "request_payment":
        return f"request_payment(table_id={args.get('table_id')})"
    elif name == "verify_payment":
        return f"verify_payment(table_id={args.get('table_id')})"
    else:
        return f"{name}({args})"


def format_tool_output(to: Dict) -> str:
    """Format a tool output for logging."""
    name = to.get("name", "unknown")
    content = to.get("content", "")
    if len(content) > 200:
        content = content[:200] + "..."
    return f"[{name}] {content}"


def format_state(state: Dict) -> str:
    """Format state for logging."""
    order_stage = state.get("order_stage", "IDLE")
    active_cart = state.get("active_cart")
    intents = state.get("current_intents", [])
    is_valid = state.get("is_valid", True)
    loop_count = state.get("loop_count", 0)
    feedback = state.get("feedback")

    parts = [f"order_stage={order_stage}"]
    if active_cart:
        items = active_cart.get("items", []) if isinstance(active_cart, dict) else getattr(active_cart, "items", [])
        total = active_cart.get("total_price", 0) if isinstance(active_cart, dict) else getattr(active_cart, "total_price", 0)
        parts.append(f"active_cart={len(items)} items, total={total}")
    else:
        parts.append("active_cart=None")
    parts.append(f"intents={intents}")
    parts.append(f"is_valid={is_valid}")
    parts.append(f"loop_count={loop_count}")
    if feedback:
        parts.append(f"feedback='{feedback[:50]}...'")
    return " | ".join(parts)


def check_assertions(asserts: dict, ai_response: str, tool_calls: List[Dict],
                     tool_outputs: List[Dict], state: Dict) -> tuple:
    """Check assertions and return (passed, logs, assertion_details)."""
    passed = True
    logs = []
    details = []

    tool_call_names = [tc.get("name") for tc in tool_calls]
    tool_output_contents = [to.get("content", "") for to in tool_outputs]

    expected_tool = asserts.get('tool_called')
    if expected_tool:
        if expected_tool in tool_call_names:
            logs.append(f"    [PASS] Tool '{expected_tool}' called")
            details.append({"check": f"tool_called:{expected_tool}", "passed": True})
        else:
            logs.append(f"    [FAIL] Tool '{expected_tool}' NOT called. Actual: {tool_call_names}")
            details.append({"check": f"tool_called:{expected_tool}", "passed": False, "actual": tool_call_names})
            passed = False

    not_expected = asserts.get('tool_must_NOT_call')
    if not_expected:
        if not_expected in tool_call_names:
            logs.append(f"    [FAIL] Tool '{not_expected}' was called but shouldn't")
            details.append({"check": f"tool_must_NOT_call:{not_expected}", "passed": False})
            passed = False
        else:
            logs.append(f"    [PASS] Tool '{not_expected}' correctly NOT called")
            details.append({"check": f"tool_must_NOT_call:{not_expected}", "passed": True})

    tool_output_check = asserts.get('tool_output_contains')
    if tool_output_check:
        check_text = "success" if tool_output_check == "PENDING_CART" else tool_output_check
        found = any(check_text.lower() in out.lower() for out in tool_output_contents)
        if found:
            logs.append(f"    [PASS] Tool output contains '{tool_output_check}'")
            details.append({"check": f"tool_output_contains:{tool_output_check}", "passed": True})
        else:
            logs.append(f"    [FAIL] Tool output missing '{tool_output_check}'")
            for i, to in enumerate(tool_outputs):
                logs.append(f"           Output[{i}]: {to.get('content', '')[:100]}...")
            details.append({"check": f"tool_output_contains:{tool_output_check}", "passed": False})
            passed = False

    response_one_of = asserts.get('response_should_contain_one_of', [])
    if response_one_of:
        found = any(term.lower() in ai_response.lower() for term in response_one_of)
        if found:
            logs.append(f"    [PASS] Response contains one of {response_one_of}")
            details.append({"check": "response_should_contain_one_of", "passed": True})
        else:
            logs.append(f"    [FAIL] Response missing all of {response_one_of}")
            logs.append(f"           Response: '{ai_response[:150]}...'")
            details.append({"check": "response_should_contain_one_of", "passed": False, "expected": response_one_of, "actual": ai_response[:150]})
            passed = False

    response_contains = asserts.get('response_contains')
    if response_contains:
        check_text = "success" if response_contains == "SUCCESS" else response_contains
        found = (check_text.lower() in ai_response.lower() or
                 any(check_text.lower() in out.lower() for out in tool_output_contents))
        if found:
            logs.append(f"    [PASS] Response/tool contains '{response_contains}'")
            details.append({"check": f"response_contains:{response_contains}", "passed": True})
        else:
            logs.append(f"    [FAIL] Response/tool missing '{response_contains}'")
            details.append({"check": f"response_contains:{response_contains}", "passed": False})
            passed = False

    must_contain = asserts.get('confirmed_items_must_contain')
    if must_contain:
        confirm_tc = next((tc for tc in tool_calls if tc.get('name') == 'confirm_order'), None)
        if confirm_tc:
            item_names = [i.get('name', '') for i in confirm_tc.get('args', {}).get('items', [])]
            if any(must_contain.lower() in n.lower() for n in item_names):
                logs.append(f"    [PASS] Confirmed items contain '{must_contain}'")
                details.append({"check": f"confirmed_items_must_contain:{must_contain}", "passed": True})
            else:
                logs.append(f"    [FAIL] Confirmed items {item_names} missing '{must_contain}'")
                details.append({"check": f"confirmed_items_must_contain:{must_contain}", "passed": False, "actual": item_names})
                passed = False
        else:
            logs.append(f"    [FAIL] confirm_order not called, can't check '{must_contain}'")
            details.append({"check": f"confirmed_items_must_contain:{must_contain}", "passed": False, "reason": "confirm_order not called"})
            passed = False

    must_not_contain = asserts.get('confirmed_items_must_NOT_contain')
    if must_not_contain:
        confirm_tc = next((tc for tc in tool_calls if tc.get('name') == 'confirm_order'), None)
        if confirm_tc:
            item_names = [i.get('name', '') for i in confirm_tc.get('args', {}).get('items', [])]
            if not any(must_not_contain.lower() in n.lower() for n in item_names):
                logs.append(f"    [PASS] Confirmed items don't contain '{must_not_contain}'")
                details.append({"check": f"confirmed_items_must_NOT_contain:{must_not_contain}", "passed": True})
            else:
                logs.append(f"    [FAIL] Confirmed items {item_names} contain forbidden '{must_not_contain}'")
                details.append({"check": f"confirmed_items_must_NOT_contain:{must_not_contain}", "passed": False, "actual": item_names})
                passed = False
        else:
            logs.append(f"    [FAIL] confirm_order not called, can't check NOT '{must_not_contain}'")
            details.append({"check": f"confirmed_items_must_NOT_contain:{must_not_contain}", "passed": False, "reason": "confirm_order not called"})
            passed = False

    return passed, logs, details


def run_scenario(app, scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Run a single scenario and return detailed results."""
    sid = scenario['id']
    thread_id = f"eval_e2e_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    log(f"\n{'='*60}")
    log(f"SCENARIO {sid}: {scenario['name']}")
    log(f"{'='*60}")
    log(f"Description: {scenario['description']}")
    log(f"Table ID: {scenario['table_id']}")
    log(f"Difficulty: {scenario.get('difficulty', 'unknown')}")

    turns_results = []
    scenario_ok = True

    for turn_data in scenario['turns']:
        t = turn_data['turn']
        user_input = turn_data['content']
        asserts = turn_data.get('assert', {})

        log(f"\n  --- Turn {t} ---")
        log(f"  [User]: {user_input}")

        input_state = {
            "messages": [HumanMessage(content=user_input)],
            "table_id": scenario['table_id'],
        }

        start_time = time.time()
        stream_updates = []
        for chunk in app.stream(input_state, config=config, stream_mode="updates"):
            stream_updates.append(chunk)
        latency = time.time() - start_time

        routing_meta = extract_routing_meta(stream_updates)
        tool_calls = extract_tool_calls_from_stream(stream_updates)
        tool_outputs = extract_tool_outputs_from_stream(stream_updates)
        ai_response = extract_ai_response_from_stream(stream_updates)

        final_state = app.get_state(config)
        state_values = final_state.values if final_state else {}

        log(f"  [Router]    intent={routing_meta.get('semantic_intent', 'N/A')} | "
            f"decided_by={routing_meta.get('decided_by', 'N/A')} | "
            f"confidence={routing_meta.get('semantic_confidence', 0):.3f}")
        if routing_meta.get('all_similarities'):
            sims = routing_meta['all_similarities']
            sims_str = ", ".join([f"{k}={v:.3f}" for k, v in sims.items()])
            log(f"              all_sims={{{sims_str}}}")
        if routing_meta.get('slm_intents'):
            log(f"              slm_intents={routing_meta['slm_intents']}")

        log(f"  [Latency]   {latency:.2f}s")

        if tool_calls:
            log(f"  [ToolCalls]")
            for tc in tool_calls:
                log(f"              {format_tool_call(tc)}")
        else:
            log(f"  [ToolCalls] (none)")

        if tool_outputs:
            log(f"  [ToolOutputs]")
            for to in tool_outputs:
                log(f"              {format_tool_output(to)}")
        else:
            log(f"  [ToolOutputs] (none)")

        log(f"  [AI]        {ai_response[:200] if ai_response else '(empty)'}")
        if len(ai_response) > 200:
            log(f"              ...{ai_response[200:]}")

        log(f"  [State]     {format_state(state_values)}")

        ok, assertion_logs, assertion_details = check_assertions(
            asserts, ai_response, tool_calls, tool_outputs, state_values
        )
        if assertion_logs:
            log(f"  [Assertions]")
            for line in assertion_logs:
                log(line)
        else:
            log(f"  [Assertions] (no assertions)")

        turns_results.append({
            "turn": t,
            "success": ok,
            "latency_seconds": round(latency, 2),
            "routing": {
                "intent": routing_meta.get('semantic_intent'),
                "decided_by": routing_meta.get('decided_by'),
                "confidence": routing_meta.get('semantic_confidence'),
                "all_similarities": routing_meta.get('all_similarities'),
                "slm_intents": routing_meta.get('slm_intents'),
            },
            "tool_calls": [{"name": tc.get("name"), "args": tc.get("args")} for tc in tool_calls],
            "tool_outputs": tool_outputs,
            "response": ai_response,
            "state": {
                "order_stage": state_values.get("order_stage"),
                "active_cart": str(state_values.get("active_cart")) if state_values.get("active_cart") else None,
                "current_intents": state_values.get("current_intents"),
                "is_valid": state_values.get("is_valid"),
                "loop_count": state_values.get("loop_count"),
            },
            "assertions": assertion_details,
        })
        if not ok:
            scenario_ok = False

    return {"id": sid, "name": scenario['name'], "success": scenario_ok, "turns": turns_results}


def run_evaluation(limit: int = None, datasets: List[str] = None):
    log("=" * 60)
    log("E2E EVALUATION - COMPREHENSIVE LOGGING")
    log("=" * 60)
    if limit:
        log(f"Limit: {limit} scenarios")
    if datasets:
        log(f"Datasets: {datasets}")

    checkpoint_db = os.path.join(PROJECT_ROOT, "storage", "db", "checkpoints.db")
    if os.path.exists(checkpoint_db):
        os.remove(checkpoint_db)
        log(f"Cleared checkpoint DB: {checkpoint_db}")

    # Reset transactional tables in the orchestrator DB (the single ledger) so each run starts
    # clean. Most scenarios confirm orders but never pay, so their sessions stay open and their
    # orders would otherwise accumulate across runs and inflate the bills. The agent reaches this
    # DB through the backend now, so the backend must be running for the e2e flow to persist.
    orchestrator_db = os.path.join(PROJECT_ROOT, "storage", "db", "orchestrator.db")
    if os.path.exists(orchestrator_db):
        import sqlite3
        try:
            conn = sqlite3.connect(orchestrator_db)
            cur = conn.cursor()
            existing = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ("payments", "order_items", "orders", "sessions"):
                if table in existing:
                    cur.execute(f"DELETE FROM {table}")
            conn.commit()
            conn.close()
            log(f"Reset orchestrator DB tables: {orchestrator_db}")
        except sqlite3.Error as e:
            log(f"Orchestrator DB reset failed (non-fatal): {e}")

    log("Warming up agent (cold start)...")
    try:
        app = get_agent_app()
        warmup_config = {"configurable": {"thread_id": "warmup"}}
        for _ in app.stream(
            {"messages": [HumanMessage(content="warmup")], "table_id": "warmup"},
            config=warmup_config,
            stream_mode="updates"
        ):
            pass
        log("Warm-up complete.")
    except Exception as e:
        log(f"Warm-up failed (non-fatal): {e}")
        app = get_agent_app()

    all_results = []
    scenario_queue = []

    if datasets is None:
        datasets = ["e2e_conversations_part1.json"]

    for ds in datasets:
        path = os.path.join(E2E_DATA_DIR, ds)
        if not os.path.exists(path):
            log(f"Warning: {path} not found, skipping")
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        scenarios = data.get("scenarios", [])
        log(f"Loaded {len(scenarios)} scenarios from {ds}")
        scenario_queue.extend(scenarios)

    if limit:
        scenario_queue = scenario_queue[:limit]

    log(f"Executing {len(scenario_queue)} scenarios...")

    for scenario in scenario_queue:
        result = run_scenario(app, scenario)
        all_results.append(result)

    total = len(all_results)
    passed = sum(1 for r in all_results if r['success'])
    rate = passed / total if total > 0 else 0

    log(f"\n{'='*60}")
    log("E2E EVALUATION SUMMARY")
    log(f"{'='*60}")
    log(f"Total Scenarios: {total}")
    log(f"Passed:          {passed}")
    log(f"Failed:          {total - passed}")
    log(f"Pass Rate:       {rate:.2%}")
    log("")
    for r in all_results:
        status = "PASS" if r['success'] else "FAIL"
        log(f"  [{status}] {r['id']}: {r['name']}")

    report = {
        "summary": {
            "timestamp": datetime.now().isoformat(),
            "pass_rate": rate,
            "total_scenarios": total,
            "passed_count": passed,
        },
        "results": all_results,
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log(f"\nReport saved to {REPORT_FILE}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="E2E Evaluation for AI Waiter")
    parser.add_argument("--limit", type=int, default=None, help="Max scenarios to run")
    parser.add_argument("--datasets", nargs="+", default=None,
                        help="Dataset filenames (default: e2e_conversations_part1.json)")
    args = parser.parse_args()
    run_evaluation(limit=args.limit, datasets=args.datasets)
