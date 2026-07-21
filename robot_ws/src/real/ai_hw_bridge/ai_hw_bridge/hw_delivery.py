"""hw_delivery — real-robot motion layer for the AI Waiter task bridge.

Real twin of the sim's ``turtlebot4_python_tutorials/food_delivery.py``. Same public surface, so
``task_bridge.py`` stays a near-verbatim copy of the sim bridge:

    NavigatorReal, ArucoTracker, CMD_VEL_TOPIC, DESTINATIONS,
    startup_sequence(nav, tracker, cmd_pub)
    deliver_to(nav, name, tracker, cmd_pub)
    return_to_dock(nav, tracker, cmd_pub)

Two things differ from the sim on purpose:

1. **Localization is RTAB-Map, not AMCL.** The bridge never publishes an initial pose: RTAB-Map
   relocalizes on its saved database (``Mem/InitWMWithAllNodes``) and, once the operator has given
   it a starting hint with RViz's "2D Pose Estimate", it maintains ``map -> odom`` on its own. So
   ``startup_sequence`` waits for the ``map -> base_footprint`` TF instead of setting it, and
   ``waitUntilNav2Active(localizer='robot_localization')`` skips Nav2's AMCL-specific wait.

2. **ArUco does NOT correct the pose here.** On the real robot, marker-based pose correction runs
   *inside* RTAB-Map (``RGBD/MarkerDetection``, see rtabmap_localization_params.yaml) as a proper
   graph landmark constraint. The tracker in this file is only used for the last-metre *visual
   alignment* (rotate until the marker is centred), and it publishes no pose whatsoever. The sim's
   ``trigger_pose_correction`` / ``/initialpose`` path has deliberately no equivalent — having both
   would fight over the same estimate.

Waypoints come from ``config/floorplan.json`` — the same file the backend reads, so the dispatcher's
"nearest robot" scoring and the panel minimap can never drift from where the robot actually drives.

Run (needs localization + Nav2 up, see tarkbot_robot/launch/navigation):
    ros2 run ai_hw_bridge task_bridge --ros-args -p server_host:=<host>:8000 -p robot_id:=robo-1
"""

import json
import math
import os
import threading
import time

import numpy as np

import cv2
from cv_bridge import CvBridge

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from geometry_msgs.msg import PoseStamped, Twist
from sensor_msgs.msg import CameraInfo, Image
import tf2_ros

from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult

# ─────────────────────────────────────────────────────────── topics / frames
CMD_VEL_TOPIC = '/cmd_vel'
CAMERA_TOPIC = '/camera/camera/color/image_raw'
CAMERA_INFO_TOPIC = '/camera/camera/color/camera_info'
MAP_FRAME = 'map'
BASE_FRAME = 'base_footprint'  # what the EKF and Nav2 costmaps use on this robot

# Must match Marker/Dictionary '0' and Marker/Length in rtabmap_localization_params.yaml.
ARUCO_DICT_TYPE = cv2.aruco.DICT_4X4_50
MARKER_SIZE = 0.15

# ─────────────────────────────────────────────────────────── behaviour tuning
# Ablation switch: False = pure Nav2 arrival (no marker search/align), so the raw arrival error
# ([Arrival] err_x) can be read and you can judge whether alignment earns its keep.
ENABLE_VISUAL_ALIGN = True

STARTUP_TF_TIMEOUT = 120.0  # s to wait for map->base_footprint before giving up on localization
NAV_GOAL_TIMEOUT = 180.0    # s cap on a single Nav2 drive (a table is seconds away, not minutes)

DETECT_MAX_AGE = 1.0        # a detection older than this is stale
POST_NAV_SETTLE_TIMEOUT = 1.5

SEARCH_ANGULAR_SPEED = 0.10  # rad/s (~6°/s) sweep speed when the marker is not in view
SEARCH_SWEEP_RAD = math.pi / 2  # bounded ±90° sweep instead of a full spin

ALIGN_KP_ANG = 1.3
ALIGN_MAX_ANG = 0.5
ALIGN_CENTER_TOL = 0.02     # |err_x| under this = pointing at the marker
ALIGN_TIMEOUT = 30.0
ALIGN_LOST_TIMEOUT = 3.5
ALIGN_LOG_PERIOD = 1.0

# ─────────────────────────────────────────────────────────── floorplan (shared with the backend)
DESTINATIONS: dict[str, dict] = {}
DOCK: dict = {'id': 0, 'approach': ([0.0, 0.0], 0.0)}
DOCK_MARKER_ID = 0


def _default_floorplan_path() -> str:
    """The installed package share copy, falling back to the file in the source tree.

    The repo path keeps `python3 hw_delivery.py` and a not-yet-installed workspace working; the
    share path is what a colcon-installed robot actually uses.
    """
    try:
        from ament_index_python.packages import get_package_share_directory
        share = os.path.join(
            get_package_share_directory('ai_hw_bridge'), 'config', 'floorplan.json')
        if os.path.exists(share):
            return share
    except Exception:  # noqa: BLE001 — package not installed yet; fall through to the source tree
        pass
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'config', 'floorplan.json')


def load_floorplan(path: str | None = None) -> str:
    """(Re)load waypoints into DESTINATIONS/DOCK. Returns the path actually read."""
    path = path or _default_floorplan_path()
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    def entry(node: dict) -> dict:
        a = node['approach']
        return {
            'id': node.get('marker_id'),  # None = marker not printed yet -> skip visual align
            'approach': ([float(a['x']), float(a['y'])], float(a.get('yaw_deg', 0.0))),
        }

    DESTINATIONS.clear()
    for t in data['tables']:
        DESTINATIONS[f"Table {int(t['id'])}"] = entry(t)

    global DOCK, DOCK_MARKER_ID
    DOCK = entry(data['dock'])
    DOCK_MARKER_ID = DOCK['id']
    return path


load_floorplan()  # import-time load so task_bridge sees DESTINATIONS immediately


# ─────────────────────────────────────────────────────────── navigation
def _yaw_to_quat(yaw_deg: float) -> tuple[float, float]:
    """(z, w) of a yaw-only quaternion — 2D robot, roll/pitch are always zero."""
    half = math.radians(yaw_deg) / 2.0
    return math.sin(half), math.cos(half)


class NavigatorReal(BasicNavigator):
    """Nav2 client for the tarkbot. `BasicNavigator` spins itself inside its own calls, so it is
    driven from the main thread and must NOT be added to the bridge's executor."""

    def __init__(self):
        super().__init__(node_name='ai_hw_navigator')

    def pose(self, position, yaw_deg: float) -> PoseStamped:
        p = PoseStamped()
        p.header.frame_id = MAP_FRAME
        p.header.stamp = self.get_clock().now().to_msg()
        p.pose.position.x = float(position[0])
        p.pose.position.y = float(position[1])
        z, w = _yaw_to_quat(yaw_deg)
        p.pose.orientation.z = z
        p.pose.orientation.w = w
        return p


class ArucoTracker(Node):
    """Marker detector + TF buffer for the bridge.

    Detection only runs while a destination's marker is active (``set_correction_target``), so the
    camera pipeline costs nothing while the robot idles at the dock — RTAB-Map and the aruco_debug
    node are already working the same frames.

    The name ``set_correction_target`` is kept from the sim for API parity, but here it gates
    *alignment*, not pose correction: this node never publishes a pose (see the module docstring).
    """

    def __init__(self):
        super().__init__('aruco_tracker')

        self.bridge = CvBridge()
        self.camera_matrix = None
        self.dist_coeffs = None
        self._markers: dict[int, tuple] = {}
        self._lock = threading.Lock()
        self._correction_target: int | None = None

        if hasattr(cv2.aruco, 'getPredefinedDictionary'):
            self.aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)
        else:  # OpenCV < 4.7
            self.aruco_dict = cv2.aruco.Dictionary_get(ARUCO_DICT_TYPE)
        self._detect = self._make_detector()

        half = MARKER_SIZE / 2.0
        self.obj_pts = np.array([
            [-half,  half, 0.0],
            [half,  half, 0.0],
            [half, -half, 0.0],
            [-half, -half, 0.0],
        ], dtype=np.float32)

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        self.create_subscription(
            CameraInfo, CAMERA_INFO_TOPIC, self._camera_info_cb, qos_profile_sensor_data)
        self.create_subscription(
            Image, CAMERA_TOPIC, self._image_cb, qos_profile_sensor_data)

        self.get_logger().info(
            f'[ArUco] tracker up (TF live, detection idle until a task starts). '
            f'Camera: {CAMERA_TOPIC}')

    def _make_detector(self):
        """ArUco detector that works on both the old and new OpenCV APIs."""
        if hasattr(cv2.aruco, 'ArucoDetector'):  # OpenCV >= 4.7
            detector = cv2.aruco.ArucoDetector(self.aruco_dict, cv2.aruco.DetectorParameters())
            return lambda gray: detector.detectMarkers(gray)
        params = cv2.aruco.DetectorParameters_create()
        # Loosen the defaults so small / oblique markers still decode after a Nav2 approach.
        params.minMarkerPerimeterRate = 0.02
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        return lambda gray: cv2.aruco.detectMarkers(gray, self.aruco_dict, parameters=params)

    # ---------------------------------------------------------------- gating
    def set_correction_target(self, marker_id):
        """Start detecting, and only care about `marker_id` (None = stay idle)."""
        self._correction_target = marker_id
        if marker_id is not None:
            self.get_logger().info(f'[ArUco] watching marker {marker_id}')

    def clear_correction_target(self):
        self._correction_target = None
        with self._lock:
            self._markers.clear()

    # ---------------------------------------------------------------- camera
    def _camera_info_cb(self, msg: CameraInfo):
        if self.camera_matrix is None:
            self.camera_matrix = np.array(msg.k).reshape((3, 3))
            self.dist_coeffs = np.array(msg.d)
            self.get_logger().info('[ArUco] received CameraInfo')

    def _image_cb(self, msg: Image):
        if self._correction_target is None or self.camera_matrix is None:
            return  # idle: no task in flight (or intrinsics not in yet) — do not burn CPU

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:  # noqa: BLE001
            self.get_logger().warn(f'[ArUco] cv_bridge error: {e}')
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self._detect(gray)
        if ids is None or len(ids) == 0:
            return

        now = time.time()
        h, w = gray.shape[:2]
        for i in range(len(ids)):
            marker_id = int(ids[i][0])
            if marker_id != self._correction_target:
                continue
            c = corners[i][0]
            ok, rvec, tvec = cv2.solvePnP(
                self.obj_pts, c, self.camera_matrix, self.dist_coeffs)
            if not ok:
                continue
            xs, ys = c[:, 0], c[:, 1]
            with self._lock:
                self._markers[marker_id] = (
                    float(xs.mean()), float(xs.max() - xs.min()), w, now, rvec, tvec)

    def get_marker(self, marker_id, max_age: float = DETECT_MAX_AGE):
        """Latest detection of `marker_id`, or None if never seen / too old."""
        if marker_id is None:
            return None
        with self._lock:
            data = self._markers.get(marker_id)
        if data is None:
            return None
        cx, bw, iw, stamp, rvec, tvec = data
        if time.time() - stamp > max_age:
            return None
        return {
            'err_x': (cx - iw / 2.0) / (iw / 2.0),  # >0: marker is right of image centre
            'width_ratio': bw / iw,
            'marker_yaw': _marker_yaw_from_rvec(rvec),  # obliqueness, diagnostics only
            'range': float(np.linalg.norm(tvec)),
        }


def _marker_yaw_from_rvec(rvec) -> float:
    """Yaw of the marker normal in the camera frame (0 = perfectly face-on)."""
    rmat, _ = cv2.Rodrigues(rvec)
    nx, nz = float(rmat[0, 2]), float(rmat[2, 2])
    return math.atan2(nx, -nz)


# ─────────────────────────────────────────────────────────── motion primitives
def _stop(cmd_pub):
    cmd_pub.publish(Twist())


def _wait_for_localization(nav, tracker, timeout: float = STARTUP_TF_TIMEOUT) -> bool:
    """Block until RTAB-Map publishes map->base_footprint (the operator may still need to give it
    a 2D Pose Estimate in RViz). Returns False on timeout — the caller carries on so the WS link
    and heartbeats stay alive and the panel shows the robot as connected."""
    deadline = time.time() + timeout
    warned = False
    while time.time() < deadline and rclpy.ok():
        try:
            tracker.tf_buffer.lookup_transform(MAP_FRAME, BASE_FRAME, rclpy.time.Time())
            return True
        except Exception:  # noqa: BLE001 — TF not ready yet
            if not warned:
                warned = True
                nav.info(f'[STARTUP] waiting for {MAP_FRAME}->{BASE_FRAME} — is RTAB-Map up, and '
                         f'has the initial pose been set in RViz ("2D Pose Estimate")?')
            time.sleep(0.5)
    nav.warn(f'[STARTUP] no {MAP_FRAME}->{BASE_FRAME} after {timeout:.0f}s — carrying on; tasks '
             f'will fail until localization is up.')
    return False


def startup_sequence(nav, tracker, cmd_pub):
    """Wait for localization + Nav2, then declare the robot ready.

    No initial pose is published: RTAB-Map owns map->odom on this robot (see module docstring).
    """
    _wait_for_localization(nav, tracker)
    # localizer='robot_localization' is the documented way to tell nav2_simple_commander "this is
    # not AMCL": it skips both the AMCL lifecycle check and the /initialpose handshake.
    nav.waitUntilNav2Active(localizer='robot_localization')
    nav.info('[STARTUP] Nav2 ACTIVE — ready for tasks.')


def _run_nav_goal(nav, position, yaw_deg: float, label: str) -> bool:
    """Drive to (position, yaw) and block until Nav2 finishes. True on SUCCEEDED."""
    nav.clearAllCostmaps()  # RTAB-Map's static map + a fresh obstacle scan beat a stale costmap
    time.sleep(0.5)
    nav.goToPose(nav.pose(position, yaw_deg))

    deadline = time.time() + NAV_GOAL_TIMEOUT
    while not nav.isTaskComplete():
        if time.time() > deadline:
            nav.warn(f'[{label}] Nav2 goal exceeded {NAV_GOAL_TIMEOUT:.0f}s — cancelling.')
            nav.cancelTask()
            return False
        time.sleep(0.1)

    result = nav.getResult()
    if result == TaskResult.SUCCEEDED:
        return True
    nav.warn(f'[{label}] Nav2 goal did not succeed: {result}')
    return False


def _search_marker(nav, tracker, cmd_pub, marker_id) -> bool:
    """Bounded ±90° sweep to bring `marker_id` into view (fallback when it is not already in FOV)."""
    if tracker.get_marker(marker_id) is not None:
        return True
    nav.info(f'[Search] marker {marker_id} not visible — sweeping '
             f'±{math.degrees(SEARCH_SWEEP_RAD):.0f}°.')
    twist = Twist()
    for direction, span in ((+1.0, SEARCH_SWEEP_RAD), (-1.0, 2 * SEARCH_SWEEP_RAD)):
        swept = 0.0
        last = time.time()
        while swept < span and rclpy.ok():
            if tracker.get_marker(marker_id) is not None:
                _stop(cmd_pub)
                nav.info(f'[Search] found marker {marker_id}.')
                return True
            now = time.time()
            swept += SEARCH_ANGULAR_SPEED * (now - last)
            last = now
            twist.angular.z = direction * SEARCH_ANGULAR_SPEED
            cmd_pub.publish(twist)
            time.sleep(0.05)
        _stop(cmd_pub)
    found = tracker.get_marker(marker_id) is not None
    if not found:
        nav.warn(f'[Search] marker {marker_id} not found after sweep.')
    return found


def _visual_align(nav, tracker, cmd_pub, marker_id):
    """Rotate in place until the marker is horizontally centred.

    err_x -> 0 means the robot's heading points straight at the marker (and therefore at the
    table / dock behind it). Rotation only: obliqueness would need translation and is left to the
    approach waypoint, so it is logged but not driven.
    """
    nav.info(f'[Align] centering on marker {marker_id}.')
    twist = Twist()
    start = last_seen = time.time()
    last_log = 0.0
    while rclpy.ok():
        now = time.time()
        if now - start > ALIGN_TIMEOUT:
            nav.warn(f'[Align] timeout ({ALIGN_TIMEOUT:.0f}s) — stopping.')
            break

        m = tracker.get_marker(marker_id)
        if m is None:
            if now - last_seen > ALIGN_LOST_TIMEOUT:
                nav.warn('[Align] marker lost — aborting align.')
                break
            _stop(cmd_pub)  # hold still and wait to re-acquire
            time.sleep(0.05)
            continue

        last_seen = now
        err_x = m['err_x']
        if abs(err_x) < ALIGN_CENTER_TOL:
            _stop(cmd_pub)
            nav.info(f'[Align] locked: err_x={err_x:+.3f} (yaw={m["marker_yaw"]:+.2f}).')
            break

        # Marker right of centre (err_x > 0) -> rotate clockwise (angular.z < 0).
        ang = max(-ALIGN_MAX_ANG, min(ALIGN_MAX_ANG, -ALIGN_KP_ANG * err_x))
        twist.angular.z = ang
        twist.linear.x = 0.0
        cmd_pub.publish(twist)

        if now - last_log > ALIGN_LOG_PERIOD:
            last_log = now
            nav.info(f'[Align] err_x={err_x:+.3f}, yaw={m["marker_yaw"]:+.2f}, ang={ang:+.2f}')
        time.sleep(0.05)

    _stop(cmd_pub)


def _acquire_and_align(nav, tracker, cmd_pub, marker_id, label):
    """After a Nav2 arrival: settle, log the raw arrival error, then search + align."""
    settle = time.time()
    while time.time() - settle < POST_NAV_SETTLE_TIMEOUT:
        if tracker.get_marker(marker_id) is not None:
            break
        time.sleep(0.05)

    # Objective arrival metric — pure Nav2 heading, before any search/align touches it.
    m = tracker.get_marker(marker_id)
    if m is not None:
        nav.info(f'[Arrival] err_x={m["err_x"]:+.3f}, marker_yaw={m["marker_yaw"]:+.2f}, '
                 f'range={m["range"]:.2f}m (marker {marker_id}, before search/align)')
    else:
        nav.warn(f'[Arrival] marker {marker_id} NOT visible on arrival (heading off, or occluded).')

    if not ENABLE_VISUAL_ALIGN:
        nav.info('[Align] disabled (ablation) — heading left as Nav2 delivered it.')
        return

    if m is None and not _search_marker(nav, tracker, cmd_pub, marker_id):
        nav.warn(f'[{label}] could not acquire marker {marker_id} — skipping align.')
        return
    _visual_align(nav, tracker, cmd_pub, marker_id)


def _go(nav, tracker, cmd_pub, dest: dict, label: str) -> bool:
    """Nav2 to a destination's approach pose, then align on its marker if there is one."""
    position, yaw_deg = dest['approach']
    marker_id = dest['id']
    nav.info(f'── {label} → ({position[0]:.2f}, {position[1]:.2f}) @ {yaw_deg:.1f}° '
             f'{"(ArUco " + str(marker_id) + ")" if marker_id is not None else "(no marker)"} ──')

    tracker.set_correction_target(marker_id)
    try:
        reached = _run_nav_goal(nav, position, yaw_deg, label)
        if not reached:
            return False
        if marker_id is None:
            # Marker not printed for this destination yet — the Nav2 pose is the final pose.
            nav.info(f'[{label}] arrived (no ArUco configured — skipping visual align).')
            return True
        nav.info(f'[{label}] reached approach pose — acquiring marker.')
        _acquire_and_align(nav, tracker, cmd_pub, marker_id, label)
        return True
    finally:
        tracker.clear_correction_target()
        _stop(cmd_pub)


def deliver_to(nav, name, tracker, cmd_pub) -> bool:
    """Drive to a table's approach pose and align on its marker. True if Nav2 got there."""
    return _go(nav, tracker, cmd_pub, DESTINATIONS[name], name)


def return_to_dock(nav, tracker, cmd_pub) -> bool:
    """Drive home to the dock and align on the dock marker."""
    return _go(nav, tracker, cmd_pub, DOCK, 'Dock')
