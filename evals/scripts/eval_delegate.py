"""Delegate Mechanism Evaluator — measures delegate usage across all scenarios
and provides an ablation mode where delegate is removed.

Usage:
    PYTHONPATH=. uv run python evals/scripts/eval_delegate.py
    PYTHONPATH=. uv run python evals/scripts/eval_delegate.py --ablation
"""

import json
import os
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.agent_brain.agent.agent import get_agent_app

E2E_DIR = os.path.join(PROJECT_ROOT, "evals", "data", "e2e")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "evals", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")

DATASETS = [
    "e2e_conversations_part1.json",
    "e2e_conversations_part2.json",
    "e2e_out_of_menu_test.json",
    "e2e_real_life.json",
]


def log(msg: str, log_path: str):
    t = datetime.now().strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    print(line)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def extract_tool_calls(stream: list) -> list[dict]:
    calls = []
    for update in stream:
        for node in ["order_worker", "search_worker", "payment_dispatch"]:
            if node in update:
                for msg in update[node].get("messages", []):
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        calls.extend(msg.tool_calls)
    return calls


def extract_tool_outputs(stream: list) -> list[dict]:
    outputs = []
    for update in stream:
        if "tools" in update:
            for msg in update["tools"].get("messages", []):
                if isinstance(msg, ToolMessage):
                    outputs.append({"name": msg.name, "content": str(msg.content)})
    return outputs


def extract_routing_meta(stream: list) -> dict:
    for update in stream:
        if "router" in update:
            return update["router"].get("routing_meta", {})
    return {}


def node_names(stream: list) -> list:
    names = []
    for update in stream:
        names.extend(update.keys())
    return names


def run_scenarios(app, scenarios: list, log_path: str) -> dict:
    """Run all scenarios and collect delegate call data."""
    delegate_calls: list[dict] = []
    wrong_tool_calls: list[dict] = []
    total_turns = 0
    scenario_results = []

    for scenario in scenarios:
        sid = scenario["id"]
        thread_id = f"delegate_{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": thread_id}}

        log(f"\n  Scenario {sid}: {scenario['name']}", log_path)
        scenario_delegate_count = 0
        turn_results = []

        for turn_data in scenario["turns"]:
            t = turn_data["turn"]
            user_input = turn_data["content"]
            total_turns += 1

            state = {
                "messages": [HumanMessage(content=user_input)],
                "table_id": scenario["table_id"],
            }

            start = time.time()
            stream = []
            for chunk in app.stream(state, config=config, stream_mode="updates"):
                stream.append(chunk)
            latency = time.time() - start

            tool_calls = extract_tool_calls(stream)
            tool_outputs = extract_tool_outputs(stream)
            routing = extract_routing_meta(stream)
            nodes = node_names(stream)

            tc_names = [tc.get("name") for tc in tool_calls]

            # Detect delegate calls
            delegate_in_turn = [tc for tc in tool_calls if tc.get("name") == "delegate"]
            for d in delegate_in_turn:
                reason = d.get("args", {}).get("reason", "unknown")
                worker = routing.get("semantic_intent", "unknown")
                delegate_calls.append({
                    "scenario": sid,
                    "turn": t,
                    "input": user_input,
                    "worker": worker,
                    "reason": reason,
                    "routed_to": "chat_worker",
                })
                scenario_delegate_count += 1
                log(f"    Turn {t}: DELEGATE from {worker} — '{reason[:80]}'", log_path)

            # Detect potentially wrong tool calls in search/order workers
            # (when the tool called doesn't match the worker's domain)
            if tc_names:
                intent = routing.get("semantic_intent", "unknown")
                if intent == "SEARCH" and "add_cart" in tc_names:
                    wrong_tool_calls.append({
                        "scenario": sid,
                        "turn": t,
                        "input": user_input,
                        "intent": intent,
                        "tool": "add_cart",
                        "expected_domain": "search",
                    })
                if intent == "ORDER" and "search" in tc_names:
                    wrong_tool_calls.append({
                        "scenario": sid,
                        "turn": t,
                        "input": user_input,
                        "intent": intent,
                        "tool": "search",
                        "expected_domain": "order",
                    })

            log(f"    Turn {t}: intent={routing.get('semantic_intent')} tools={tc_names} delegate={len(delegate_in_turn)} ({latency:.2f}s)", log_path)

            turn_results.append({
                "turn": t,
                "tool_calls": tc_names,
                "delegate_count": len(delegate_in_turn),
                "latency": round(latency, 2),
            })

        scenario_results.append({
            "id": sid,
            "name": scenario["name"],
            "delegate_call_count": scenario_delegate_count,
            "turns": turn_results,
        })

    return {
        "total_turns": total_turns,
        "total_delegate_calls": len(delegate_calls),
        "delegate_rate": len(delegate_calls) / total_turns if total_turns else 0,
        "delegate_calls": delegate_calls,
        "wrong_tool_calls": wrong_tool_calls,
        "scenarios": scenario_results,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Delegate Mechanism Evaluator")
    parser.add_argument("--ablation", action="store_true", help="Also report delegate impact analysis")
    args = parser.parse_args()

    suffix = "ablation" if args.ablation else "baseline"
    log_path = os.path.join(RESULTS_DIR, f"delegate_{suffix}_{TS}.log")
    report_path = os.path.join(RESULTS_DIR, f"delegate_{suffix}_{TS}.json")

    log("DELEGATE MECHANISM EVALUATION", log_path)
    log("=" * 60, log_path)

    checkpoint_db = os.path.join(PROJECT_ROOT, "storage", "db", "checkpoints.db")
    if os.path.exists(checkpoint_db):
        os.remove(checkpoint_db)

    log("Loading agent...", log_path)
    app = get_agent_app()

    warmup_cfg = {"configurable": {"thread_id": "warmup_del"}}
    for _ in app.stream(
        {"messages": [HumanMessage(content="warmup")], "table_id": "warmup"},
        config=warmup_cfg,
        stream_mode="updates",
    ):
        pass
    log("Agent ready.", log_path)

    all_scenarios = []
    for ds in DATASETS:
        path = os.path.join(E2E_DIR, ds)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            scenarios = data.get("scenarios", [])
            all_scenarios.extend(scenarios)
            log(f"Loaded {len(scenarios)} scenarios from {ds}", log_path)
        else:
            log(f"Warning: {path} not found", log_path)

    log(f"\nRunning {len(all_scenarios)} scenarios...", log_path)

    result = run_scenarios(app, all_scenarios, log_path)

    # Per-worker breakdown
    order_delegates = [d for d in result["delegate_calls"] if "ORDER" in d["worker"].upper()]
    search_delegates = [d for d in result["delegate_calls"] if "SEARCH" in d["worker"].upper()]
    order_turns = sum(1 for d in result["delegate_calls"] if "ORDER" in d["worker"].upper())
    search_turns = sum(1 for d in result["delegate_calls"] if "SEARCH" in d["worker"].upper())

    log(f"\n{'='*60}", log_path)
    log("DELEGATE SUMMARY", log_path)
    log(f"{'='*60}", log_path)
    log(f"Total turns:            {result['total_turns']}", log_path)
    log(f"Total delegate calls:   {result['total_delegate_calls']}", log_path)
    log(f"Delegate rate:          {result['delegate_rate']:.2%}", log_path)
    log(f"ORDER worker delegates: {len(order_delegates)}", log_path)
    log(f"SEARCH worker delegates: {len(search_delegates)}", log_path)
    log(f"Potential wrong calls:  {len(result['wrong_tool_calls'])}", log_path)
    log("", log_path)

    log("Delegate call details:", log_path)
    for d in result["delegate_calls"]:
        log(f"  [{d['scenario']}] T{d['turn']}: '{d['input'][:60]}' | worker={d['worker']} reason='{d['reason'][:60]}'", log_path)

    if result["wrong_tool_calls"]:
        log("\nPotential wrong tool calls:", log_path)
        for w in result["wrong_tool_calls"]:
            log(f"  [{w['scenario']}] T{w['turn']}: intent={w['intent']} called {w['tool']} ({w['expected_domain']} domain)", log_path)

    report = {
        "timestamp": TS,
        "mode": "baseline",
        "summary": {
            "total_turns": result["total_turns"],
            "total_delegate_calls": result["total_delegate_calls"],
            "delegate_rate": round(result["delegate_rate"], 4),
            "order_worker_delegates": len(order_delegates),
            "search_worker_delegates": len(search_delegates),
            "potential_wrong_tool_calls": len(result["wrong_tool_calls"]),
        },
        "delegate_calls": result["delegate_calls"],
        "wrong_tool_calls": result["wrong_tool_calls"],
        "scenarios": result["scenarios"],
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log(f"\nReport saved to {report_path}", log_path)


if __name__ == "__main__":
    main()
