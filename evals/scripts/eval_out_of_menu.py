import json
import os
import sys
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

from dotenv import load_dotenv
load_dotenv()

from src.agent_brain.agent.agent import get_agent_app
from src.agent_brain.config import settings
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from evals.lib.stats import RunAggregate
from src.agent_brain.utils.menu_utils import resolve_menu_name

# --- Validator false-positive tracking ---

def _item_in_menu(item_name: str) -> bool:
    """Check if an item name resolves to any menu dish (any resolution level)."""
    r = resolve_menu_name(item_name)
    return r["kind"] in ("exact", "single")

# Dedicated single-scenario path
E2E_DATA_FILES = [
    settings.PROJECT_ROOT / "evals/data/e2e/e2e_out_of_menu_test.json"
]
RESULTS_DIR = settings.PROJECT_ROOT / "evals/results"
LOG_FILE = RESULTS_DIR / f"e2e_out_of_menu_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
REPORT_FILE = RESULTS_DIR / f"e2e_out_of_menu_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

os.makedirs(RESULTS_DIR, exist_ok=True)

def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] {message}"
    print(formatted_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted_message + "\n")

def run_scenario(app, scenario: Dict[str, Any]) -> Dict[str, Any]:
    scenario_id = scenario['id']
    thread_id = f"eval_out_of_menu_{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    
    log(f"\n--- RUNNING SCENARIO {scenario_id}: {scenario['name']} ---")
    log(f"Description: {scenario['description']}")
    
    turns_results = []
    scenario_success = True
    
    for turn_data in scenario['turns']:
        turn_num = turn_data['turn']
        user_input = turn_data['content']
        expected_assertions = turn_data.get('assert', {})
        
        log(f"Turn {turn_num} [User]: {user_input}")
        
        # Invoke agent
        input_state = {"messages": [HumanMessage(content=user_input)], "table_id": scenario['table_id']}
        output_state = app.invoke(input_state, config=config)
        
        messages = output_state['messages']
        ai_response = messages[-1].content
        log(f"Turn {turn_num} [AI]: {ai_response}")
        
        turn_tool_calls = []
        turn_tool_outputs = []
        turn_tool_call_details = []

        new_messages = []
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage) and msg.content == user_input:
                break
            new_messages.append(msg)
        new_messages.reverse()

        for msg in new_messages:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    turn_tool_calls.append(tc['name'])
                    turn_tool_call_details.append({"name": tc["name"], "args": tc.get("args", {})})
            if isinstance(msg, ToolMessage):
                turn_tool_outputs.append(str(msg.content))
        
        # Assertions
        turn_success = True
        assertion_logs = []
        
        # 1. Tool Called
        expected_tool = expected_assertions.get('tool_called')
        if expected_tool:
            if expected_tool == "verify_and_prepare_order":
                check_tool = "add_cart"
            elif expected_tool == "search_menu":
                check_tool = "search"
            else:
                check_tool = expected_tool
            
            if check_tool in turn_tool_calls:
                assertion_logs.append(f"  [PASS] Tool '{expected_tool}' (mapped to '{check_tool}') called")
            else:
                assertion_logs.append(f"  [FAIL] Tool '{expected_tool}' (mapped to '{check_tool}') NOT called. Actual: {turn_tool_calls}")
                turn_success = False
        
        # 2. Tool NOT Called
        not_expected_tool = expected_assertions.get('tool_must_NOT_call')
        if not_expected_tool:
            if not_expected_tool == "verify_and_prepare_order":
                check_not_tool = "add_cart"
            elif not_expected_tool == "search_menu":
                check_not_tool = "search"
            else:
                check_not_tool = not_expected_tool
                
            if check_not_tool in turn_tool_calls:
                assertion_logs.append(f"  [FAIL] Tool '{not_expected_tool}' (mapped to '{check_not_tool}') was called but shouldn't have been")
                turn_success = False
            else:
                assertion_logs.append(f"  [PASS] Tool '{not_expected_tool}' (mapped to '{check_not_tool}') NOT called as expected")
        
        # 3. Tool Output Contains
        tool_output_check = expected_assertions.get('tool_output_contains')
        if tool_output_check:
            check_output = "SYNC_CART_SUCCESS" if tool_output_check == "PENDING_CART" else tool_output_check
            found = any(check_output in out for out in turn_tool_outputs)
            if found:
                assertion_logs.append(f"  [PASS] Tool output contains '{tool_output_check}' (mapped to '{check_output}')")
            else:
                assertion_logs.append(f"  [FAIL] Tool output does NOT contain '{tool_output_check}' (mapped to '{check_output}')")
                turn_success = False
        
        # 4. Response Should Contain One Of
        response_one_of = expected_assertions.get('response_should_contain_one_of', [])
        if response_one_of:
            found = any(str(term).lower() in ai_response.lower() for term in response_one_of)
            if found:
                assertion_logs.append(f"  [PASS] Response contains one of expected terms")
            else:
                assertion_logs.append(f"  [FAIL] Response does NOT contain any of {response_one_of}")
                turn_success = False
        
        # 5. Response Contains
        response_contains = expected_assertions.get('response_contains')
        if response_contains:
            found_in_ai = response_contains.lower() in ai_response.lower()
            found_in_tool = any(response_contains.lower() in out.lower() for out in turn_tool_outputs)
            if found_in_ai or found_in_tool:
                assertion_logs.append(f"  [PASS] Response/Tool output contains '{response_contains}'")
            else:
                assertion_logs.append(f"  [FAIL] Response/Tool output does NOT contain '{response_contains}'")
                turn_success = False
        
        # 6. Response Must NOT Contain
        # Carries the hallucination-bait scenarios: the customer asserts a price for a dish
        # that does not exist, and the failure being tested is the agent repeating that number
        # back as though it were real. Without this check those scenarios pass while the
        # response quotes a fabricated price.
        response_forbidden = expected_assertions.get('response_must_NOT_contain', [])
        if response_forbidden:
            hits = [t for t in response_forbidden if str(t).lower() in ai_response.lower()]
            if hits:
                assertion_logs.append(f"  [FAIL] Response contains forbidden term(s): {hits}")
                turn_success = False
            else:
                assertion_logs.append(f"  [PASS] Response avoids all of {response_forbidden}")

        # 7 & 8. Cart state. Read from the state the graph actually returned rather than
        # inferred from tool calls -- a tool may be called and still leave the cart unchanged,
        # and it is the cart that decides whether the customer gets charged.
        # active_cart is a pydantic Cart, but the checkpointer can hand back a plain dict on a
        # resumed thread, so both shapes are handled. Guessing one and calling .get() on the
        # other returns an empty list silently, which would make every cart assertion pass.
        cart = output_state.get('active_cart')
        cart_items = getattr(cart, 'items', None)
        if cart_items is None:
            cart_items = cart.get('items', []) if isinstance(cart, dict) else []
        cart_names = [
            str(getattr(i, 'name', None) or (i.get('name', '') if isinstance(i, dict) else ''))
            for i in cart_items
        ]

        if expected_assertions.get('cart_must_be_empty'):
            if cart_names:
                assertion_logs.append(f"  [FAIL] Cart should be empty but holds: {cart_names}")
                turn_success = False
            else:
                assertion_logs.append("  [PASS] Cart empty as expected")

        cart_expected = expected_assertions.get('cart_must_contain', [])
        if cart_expected:
            lowered = [n.lower() for n in cart_names]
            missing = [n for n in cart_expected if not any(n.lower() in c for c in lowered)]
            if missing:
                assertion_logs.append(f"  [FAIL] Cart missing {missing}. Holds: {cart_names}")
                turn_success = False
            else:
                assertion_logs.append(f"  [PASS] Cart contains all of {cart_expected}")

        # The safety property this suite exists to measure is "no dish the customer did not
        # order ends up in the cart". Checking that directly is far more meaningful than
        # checking the reply for a phrase like "không có": an agent that politely offers a
        # substitute and adds nothing is behaving correctly, and the first version of this
        # dataset failed seven such scenarios purely on wording.
        cart_forbidden = expected_assertions.get('cart_must_NOT_contain', [])
        if cart_forbidden:
            lowered = [n.lower() for n in cart_names]
            present = [n for n in cart_forbidden if any(n.lower() in c for c in lowered)]
            if present:
                assertion_logs.append(f"  [FAIL] Cart contains rejected item(s) {present}: {cart_names}")
                turn_success = False
            else:
                assertion_logs.append(f"  [PASS] Cart free of {cart_forbidden}")

        # Guards the fuzzy-resolution failure mode found on 2026-07-23: "gà rán" resolved to
        # "Chân Gà Rang Muối Hồng Kông" (diacritic-insensitive matching makes rán ~ rang) and
        # was added to the cart. Any cart entry outside the scenario's declared valid_items is
        # a substitution the customer never asked for.
        if expected_assertions.get('cart_only_declared_valid'):
            allowed = [v.lower() for v in scenario.get('valid_items', [])]
            extra = [n for n in cart_names if not any(a in n.lower() or n.lower() in a for a in allowed)]
            if extra:
                assertion_logs.append(f"  [FAIL] Cart holds undeclared item(s) {extra}; allowed: {scenario.get('valid_items', [])}")
                turn_success = False
            else:
                assertion_logs.append("  [PASS] Cart holds only declared valid items")

        # Any assertion key the runner does not implement is a scenario that reports success
        # without having been tested. Fail loudly instead: a silently skipped check is worse
        # than a missing one, because it produces a number nobody knows is hollow.
        # Advisory: recorded in the report so wording can still be inspected, but it does not
        # decide pass/fail. Requiring a phrase like "không có" failed seven scenarios in which
        # the agent refused correctly and simply offered a substitute instead.
        response_may = expected_assertions.get('response_may_contain_one_of', [])
        if response_may:
            hit = any(str(t).lower() in ai_response.lower() for t in response_may)
            assertion_logs.append(
                f"  [note] Response {'uses' if hit else 'avoids'} the expected refusal wording"
            )

        SUPPORTED = {
            'tool_called', 'tool_must_NOT_call', 'tool_output_contains',
            'response_should_contain_one_of', 'response_contains',
            'response_must_NOT_contain', 'cart_must_be_empty', 'cart_must_contain',
            'cart_must_NOT_contain', 'cart_only_declared_valid', 'response_may_contain_one_of',
        }
        unknown = set(expected_assertions) - SUPPORTED
        if unknown:
            assertion_logs.append(f"  [FAIL] Unimplemented assertion(s) {sorted(unknown)} — not checked")
            turn_success = False

        for l in assertion_logs: log(l)

        turns_results.append({
            "turn": turn_num,
            "success": turn_success,
            "tool_calls": turn_tool_calls,
            "tool_call_details": turn_tool_call_details,
            "response": ai_response,
            "cart": cart_names,
        })
        
        if not turn_success:
            scenario_success = False

    # Validator false-positive tracking: items the LLM proposed that are valid but
    # never reached the cart (i.e. the validator wrongly blocked them).
    valid_proposed = 0
    valid_rejected = 0
    for t in turns_results:
        for tc_name, tc_args in t.get("tool_call_details", []):
            if tc_name in ("add_cart", "confirm_order"):
                for item in tc_args.get("items", []):
                    name = item.get("name", "")
                    if name and _item_in_menu(name):
                        valid_proposed += 1
                        lowered_cart = [c.lower() for c in t.get("cart", [])]
                        if not any(name.lower() in c for c in lowered_cart):
                            valid_rejected += 1

    return {
        "id": scenario_id,
        "name": scenario['name'],
        "success": scenario_success,
        "turns": turns_results,
        "valid_items_proposed": valid_proposed,
        "valid_items_rejected": valid_rejected,
    }

def run_evaluation():
    import argparse
    ap = argparse.ArgumentParser(description="Out-of-Menu Rejection E2E Evaluation")
    ap.add_argument("--runs", type=int, default=5, help="Repetitions (§5.2.3 requires 5)")
    args = ap.parse_args()

    log("Starting Out-of-Menu Rejection E2E Evaluation...")

    scenarios_to_run = []
    for data_file in E2E_DATA_FILES:
        if not os.path.exists(data_file):
            log(f"Warning: Data file {data_file} not found. Skipping.")
            continue
        with open(data_file, "r", encoding="utf-8") as f:
            dataset = json.load(f)
        log(f"Loaded {len(dataset.get('scenarios', []))} scenarios from {os.path.basename(data_file)}")
        scenarios_to_run.extend(dataset.get('scenarios', []))

    log(f"Executing {len(scenarios_to_run)} scenarios × {args.runs} runs...")

    per_run_pass_rate: list[float] = []
    per_run_conn_errors: list[int] = []
    per_run_valid_proposed: list[int] = []
    per_run_valid_rejected: list[int] = []
    all_run_results: list[dict] = []

    for run_idx in range(args.runs):
        app = get_agent_app()
        all_scenario_results = []
        connection_errors = 0
        run_valid_proposed = 0
        run_valid_rejected = 0

        for scenario in scenarios_to_run:
            result = run_scenario(app, scenario)
            all_scenario_results.append(result)
            run_valid_proposed += result.get("valid_items_proposed", 0)
            run_valid_rejected += result.get("valid_items_rejected", 0)
            for t in result.get("turns", []):
                resp = t.get("response", "")
                if "connection" in resp.lower() or "timeout" in resp.lower():
                    connection_errors += 1

        total = len(all_scenario_results)
        passed = sum(1 for r in all_scenario_results if r['success'])
        rate = passed / total if total > 0 else 0

        per_run_pass_rate.append(rate)
        per_run_conn_errors.append(connection_errors)
        per_run_valid_proposed.append(run_valid_proposed)
        per_run_valid_rejected.append(run_valid_rejected)
        all_run_results.append({"run": run_idx, "passed": passed, "total": total,
                                 "connection_errors": connection_errors,
                                 "valid_proposed": run_valid_proposed,
                                 "valid_rejected": run_valid_rejected})

        log(f"  Run {run_idx+1}/{args.runs}: {passed}/{total} = {rate:.1%}  "
            f"validator_FP={run_valid_rejected}/{run_valid_proposed}")

    pass_agg = RunAggregate("pass_rate", per_run_pass_rate)
    fp_rate = RunAggregate("validator_FP_rate", [
        r / p if p else 0.0 for r, p in zip(per_run_valid_rejected, per_run_valid_proposed)
    ])
    conn_total = sum(per_run_conn_errors)
    if conn_total > 0:
        log(f"\n  !! {conn_total} connection errors across {args.runs} runs")

    log(f"\nE2E OUT-OF-MENU EVALUATION SUMMARY ({args.runs} runs):")
    log(f"  Pass rate:      {pass_agg}")
    log(f"  Validator FP:   {fp_rate}  (valid items wrongly blocked)")

    report = {
        "summary": {
            "timestamp": datetime.now().isoformat(),
            "runs": args.runs,
            "pass_rate": pass_agg.as_dict(),
            "validator_false_positive_rate": fp_rate.as_dict(),
        },
        "per_run": all_run_results,
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    log(f"\nFull E2E report saved to {REPORT_FILE}")

if __name__ == "__main__":
    run_evaluation()
