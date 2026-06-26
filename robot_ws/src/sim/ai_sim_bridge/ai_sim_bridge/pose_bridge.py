"""pose_bridge (SIM) — stream the simulated robot's pose to the backend so the panel minimap moves.

This is the **simulation** bridge. The real-robot bridge lives separately under
`robot_ws/src/real/ai_hw_bridge` and will differ a lot (real battery from `/battery_state`, real
localization/hardware, safety, etc.). Keep the two apart on purpose.

Phase 1: telemetry only (no task handling yet). The whole receiving end already exists — the
backend WS hub takes `role=robot` heartbeats, fleet.py keeps the live pose in RAM, and the
dispatcher broadcasts `robot.updated` to the panel (throttled ~5 Hz). So this node only has to
read where the robot is and send heartbeats.

Coordinate frame (the part that's easy to get wrong): the panel minimap and the table waypoints
(dispatcher.TABLE_POS) live in the **saved SLAM map frame** (restaurant.pgm/.yaml), which is NOT
the Gazebo world frame. So we report the pose from the **`map` frame** — the TF `map -> base_link`
that Nav2/AMCL maintains — and it lines up with the scanned walls without any recalibration. (Using
`/odom` would be a different, drifting frame and the dot would land in the wrong place.)

Battery: the sim has no battery, so we send a fixed 100.0 (the backend uses a 0–100 scale).

Run (after `colcon build` + sourcing the workspace, with Gazebo + Nav2 already up):
    ros2 run ai_sim_bridge pose_bridge --ros-args \
        -p server_host:=127.0.0.1:8000 -p robot_id:=robo-1
"""

import json
import threading
import time

import rclpy
from rclpy.node import Node
from tf2_ros import (
    Buffer,
    TransformListener,
    LookupException,
    ConnectivityException,
    ExtrapolationException,
)

import websocket  # websocket-client: handles the WS handshake + ping/pong + masking for us


class PoseBridge(Node):
    def __init__(self) -> None:
        super().__init__("pose_bridge")

        # --- params (override with --ros-args -p name:=value) ---
        self.declare_parameter("server_host", "100.66.165.221:8000")  # backend host:port
        self.declare_parameter("robot_id", "robo-1")             # MUST match the seeded robots row
        self.declare_parameter("map_frame", "map")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("rate_hz", 5.0)                   # heartbeat rate
        self.declare_parameter("battery", 100.0)                 # sim has no battery → fake 100% (0–100 scale)

        host = self.get_parameter("server_host").get_parameter_value().string_value
        self.robot_id = self.get_parameter("robot_id").get_parameter_value().string_value
        self.map_frame = self.get_parameter("map_frame").get_parameter_value().string_value
        self.base_frame = self.get_parameter("base_frame").get_parameter_value().string_value
        self.battery = float(self.get_parameter("battery").value)
        rate = float(self.get_parameter("rate_hz").value)

        self.url = f"ws://{host}/ws?role=robot&robot_id={self.robot_id}"

        # TF gives us a continuous map->base_link pose even while the robot is idle (unlike
        # /amcl_pose, which only republishes on filter updates) — so the dot shows up at the
        # initial point and tracks every Nav2 move.
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        self._ws = None
        self._ws_lock = threading.Lock()
        self._connected = threading.Event()
        self._last_notf_warn = 0.0   # throttle the "no TF" warning
        self._last_pose_log = 0.0    # throttle the "sending pose" info log

        threading.Thread(target=self._ws_loop, daemon=True).start()
        self.create_timer(1.0 / rate, self._on_timer)
        self.get_logger().info(
            f"pose_bridge (sim) → {self.url}  (TF {self.map_frame}->{self.base_frame}, {rate:.0f} Hz)"
        )

    def _ws_loop(self) -> None:
        """Keep a WS connection to the backend alive, reconnecting on drop."""
        def on_open(_ws):
            self._connected.set()
            self.get_logger().info("WS connected to backend")

        def on_close(_ws, *_a):
            self._connected.clear()
            self.get_logger().warn("WS closed — will reconnect")

        def on_error(_ws, err):
            self.get_logger().warn(f"WS error: {err}")

        while rclpy.ok():
            app = websocket.WebSocketApp(
                self.url, on_open=on_open, on_close=on_close, on_error=on_error
            )
            with self._ws_lock:
                self._ws = app
            try:
                app.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:  # noqa: BLE001 — never let the WS thread die
                self.get_logger().warn(f"WS loop error: {e}")
            self._connected.clear()
            time.sleep(2.0)  # backoff before reconnecting

    def _on_timer(self) -> None:
        """Read map->base_link and push one heartbeat."""
        if not self._connected.is_set():
            return
        now = time.monotonic()
        try:
            tf = self._tf_buffer.lookup_transform(
                self.map_frame, self.base_frame, rclpy.time.Time()
            )
        except (LookupException, ConnectivityException, ExtrapolationException):
            # Keep reminding (throttled) so it's clear we're still waiting on localization, not
            # hung. Disappears the moment AMCL starts publishing map->base_link.
            if now - self._last_notf_warn >= 3.0:
                self._last_notf_warn = now
                self.get_logger().warn(
                    f"No TF {self.map_frame}->{self.base_frame} yet — is localization/Nav2 up "
                    "and the initial pose set (RViz '2D Pose Estimate')?"
                )
            return

        x = tf.transform.translation.x
        y = tf.transform.translation.y
        msg = json.dumps({
            "type": "heartbeat",
            "robot_id": self.robot_id,
            "battery": self.battery,
            "x": x,
            "y": y,
        })
        with self._ws_lock:
            ws = self._ws
        try:
            if ws is not None:
                ws.send(msg)
        except Exception as e:  # noqa: BLE001
            self.get_logger().warn(f"heartbeat send failed: {e}")
            self._connected.clear()
            return

        # Positive feedback in the terminal (throttled) so it's obvious the pose is flowing.
        if now - self._last_pose_log >= 2.0:
            self._last_pose_log = now
            self.get_logger().info(
                f"sending pose  x={x:.2f}  y={y:.2f}  battery={self.battery:.0f}%"
            )


def main(args=None) -> None:
    rclpy.init(args=args)
    node = PoseBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
