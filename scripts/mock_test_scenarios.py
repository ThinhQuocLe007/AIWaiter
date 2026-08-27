"""Mock test: does the server actually drive the simulation? (no voice needed)

Starts a simulated robot (scripts/mock_robot.py) and plays scripted warehouse
scenarios by talking to the orchestrator's REST API directly (the same calls the
brain makes after understanding speech). It then WATCHES the simulated robot's
live pose to prove the server really controls it — not just that DB rows flip.

Run (orchestrator must already be up on :8000, e.g. `make backend`):
    uv run python scripts/mock_test_scenarios.py
    uv run python scripts/mock_test_scenarios.py --orch-url http://192.168.1.10:8000

This is the "kịch bản" counterpart of the voice demo: same outcomes, no mic.

Server -> robot contract under test:
  * navigate X      -> POST /navigation            -> WS task.assign (pose)
  * hủy / stop      -> POST /tasks/cancel          -> WS task.cancel (abort)
  * new destination -> POST /navigation            -> preempt + task.assign (latest wins)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

REPO = Path(__file__).resolve().parents[1]
ROBOT_ID = "robo-1"

# Expected goal poses (server frame). Keep in sync with assets/data/warehouse_layout.json.
TARGETS = {
    "A": (6.0, 6.0),
    "B": (6.0, 0.0),
    "C": (6.0, -6.0),
    "D": (0.0, 6.0),
    "dock": (0.0, 0.0),
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Mock test: server controls the simulation (no voice).")
    ap.add_argument("--orch-url", default="http://127.0.0.1:8000", help="Orchestrator base URL")
    ap.add_argument("--robot-id", default=ROBOT_ID)
    ap.add_argument("--no-spawn", action="store_true", help="Don't launch mock_robot (you run it)")
    args = ap.parse_args()

    base = args.orch_url.rstrip("/")  # httpx base_url must not end with /
    robot_id = args.robot_id

    # 1) orchestrator up?
    try:
        httpx.get(f"{base}/health", timeout=5).raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] orchestrator not reachable at {base} — chạy `make backend` trước.\n  {e}")
        return 1

    # 2) launch the simulated robot (unless the user runs their own)
    proc = None
    if not args.no_spawn:
        p = urlparse(base)
        host = p.hostname or "127.0.0.1"
        port = p.port or 8000
        mock = REPO / "scripts" / "mock_robot.py"
        print(f"[setup] launching simulated robot: {mock.name} --id {robot_id} --host {host} --port {port}")
        proc = subprocess.Popen(
            [sys.executable, str(mock), "--id", robot_id, "--host", host, "--port", str(port)],
            cwd=str(REPO),
        )
        # wait for it to connect (status flips from offline -> idle)
        for _ in range(30):
            try:
                r = httpx.get(f"{base}/robots", timeout=5).json()
                st = next((x["status"] for x in r if x["id"] == robot_id), "offline")
                if st != "offline":
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)

    client = httpx.Client(base_url=base, timeout=15)
    results: list[tuple[str, bool, str]] = []

    def navigate(token: str) -> int:
        resp = client.post("/navigation", json={"token": token}).json()
        return resp["id"]

    def cancel() -> None:
        client.post("/tasks/cancel", json={"robot_id": robot_id})

    def robot() -> dict:
        for r in client.get("/robots").json():
            if r["id"] == robot_id:
                return r
        return {}

    def task(tid: int) -> dict | None:
        for t in client.get("/tasks").json():
            if t["id"] == tid:
                return t
        return None

    def wait_until(tid: int, want, timeout: float = 40.0) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            t = task(tid)
            if t and t["status"] in want:
                return t
            time.sleep(0.3)
        return task(tid)

    def wait_pose(target, timeout: float = 45.0):
        """Poll the robot's live pose; return (final_x, final_y, min_dist_to_target).

        We track the *minimum* distance rather than requiring the final pose to be at the goal,
        because after arriving the robot drives back to the dock — so the final sample would be
        (0,0). The min distance proves it actually visited the target.
        """
        tx, ty = TARGETS[target]
        deadline = time.time() + timeout
        min_d = 1e9
        last = (None, None)
        while time.time() < deadline:
            r = robot()
            x, y = r.get("x"), r.get("y")
            last = (x, y)
            if x is not None and y is not None:
                d = ((x - tx) ** 2 + (y - ty) ** 2) ** 0.5
                min_d = min(min_d, d)
                if d < 0.7:
                    return x, y, min_d
            time.sleep(0.4)
        return last[0], last[1], min_d

    def banner(title: str) -> None:
        print("\n" + "=" * 72 + f"\n  {title}\n" + "=" * 72)

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    try:
        # ---- Kịch bản 1: đi tới khu A ----
        banner("KỊCH BẢN 1: 'đi tới khu A'  → robot phải chạy tới (6,6)")
        tid = navigate("A")
        print("  gửi POST /navigation {token:A}  → task", tid)
        pos = wait_pose("A")
        t = wait_until(tid, {"DONE", "CANCELLED"}, timeout=45)
        ok = t is not None and t["status"] == "DONE" and pos[2] < 0.7
        check(f"khu A: robot tới (6,6) & task DONE", ok, f"min_dist={pos[2]:.2f} status={t['status'] if t else '?'}")

        # ---- Kịch bản 2: đi tới khu B ----
        banner("KỊCH BẢN 2: 'đi tới khu B'  → robot chạy tới (6,0)")
        tid = navigate("B")
        pos = wait_pose("B")
        t = wait_until(tid, {"DONE", "CANCELLED"}, timeout=45)
        ok = t is not None and t["status"] == "DONE" and pos[2] < 0.7
        check(f"khu B: robot tới (6,0) & task DONE", ok, f"min_dist={pos[2]:.2f} status={t['status'] if t else '?'}")

        # ---- Kịch bản 3: đang đi A… đổi ý… đi C (preempt) ----
        banner("KỊCH BẢN 3: đang đi A… 'đi tới khu C'  → A bị hủy, robot quẹo sang C")
        tid_a = navigate("A")
        time.sleep(1.5)  # let it start driving
        tid_c = navigate("C")  # new destination while A in flight
        print("  gửi A rồi C  → mong A CANCELLED, C ASSIGNED và robot tới C")
        pos = wait_pose("C")
        t_a = wait_until(tid_a, {"CANCELLED"}, timeout=20)
        t_c = wait_until(tid_c, {"DONE", "CANCELLED"}, timeout=45)
        ok = (t_a and t_a["status"] == "CANCELLED" and t_c and t_c["status"] == "DONE"
              and pos[2] < 0.7)
        check("preempt: A CANCELLED, C DONE, robot tới (6,-6)", ok,
              f"A={t_a['status'] if t_a else '?'} C={t_c['status'] if t_c else '?'} min_dist={pos[2]:.2f}")

        # ---- Kịch bản 4: đi A rồi 'hủy' ----
        banner("KỊCH BẢN 4: đi A… 'hủy'  → task CANCELLED, robot dừng (holding)")
        tid = navigate("A")
        time.sleep(1.5)
        cancel()
        print("  gửi POST /tasks/cancel  → task CANCELLED, robot không tới A")
        t = wait_until(tid, {"CANCELLED"}, timeout=20)
        time.sleep(1.0)
        r = robot()
        aborted = r.get("status") in ("holding", "idle")  # not still driving to A
        ok = t is not None and t["status"] == "CANCELLED" and aborted
        check("hủy: task CANCELLED & robot dừng (không tới A)", ok,
              f"status={t['status'] if t else '?'} robot={r.get('status')} pos=({r.get('x')},{r.get('y')})")

    finally:
        client.close()
        if proc is not None:
            print("\n[cleanup] stopping simulated robot")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()

    # ---- summary ----
    banner("KẾT QUẢ MOCK TEST")
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n  {passed}/{len(results)} kịch bản PASS")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
