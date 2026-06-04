import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any

from ai_waiter_core.services.retriever.hybrid_retriever import RetrieverManager
from ai_waiter_core.config import settings

# Paths
EVAL_DATA_PATH = settings.PROJECT_ROOT / "evals/data/retrieval/retrieval_eval.json"
RESULTS_DIR = settings.PROJECT_ROOT / "evals/results"
LOG_FILE = RESULTS_DIR / f"retrieval_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
REPORT_FILE = RESULTS_DIR / "retrieval_report.json"

os.makedirs(RESULTS_DIR, exist_ok=True)

def log(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"[{timestamp}] {message}"
    print(formatted_message)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted_message + "\n")

def calculate_metrics(results: List[Any], expected_relevant: List[str]):
    # Extract item names from search results
    # Assuming names are in document metadata 'name' or 'title'
    retrieved_names = []
    for r in results:
        metadata = r.document.metadata
        name = metadata.get('name') or metadata.get('title') or "Unknown"
        retrieved_names.append(name.lower())
    
    expected_relevant_lower = [name.lower() for name in expected_relevant]
    
    # Calculate Precision and Recall at K
    hits = [name for name in retrieved_names if name in expected_relevant_lower]
    precision = len(hits) / len(retrieved_names) if retrieved_names else 0
    recall = len(hits) / len(expected_relevant_lower) if expected_relevant_lower else 0
    hit_rate = 1 if len(hits) > 0 else 0
    
    # Calculate MRR
    mrr = 0
    for i, name in enumerate(retrieved_names):
        if name in expected_relevant_lower:
            mrr = 1 / (i + 1)
            break
            
    return {
        "precision": precision,
        "recall": recall,
        "hit_rate": hit_rate,
        "mrr": mrr,
        "retrieved": retrieved_names,
        "hits": hits
    }

def run_evaluation():
    log("Starting Retrieval Evaluation...")
    
    # Load dataset
    with open(EVAL_DATA_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    
    log(f"Dataset: {dataset['dataset']} v{dataset['version']}")
    log(f"Total test cases: {len(dataset['cases'])}")
    
    # Initialize Retriever
    retriever = RetrieverManager()
    if not retriever.load_database():
        log("Error: Could not load database. Rebuilding...")
        data_path = settings.PROJECT_ROOT / "assets" / "data"
        retriever.build_database([str(data_path)])
    
    overall_results = []
    start_time = time.time()
    
    # Run cases
    for case in dataset['cases']:
        query = case['query']
        log(f"\nEvaluating Case {case['id']}: '{query}' (Difficulty: {case['difficulty']})")
        
        # We test both RRF and Weighted
        for mode in ["rrf", "weighted"]:
            results = retriever.hybrid_search(query, k=3, mode=mode)
            metrics = calculate_metrics(results, case['expected_relevant'])
            
            log(f"  [{mode.upper()}] Metrics: Precision={metrics['precision']:.2f}, Recall={metrics['recall']:.2f}, MRR={metrics['mrr']:.2f}")
            if metrics['hit_rate'] == 0:
                log(f"  [WARNING] MISS! Expected: {case['expected_relevant']}, Got: {metrics['retrieved']}")
            
            case_result = {
                "id": case['id'],
                "query": query,
                "mode": mode,
                "difficulty": case['difficulty'],
                "category": case['category'],
                "metrics": metrics
            }
            overall_results.append(case_result)
            
    total_time = time.time() - start_time
    log(f"\nEvaluation complete in {total_time:.2f} seconds.")
    
    # Aggregate Metrics
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_cases": len(dataset['cases']),
        "modes": {}
    }
    
    for mode in ["rrf", "weighted"]:
        mode_results = [r for r in overall_results if r['mode'] == mode]
        avg_precision = sum(r['metrics']['precision'] for r in mode_results) / len(mode_results)
        avg_recall = sum(r['metrics']['recall'] for r in mode_results) / len(mode_results)
        avg_mrr = sum(r['metrics']['mrr'] for r in mode_results) / len(mode_results)
        hit_rate = sum(r['metrics']['hit_rate'] for r in mode_results) / len(mode_results)
        
        summary["modes"][mode] = {
            "avg_precision": avg_precision,
            "avg_recall": avg_recall,
            "avg_mrr": avg_mrr,
            "hit_rate": hit_rate
        }
        log(f"\nSUMMARY [{mode.upper()}]:")
        log(f"  Avg Precision@3: {avg_precision:.4f}")
        log(f"  Avg Recall@3:    {avg_recall:.4f}")
        log(f"  Avg MRR:         {avg_mrr:.4f}")
        log(f"  Hit Rate:        {hit_rate:.4f}")

    # Save report
    report = {
        "summary": summary,
        "detailed_results": overall_results
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    log(f"\nFull report saved to {REPORT_FILE}")

if __name__ == "__main__":
    run_evaluation()
