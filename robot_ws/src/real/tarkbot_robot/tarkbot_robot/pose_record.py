#!/usr/bin/env python3

"""Pose recorder for surveying real-robot waypoints into floorplan.json.

Real twin of sim ``pose_aruco_debug``. Two outputs:

``[POSE]`` / ``[PASTE robot]``
    Raw ``map → base_footprint``. Diagnostics — where the robot itself is standing.

``[SURVEY n]`` / ``[PASTE table]``
    **The one you paste.** Solves the marker's pose in the map from PnP, then *computes*
    the approach point: ``SURVEY_STANDOFF_M`` out along the marker's normal, yaw pointing
    back at the marker. Same construction the sim uses (``food_delivery.get_marker_global_tf``
    + ``APPROACH_DIST``), so the robot arrives face-on instead of inheriting however
    obliquely you happened to park while surveying.

That distinction is the whole point: ``visual_delivery._visual_align`` only *rotates*
(centres ``err_x``), it can never remove ``marker_yaw`` obliqueness — that has to be baked
into the approach waypoint here.

Does NOT publish ``/initialpose`` — localization is RTAB-Map.

Demo focus: Table 1 (ArUco 1) and dock (ArUco 6).

Run (localization already up)::

    ros2 run tarkbot_robot pose_record
    ros2 run tarkbot_robot pose_record --ros-args -p standoff:=0.6

Workflow:
  1. Park the robot anywhere the marker is clearly visible — ideally 0.6–1.5 m away and
     roughly square-on (``view_yaw`` small ⇒ better PnP). Exact parking does not matter.
  2. Wait for ``[SURVEY n]`` to reach n≈15 and the numbers to stop moving.
  3. Copy the ``[PASTE table]`` / ``[PASTE dock]`` block into ``floorplan.json``.
  4. Re-park somewhere else and repeat once — the two answers should agree within ~2 cm.
"""

from __future__ import annotations

import math
from collections import deque

import cv2
from cv_bridge import CvBridge
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import CameraInfo, Image
import tf2_ros

# Must match Marker/Dictionary '0' and Marker/Length in rtabmap configs / aruco_debug.
ARUCO_DICT_TYPE = cv2.aruco.DICT_4X4_50
MARKER_LENGTH = 0.15
CAMERA_TOPIC = '/camera/camera/color/image_raw'
CAMERA_INFO_TOPIC = '/camera/camera/color/camera_info'
# Separate topic so this node does not fight the existing aruco_debug publisher.
DEBUG_IMAGE_TOPIC = '/pose_record_debug'

MAP_FRAME = 'map'
BASE_FRAME = 'base_footprint'

POSE_PERIOD_S = 1.0
POSE_MOVE_M = 0.05
POSE_MOVE_RAD = 0.05  # ~3°
PUBLISH_RATE_HZ = 10.0

# Demo: Table 1 = service; ArUco 6 = dock (see floorplan.json).
DEMO_MARKER_IDS = frozenset({1, 6})

# ── survey (computed approach) ────────────────────────────────────────────────
# How far in front of the marker the robot should stand. Sim uses 0.80 m; override with
# `-p standoff:=…` if a table needs the robot closer.
SURVEY_STANDOFF_M = 0.80
SURVEY_PERIOD_S = 1.0        # s between survey *evaluations* (printing is change-gated)
# Standing still, the answer stops moving — so re-printing it is pure noise. Print only when
# the computed approach shifts by more than this, or every SURVEY_HEARTBEAT_S regardless.
SURVEY_PRINT_MOVE_M = 0.015
SURVEY_PRINT_MOVE_DEG = 1.5
SURVEY_HEARTBEAT_S = 20.0
SURVEY_SAMPLES = 15          # ring buffer size; the print is the per-axis median
SURVEY_MAX_AGE_S = 3.0       # drop samples older than this (you moved / lost the marker)
# A marker whose normal is near-vertical (lying flat on a table, facing the ceiling) has no
# meaningful floor-plane approach direction.
SURVEY_MIN_NORMAL_XY = 0.30


def _make_detector(aruco_dict):
    """Build an ArUco detector compatible with both old and new OpenCV APIs."""
    if hasattr(cv2.aruco, 'ArucoDetector'):
        params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        return lambda gray: detector.detectMarkers(gray)
    params = cv2.aruco.DetectorParameters_create()
    return lambda gray: cv2.aruco.detectMarkers(gray, aruco_dict, parameters=params)


def _yaw_from_quat(x: float, y: float, z: float, w: float) -> float:
    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    return math.atan2(t3, t4)


def _quat_to_rot(x: float, y: float, z: float, w: float) -> np.ndarray:
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def _transform_to_matrix(transform) -> np.ndarray:
    """geometry_msgs Transform → 4x4 homogeneous matrix."""
    t, q = transform.translation, transform.rotation
    T = np.eye(4)
    T[:3, :3] = _quat_to_rot(q.x, q.y, q.z, q.w)
    T[:3, 3] = [t.x, t.y, t.z]
    return T


class PoseRecordNode(Node):
    def __init__(self):
        super().__init__('pose_record')

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        self.bridge = CvBridge()
        self.camera_matrix = None
        self.dist_coeffs = None
        self._have_info = False
        self._last_ids: list[int] | None = None

        if hasattr(cv2.aruco, 'getPredefinedDictionary'):
            self.aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)
        else:
            self.aruco_dict = cv2.aruco.Dictionary_get(ARUCO_DICT_TYPE)
        self._detect = _make_detector(self.aruco_dict)

        half = MARKER_LENGTH / 2.0
        self.obj_pts = np.array([
            [-half,  half, 0.0],
            [ half,  half, 0.0],
            [ half, -half, 0.0],
            [-half, -half, 0.0],
        ], dtype=np.float32)

        self._min_period = 1.0 / PUBLISH_RATE_HZ if PUBLISH_RATE_HZ > 0 else 0.0
        self._last_proc = self.get_clock().now()
        self.last_pose = None

        self.declare_parameter('standoff', SURVEY_STANDOFF_M)
        self._standoff = float(self.get_parameter('standoff').value)
        # marker_id -> deque of (t_sec, mx, my, nx, ny, view_yaw, cam_range) in the map frame
        self._survey: dict[int, deque] = {}
        # marker_id -> last PRINTED (ax, ay, yaw_deg, t_sec), for change-gating the output
        self._last_print: dict[int, tuple] = {}

        self.create_subscription(
            CameraInfo, CAMERA_INFO_TOPIC, self._camera_info_cb, qos_profile_sensor_data)
        self.create_subscription(
            Image, CAMERA_TOPIC, self._image_cb, qos_profile_sensor_data)
        self.debug_pub = self.create_publisher(Image, DEBUG_IMAGE_TOPIC, 10)
        self.create_timer(POSE_PERIOD_S, self._print_pose)
        self.create_timer(SURVEY_PERIOD_S, self._print_survey)

        self.get_logger().info(
            f'Pose recorder up. TF {MAP_FRAME}->{BASE_FRAME} | '
            f'cam {CAMERA_TOPIC} | debug {DEBUG_IMAGE_TOPIC} | '
            f'demo marker ids {sorted(DEMO_MARKER_IDS)} | '
            f'standoff {self._standoff:.2f} m. '
            'No /initialpose (RTAB-Map). Paste the [SURVEY]/[PASTE] block into '
            'tarkbot_robot/config/floorplan.json.')

    def _camera_info_cb(self, msg: CameraInfo):
        if not self._have_info:
            self.camera_matrix = np.array(msg.k).reshape((3, 3))
            self.dist_coeffs = np.array(msg.d)
            self._have_info = True
            self.get_logger().info('Received CameraInfo.')

    def _image_cb(self, msg: Image):
        now = self.get_clock().now()
        if self._min_period > 0.0:
            dt = (now - self._last_proc).nanoseconds * 1e-9
            if dt < self._min_period:
                return
        self._last_proc = now

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().warn(f'cv_bridge error: {e}')
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self._detect(gray)

        id_list: list[int] = []
        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            for i in range(len(ids)):
                marker_id = int(ids[i][0])
                id_list.append(marker_id)
                c = corners[i][0]
                xs, ys = c[:, 0], c[:, 1]
                cv2.putText(
                    frame, f'id={marker_id}',
                    (int(xs.min()), max(20, int(ys.min()) - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
                if self._have_info:
                    ok, rvec, tvec = cv2.solvePnP(
                        self.obj_pts, c, self.camera_matrix, self.dist_coeffs)
                    if ok:
                        axis_len = MARKER_LENGTH * 0.5
                        if hasattr(cv2, 'drawFrameAxes'):
                            cv2.drawFrameAxes(
                                frame, self.camera_matrix, self.dist_coeffs,
                                rvec, tvec, axis_len)
                        else:
                            cv2.aruco.drawAxis(
                                frame, self.camera_matrix, self.dist_coeffs,
                                rvec, tvec, axis_len)
                        self._record_survey(
                            marker_id, rvec, tvec, msg.header.frame_id)

            id_list = sorted(set(id_list))
            if id_list != self._last_ids:
                demo = [i for i in id_list if i in DEMO_MARKER_IDS]
                other = [i for i in id_list if i not in DEMO_MARKER_IDS]
                msg_ids = f'[ArUco] detected ids={id_list}'
                if demo:
                    msg_ids += f'  (demo table marker(s) {demo} — OK to survey)'
                if other:
                    msg_ids += f'  (other {other})'
                self.get_logger().info(msg_ids)
                self._last_ids = id_list
        elif self._last_ids:
            self._last_ids = None

        try:
            debug_msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            debug_msg.header = msg.header
            self.debug_pub.publish(debug_msg)
        except Exception as e:
            self.get_logger().warn(f'Publish debug image error: {e}')

    # ------------------------------------------------------------------ survey
    def _record_survey(self, marker_id: int, rvec, tvec, camera_frame: str):
        """Solve the marker's map pose from this detection and buffer it.

        ``T_map_marker = T_map_cam @ T_cam_marker``. The marker's +Z axis is its normal
        pointing back out at the camera (OpenCV convention with our corner ordering), so
        its xy projection is the direction the robot must stand in.
        """
        try:
            tf_map_cam = self.tf_buffer.lookup_transform(
                MAP_FRAME, camera_frame, rclpy.time.Time())
        except Exception:  # TF not ready / camera frame not in the tree yet
            return

        rmat, _ = cv2.Rodrigues(rvec)
        T_cam_marker = np.eye(4)
        T_cam_marker[:3, :3] = rmat
        T_cam_marker[:3, 3] = np.asarray(tvec).flatten()

        T_map_marker = _transform_to_matrix(tf_map_cam.transform) @ T_cam_marker
        mx, my = float(T_map_marker[0, 3]), float(T_map_marker[1, 3])
        nx, ny = float(T_map_marker[0, 2]), float(T_map_marker[1, 2])

        norm = math.hypot(nx, ny)
        if norm < SURVEY_MIN_NORMAL_XY:
            return  # marker faces up/down — no sensible approach direction on the floor
        nx, ny = nx / norm, ny / norm

        # How oblique THIS view is (0 = square-on). Quality signal only: the computed
        # approach is view-independent, but PnP is far more trustworthy near 0.
        view_yaw = math.atan2(float(rmat[0, 2]), -float(rmat[2, 2]))
        cam_range = float(np.linalg.norm(tvec))

        now = self.get_clock().now().nanoseconds * 1e-9
        buf = self._survey.setdefault(marker_id, deque(maxlen=SURVEY_SAMPLES))
        buf.append((now, mx, my, nx, ny, view_yaw, cam_range))

    def _print_survey(self):
        """Print the median-filtered marker pose + the computed face-on approach."""
        now = self.get_clock().now().nanoseconds * 1e-9
        for marker_id in sorted(self._survey):
            buf = self._survey[marker_id]
            fresh = [s for s in buf if now - s[0] <= SURVEY_MAX_AGE_S]
            if not fresh:
                continue

            arr = np.array([s[1:] for s in fresh], dtype=float)
            mx, my = float(np.median(arr[:, 0])), float(np.median(arr[:, 1]))
            nx, ny = float(np.median(arr[:, 2])), float(np.median(arr[:, 3]))
            norm = math.hypot(nx, ny) or 1.0
            nx, ny = nx / norm, ny / norm
            view_yaw = float(np.median(arr[:, 4]))
            cam_range = float(np.median(arr[:, 5]))
            spread = float(np.hypot(arr[:, 0].std(), arr[:, 1].std()))

            ax, ay = mx + nx * self._standoff, my + ny * self._standoff
            approach_yaw_deg = math.degrees(math.atan2(-ny, -nx))
            label = 'dock' if marker_id == 6 else 'table'

            prev = self._last_print.get(marker_id)
            if prev is not None:
                pax, pay, pyaw, pt = prev
                moved = math.hypot(ax - pax, ay - pay)
                turned = abs((approach_yaw_deg - pyaw + 180.0) % 360.0 - 180.0)
                if (moved < SURVEY_PRINT_MOVE_M
                        and turned < SURVEY_PRINT_MOVE_DEG
                        and now - pt < SURVEY_HEARTBEAT_S):
                    continue  # same answer as last time — nothing to read
            self._last_print[marker_id] = (ax, ay, approach_yaw_deg, now)

            self.get_logger().info(
                f'[SURVEY {len(fresh):2d}] id={marker_id} marker=({mx:.3f}, {my:.3f}) '
                f'normal=({nx:+.2f}, {ny:+.2f}) | view_yaw={view_yaw:+.2f} rad '
                f'range={cam_range:.2f} m spread={spread * 100:.1f} cm')
            self.get_logger().info(
                f'[PASTE {label}] "marker_id": {marker_id}, '
                f'"approach": {{ "x": {ax:.3f}, "y": {ay:.3f}, '
                f'"yaw_deg": {approach_yaw_deg:.1f} }}, '
                f'"marker": {{ "x": {mx:.3f}, "y": {my:.3f} }}')

    def _print_pose(self):
        try:
            trans = self.tf_buffer.lookup_transform(
                MAP_FRAME, BASE_FRAME, rclpy.time.Time())
        except Exception:
            return

        t = trans.transform.translation
        q = trans.transform.rotation
        yaw = _yaw_from_quat(q.x, q.y, q.z, q.w)
        current = (t.x, t.y, yaw)

        if self.last_pose is not None:
            dx = abs(current[0] - self.last_pose[0])
            dy = abs(current[1] - self.last_pose[1])
            dyaw = abs(math.atan2(
                math.sin(current[2] - self.last_pose[2]),
                math.cos(current[2] - self.last_pose[2])))
            if dx <= POSE_MOVE_M and dy <= POSE_MOVE_M and dyaw <= POSE_MOVE_RAD:
                return

        self.last_pose = current
        yaw_deg = math.degrees(yaw)
        # One line, and only while actually driving — where the ROBOT stands is diagnostics.
        # What you paste is [SURVEY]/[PASTE], which is computed from the marker instead.
        self.get_logger().info(
            f'[POSE] robot at x={t.x:.3f} y={t.y:.3f} yaw_deg={yaw_deg:.1f}')


def main(args=None):
    rclpy.init(args=args)
    node = PoseRecordNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
