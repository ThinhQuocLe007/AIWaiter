#!/usr/bin/env python3
"""Laptop half of the command link: UDP datagram in, robot motion out.

Runs on the machine hosting Gazebo + Nav2 + V-JEPA, next to `warehouse_agv_demo`. It adds nothing
to that project and changes none of its logic — every action below drives it through an interface
it already exposes:

  stop      publish a zero Twist on ``/cmd_vel_keyboard`` at 20 Hz. ``keyboard_cmd_mux.py``
            documents "keyboard > Nav2" priority with a 0.12 s manual timeout, so holding that
            topic parks the AGV while its Nav2 goal stays alive.
  resume    stop publishing. The mux falls back to ``/cmd_vel_smoothed`` and the same goal
            continues — no replan, no re-issued mission.
  cancel    SIGINT the mission process group. ``storage_pick_mission.py`` keeps Python's
            KeyboardInterrupt handler specifically so Ctrl+C cancels the active Nav2 goal before
            shutting down; SIGINT is that path, reached from here instead of a terminal.
  navigate  run ``run_storage_pick.sh --storage <X> [--color <c>]``. A mission already running is
            cancelled first, which is what "đang đi thì bảo đi sang kệ khác" means.

Why NOT ``/warehouse/person_stop``, the other obvious brake: ``person_safety_monitor.py`` owns it
and republishes it on a 20 Hz timer from its own occupancy prediction. Anything written there by a
second publisher is overwritten within 50 ms, so a voice stop on that topic would look like it
worked and then quietly let go.

    python3 -m src.robot_link.bridge --demo-dir ../warehouse_agv_demo --bind 0.0.0.0:45455
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from src.robot_link import capabilities, parse_text, protocol
from src.robot_link.protocol import Command, Deduper, decode

logger = logging.getLogger("robot_link.bridge")

# Rate at which the stop hold re-asserts itself. Two constraints set it. keyboard_cmd_mux.py
# treats a manual command as stale after 0.12 s, so anything slower than ~10 Hz lets Nav2 back in
# between ticks. And on the second channel (see HOLD_TOPICS) we are outright racing another
# publisher that runs at 20 Hz, so we have to run several times faster than it to win.
HOLD_HZ = 50.0

# The AGV is driven from two different places and a stop has to reach both.
#
#   /cmd_vel_keyboard   Nav2's aisle driving. Goes through keyboard_cmd_mux, which documents
#                       "keyboard > Nav2" priority, so a zero here parks the robot cleanly while
#                       its Nav2 goal stays alive and "đi tiếp" resumes the same goal.
#
#   /cmd_vel            The camera-guided final approach at the shelf. vqa_mission.py:516 opens
#                       its own publisher straight onto /cmd_vel, downstream of the mux and of
#                       the collision monitor, so nothing on the first channel can reach it.
#
# Publishing zeros on /cmd_vel is safe during Nav2 driving too: the collision monitor is feeding
# that topic the mux's output, which the first channel has already forced to zero, so both
# publishers agree. During the pick the two disagree and it becomes a race — see _control().
HOLD_TOPICS = ("/cmd_vel_keyboard", "/cmd_vel")

# Where "is it actually rolling?" is read from. /odom, not /cmd_vel: the stop hold publishes zeros
# onto /cmd_vel itself, so a sender watching commanded velocity would be watching us, not the AGV.
# Odom is ground truth. Both are knobs because a different sim/robot names them differently.
ODOM_TOPIC = os.environ.get("ROBOT_ODOM_TOPIC", "/odom")
# Below this the AGV is parked, not creeping. Gazebo odom is noisy at rest; 0.02 m/s clears it.
MOVING_EPS = float(os.environ.get("ROBOT_MOVING_EPS", "0.02"))
# Odom arrives at ~30 Hz; if the last non-zero sample is older than this the wheels have stopped.
MOVING_STALE_S = 0.5

# Which script runs for which action lives in one declarative table, `robot_link.capabilities`.
# Re-exported here because scripts/check_warehouse_map.py and older callers import them from the
# bridge, and because the table is the thing to edit when the robot learns something new.
_STORAGES = set(capabilities.STORAGES)
_COLORS = set(capabilities.COLORS)


# ── ROS side ──────────────────────────────────────────────────────────────────
class VelocityHold:
    """Parks the AGV by holding ``/cmd_vel_keyboard`` at zero; releases by simply going quiet."""

    def __init__(self) -> None:
        import rclpy  # imported here so this module stays importable without ROS on the desk
        from geometry_msgs.msg import Twist
        from nav_msgs.msg import Odometry
        from rclpy.node import Node

        self._rclpy = rclpy
        self._Twist = Twist
        if not rclpy.ok():
            rclpy.init()
        self._node = Node("voice_velocity_hold")
        self._pubs = [self._node.create_publisher(Twist, t, 10) for t in HOLD_TOPICS]
        self._last_motion = 0.0
        self._node.create_subscription(Odometry, ODOM_TOPIC, self._on_odom, 10)
        self._engaged = threading.Event()
        self._stop = threading.Event()
        threading.Thread(target=self._spin, daemon=True).start()
        threading.Thread(target=self._pump, daemon=True).start()
        logger.info("Giữ tốc độ: publisher %s sẵn sàng", " + ".join(HOLD_TOPICS))

    @property
    def engaged(self) -> bool:
        return self._engaged.is_set()

    @property
    def moving(self) -> bool:
        """Have the wheels turned within the last `MOVING_STALE_S`?"""
        return (time.time() - self._last_motion) < MOVING_STALE_S

    def _on_odom(self, msg) -> None:
        twist = msg.twist.twist
        if abs(twist.linear.x) + abs(twist.angular.z) > MOVING_EPS:
            self._last_motion = time.time()

    def engage(self) -> None:
        # Publish once inline before the pump's next tick: the whole point is that the wheels
        # stop on the same millisecond the datagram lands, not up to 50 ms later.
        self._publish_zero()
        self._engaged.set()

    def release(self) -> None:
        self._engaged.clear()

    def pulse(self, linear: float, angular: float, duration: float = 1.2) -> None:
        """Drive the AGV one direction for a fixed time — the motion-primitive command.

        Publishes on the same two topics the stop hold uses, so it overrides Nav2 while a goal is
        active and is a no-op-conflict-free with an idle robot. `HOLD_HZ` ticks keep the command
        alive for the whole pulse; we then zero the topics so the robot doesn't coast.
        """
        twist = self._Twist()
        twist.linear.x = linear
        twist.angular.z = angular
        ticks = max(1, int(duration * HOLD_HZ))
        for _ in range(ticks):
            for pub in self._pubs:
                pub.publish(twist)
            time.sleep(1.0 / HOLD_HZ)
        self._publish_zero()

    def shutdown(self) -> None:
        self._stop.set()

    def _publish_zero(self) -> None:
        zero = self._Twist()
        for pub in self._pubs:
            pub.publish(zero)

    def _pump(self) -> None:
        period = 1.0 / HOLD_HZ
        while not self._stop.is_set():
            if self._engaged.is_set():
                self._publish_zero()
            time.sleep(period)

    def _spin(self) -> None:
        self._rclpy.spin(self._node)


class MissionStateRelay:
    """Mirrors ``/warehouse/mission_state`` to the orchestrator so the web monitor can show it.

    Telemetry, not control: it goes over HTTP because losing a progress update costs a stale
    label on a web page, and stdlib urllib because this process runs under ROS's interpreter,
    where adding a dependency means adding one to a machine we do not own.
    """

    def __init__(self, orchestrator_url: str) -> None:
        import rclpy
        from rclpy.node import Node
        from std_msgs.msg import String

        self._url = orchestrator_url.rstrip("/") + "/voice/event"
        if not rclpy.ok():
            rclpy.init()
        self._node = Node("voice_mission_relay")
        self._node.create_subscription(String, "/warehouse/mission_state", self._on_state, 10)
        self._node.create_subscription(String, "/warehouse/behavior_decision", self._on_decision, 10)
        threading.Thread(target=lambda: rclpy.spin(self._node), daemon=True).start()
        logger.info("Gương trạng thái nhiệm vụ → %s", self._url)

    def _on_state(self, msg) -> None:
        self._post({"type": "robot.mission", "stage": _field(msg.data, "state"), "text": msg.data})

    def _on_decision(self, msg) -> None:
        decision = _field(msg.data, "decision")
        if decision:  # WAIT/PASS/REPLAN — only worth mirroring when the planner actually decided
            self._post({"type": "robot.decision", "stage": decision, "text": msg.data})

    def _post(self, payload: dict) -> None:
        threading.Thread(target=self._post_blocking, args=(payload,), daemon=True).start()

    def _post_blocking(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self._url, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=2.0).close()
        except (urllib.error.URLError, OSError) as e:
            logger.debug("Không gửi được telemetry: %s", e)


def _field(raw: str, key: str) -> str:
    try:
        return str(json.loads(raw).get(key, ""))
    except (json.JSONDecodeError, AttributeError):
        return ""


# ── mission process ───────────────────────────────────────────────────────────
class MissionRunner:
    """Owns at most one ``run_storage_pick.sh`` at a time."""

    def __init__(self, demo_dir: Path, dry_run: bool = False) -> None:
        self.demo_dir = demo_dir
        self.dry_run = dry_run
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()

    def running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def start(self, argv: list[str]) -> None:
        with self._lock:
            self._cancel_locked()
            cmd = [str(self.demo_dir / argv[0]), *argv[1:]]
            if self.dry_run:
                logger.info("[dry-run] sẽ chạy: %s", " ".join(cmd))
                return
            # Its own session, so cancelling reaches the mission AND anything it spawned
            # (vqa_mission.py) with one signal instead of leaving orphans holding Nav2 goals.
            self._proc = subprocess.Popen(cmd, cwd=str(self.demo_dir), start_new_session=True)
            logger.info("Chạy nhiệm vụ pid=%d: %s", self._proc.pid, " ".join(cmd))

    def cancel(self) -> bool:
        with self._lock:
            return self._cancel_locked()

    def _cancel_locked(self) -> bool:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            self._proc = None
            return False
        # SIGINT, not SIGTERM: storage_pick_mission.py installs no SIGTERM handler but keeps
        # Python's KeyboardInterrupt one, whose except-path calls cancel_active_goal(). SIGTERM
        # would kill it with the Nav2 goal still active on the server and the AGV still driving.
        logger.info("Hủy nhiệm vụ pid=%d (SIGINT)", proc.pid)
        try:
            os.killpg(proc.pid, signal.SIGINT)
        except ProcessLookupError:
            self._proc = None
            return False
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            logger.warning("Nhiệm vụ không thoát sau 5s — SIGKILL")
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self._proc = None
        return True


# ── bridge ────────────────────────────────────────────────────────────────────
class RobotBridge:
    def __init__(self, demo_dir: Path, hold: VelocityHold | None, runner: MissionRunner) -> None:
        self.demo_dir = demo_dir
        self.hold = hold
        self.runner = runner
        self.dedupe = Deduper()
        self.items = parse_text.load_items()
        if not self.items:
            logger.warning("Không đọc được data/inventory.csv — chế độ dự phòng đọc câu sẽ không "
                           "tra được mặt hàng nào")

    def status(self) -> str:
        """One word for "what is the AGV doing right now", answered on every ack.

        Lets the sender wait for `moving` instead of sleeping a guess: this AGV's Nav2/AMCL takes
        6–8 s to plan, and an accepted goal that has not moved yet is indistinguishable from a
        command nobody received.
        """
        if self.hold is None:
            return protocol.ST_UNKNOWN
        if self.hold.moving:
            return protocol.ST_MOVING
        if self.hold.engaged:
            return protocol.ST_STOPPED
        return protocol.ST_PLANNING if self.runner.running() else protocol.ST_IDLE

    def handle(self, cmd: Command) -> None:
        if cmd.kind in (protocol.KIND_PING, protocol.KIND_ACK):
            return
        action, origin = cmd.action, cmd.source
        if not action:
            action, origin = self._read_sentence(cmd), "laptop tự đọc"
        if not action:
            return
        if action.get("type") == protocol.KIND_CONTROL:
            self._control(action, cmd, origin)
        elif action.get("type") == protocol.KIND_MOTION:
            self._motion(action, cmd, origin)
        else:
            self._run(action, cmd, origin)

    def _read_sentence(self, cmd: Command) -> dict | None:
        """No action came with the datagram — fall back to reading the sentence ourselves.

        Normal turns always carry an action, so arriving here means the Jetson could not reach the
        brain (VPN down, home PC asleep, agent errored). Log it loudly: the robot will still move,
        but it is moving on a substring match instead of the trained router, and the operator
        should know which one they are watching.
        """
        if not cmd.sentence:
            return None
        action = parse_text.parse(cmd.sentence, self.items)
        if action is None:
            if parse_text.needs_memory(cmd.sentence):
                logger.warning("%r là lệnh thật, nhưng nhánh dự phòng không nhớ được hộp nào đang "
                               "trên khay. Cần brain (VPN + PC ở nhà) cho lệnh này.", cmd.sentence)
            else:
                logger.info("Câu %r không phải lệnh cho robot — bỏ qua", cmd.sentence)
            return None
        logger.warning("KHÔNG CÓ LỜI GIẢI TỪ BRAIN — tự đọc %r → %s", cmd.sentence, action)
        return action

    # ── control ───────────────────────────────────────────────────────────────
    def _control(self, action: dict, cmd: Command, origin: str) -> None:
        verb = action.get("verb", "")
        if self.hold is None:
            logger.warning("Nhận lệnh %r nhưng không có ROS — bỏ qua", verb)
            return
        if verb == "stop":
            self.hold.engage()
            logger.info("DỪNG (%s) ← %r", origin, cmd.sentence)
            if self.runner.running():
                # Honest about the one case this does not fully cover. While the mission is in
                # its camera-guided pick, vqa_mission.py is publishing its own velocities onto
                # /cmd_vel at 20 Hz and we are only outvoting it, not silencing it — the AGV may
                # creep instead of stopping dead. A guaranteed halt there is "hủy chuyến", which
                # ends the mission process outright.
                logger.info("      (nếu đang gắp hàng ở kệ: xe có thể nhích nhẹ — "
                            "muốn dừng hẳn thì nói “hủy chuyến”)")
        elif verb == "resume":
            self.hold.release()
            logger.info("CHẠY TIẾP (%s) ← %r", origin, cmd.sentence)
        elif verb == "cancel":
            # Hold first: SIGINT plus Nav2's own cancel takes a moment to reach the wheels, and
            # "hủy" must not mean "keep coasting for another second".
            self.hold.engage()
            self.runner.cancel()
            # Release once the goal is gone, otherwise the next mission would start against a
            # keyboard hold that nothing will lift.
            threading.Timer(1.5, self.hold.release).start()
            logger.info("HỦY CHUYẾN (%s) ← %r", origin, cmd.sentence)
        else:
            logger.warning("Verb điều khiển lạ: %r", verb)

    # ── motion primitive: a timed velocity pulse, no destination ──────────────
    def _motion(self, action: dict, cmd: Command, origin: str) -> None:
        if self.hold is None:
            logger.warning("Nhận lệnh di chuyển %r nhưng không có ROS — bỏ qua", action.get("direction"))
            return
        direction = (action or {}).get("direction", "")
        lin, ang = 0.0, 0.0
        if direction == "forward":
            lin = 0.2
        elif direction == "back":
            lin = -0.2
        elif direction == "left":
            ang = 0.6
        elif direction == "right":
            ang = -0.6
        else:
            logger.warning("Hướng di chuyển lạ: %r", direction)
            return
        # A stop hold would pin the AGV; lift it so the pulse actually moves the robot.
        self.hold.release()
        logger.info("DI CHUYỂN %s (%s) ← %r", direction, origin, cmd.sentence)
        self.hold.pulse(lin, ang, duration=1.2)

    # ── everything that shells out to warehouse_agv_demo ──────────────────────
    def _run(self, action: dict, cmd: Command, origin: str) -> None:
        try:
            argv = capabilities.resolve(action)
        except capabilities.Unsupported as e:
            # Say why. A command that vanishes without a reason is indistinguishable from a dead
            # link, and the operator will spend the demo checking network settings.
            logger.warning("KHÔNG LÀM ĐƯỢC: %s ← %r", e, cmd.sentence)
            return

        # A new order while one is running is a redirect, not a queue. MissionRunner.start cancels
        # first; release any stop hold so the fresh mission is not parked the moment it starts.
        if self.hold is not None and self.hold.engaged:
            self.hold.release()
        logger.info("CHẠY %s (%s) ← %r", " ".join(argv), origin, cmd.sentence)
        self.runner.start(argv)

    def _argv_for(self, token: str, color: str) -> list[str] | None:
        """Kept for scripts/check_warehouse_map.py, which walks every token the brain can emit."""
        try:
            return capabilities.resolve(
                {"type": "navigate", "task": "fetch",
                 "position": {"token": token, "color": color}}
            )
        except capabilities.Unsupported:
            return None


# ── receive loop ──────────────────────────────────────────────────────────────
def serve(bridge: RobotBridge, host: str, port: int) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    logger.info("Nghe lệnh giọng nói trên udp://%s:%d", host, port)
    while True:
        try:
            raw, addr = sock.recvfrom(protocol.MAX_DATAGRAM + 256)
        except OSError as e:
            logger.error("Lỗi socket: %s", e)
            continue
        cmd = decode(raw)
        if cmd is None:
            logger.debug("Gói lạ từ %s, bỏ qua", addr)
            continue
        # Acknowledge before doing the work, and acknowledge duplicates too. The ack says "your
        # datagram reached this process", which is true the moment it is decoded; delaying it
        # until after a mission launch would make a slow subprocess look like a dead link.
        try:
            sock.sendto(protocol.ack_for(cmd, bridge.status()), addr)
        except OSError:
            pass
        if bridge.dedupe.is_duplicate(cmd):
            continue
        try:
            bridge.handle(cmd)
        except Exception:
            # One malformed command must not take the bridge down mid-demo.
            logger.exception("Lỗi khi xử lý lệnh seq=%d", cmd.seq)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo-dir", default=os.environ.get("WAREHOUSE_DEMO_DIR", "../warehouse_agv_demo"),
                        help="thư mục warehouse_agv_demo")
    parser.add_argument("--bind", default=os.environ.get("ROBOT_UDP_BIND", "0.0.0.0:45455"),
                        help="địa chỉ:cổng UDP để nghe")
    parser.add_argument("--orchestrator", default=os.environ.get("ORCHESTRATOR_URL", ""),
                        help="URL orchestrator để gương trạng thái nhiệm vụ lên web monitor")
    parser.add_argument("--no-ros", action="store_true", help="chỉ in lệnh, không đụng ROS")
    parser.add_argument("--dry-run", action="store_true", help="không chạy nhiệm vụ thật")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    demo_dir = Path(args.demo_dir).expanduser().resolve()
    if not (demo_dir / "run_storage_pick.sh").exists():
        parser.error(f"{demo_dir} không phải thư mục warehouse_agv_demo (thiếu run_storage_pick.sh)")

    host, _, port = args.bind.rpartition(":")

    hold: VelocityHold | None = None
    if not args.no_ros:
        try:
            hold = VelocityHold()
            if args.orchestrator:
                MissionStateRelay(args.orchestrator)
        except ImportError as e:
            # Say it loudly. Without ROS the bridge still logs and starts missions, but "dừng
            # lại" silently does nothing — the single worst way for this to fail in front of a room.
            logger.error("Không import được ROS 2 (%s). Lệnh DỪNG sẽ KHÔNG hoạt động. "
                         "Chạy trong terminal đã `source /opt/ros/jazzy/setup.bash`, "
                         "hoặc thêm --no-ros nếu cố ý.", e)
            return 2

    bridge = RobotBridge(demo_dir, hold, MissionRunner(demo_dir, dry_run=args.dry_run))
    try:
        serve(bridge, host or "0.0.0.0", int(port))
    except KeyboardInterrupt:
        logger.info("Dừng bridge.")
        if hold is not None:
            hold.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
