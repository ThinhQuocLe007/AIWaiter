"""API Benchmark Tool — measures p50/p95/p99 latency for all orchestrator
REST endpoints and simulates concurrent table load.

Requires: Orchestrator backend running on :8000
Usage:
    PYTHONPATH=. uv run python evals/scripts/bench_api.py
    PYTHONPATH=. uv run python evals/scripts/bench_api.py --concurrent 2
"""

import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean, median, quantiles

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

TS = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_PATH = RESULTS_DIR / f"bench_api_{TS}.json"

BASE_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000")

ENDPOINTS = [
    # (method, path, description)
    ("GET", "/menu", "Menu listing"),
    ("GET", "/tables", "All tables status"),
    ("GET", "/tables/1", "Single table"),
    ("POST", "/seatings", "Seat a table", {"table_id": 99, "party_size": 2}),
    ("GET", "/orders", "All orders"),
    ("POST", "/orders", "Create order", {"table_id": 1, "items": [{"name": "Lẩu Thái", "quantity": 1}]}),
    ("GET", "/payments", "Payment status"),
    ("GET", "/robots", "Robot fleet status"),
    ("GET", "/tasks", "Tasks list"),
    ("GET", "/layout", "Restaurant layout"),
    ("POST", "/voice/event", "Voice event mirror", {"table_id": "T1", "transcript": "test", "reply": "test", "ui_action": None}),
    ("POST", "/voice/listen", "Voice listen trigger", {"robot_id": "robo-1"}),
]

N_WARMUP = 2
N_SAMPLES = 10


def benchmark_endpoint(client: httpx.Client, method: str, path: str, body: dict | None = None) -> dict:
    """Measure latency for a single endpoint, returning p50/p95/p99."""
    latencies = []

    for _ in range(N_WARMUP):
        try:
            if method == "GET":
                resp = client.get(path)
            elif method == "POST":
                resp = client.post(path, json=body or {})
            elif method == "PATCH":
                resp = client.patch(path, json=body or {})
            resp.read()
        except Exception:
            pass

    for _ in range(N_SAMPLES):
        try:
            start = time.perf_counter()
            if method == "GET":
                resp = client.get(path)
            elif method == "POST":
                resp = client.post(path, json=body or {})
            elif method == "PATCH":
                resp = client.patch(path, json=body or {})
            resp.read()
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
        except Exception as e:
            latencies.append(-1)

    valid = [l for l in latencies if l >= 0]
    if not valid:
        return {"method": method, "path": path, "error": "All requests failed", "n": N_SAMPLES}

    p50 = median(valid)
    q = quantiles(valid, n=20) if len(valid) >= 20 else [min(valid), max(valid)]
    p95 = q[18] if len(q) > 18 else max(valid)
    p99 = q[19] if len(q) > 19 else max(valid)

    return {
        "method": method,
        "path": path,
        "n_ok": len(valid),
        "n_err": len(latencies) - len(valid),
        "mean_ms": round(mean(valid), 2),
        "median_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "min_ms": round(min(valid), 2),
        "max_ms": round(max(valid), 2),
    }


def run_concurrent_test(n_tables: int) -> dict:
    """Simulate N tables ordering simultaneously."""
    print(f"\n  Concurrent test: {n_tables} tables ordering simultaneously...")

    def order_for_table(tid: int):
        try:
            with httpx.Client(base_url=BASE_URL, timeout=httpx.Timeout(10.0)) as cli:
                start = time.perf_counter()
                cli.post("/orders", json={
                    "table_id": tid,
                    "items": [{"name": "Lẩu Thái", "quantity": 1}],
                })
                return (time.perf_counter() - start) * 1000
        except Exception as e:
            return -1

    with ThreadPoolExecutor(max_workers=n_tables) as pool:
        futures = [pool.submit(order_for_table, i + 1) for i in range(n_tables)]
        latencies = [f.result() for f in as_completed(futures)]

    valid = [l for l in latencies if l >= 0]
    if not valid:
        return {"error": "All concurrent requests failed"}

    return {
        "n_tables": n_tables,
        "n_ok": len(valid),
        "n_err": len(latencies) - len(valid),
        "mean_ms": round(mean(valid), 2),
        "median_ms": round(median(valid), 2),
        "p95_ms": round(quantiles(valid, n=20)[18] if len(valid) >= 20 else max(valid), 2),
        "p99_ms": round(quantiles(valid, n=20)[19] if len(valid) >= 20 else max(valid), 2),
    }


def main():
    print("API BENCHMARK TOOL")
    print(f"Target: {BASE_URL}")
    print(f"Samples per endpoint: {N_SAMPLES} (warmup: {N_WARMUP})")
    print("=" * 60)

    # Check if backend is up
    try:
        with httpx.Client(base_url=BASE_URL, timeout=httpx.Timeout(5.0)) as cli:
            resp = cli.get("/menu")
            if resp.status_code >= 400:
                print(f"WARNING: Backend returned status {resp.status_code}. Continuing anyway...")
            else:
                print(f"Backend is up (GET /menu → {resp.status_code})")
    except (httpx.ConnectError, httpx.ConnectTimeout):
        print(f"ERROR: Cannot connect to {BASE_URL}. Make sure the orchestrator is running.")
        report = {"timestamp": TS, "error": "Backend unreachable", "endpoints": [], "concurrent": None}
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Empty report saved to {REPORT_PATH}")
        return

    results = []

    with httpx.Client(base_url=BASE_URL, timeout=httpx.Timeout(10.0)) as client:
        for method, path, *rest in ENDPOINTS:
            description = rest[0] if rest else path
            body = rest[1] if len(rest) > 1 else None

            print(f"\n  {method} {path} ({description})")
            result = benchmark_endpoint(client, method, path, body)
            result["description"] = description
            results.append(result)

            if "error" in result:
                print(f"    ERROR: {result['error']}")
            else:
                print(f"    mean={result['mean_ms']:.1f}ms  median={result['median_ms']:.1f}ms  p95={result['p95_ms']:.1f}ms  p99={result['p99_ms']:.1f}ms  ({result['n_ok']}/{result.get('n_err',0)+result['n_ok']} ok)")

    # Concurrent test
    concurrent = run_concurrent_test(2)
    concurrent2 = run_concurrent_test(4)

    # Summary
    print(f"\n{'='*60}")
    print("API BENCHMARK SUMMARY")
    print(f"{'='*60}")
    print(f"{'Endpoint':<45} {'Mean':>8} {'p50':>8} {'p95':>8} {'p99':>8}")
    print("-" * 77)
    for r in results:
        if "error" in r:
            print(f"  {r['method']} {r['path']:<42} {'ERROR':>8}")
        else:
            print(f"  {r['method']} {r['path']:<42} {r['mean_ms']:>7.1f} {r['median_ms']:>7.1f} {r['p95_ms']:>7.1f} {r['p99_ms']:>7.1f}")

    report = {
        "timestamp": TS,
        "target": BASE_URL,
        "n_samples": N_SAMPLES,
        "endpoints": results,
        "concurrent": {
            "2_tables": concurrent,
            "4_tables": concurrent2,
        },
    }

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
