import json
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
from collections import defaultdict

# Add ai_waiter_core to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
AI_WAITER_CORE_PATH = PROJECT_ROOT / "ai_waiter_core"
sys.path.insert(0, str(AI_WAITER_CORE_PATH))

from langchain_core.messages import HumanMessage
from ai_waiter_core.agent.nodes.hybrid_router_node import hybrid_router_node

EVAL_DATA_PATH = PROJECT_ROOT / "evals" / "data" / "router" / "router_eval.json"
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = RESULTS_DIR / f"eval_router_slm_{timestamp}.log"
JSON_PATH = RESULTS_DIR / f"eval_router_slm_{timestamp}.json"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

def main():
    if not EVAL_DATA_PATH.exists():
        logging.error(f"Eval dataset not found at {EVAL_DATA_PATH}")
        return

    with open(EVAL_DATA_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    cases = dataset.get("cases", [])
    if not cases:
        logging.error("No cases found in the dataset.")
        return

    logging.info(f"Starting Router Evaluation for {len(cases)} cases.")
    
    # --- ADD WARM-UP RUN TO ELIMINATE COLD START BIAS ---
    logging.info("Warming up Semantic and SLM models (Cold Start Initialization)...")
    warmup_state = {
        "messages": [HumanMessage(content="Xin chào")],
        "table_id": "T1",
        "loop_count": 0,
        "is_valid": True,
        "order_stage": "IDLE"
    }
    try:
        # Run a dummy classification to load PyTorch weights & Ollama channels
        hybrid_router_node(warmup_state)
        logging.info("Warm-up complete. All models loaded and warmed up.")
    except Exception as e:
        logging.warning(f"Warm-up failed: {e}")
    # ----------------------------------------------------

    results = []
    correct_count = 0
    latencies = defaultdict(list)
    semantic_count = 0
    slm_count = 0

    for case in tqdm(cases, desc="Evaluating Router Node"):
        case_id = case["id"]
        raw_expected = case["expected_route"]
        
        # 1. Standardize expected route as a list of strings
        if isinstance(raw_expected, list):
            expected = raw_expected
        else:
            if raw_expected == "ORDER_CONFIRM":
                raw_expected = "ORDER"
            expected = [raw_expected]


        state = {
            "messages": [HumanMessage(content=case["input"])],
            "table_id": "T1",
            "loop_count": 0,
            "is_valid": True,
            "order_stage": case.get("order_stage", "IDLE")
        }

        logging.info(f"Evaluating Case {case_id}: '{case['input']}'")
        logging.info(f"  Expected: {expected}")
        
        # Call the router node with latency tracking
        routing_meta = {}
        try:
            start_time = time.time()
            output = hybrid_router_node(state)
            latency = time.time() - start_time
            
            # The hybrid router node now returns a list of intents: current_intents
            predicted = output.get("current_intents", ["UNKNOWN"])
            routing_meta = output.get("routing_meta", {})
            latencies[str(expected)].append(latency)
        except Exception as e:
            logging.error(f"  Error evaluating case {case_id}: {e}")
            predicted = ["ERROR"]
            latency = 0.0

        decided_by = routing_meta.get("decided_by", "N/A")
        sem_conf = routing_meta.get("semantic_confidence", 0.0)
        sem_intent = routing_meta.get("semantic_intent", "N/A")

        if decided_by == "SEMANTIC":
            semantic_count += 1
        else:
            slm_count += 1

        # ORDER_CONFIRM is acceptable for ORDER (both route to order_worker)
        if predicted == ["ORDER_CONFIRM"] and expected == ["ORDER"]:
            is_correct = True
        else:
            is_correct = (predicted == expected)
        if is_correct:
            correct_count += 1
            logging.info(f"  [SUCCESS] {predicted} | by={decided_by} | sem_conf={sem_conf:.4f} | sem_intent={sem_intent} | {latency:.2f}s")
        else:
            logging.warning(f"  [FAILURE] expected={expected} got={predicted} | by={decided_by} | sem_conf={sem_conf:.4f} | sem_intent={sem_intent} | {latency:.2f}s")

        results.append({
            "id": case_id,
            "input": case["input"],
            "expected": expected,
            "predicted": predicted,
            "is_correct": is_correct,
            "latency": latency,
            "difficulty": case.get("difficulty", "unknown"),
            "decided_by": decided_by,
            "semantic_confidence": sem_conf,
            "semantic_intent": sem_intent,
            "slm_intents": routing_meta.get("slm_intents"),
        })

    accuracy = correct_count / len(cases) * 100
    
    # Calculate average latency per intent
    avg_latency = {}
    total_latency = 0
    total_cases = 0
    for intent_str, l_list in latencies.items():
        if l_list:
            avg_latency[intent_str] = sum(l_list) / len(l_list)
            total_latency += sum(l_list)
            total_cases += len(l_list)
    
    overall_avg_latency = total_latency / total_cases if total_cases > 0 else 0

    # Build Report
    report = {
        "accuracy": accuracy,
        "total": len(cases),
        "correct": correct_count,
        "overall_avg_latency_s": overall_avg_latency,
        "avg_latency_per_intent_s": avg_latency,
        "routing_engine_stats": {
            "semantic_decisions": semantic_count,
            "slm_decisions": slm_count,
        },
        "results": results
    }

    logging.info("--- Evaluation Summary ---")
    logging.info(f"Total Cases: {len(cases)}")
    logging.info(f"Correct: {correct_count}")
    logging.info(f"Accuracy: {accuracy:.2f}%")
    logging.info(f"Overall Avg Latency: {overall_avg_latency:.2f}s")
    logging.info(f"Routing Decisions: SEMANTIC={semantic_count} | SLM={slm_count}")
    for intent_str, lat in avg_latency.items():
        logging.info(f"  - {intent_str}: {lat:.2f}s")

    # Save JSON report
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logging.info(f"Report saved to {JSON_PATH}")
    logging.info(f"Detailed logs saved to {LOG_PATH}")

if __name__ == "__main__":
    main()
