"""task_bridge (REAL) — full robot WS client: dispatcher tasks → tarkbot Nav2 motion.

Real-robot twin of ``ai_sim_bridge.task_bridge``. The WS link, heartbeat, and task
lifecycle are IDENTICAL to the sim bridge (transport-agnostic); only the motion layer
differs — it drives the real tarkbot Nav2 stack (RTAB-Map localization) via
``tarkbot_robot.visual_delivery`` instead of the Gazebo TurtleBot4 pipeline.

Contract (same one scripts/mock_robot.py fakes and the dispatcher expects):
    server → robot : task.assign {task_id, kind, table_id}   ·  task.release {table_id}
    robot → server : task_accepted / arrived / task_done {task_id}   ·  at_dock
                     heartbeat {robot_id, battery, x, y}   (map frame)

Task lifecycle:
  * ``go_to_table`` / ``call`` — drive to the table, report ``arrived``, then WAIT
    there until the server sends ``task.release``, then ``task_done`` and head back to
    the dock. Nothing else ends that wait: the robot holds the table's microphone while
    it is parked, so it stays put for the whole visit and the server releases it when the
    bill is settled (backend ``settings.release_robot_on_order`` flips that to "leave as
    soon as the order is placed").
  * ``deliver`` — drive to the table, ``arrived``, pause a few seconds, ``task_done``,
    head back to the dock.

Demo floor (2026-07-22): one surveyed table — Table 1 = ArUco 1, dock = ArUco 6. The web still
offers six tables, so a task for an unsurveyed table is served at Table 1 (``default_table``);
the guest's real table id is untouched, only the physical destination collapses.

Run the whole real stack (localization → Nav2 → this bridge) with one command:
    ros2 launch ai_hw_bridge ai_waiter.launch.py server_host:=100.66.165.221:8000

Or this node alone, once localization + Nav2 are already up (`make hwbridge`):
    ros2 run ai_hw_bridge task_bridge --ros-args \
        -p server_host:=100.66.165.221:8000 -p robot_id:=robo-1
"""

import json
import queue
import threading
import time

import rclpy
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32
from tf2_ros import (
    LookupException,
    ConnectivityException,
    ExtrapolationException,
)

import websocket  # websocket-client

# Real-robot motion layer (Nav2 NavigateToPose + ArUco align) lives in tarkbot_robot.
# Same names as the sim's food_delivery so this file stays near-verbatim with ai_sim_bridge.
from tarkbot_robot.visual_delivery import (
    ArucoTracker,
    NavigatorReal,
    CMD_VEL_TOPIC,
    DESTINATIONS,
    deliver_to,
    load_floorplan,
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
        self._node = node  # any live node, for params + logging

        node.declare_parameter("server_host", "127.0.0.1:8000")
        node.declare_parameter("robot_id", "robo-1")
        node.declare_parameter("map_frame", "map")
        # base_footprint, not base_link: that is the frame the EKF, RTAB-Map and the Nav2 costmaps
        # all use on this robot (ekf.yaml base_link_frame, nav2_params robot_base_frame). Looking
        # up base_link would still resolve through the URDF, but this is the pose Nav2 controls.
        node.declare_parameter("base_frame", "base_footprint")
        node.declare_parameter("rate_hz", 5.0)  # heartbeat rate
        # Battery: the STM32 base (tarkbot robot_node) publishes pack VOLTAGE (std_msgs/Float32,
        # Volts) on `battery_topic`. The backend/panel expect a PERCENT (0-100) and the dispatcher
        # skips robots below MIN_BATTERY=20 — so we map Volts→% here. `battery` is the fallback %
        # streamed until the first voltage reading arrives.
        node.declare_parameter("battery", 100.0)
        node.declare_parameter("battery_topic", "/bat_vol")
        # Pack is a 3S Li-ion (12.6 V full / 10.5 V empty). Sending raw Volts instead would read
        # as "12%" < MIN_BATTERY server-side and the dispatcher would never pick us. Refine the
        # two numbers from a real `ros2 topic echo /bat_vol` full-to-empty run; no rebuild needed
        # (`-p battery_full_v:=...`).
        node.declare_parameter("battery_full_v", 12.6)
        node.declare_parameter("battery_empty_v", 10.5)
        # Waypoints. Empty = the packaged config/floorplan.json, which is the SAME file the backend
        # reads for its "nearest robot" scoring and the panel minimap — keep them in sync by
        # editing that file, not by copying numbers here.
        node.declare_parameter("floorplan_file", "")
        # This floor has ONE surveyed table (Table 1 = ArUco 1), but the web seats guests at any of
        # its six tables. A table with no waypoint of its own is served AT this one: the robot drives
        # to ArUco 1 while the server keeps the guest's REAL table id — that id is what binds the
        # tablet and the microphone, so the guest still talks to their own table. Set 0 to refuse
        # unknown tables instead (what you want once every table is surveyed).
        node.declare_parameter("default_table", 1)

        floorplan_file = node.get_parameter("floorplan_file").value
        loaded = load_floorplan(floorplan_file or None)
        self._default_table = int(node.get_parameter("default_table").value)
        fallback = (f" · bàn chưa có waypoint → phục vụ tại Table {self._default_table}"
                    if self._default_table else "")
        node.get_logger().info(
            f"waypoints from {loaded}: {', '.join(sorted(DESTINATIONS)) or '(none!)'}{fallback}")

        host = node.get_parameter("server_host").value
        self.robot_id = node.get_parameter("robot_id").value
        self.map_frame = node.get_parameter("map_frame").value
        self.base_frame = node.get_parameter("base_frame").value
        self.battery = float(node.get_parameter("battery").value)
        self._battery_full_v = float(node.get_parameter("battery_full_v").value)
        self._battery_empty_v = float(node.get_parameter("battery_empty_v").value)
        self._battery_v = None  # last raw voltage from the base; None until first reading
        self._hb_period = 1.0 / float(node.get_parameter("rate_hz").value)
        self.url = f"ws://{host}/ws?role=robot&robot_id={self.robot_id}"

        # Subscribe on the passed node (it spins in the executor) — store the latest pack voltage.
        battery_topic = node.get_parameter("battery_topic").value
        node.create_subscription(Float32, battery_topic, self._on_battery, 10)

        # TF map->base_link tracks the robot continuously (RTAB-Map map->odom + EKF
        # odom->base_link), matching the frame the panel minimap + dispatcher use.
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

    # ---------------------------------------------------------------- battery
    def _on_battery(self, msg: Float32) -> None:
        self._battery_v = float(msg.data)

    def _battery_pct(self) -> float:
        """Map the last pack voltage to 0-100%. Fall back to the fixed `battery` param until
        the first reading lands (avoids reporting 0% and being skipped by the dispatcher)."""
        if self._battery_v is None:
            return self.battery
        span = self._battery_full_v - self._battery_empty_v
        if span <= 0:
            return self.battery  # misconfigured range → fall back rather than divide-by-zero
        pct = (self._battery_v - self._battery_empty_v) / span * 100.0
        return max(0.0, min(100.0, pct))

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
        """Stream battery every tick, plus map-frame pose WHEN localization is up.

        Battery is sent even before a `map->base_link` TF exists, so the panel shows the robot
        alive + charge % as soon as the base (STM32) is publishing `bat_vol` — the minimap dot
        (x, y) fills in later once localization/nav is running. The backend tolerates a heartbeat
        with no x/y (dispatcher.on_heartbeat uses msg.get + DB COALESCE)."""
        while rclpy.ok():
            time.sleep(self._hb_period)
            if not self._connected.is_set():
                continue
            hb = {
                "type": "heartbeat",
                "robot_id": self.robot_id,
                "battery": self._battery_pct(),
            }
            try:
                tf = self._tf_buffer.lookup_transform(
                    self.map_frame, self.base_frame, rclpy.time.Time()
                )
                hb["x"] = tf.transform.translation.x
                hb["y"] = tf.transform.translation.y
            except (LookupException, ConnectivityException, ExtrapolationException):
                now = time.monotonic()
                if now - self._last_notf_warn >= 5.0:
                    self._last_notf_warn = now
                    self._log().warn(
                        f"No TF {self.map_frame}->{self.base_frame} yet — sending battery only "
                        f"(pose fills in when localization runs)"
                    )
            self._send(hb)

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

    def _resolve_dest(self, table_id, task_id) -> str | None:
        """Which floorplan waypoint serves this table — None if we cannot serve it at all.

        Only surveyed tables have a waypoint; the rest fall back to `default_table` (see the
        parameter). The fallback is physical only — the *task* keeps the guest's real table id
        everywhere it matters (arrived/task_done, the tablet, the microphone binding).
        """
        name = f"Table {table_id}"
        if name in DESTINATIONS:
            return name
        fallback = f"Table {self._default_table}" if self._default_table else ""
        if fallback not in DESTINATIONS:
            self._log().error(
                f"task {task_id}: bàn {table_id} không có waypoint và không có bàn mặc định "
                f"(known: {sorted(DESTINATIONS)}) — bỏ qua")
            return None
        self._log().info(
            f"task {task_id}: bàn {table_id} chưa khảo sát → chạy tới {fallback} (demo một bàn)")
        return fallback

    def _run_task(self, task: dict) -> None:
        task_id = task.get("task_id")
        kind = task.get("kind", "go_to_table")
        table_id = task.get("table_id")
        dest_name = self._resolve_dest(table_id, task_id)
        if dest_name is None:
            # Nowhere to drive. Close the task anyway — dropping it silently would leave it
            # ASSIGNED forever in the panel's queue, and the dispatcher would never free us for
            # the next one. `at_dock` because we never left (the server only acts on it while we
            # are 'returning', so a stale frame is harmless).
            self._send({"type": "task_done", "task_id": task_id})
            self._send({"type": "at_dock"})
            return

        self._release.clear()
        self._send({"type": "task_accepted", "task_id": task_id})

        # Nav2 approach + ArUco align on the table's marker (skipped for tables whose marker is
        # not printed yet — see floorplan.json).
        if not deliver_to(self._nav, dest_name, self._tracker, self._cmd_pub):
            # Never report `arrived` for a drive that failed: `arrived` is what binds the table's
            # microphone to this robot, and binding a robot that is not at the table would send the
            # guest's voice to an empty seat. The contract has no "task failed" frame, so close the
            # task (it would otherwise sit IN_PROGRESS forever) and go home.
            self._log().error(
                f"task {task_id}: could not reach {dest_name} — closing task and returning to dock. "
                f"(visual_delivery already accepts a near-goal arrival, so this means Nav2 gave up "
                f"far from the waypoint: check localization and the path, not the goal tolerances.)")
            self._send({"type": "task_done", "task_id": task_id})
            return_to_dock(self._nav, self._tracker, self._cmd_pub)
            self._send({"type": "at_dock"})
            return

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

        # Head home unless the dispatcher already queued our next job.
        if self._tasks.empty():
            return_to_dock(self._nav, self._tracker, self._cmd_pub)
            self._send({"type": "at_dock"})


def main(args=None) -> None:
    rclpy.init(args=args)

    nav = NavigatorReal()
    tracker = ArucoTracker()
    cmd_pub = nav.create_publisher(Twist, CMD_VEL_TOPIC, 10)

    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(tracker)
    threading.Thread(target=executor.spin, daemon=True).start()

    bridge = TaskBridge(nav, tracker, cmd_pub, tracker)

    try:
        # Same boot as the sim bridge: set the initial pose and wait for Nav2 active.
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
