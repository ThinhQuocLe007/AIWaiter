import json
import os
import sys
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC_DIR = os.path.join(PROJECT_ROOT, 'ai_waiter_core')
if os.path.isdir(SRC_DIR):
    sys.path.insert(0, SRC_DIR)

from dotenv import load_dotenv
load_dotenv()

from ai_waiter_core.agent.agent import get_agent_app
from ai_waiter_core.config import settings
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Dedicated single-scenario path
E2E_DATA_FILES = [
    settings.PROJECT_ROOT / "evals/data/e2e/e2e_out_of_menu_test.json"
]
RESULTS_DIR = settings.PROJECT_ROOT / "evals/results"
LOG_FILE = RESULTS_DIR / f"e2e_out_of_menu_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
REPORT_FILE = RESULTS_DIR / "e2e_out_of_menu_report.json"

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
            if isinstance(msg, ToolMessage):
                turn_tool_outputs.append(str(msg.content))
        
        # Assertions
        turn_success = True
        assertion_logs = []
        
        # 1. Tool Called
        expected_tool = expected_assertions.get('tool_called')
        if expected_tool:
            if expected_tool == "verify_and_prepare_order":
                check_tool = "sync_cart"
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
                check_not_tool = "sync_cart"
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
        
        for l in assertion_logs: log(l)
        
        turns_results.append({
            "turn": turn_num,
            "success": turn_success,
            "tool_calls": turn_tool_calls,
            "response": ai_response
        })
        
        if not turn_success:
            scenario_success = False
            
    return {
        "id": scenario_id,
        "name": scenario['name'],
        "success": scenario_success,
        "turns": turns_results
    }

def run_evaluation():
    log("Starting Out-of-Menu Rejection Single-Scenario E2E Evaluation...")
    
    app = get_agent_app()
    all_scenario_results = []
    scenarios_to_run = []
    
    for data_file in E2E_DATA_FILES:
        if not os.path.exists(data_file):
            log(f"Warning: Data file {data_file} not found. Skipping.")
            continue
            
        with open(data_file, "r", encoding="utf-8") as f:
            dataset = json.load(f)
            
        log(f"Loaded {len(dataset.get('scenarios', []))} scenarios from {os.path.basename(data_file)}")
        scenarios_to_run.extend(dataset.get('scenarios', []))
        
    log(f"Executing {len(scenarios_to_run)} scenarios...")
    
    for scenario in scenarios_to_run:
        result = run_scenario(app, scenario)
        all_scenario_results.append(result)
            
    total = len(all_scenario_results)
    passed = sum(1 for r in all_scenario_results if r['success'])
    pass_rate = passed / total if total > 0 else 0
    
    log(f"\nE2E OUT-OF-MENU EVALUATION SUMMARY:")
    log(f"  Total Scenarios: {total}")
    log(f"  Passed:          {passed}")
    log(f"  Pass Rate:       {pass_rate:.2%}")
    
    report = {
        "summary": {
            "timestamp": datetime.now().isoformat(),
            "pass_rate": pass_rate,
            "total_scenarios": total,
            "passed_count": passed
        },
        "results": all_scenario_results
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    log(f"\nFull E2E report saved to {REPORT_FILE}")

if __name__ == "__main__":
    run_evaluation()
