"""Live demo: what signals the orchestrator pushes to the (simulated) robot.

Run:  uv run python scripts/demo_nav_signals.py

Spins up the real orchestrator in-process (temp DB) and a WebSocket "robot" that
prints every frame the server sends it. Drives the scenarios from the chat and
prints, for each step, the HTTP call + the server->robot signal + the resulting
task/robot state.

NOTE on the architecture (easy to misread):
  * Navigation goals  -> server --WS task.assign--> ROBOT (simulated machine).
  * Stop / turn words -> JETSON --UDP--> ROBOT  (server is NOT in this path).
So "dừng lại" / "đi thẳng" produce NO server->robot signal; the server only
reacts when a NEW destination is spoken (which preempts the old goal).
"""

from __future__ import annotations

import os
import sys
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("ORCH_DB_PATH", os.path.join(tempfile.mkdtemp(), "orchestrator.db"))

from fastapi.testclient import TestClient  # noqa: E402

from src.server_orchestrator.config import settings  # noqa: E402
from src.server_orchestrator.data.db import init_db  # noqa: E402
from src.server_orchestrator.main import app  # noqa: E402
from src.server_orchestrator.services.menu_loader import seed_robots  # noqa: E402

settings.db_path = Path(tempfile.mkdtemp()) / "orchestrator.db"
init_db()
seed_robots()
client = TestClient(app)


def line(c="="):
    print(c * 78)


def tasks():
    return {t["id"]: t for t in client.get("/tasks").json()}


def robot_state():
    for r in client.get("/robots").json():
        if r["id"] == "robo-1":
            return r["status"]
    return "?"


def nav(token: str):
    """Simulate the brain POSTing a navigation goal (what 'đi tới khu X' becomes)."""
    print(f"\n>> BRAIN -> POST /navigation  {{token: '{token}'}}")
    resp = client.post("/navigation", json={"token": token})
    print(f"   orchestrator: task {resp.json()['id']} created")


def cancel():
    print(f"\n>> PANEL/EDGE -> POST /tasks/cancel  {{robot_id: 'robo-1'}}  (lệnh 'hủy')")
    client.post("/tasks/cancel", json={"robot_id": "robo-1"})


def robot_recv(robot, label: str):
    """Read the frame the server just pushed to the robot and pretty-print it."""
    frame = robot.receive_json()
    print(f"   SERVER -> ROBOT (WS): {label}")
    print("      " + json.dumps(frame, ensure_ascii=False))


def status_dump():
    ts = tasks()
    print("   state -> robot:", robot_state(),
          "| tasks:", {tid: t["status"] for tid, t in sorted(ts.items())})


with client.websocket_connect("/ws?role=robot&robot_id=robo-1") as robot:
    line()
    print("SCENARIO 1: đi tới khu A")
    line()
    nav("A")
    robot_recv(robot, "task.assign (goal = khu A)")
    status_dump()

    line()
    print("SCENARIO 2: đang đi tới A thì dừng, kêu 'đi tới khu B'")
    line()
    print("   'dừng lại' -> JETSON --UDP--> ROBOT (server KHÔNG gửi gì; task A giữ IN_PROGRESS)")
    status_dump()
    nav("B")
    robot_recv(robot, "task.assign (goal = khu B)  -- A đã bị cancel/preempt")
    status_dump()

    line()
    print("SCENARIO 3: đang đi tới A thì dừng, sau đó bảo 'đi tiếp'")
    line()
    # fresh robot state
    nav("A")
    robot_recv(robot, "task.assign (goal = khu A)")
    robot.send_json({"type": "task_accepted", "task_id": max(tasks())})
    print("   'dừng lại' -> JETSON --UDP--> ROBOT (server: task A vẫn IN_PROGRESS, có thể resume)")
    status_dump()
    print("   'đi tiếp' -> JETSON --UDP--> ROBOT (server: không gửi gì; robot tiếp tục tới A)")
    # robot finishes A on its own
    aid = [t["id"] for t in tasks().values() if t["target_token"] == "A" and t["status"] != "CANCELLED"][-1]
    robot.send_json({"type": "arrived", "task_id": aid})
    robot.send_json({"type": "task_done", "task_id": aid})
    print("   ROBOT -> SERVER: arrived + task_done (A hoàn thành)")
    status_dump()

    line()
    print("SCENARIO 4 (hủy rõ ràng): đi tới khu A, rồi 'hủy'")
    line()
    nav("A")
    robot_recv(robot, "task.assign (goal = khu A)")
    cancel()
    status_dump()

    line()
    print("DONE — server->robot signals verified")
    line()
