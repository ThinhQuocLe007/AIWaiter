"""task_bridge (SIM) — full robot WS client: dispatcher tasks → Nav2/ArUco motion in Gazebo.

This supersedes ``pose_bridge`` (telemetry-only) by speaking the complete robot contract the
backend dispatcher expects (the same one ``scripts/mock_robot.py`` fakes):

    server → robot : task.assign {task_id, kind, table_id}   ·  task.release {table_id}
    robot → server : task_accepted / arrived / task_done {task_id}
                     heartbeat {battery, x, y}   (map frame, battery fixed 100% in sim)

The physical execution reuses the tuned delivery pipeline from
``turtlebot4_python_tutorials.food_delivery`` (Nav2 approach pose → ArUco search/align →
opportunistic AMCL correction) — exactly what the interactive menu in that script drives,
but commanded by the dispatcher instead of a human typing numbers.

Task lifecycle mirrors the mock robot:
  * ``go_to_table`` / ``call`` — drive to the table, report ``arrived``, then WAIT there
    (serving the guest) until the server sends ``task.release`` (the guest ordered or paid).
    Only then report ``task_done`` and head back to the dock.
  * ``deliver`` — drive to the table, report ``arrived``, pause a few seconds for the guest
    to take the food, report ``task_done``, head back to the dock.

A task assigned while we're still driving home is queued and starts as soon as the robot
is free (the dispatcher marks us idle on ``task_done``, so this window is real).

Run (after `colcon build` + sourcing, with Gazebo + Nav2 up — replaces pose_bridge):
    ros2 run ai_sim_bridge task_bridge --ros-args \
        -p server_host:=127.0.0.1:8000 -p robot_id:=robo-1
"""

import json
import queue
import threading
import time

import rclpy
from geometry_msgs.msg import Twist
from tf2_ros import (
    LookupException,
    ConnectivityException,
    ExtrapolationException,
)

import websocket  # websocket-client

# The tuned delivery pipeline (Nav2 + ArUco search/align + AMCL correction) lives in the
# tutorials package; we drive it from dispatcher tasks instead of the interactive menu.
from turtlebot4_python_tutorials.food_delivery import (
    ArucoTracker,
    NavigatorWithSim,
    CMD_VEL_TOPIC,
    DESTINATIONS,
    deliver_to,
    return_to_dock,
    startup_sequence,
)

DELIVER_SERVE_SECONDS = 5.0  # deliver task: pause at the table for the guest to take the food


class TaskBridge:
    """Owns the WS link + heartbeat thread; the caller's main thread runs `work_loop()`."""

    def __init__(self, nav, tracker, cmd_pub, node) -> None:
        self._nav = nav
        self._tracker = tracker
        self._cmd_pub = cmd_pub
        self._node = node  # any live node, for params + logging (the tracker)

        node.declare_parameter("server_host", "127.0.0.1:8000")
        node.declare_parameter("robot_id", "robo-1")
        node.declare_parameter("map_frame", "map")
        node.declare_parameter("base_frame", "base_link")
        node.declare_parameter("rate_hz", 5.0)  # heartbeat rate
        node.declare_parameter("battery", 100.0)  # sim has no battery → fixed 100%

        host = node.get_parameter("server_host").value
        self.robot_id = node.get_parameter("robot_id").value
        self.map_frame = node.get_parameter("map_frame").value
        self.base_frame = node.get_parameter("base_frame").value
        self.battery = float(node.get_parameter("battery").value)
        self._hb_period = 1.0 / float(node.get_parameter("rate_hz").value)
        self.url = f"ws://{host}/ws?role=robot&robot_id={self.robot_id}"

        # TF map->base_link tracks the robot continuously (AMCL), matching the frame the panel
        # minimap + dispatcher waypoints use. The ArUco tracker already keeps a TF buffer alive
        # (it spins in the executor) — reuse it instead of opening a second /tf subscription.
        self._tf_buffer = tracker.tf_buffer

        self._ws = None
        self._ws_lock = threading.Lock()
        self._connected = threading.Event()
        self._tasks: queue.Queue[dict] = queue.Queue()
        # "Guest is done" gate for the task currently being served, set by task.release.
        self._release = threading.Event()
        self._last_notf_warn = 0.0

        threading.Thread(target=self._ws_loop, daemon=True).start()
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

    # ---------------------------------------------------------------- WS plumbing
    def _log(self):
        return self._node.get_logger()

    def _send(self, payload: dict) -> None:
        with self._ws_lock:
            ws = self._ws
        if ws is None:
            return
        try:
            ws.send(json.dumps(payload))
        except Exception as e:  # noqa: BLE001 — link drop; the ws loop reconnects
            self._log().warn(f"WS send failed ({payload.get('type')}): {e}")
            self._connected.clear()

    def _ws_loop(self) -> None:
        def on_open(_ws):
            self._connected.set()
            self._log().info(f"WS connected → {self.url}")

        def on_close(_ws, *_a):
            self._connected.clear()
            self._log().warn("WS closed — reconnecting")

        def on_error(_ws, err):
            self._log().warn(f"WS error: {err}")

        def on_message(_ws, raw):
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                self._log().warn(f"bad WS frame: {raw[:200]}")
                return
            mtype = msg.get("type")
            if mtype == "task.assign":
                self._log().info(
                    f"task.assign #{msg.get('task_id')} {msg.get('kind')} → bàn {msg.get('table_id')}"
                )
                self._tasks.put(msg)
            elif mtype == "task.release":
                # Guest ordered / paid → let the waiting task finish and leave the table.
                self._log().info(f"task.release (bàn {msg.get('table_id')})")
                self._release.set()

        while rclpy.ok():
            app = websocket.WebSocketApp(
                self.url,
                on_open=on_open,
                on_close=on_close,
                on_error=on_error,
                on_message=on_message,
            )
            with self._ws_lock:
                self._ws = app
            try:
                app.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:  # noqa: BLE001 — never let the WS thread die
                self._log().warn(f"WS loop error: {e}")
            self._connected.clear()
            time.sleep(2.0)

    def _heartbeat_loop(self) -> None:
        """Stream map-frame pose + fixed battery. Runs for the whole process life — the panel
        minimap dot must track the robot while idle, driving, and serving alike."""
        while rclpy.ok():
            time.sleep(self._hb_period)
            if not self._connected.is_set():
                continue
            try:
                tf = self._tf_buffer.lookup_transform(
                    self.map_frame, self.base_frame, rclpy.time.Time()
                )
            except (LookupException, ConnectivityException, ExtrapolationException):
                now = time.monotonic()
                if now - self._last_notf_warn >= 5.0:
                    self._last_notf_warn = now
                    self._log().warn(
                        f"No TF {self.map_frame}->{self.base_frame} yet — waiting for AMCL"
                    )
                continue
            self._send(
                {
                    "type": "heartbeat",
                    "robot_id": self.robot_id,
                    "battery": self.battery,
                    "x": tf.transform.translation.x,
                    "y": tf.transform.translation.y,
                }
            )

    # ---------------------------------------------------------------- task execution
    def work_loop(self) -> None:
        """Blocking task loop (call from the main thread — Nav2 actions run here)."""
        self._log().info("task_bridge ready — waiting for dispatcher tasks")
        while rclpy.ok():
            try:
                task = self._tasks.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._run_task(task)
            except Exception as e:  # noqa: BLE001 — one bad task must not kill the bridge
                self._log().error(f"task {task.get('task_id')} failed: {e}")

    def _run_task(self, task: dict) -> None:
        task_id = task.get("task_id")
        kind = task.get("kind", "go_to_table")
        table_id = task.get("table_id")
        dest_name = f"Table {table_id}"
        if dest_name not in DESTINATIONS:
            self._log().error(f"task {task_id}: unknown table {table_id} — ignoring")
            return

        self._release.clear()
        self._send({"type": "task_accepted", "task_id": task_id})

        # Nav2 approach + ArUco search/align — the whole tuned pipeline from food_delivery.
        deliver_to(self._nav, dest_name, self._tracker, self._cmd_pub)
        self._send({"type": "arrived", "task_id": task_id})

        if kind in ("go_to_table", "call"):
            # Serve the guest: park at the table (heartbeats keep flowing) until the server
            # says the visit step is over (guest placed an order / paid) via task.release.
            self._log().info(f"Đang phục vụ bàn {table_id} — chờ khách đặt món / thanh toán…")
            while rclpy.ok() and not self._release.wait(timeout=0.5):
                pass
        else:  # deliver — hand the food over and leave on our own
            time.sleep(DELIVER_SERVE_SECONDS)

        self._send({"type": "task_done", "task_id": task_id})

        # Head home unless the dispatcher already queued our next job (we're idle server-side
        # from task_done on, so a new task can land while we'd be driving back).
        if self._tasks.empty():
            return_to_dock(self._nav, self._tracker, self._cmd_pub)


def main(args=None) -> None:
    rclpy.init(args=args)

    nav = NavigatorWithSim()
    tracker = ArucoTracker()
    cmd_pub = nav.create_publisher(Twist, CMD_VEL_TOPIC, 10)

    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(tracker)
    threading.Thread(target=executor.spin, daemon=True).start()

    bridge = TaskBridge(nav, tracker, cmd_pub, tracker)

    try:
        # Same boot as food_delivery: set the initial pose at the dock and wait for Nav2.
        startup_sequence(nav, tracker, cmd_pub)
        bridge.work_loop()
    except KeyboardInterrupt:
        nav.info("Interrupted by user.")
    finally:
        if rclpy.ok():
            try:
                cmd_pub.publish(Twist())
            except Exception:  # noqa: BLE001 — already shutting down
                pass
            tracker.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    main()
