"""Mock test đơn giản: server có điều khiển đúng cái simulation không?

Chạy trên server (orchestrator phải đang chạy trên :8000, ví dụ `make backend`):
    uv run python scripts/mock_check_server.py
    uv run python scripts/mock_check_server.py --orch-url http://192.168.1.10:8000

Script tự spawn một con robot ảo (scripts/mock_robot.py) nên bạn KHÔNG cần chạy gì khác.
Các kịch bản mô phỏng đúng câu lệnh của người vận hành:

  K1. "đi tới khu A"                     -> robot chạy tới (6,6), task DONE
  K2. "đi tới khu A" -> 3s -> "dừng lại" -> task A CANCELLED, robot dừng (holding), KHÔNG tới A
      rồi "đổi sang khu B"               -> robot chạy tới (6,0), task DONE

Server -> robot contract đang được kiểm:
  * POST /navigation {token}     -> WS task.assign(pose)  -> robot lái tới pose
  * POST /tasks/cancel {robot_id}-> WS task.cancel        -> robot abort, đứng yên
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

# Tọa độ đích kỳ vọng (khung bản đồ kho). Phải khớp assets/data/warehouse_layout.json.
TARGETS = {"A": (6.0, 6.0), "B": (6.0, 0.0), "C": (6.0, -6.0), "D": (0.0, 6.0), "dock": (0.0, 0.0)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Mock test: server có điều khiển đúng simulation?")
    ap.add_argument("--orch-url", default="http://127.0.0.1:8000", help="Orchestrator base URL")
    ap.add_argument("--robot-id", default=ROBOT_ID)
    ap.add_argument("--no-spawn", action="store_true", help="Không spawn mock_robot (bạn tự chạy)")
    args = ap.parse_args()

    base = args.orch_url.rstrip("/")
    robot_id = args.robot_id

    # 1) server sống không?
    try:
        httpx.get(f"{base}/health", timeout=5).raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] orchestrator không reachable ở {base} — chạy `make backend` trước.\n  {e}")
        return 1

    # 2) spawn robot ảo (trừ khi bạn tự chạy)
    proc = None
    if not args.no_spawn:
        p = urlparse(base)
        host = p.hostname or "127.0.0.1"
        port = p.port or 8000
        mock = REPO / "scripts" / "mock_robot.py"
        print(f"[setup] spawn robot ảo: {mock.name} --id {robot_id} --host {host} --port {port}")
        proc = subprocess.Popen(
            [sys.executable, str(mock), "--id", robot_id, "--host", host, "--port", str(port)],
            cwd=str(REPO),
        )
        # đợi robot online (offline -> idle)
        for _ in range(40):
            try:
                st = next((x["status"] for x in httpx.get(f"{base}/robots", timeout=5).json()
                           if x["id"] == robot_id), "offline")
                if st != "offline":
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.5)

    client = httpx.Client(base_url=base, timeout=15)
    results: list[tuple[str, bool, str]] = []

    def navigate(token: str) -> int:
        return client.post("/navigation", json={"token": token}).json()["id"]

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

    def wait_until(tid: int, want, timeout: float = 45.0) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            t = task(tid)
            if t and t["status"] in want:
                return t
            time.sleep(0.3)
        return task(tid)

    def wait_idle(timeout: float = 45.0) -> bool:
        """Đợi robot về hẳn dock và ở trạng thái idle trước kịch bản mới.

        Quan trọng: nếu không đợi, robot còn đang lái về dock (status 'returning')
        thì lệnh navigate tiếp theo sẽ bị bắt đi ngay và có khi tới nơi trước khi
        ta kịp bấm 'dừng lại' — làm kịch bản cancel thành vô nghĩa.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if robot().get("status") == "idle":
                return True
            time.sleep(0.3)
        return False

    def wait_pose(target: str, timeout: float = 45.0):
        """Poll pose robot; trả về (x, y, min_dist_to_target).

        Lấy min_dist chứ không phải pose cuối, vì sau khi tới đích robot lái về dock,
        nên pose cuối sẽ là (0,0). min_dist chứng minh nó thực sự ghé qua đích.
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
            time.sleep(0.25)
        return last[0], last[1], min_d

    def banner(t: str) -> None:
        print("\n" + "=" * 70 + f"\n  {t}\n" + "=" * 70)

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))

    try:
        # ---- K1: đi tới khu A ----
        banner("K1: 'đi tới khu A'  → robot phải chạy tới (6,6)")
        tid = navigate("A")
        print(f"  POST /navigation {{token:A}}  → task {tid}")
        pos = wait_pose("A")
        t = wait_until(tid, {"DONE", "CANCELLED"}, timeout=45)
        ok = t is not None and t["status"] == "DONE" and pos[2] < 0.7
        check("khu A: robot tới (6,6) & task DONE", ok,
              f"min_dist={pos[2]:.2f} status={t['status'] if t else '?'}")

        # ---- K2: A -> 3s -> "dừng lại" -> đổi sang B ----
        # Đợi robot về dock/idle sau K1, nếu không nó sẽ đi tiếp luôn trước khi ta kịp "dừng lại".
        wait_idle()
        banner("K2: 'đi tới khu A' → 3s → 'dừng lại' → 'đổi sang khu B'")
        tid_a = navigate("A")
        print(f"  POST /navigation {{token:A}}  → task {tid_a}")
        time.sleep(3)  # người vận hành chờ 3s rồi nói "dừng lại"
        cancel()
        print("  POST /tasks/cancel  → task A CANCELLED, robot dừng")
        t_a = wait_until(tid_a, {"CANCELLED"}, timeout=20)
        r = robot()
        aborted = r.get("status") in ("holding", "idle")  # không còn lái tới A
        d_a = ((r.get("x") or 0) - TARGETS["A"][0]) ** 2 + ((r.get("y") or 0) - TARGETS["A"][1]) ** 2
        d_a = d_a ** 0.5
        ok_stop = t_a is not None and t_a["status"] == "CANCELLED" and aborted and d_a > 3.0
        check("dừng lại: A CANCELLED, robot dừng (chưa tới A)", ok_stop,
              f"A={t_a['status'] if t_a else '?'} robot={r.get('status')} dist_to_A={d_a:.2f}")

        tid_b = navigate("B")
        print(f"  POST /navigation {{token:B}}  → task {tid_b}")
        pos = wait_pose("B")
        t_b = wait_until(tid_b, {"DONE", "CANCELLED"}, timeout=45)
        ok_b = t_b is not None and t_b["status"] == "DONE" and pos[2] < 0.7
        check("đổi sang B: robot tới (6,0) & task DONE", ok_b,
              f"min_dist={pos[2]:.2f} status={t_b['status'] if t_b else '?'}")

    finally:
        client.close()
        if proc is not None:
            print("\n[cleanup] dừng robot ảo")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001
                proc.kill()

    banner("KẾT QUẢ")
    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n  {passed}/{len(results)} kịch bản PASS")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
