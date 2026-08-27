"""Integration test: cancel + preempt for warehouse navigation tasks.

Drives the *real* orchestrator stack (Dispatcher + WS hub + routers) in-process
via FastAPI's TestClient, using a temp SQLite DB per test, and a WebSocket
"robot" to receive the `task.assign` frames the dispatcher pushes.

Scenario covered:
  1. drive to A  -> task ASSIGNED, robot gets task.assign(A)
  2. "dừng lại"  -> POST /tasks/cancel -> task A CANCELLED, robot HOLDING
  3. drive to B  -> task B ASSIGNED to the same robot (preempt), robot gets task.assign(B)
  4. a late task_done for the cancelled A is ignored (guard) — A stays CANCELLED
  5. (separate test) skipping the explicit stop: drive to A then drive to C
     preempts A automatically.

This locks in the "latest task.assign wins" behaviour without touching the
Gazebo machine.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Make `src` importable when run directly (pytest's conftest normally does this).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Default throwaway DB before the app imports config (overridden per-test anyway).
os.environ.setdefault("ORCH_DB_PATH", os.path.join(tempfile.mkdtemp(), "orchestrator.db"))

from fastapi.testclient import TestClient  # noqa: E402

from src.server_orchestrator.config import settings  # noqa: E402
from src.server_orchestrator.data.db import init_db  # noqa: E402
from src.server_orchestrator.main import app  # noqa: E402
from src.server_orchestrator.services.menu_loader import seed_robots  # noqa: E402


def make_client() -> TestClient:
    """A TestClient backed by a brand-new SQLite DB (isolated per test)."""
    settings.db_path = Path(tempfile.mkdtemp()) / "orchestrator.db"
    init_db()
    seed_robots()
    return TestClient(app)


def _tasks(client: TestClient) -> dict[int, dict]:
    return {t["id"]: t for t in client.get("/tasks").json()}


def _robot_status(client: TestClient, robot_id: str) -> str:
    for r in client.get("/robots").json():
        if r["id"] == robot_id:
            return r["status"]
    raise AssertionError(f"robot {robot_id} not found")


def test_stop_then_new_goal_preempts():
    with make_client() as client, client.websocket_connect(
        "/ws?role=robot&robot_id=robo-1"
    ) as robot:
        # 1) drive to A
        resp_a = client.post("/navigation", json={"token": "A"})
        assert resp_a.status_code == 201, resp_a.text
        task_a = resp_a.json()["id"]
        frame_a = robot.receive_json()
        assert frame_a["type"] == "task.assign"
        assert frame_a["target_token"] == "A"

        # 2) operator says "dừng lại" -> cancel current task
        cancel = client.post("/tasks/cancel", json={"robot_id": "robo-1"})
        assert cancel.status_code == 200, cancel.text
        assert _tasks(client)[task_a]["status"] == "CANCELLED"
        # robot is freed (holding) and immediately reassignable
        assert _robot_status(client, "robo-1") == "holding"

        # 3) drive to B -> preempts A, reassigns the same robot
        resp_b = client.post("/navigation", json={"token": "B"})
        assert resp_b.status_code == 201, resp_b.text
        task_b = resp_b.json()["id"]
        frame_b = robot.receive_json()
        assert frame_b["type"] == "task.assign"
        assert frame_b["target_token"] == "B"

        tasks = _tasks(client)
        assert tasks[task_a]["status"] == "CANCELLED"
        assert tasks[task_b]["status"] in ("ASSIGNED", "IN_PROGRESS")
        # only the new task is active; A did not resurrect
        active = [t for t in tasks.values() if t["status"] not in ("CANCELLED", "DONE")]
        assert active == [tasks[task_b]]

        # 4) a late task_done for the cancelled A must be ignored (callback guard)
        robot.send_json({"type": "task_done", "task_id": task_a})
        assert _tasks(client)[task_a]["status"] == "CANCELLED"


def test_preempt_without_explicit_stop():
    with make_client() as client, client.websocket_connect(
        "/ws?role=robot&robot_id=robo-1"
    ) as robot:
        # drive to A (no explicit stop this time)
        resp_a = client.post("/navigation", json={"token": "A"})
        task_a = resp_a.json()["id"]
        robot.receive_json()  # drain task.assign(A)

        # immediately drive to C -> should preempt A automatically
        resp_c = client.post("/navigation", json={"token": "C"})
        task_c = resp_c.json()["id"]
        frame_c = robot.receive_json()
        assert frame_c["target_token"] == "C"

        tasks = _tasks(client)
        assert tasks[task_a]["status"] == "CANCELLED"
        assert tasks[task_c]["status"] in ("ASSIGNED", "IN_PROGRESS")


def test_drive_a_stop_then_drive_b():
    """Scenario: đang đi tới khu A thì dừng, kêu đi tới khu B.

    "dừng lại" (STOP) is edge/UDP only -> the server keeps task A active (IN_PROGRESS),
    it does NOT cancel it. The new destination B then preempts and cancels A.
    """
    with make_client() as client, client.websocket_connect(
        "/ws?role=robot&robot_id=robo-1"
    ) as robot:
        resp_a = client.post("/navigation", json={"token": "A"})
        task_a = resp_a.json()["id"]
        robot.receive_json()  # task.assign(A)
        robot.send_json({"type": "task_accepted", "task_id": task_a})
        # after STOP: server task must still be active (hold, not cancel)
        assert _tasks(client)[task_a]["status"] == "IN_PROGRESS"

        resp_b = client.post("/navigation", json={"token": "B"})
        task_b = resp_b.json()["id"]
        frame_b = robot.receive_json()
        assert frame_b["target_token"] == "B"

        tasks = _tasks(client)
        assert tasks[task_a]["status"] == "CANCELLED"  # redirected away from A
        assert tasks[task_b]["status"] in ("ASSIGNED", "IN_PROGRESS")


def test_drive_a_stop_then_resume():
    """Scenario: đang đi tới khu A thì dừng, sau đó bảo đi tiếp.

    STOP keeps task A active; RESUME ("đi tiếp") is also edge/UDP, so the robot simply
    finishes A and reports task_done -> task A reaches DONE (not cancelled).
    """
    with make_client() as client, client.websocket_connect(
        "/ws?role=robot&robot_id=robo-1"
    ) as robot:
        resp_a = client.post("/navigation", json={"token": "A"})
        task_a = resp_a.json()["id"]
        robot.receive_json()  # task.assign(A)
        robot.send_json({"type": "task_accepted", "task_id": task_a})
        # after STOP: server task stays active (resumable)
        assert _tasks(client)[task_a]["status"] == "IN_PROGRESS"
        # "đi tiếp" (RESUME) -> robot completes A
        robot.send_json({"type": "arrived", "task_id": task_a})
        robot.send_json({"type": "task_done", "task_id": task_a})
        assert _tasks(client)[task_a]["status"] == "DONE"


if __name__ == "__main__":
    # Plain-runner so the test works without pytest installed (`uv run python tests/...`).
    test_stop_then_new_goal_preempts()
    test_preempt_without_explicit_stop()
    test_drive_a_stop_then_drive_b()
    test_drive_a_stop_then_resume()
    print("OK: cancel + preempt integration tests passed")
