#!/usr/bin/env python3

import math
import threading
import time
import numpy as np

import cv2
from cv_bridge import CvBridge

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from geometry_msgs.msg import Twist, TransformStamped, PoseWithCovarianceStamped
from sensor_msgs.msg import Image, CameraInfo
import tf2_ros

from turtlebot4_navigation.turtlebot4_navigator import (
    TurtleBot4Directions,
    TurtleBot4Navigator,
)

# ============================================================
# CONFIG
# ============================================================
SPAWN_POSE = [0.0, 0.0]
SPAWN_HEADING = TurtleBot4Directions.NORTH

ARUCO_DICT_TYPE = cv2.aruco.DICT_4X4_50
CAMERA_TOPIC = '/camera/color/image_raw'
CAMERA_INFO_TOPIC = '/camera/color/camera_info'
DEBUG_IMAGE_TOPIC = '/aruco_debug_image'
CMD_VEL_TOPIC = '/cmd_vel'

DOCK_MARKER_ID = 0
MARKER_SIZE = 0.18

DESTINATIONS = {
    # Markers for Tables 1,3,4,6 are on the south rail (world y=-0.89), face +Y_world.
    # Robot approaches from track center (X_map≈8.0) and faces SOUTH (-Y_world = -X_map).
    'Table 1': {'id': 1, 'approach': ([7.99985,  1.36319], TurtleBot4Directions.SOUTH)},
    # Markers for Tables 2 and 5 are on the north rail (world y=+0.89), rotated 180° in SDF,
    # so their ArUco face points -Y_world (southward, into the track).
    # Robot approaches from track center (X_map≈8.05) and faces NORTH (+Y_world = +X_map).
    'Table 2': {'id': 2, 'approach': ([8.05419,  0.33537], TurtleBot4Directions.NORTH)},
    'Table 3': {'id': 3, 'approach': ([7.97830, -0.64879], TurtleBot4Directions.SOUTH)},
    'Table 4': {'id': 4, 'approach': ([7.92656, -3.28752], TurtleBot4Directions.SOUTH)},
    'Table 5': {'id': 5, 'approach': ([7.98864, -4.28860], TurtleBot4Directions.NORTH)},
    'Table 6': {'id': 6, 'approach': ([8.00802, -5.27848], TurtleBot4Directions.SOUTH)},
}

DOCK_APPROACH = ([0.0, 0.0], TurtleBot4Directions.NORTH)

DETECT_MAX_AGE = 1.0               
SEARCH_ANGULAR_SPEED = -0.25  # Negative value for counter-clockwise rotation
# Bounded search: sweep -90° → current → +90° instead of a full 360.
SEARCH_SWEEP_RAD = math.pi / 2
# Brief check only — standing still almost never decodes oblique markers in FOV.
# Real detection needs continuous yaw (search_marker_360); skip long wait/wiggle.
QUICK_DETECT_TIMEOUT = 0.5
# Short settle after face-on Nav2 before starting visual_align.
POST_NAV_SETTLE_TIMEOUT = 1.5

ALIGN_KP_ANG = 1.3
ALIGN_KP_YAW = 1.2
ALIGN_MAX_ANG = 0.5                
ALIGN_FWD_SPEED = 0.10             
ALIGN_CENTER_TOL = 0.06
ALIGN_YAW_TOL = 0.25
ALIGN_FWD_GATE = 0.20              
ALIGN_STOP_WIDTH = 0.2
# Accept width in [ALIGN_STOP_WIDTH - tol, +∞) — not a hard separate 0.12 cutoff.
ALIGN_WIDTH_TOL = 0.03
ALIGN_TIMEOUT = 30.0
ALIGN_LOST_TIMEOUT = 3.5
ALIGN_LOG_PERIOD = 1.0

# Pose-correction gates (reject bad / false-ID snaps like tables→dock).
CORRECTION_MAX_YAW = 0.40         # ~23° — PnP unreliable when too oblique
CORRECTION_MAX_JUMP = 2.5         # metres; refuse teleporting AMCL across the map
CORRECTION_RANGE_TOL = 1.2        # |map_dist_to_marker - cam_range| must be within this

# Back-off after alignment: reverse (camera still on marker) until blocked/stalled.
BACKUP_SPEED = 0.10              # m/s backward
BACKUP_KP_ANG = 1.0             # keep marker centered while reversing
BACKUP_MAX_ANG = 0.4
BACKUP_STALL_DIST = 0.02        # min movement per window to count as "still moving"
BACKUP_STALL_WINDOW = 1.0       # s window for stall check
BACKUP_STALL_WINDOWS_REQUIRED = 2  # consecutive stalled windows before declaring blocked
BACKUP_WARMUP = 1.0             # s to accelerate before judging stalls
BACKUP_DIR_RANGE_EPS = 0.05     # m range change to confirm/flip travel direction
BACKUP_TIMEOUT = 20.0           # safety cap

# Distance (m) in front of the marker the robot should stand for face-on alignment
APPROACH_DIST = 0.80


def width_ok(width: float) -> bool:
    """True if marker image width is within -ALIGN_WIDTH_TOL of the stop target (or larger)."""
    return width >= (ALIGN_STOP_WIDTH - ALIGN_WIDTH_TOL)


def marker_yaw_from_rvec(rvec) -> float:
    """Yaw of marker normal in camera frame (0 = absolute face-on)."""
    rmat, _ = cv2.Rodrigues(rvec)
    # Marker +Z (normal) expressed in camera frame; face-on ⇒ mostly -Z_cam.
    nx, nz = float(rmat[0, 2]), float(rmat[2, 2])
    return math.atan2(nx, -nz)

def invert_tf(T):
    R = T[:3, :3]
    t = T[:3, 3]
    T_inv = np.eye(4)
    T_inv[:3, :3] = R.T
    T_inv[:3, 3] = -R.T @ t
    return T_inv

def rot_to_quat(R):
    trace = np.trace(R)
    if trace > 0:
        S = math.sqrt(trace + 1.0) * 2
        w = 0.25 * S
        x = (R[2, 1] - R[1, 2]) / S
        y = (R[0, 2] - R[2, 0]) / S
        z = (R[1, 0] - R[0, 1]) / S
    elif (R[0, 0] > R[1, 1]) and (R[0, 0] > R[2, 2]):
        S = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w = (R[2, 1] - R[1, 2]) / S
        x = 0.25 * S
        y = (R[0, 1] + R[1, 0]) / S
        z = (R[0, 2] + R[2, 0]) / S
    elif R[1, 1] > R[2, 2]:
        S = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w = (R[0, 2] - R[2, 0]) / S
        x = (R[0, 1] + R[1, 0]) / S
        y = 0.25 * S
        z = (R[1, 2] + R[2, 1]) / S
    else:
        S = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w = (R[1, 0] - R[0, 1]) / S
        x = (R[0, 2] + R[2, 0]) / S
        y = (R[1, 2] + R[2, 1]) / S
        z = 0.25 * S
    return [x, y, z, w]

def get_marker_global_tf(marker_id):
    T_world_marker = np.eye(4)
    poses = {
        0: [-1.95, -7.01],
        1: [-3.29282, -0.89],
        2: [-2.3, 0.89],
        3: [-1.3, -0.89],
        4: [1.3, -0.89],
        5: [2.3, 0.89],
        6: [3.3, -0.89]
    }
    if marker_id not in poses:
        return None
    x, y = poses[marker_id]
    z = 1.25
    
    if marker_id in [0, 2, 5]: # Faces -y in world
        T_world_marker[:3, :3] = np.array([[-1, 0, 0], [0, 0, -1], [0, -1, 0]])
        T_world_marker[:3, 3] = [x, y - 0.006, z]
    else: # Faces +y in world
        T_world_marker[:3, :3] = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]])
        T_world_marker[:3, 3] = [x, y + 0.006, z]
        
    # The AMCL map frame is rotated and translated relative to the Gazebo world frame.
    # X_map = Y_world + 8.0
    # Y_map = -X_world - 1.95
    T_map_world = np.eye(4)
    T_map_world[:3, :3] = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]])
    T_map_world[:3, 3] = [8.0, -1.95, 0.0]
    
    T_map_marker = T_map_world @ T_world_marker
    return T_map_marker


from rclpy.parameter import Parameter

class NavigatorWithSim(TurtleBot4Navigator):
    def __init__(self):
        super().__init__()
        self.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])

class ArucoTracker(Node):
    def __init__(self):
        super().__init__('aruco_tracker', parameter_overrides=[Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.bridge = CvBridge()
        self.camera_matrix = None
        self.dist_coeffs = None
        self._markers = {}
        self._lock = threading.Lock()
        
        self.last_correction_time = 0.0
        # When set, only this marker ID may trigger opportunistic pose corrections.
        # None means any sufficiently large marker can correct (normal free-roam).
        self._correction_target = None
        # Becomes True after the first correction fires within a locked session;
        # prevents any further automatic corrections until the target is cleared.
        self._correction_done = False

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)
        self.aruco_params = cv2.aruco.DetectorParameters_create()
        # Loosen defaults so small / oblique markers (post-Nav2 approach) still decode.
        self.aruco_params.adaptiveThreshWinSizeMin = 3
        self.aruco_params.adaptiveThreshWinSizeMax = 23
        self.aruco_params.adaptiveThreshWinSizeStep = 10
        self.aruco_params.minMarkerPerimeterRate = 0.02
        self.aruco_params.maxMarkerPerimeterRate = 4.0
        self.aruco_params.polygonalApproxAccuracyRate = 0.05
        self.aruco_params.minCornerDistanceRate = 0.02
        self.aruco_params.minDistanceToBorder = 1
        self.aruco_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX

        self.obj_pts = np.array([
            [-MARKER_SIZE/2,  MARKER_SIZE/2, 0],
            [ MARKER_SIZE/2,  MARKER_SIZE/2, 0],
            [ MARKER_SIZE/2, -MARKER_SIZE/2, 0],
            [-MARKER_SIZE/2, -MARKER_SIZE/2, 0]
        ], dtype=np.float32)

        self.create_subscription(CameraInfo, CAMERA_INFO_TOPIC, self._camera_info_cb, qos_profile_sensor_data)
        self.create_subscription(Image, CAMERA_TOPIC, self._image_cb, qos_profile_sensor_data)
        
        self.debug_pub = self.create_publisher(Image, DEBUG_IMAGE_TOPIC, 10)
        self.initialpose_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)

        self.get_logger().info(f'[ArUco] Subscribed: {CAMERA_TOPIC} and {CAMERA_INFO_TOPIC}')

    # ------------------------------------------------------------------
    # Correction-target filter
    # ------------------------------------------------------------------
    def set_correction_target(self, marker_id: int):
        """Restrict opportunistic AMCL corrections to marker_id only (first detection wins)."""
        self._correction_target = marker_id
        self._correction_done = False
        self.get_logger().info(f'[ArUco] Correction target locked to marker {marker_id}')

    def clear_correction_target(self):
        """Remove the restriction — any large marker may correct AMCL again."""
        self._correction_target = None
        self._correction_done = False
        self.get_logger().info('[ArUco] Correction target cleared (free-roam mode)')

    def _camera_info_cb(self, msg: CameraInfo):
        if self.camera_matrix is None:
            self.camera_matrix = np.array(msg.k).reshape((3, 3))
            self.dist_coeffs = np.array(msg.d)
            self.get_logger().info('[ArUco] Received CameraInfo')

    def _image_cb(self, msg: Image):
        if self.camera_matrix is None:
            return

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().warn(f'[ArUco] cv_bridge error: {e}')
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.aruco_params)

        if ids is not None and len(ids) > 0:
            now = time.time()
            for i in range(len(ids)):
                marker_id = int(ids[i][0])
                c = corners[i][0]
                
                # 3D Pose Estimation
                success, rvec, tvec = cv2.solvePnP(self.obj_pts, c, self.camera_matrix, self.dist_coeffs)
                if success:
                    # Draw Axes + ID so RViz debug image shows what OpenCV decoded
                    cv2.drawFrameAxes(frame, self.camera_matrix, self.dist_coeffs, rvec, tvec, MARKER_SIZE)
                    xs, ys = c[:, 0], c[:, 1]
                    cx, cy = float(xs.mean()), float(ys.mean())
                    bbox_w = float(xs.max() - xs.min())
                    bbox_h = float(ys.max() - ys.min())
                    h, w = gray.shape[:2]
                    cv2.putText(frame, f'id={marker_id}',
                                (int(xs.min()), max(20, int(ys.min()) - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

                    # TF Broadcast
                    rmat, _ = cv2.Rodrigues(rvec)
                    quat = rot_to_quat(rmat)
                    t = TransformStamped()
                    t.header.stamp = self.get_clock().now().to_msg()
                    t.header.frame_id = msg.header.frame_id
                    t.child_frame_id = f'aruco_marker_{marker_id}_detected'
                    t.transform.translation.x = float(tvec[0])
                    t.transform.translation.y = float(tvec[1])
                    t.transform.translation.z = float(tvec[2])
                    t.transform.rotation.x = quat[0]
                    t.transform.rotation.y = quat[1]
                    t.transform.rotation.z = quat[2]
                    t.transform.rotation.w = quat[3]
                    self.tf_broadcaster.sendTransform(t)

                    with self._lock:
                        self._markers[marker_id] = (cx, cy, bbox_w, bbox_h, w, h, now, rvec, tvec, msg.header.frame_id)

                    # NOTE: no /initialpose teleport here — we navigate to the marker
                    # with Nav2 instead of snapping AMCL.

        # Publish debug image
        try:
            debug_msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            debug_msg.header = msg.header
            self.debug_pub.publish(debug_msg)
        except Exception as e:
            self.get_logger().warn(f'[ArUco] Publish debug image error: {e}')

    def get_marker(self, marker_id: int, max_age: float = DETECT_MAX_AGE):
        with self._lock:
            data = self._markers.get(marker_id)
        if data is None:
            return None
        cx, cy, bw, bh, iw, ih, stamp, rvec, tvec, frame_id = data
        if time.time() - stamp > max_age:
            return None
        return {
            'err_x': (cx - iw / 2.0) / (iw / 2.0),
            'width_ratio': bw / iw,
            'cx': cx, 'cy': cy,
            'rvec': rvec, 'tvec': tvec, 'frame_id': frame_id,
            'marker_yaw': marker_yaw_from_rvec(rvec),
        }

    def list_recent_ids(self, max_age: float = DETECT_MAX_AGE):
        """Return sorted marker IDs seen within max_age (wall-clock)."""
        now = time.time()
        with self._lock:
            return sorted(
                mid for mid, data in self._markers.items()
                if now - data[6] <= max_age
            )

    def trigger_pose_correction(self, marker_id) -> bool:
        """Publish /initialpose from marker PnP. Returns False if gated/rejected."""
        m = self.get_marker(marker_id)
        if m is None:
            self.get_logger().warn(f'Cannot correct pose: Marker {marker_id} not recently seen.')
            return False

        T_map_marker = get_marker_global_tf(marker_id)
        if T_map_marker is None:
            self.get_logger().warn(f'No global pose known for marker {marker_id}')
            return False

        width = m['width_ratio']
        marker_yaw = m['marker_yaw']
        tvec = m['tvec'].flatten()
        cam_range = float(np.linalg.norm(tvec))

        if not width_ok(width):
            self.get_logger().warn(
                f'[Correct] Reject id={marker_id}: width={width:.2f} '
                f'(need >= {ALIGN_STOP_WIDTH - ALIGN_WIDTH_TOL:.2f} = '
                f'{ALIGN_STOP_WIDTH:.2f}±{ALIGN_WIDTH_TOL:.2f})')
            return False
        if abs(marker_yaw) > CORRECTION_MAX_YAW:
            self.get_logger().warn(
                f'[Correct] Reject id={marker_id}: yaw={marker_yaw:+.2f} too oblique '
                f'(max {CORRECTION_MAX_YAW})')
            return False

        rmat, _ = cv2.Rodrigues(m['rvec'])
        T_cam_marker = np.eye(4)
        T_cam_marker[:3, :3] = rmat
        T_cam_marker[:3, 3] = tvec

        try:
            tf_cam_base = self.tf_buffer.lookup_transform(
                m['frame_id'], 'base_link', rclpy.time.Time())
            t = tf_cam_base.transform.translation
            q = tf_cam_base.transform.rotation
            x, y, z, w = q.x, q.y, q.z, q.w
            R_cam_base = np.array([
                [1 - 2*(y**2 + z**2), 2*(x*y - z*w), 2*(x*z + y*w)],
                [2*(x*y + z*w), 1 - 2*(x**2 + z**2), 2*(y*z - x*w)],
                [2*(x*z - y*w), 2*(y*z + x*w), 1 - 2*(x**2 + y**2)]
            ])
            T_cam_base = np.eye(4)
            T_cam_base[:3, :3] = R_cam_base
            T_cam_base[:3, 3] = [t.x, t.y, t.z]
        except Exception as e:
            self.get_logger().warn(f'TF lookup failed: {e}')
            return False

        # T_map_base = T_map_marker * T_cam_marker^-1 * T_cam_base
        T_map_base = T_map_marker @ invert_tf(T_cam_marker) @ T_cam_base
        new_x, new_y = float(T_map_base[0, 3]), float(T_map_base[1, 3])
        mx, my = float(T_map_marker[0, 3]), float(T_map_marker[1, 3])

        curr_x = curr_y = None
        try:
            tf_map_base = self.tf_buffer.lookup_transform(
                'map', 'base_link', rclpy.time.Time())
            curr_x = float(tf_map_base.transform.translation.x)
            curr_y = float(tf_map_base.transform.translation.y)
            self.get_logger().info(
                f'---> BEFORE CORRECTION: Robot at x={curr_x:.3f}, y={curr_y:.3f}')
        except Exception:
            pass

        if curr_x is not None:
            jump = math.hypot(new_x - curr_x, new_y - curr_y)
            map_dist = math.hypot(mx - curr_x, my - curr_y)
            if jump > CORRECTION_MAX_JUMP:
                self.get_logger().warn(
                    f'[Correct] Reject id={marker_id}: jump {jump:.2f}m > '
                    f'{CORRECTION_MAX_JUMP}m '
                    f'(would snap to x={new_x:.3f}, y={new_y:.3f}). '
                    f'Likely wrong ID or AMCL already lost — not applying.')
                return False
            if abs(map_dist - cam_range) > CORRECTION_RANGE_TOL:
                self.get_logger().warn(
                    f'[Correct] Reject id={marker_id}: range mismatch '
                    f'map_dist_to_marker={map_dist:.2f}m vs cam_range={cam_range:.2f}m '
                    f'(tol {CORRECTION_RANGE_TOL}m). Wrong marker ID?')
                return False

        # Publish initialpose
        pose_msg = PoseWithCovarianceStamped()
        pose_msg.header.frame_id = 'map'
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.pose.pose.position.x = new_x
        pose_msg.pose.pose.position.y = new_y
        pose_msg.pose.pose.position.z = float(T_map_base[2, 3])

        quat = rot_to_quat(T_map_base[:3, :3])
        pose_msg.pose.pose.orientation.x = quat[0]
        pose_msg.pose.pose.orientation.y = quat[1]
        pose_msg.pose.pose.orientation.z = quat[2]
        pose_msg.pose.pose.orientation.w = quat[3]

        cov = np.zeros((6, 6))
        np.fill_diagonal(cov, 0.01)
        pose_msg.pose.covariance = cov.flatten().tolist()

        self.initialpose_pub.publish(pose_msg)
        self.get_logger().info(
            f'---> AFTER CORRECTION: Published new pose x={new_x:.3f}, y={new_y:.3f} '
            f'(id={marker_id}, width={width:.2f}, yaw={marker_yaw:+.2f}, '
            f'cam_range={cam_range:.2f}m)')
        return True

def _stop(cmd_pub):
    cmd_pub.publish(Twist())

def _run_nav_primitive(nav: TurtleBot4Navigator):
    while not nav.isTaskComplete():
        time.sleep(0.1)

def _wait_for_marker(tracker, marker_id, timeout_sec: float, nav=None, label: str = '') -> bool:
    """Poll the tracker on wall-clock time until marker_id is seen or timeout."""
    t0 = time.time()
    last_log = 0.0
    while rclpy.ok() and (time.time() - t0) < timeout_sec:
        rclpy.spin_once(tracker, timeout_sec=0.05)
        if tracker.get_marker(marker_id) is not None:
            return True
        now = time.time()
        if nav is not None and now - last_log >= 1.0:
            seen = tracker.list_recent_ids()
            nav.info(f'[{label}] waiting for id={marker_id}, seen_ids={seen or "[]"}')
            last_log = now
        time.sleep(0.03)
    return tracker.get_marker(marker_id) is not None

def _rotate_for(nav, tracker, cmd_pub, marker_id, signed_speed, duration) -> bool:
    """Rotate in place at signed_speed for duration seconds; True as soon as marker is decoded.

    We only need to confirm the marker exists: the face-on goal comes from the fixed
    map pose (compute_face_on_goal), and visual_align refines afterwards. So accept any
    decode — don't require a large / square view here.
    """
    twist = Twist()
    twist.angular.z = signed_speed
    t0 = time.time()
    while rclpy.ok() and (time.time() - t0) < duration:
        cmd_pub.publish(twist)
        rclpy.spin_once(tracker, timeout_sec=0.02)
        m = tracker.get_marker(marker_id)
        if m is not None:
            _stop(cmd_pub)
            nav.info(
                f'[Search] Found marker {marker_id} '
                f'(width={m["width_ratio"]:.2f}, yaw={m["marker_yaw"]:+.2f}).')
            return True
        time.sleep(0.03)
    _stop(cmd_pub)
    return False

def search_marker_360(nav, tracker, cmd_pub, marker_id) -> bool:
    """Bounded sweep -90° → current → +90° (not a full turn) to find a usable marker view."""
    nav.info(f'[Search] Sweeping ±{math.degrees(SEARCH_SWEEP_RAD):.0f}° for marker {marker_id} '
             f'(FOV≠decoded — need better viewing angle)...')
    speed = abs(SEARCH_ANGULAR_SPEED)
    t90 = SEARCH_SWEEP_RAD / speed

    # current → -90 (CW), then -90 → +90 (CCW, 180°), then +90 → current (CW)
    if _rotate_for(nav, tracker, cmd_pub, marker_id, -speed, t90):
        return True
    if _rotate_for(nav, tracker, cmd_pub, marker_id, +speed, 2 * t90):
        return True
    if _rotate_for(nav, tracker, cmd_pub, marker_id, -speed, t90):
        return True

    _stop(cmd_pub)
    nav.warn(f'[Search] Swept ±{math.degrees(SEARCH_SWEEP_RAD):.0f}° but did not find '
             f'marker {marker_id}.')
    return False

def visual_align(nav, tracker, cmd_pub, marker_id, approach=True) -> bool:
    """Phase 2 — fine visual servo AFTER the robot is already in front (Nav2).

    Order: bearing (look at marker) → yaw (square to plane) → width (creep in).
    """
    nav.info(f'[Align/Visual] Phase 2 — bearing → yaw → width '
             f'(marker {marker_id}, approach={"on" if approach else "off"})...')
    t0 = time.time()
    last_seen = time.time()
    last_err = 0.0
    last_log = 0.0
    phase = 'bearing'

    while rclpy.ok():
        if time.time() - t0 > ALIGN_TIMEOUT:
            _stop(cmd_pub)
            nav.warn('[Align/Visual] Timed out.')
            return False

        rclpy.spin_once(tracker, timeout_sec=0.02)
        m = tracker.get_marker(marker_id)
        twist = Twist()

        if m is None:
            if time.time() - last_seen > ALIGN_LOST_TIMEOUT:
                _stop(cmd_pub)
                nav.warn(f'[Align/Visual] Marker {marker_id} lost. Falling back to 360...')
                if search_marker_360(nav, tracker, cmd_pub, marker_id):
                    last_seen = time.time()
                    last_err = 0.0
                    continue
                else:
                    nav.error(f'[Align/Visual] Failed to recover marker {marker_id}.')
                    return False
            twist.angular.z = math.copysign(0.25, -last_err) if abs(last_err) > 1e-3 else 0.25
            cmd_pub.publish(twist)
            time.sleep(0.03)
            continue

        last_seen = time.time()
        err = m['err_x']
        width = m['width_ratio']
        marker_yaw = m.get('marker_yaw', 0.0)

        bearing = err
        tvec = m.get('tvec')
        if tvec is not None:
            tx, _, tz = tvec.flatten()
            if abs(tz) > 1e-4:
                bearing = math.atan2(float(tx), float(tz))
        last_err = bearing

        centered = abs(bearing) < ALIGN_CENTER_TOL
        face_on = abs(marker_yaw) < ALIGN_YAW_TOL
        close_enough = width_ok(width)

        if not centered:
            phase = 'bearing'
        elif not face_on:
            phase = 'yaw'
        elif approach and not close_enough:
            phase = 'width'
        else:
            phase = 'done'

        now = time.time()
        if now - last_log >= ALIGN_LOG_PERIOD:
            nav.info(f'[Align/Visual] [{phase}] bearing={bearing:+.3f}, '
                     f'yaw={marker_yaw:+.3f}, width={width:.2f}')
            last_log = now

        if centered and face_on and (not approach or close_enough):
            _stop(cmd_pub)
            nav.info(f'[Align/Visual] Done: bearing={bearing:+.3f}, '
                     f'yaw={marker_yaw:+.3f}, width={width:.2f}.')
            return True

        # 1) bearing  2) yaw  3) width — never mix
        if not centered:
            ang = -ALIGN_KP_ANG * bearing
            twist.angular.z = max(-ALIGN_MAX_ANG, min(ALIGN_MAX_ANG, ang))
        elif not face_on:
            ang = -ALIGN_KP_YAW * marker_yaw
            twist.angular.z = max(-ALIGN_MAX_ANG, min(ALIGN_MAX_ANG, ang))
        elif approach and not close_enough:
            twist.linear.x = ALIGN_FWD_SPEED

        cmd_pub.publish(twist)
        time.sleep(0.03)

    _stop(cmd_pub)
    return False


def back_off_until_blocked(nav, tracker, cmd_pub, marker_id, label) -> bool:
    """Reverse (camera still facing the marker) until the robot stops moving (blocked).

    Stall detection: monitor odom->base_link displacement over a time window; if the
    robot barely moved while commanded backward, it's against something → stop.
    odom is used (not map) because AMCL's map pose updates in laggy, discrete jumps
    that can look like a stall even while the robot is cruising.
    """
    nav.info(f'[{label}] Backing off — reversing until blocked (camera on marker {marker_id})...')

    def get_xy():
        # Prefer odom (continuous, wheel-driven); fall back to map if odom missing.
        for parent in ('odom', 'map'):
            try:
                tf = tracker.tf_buffer.lookup_transform(parent, 'base_link', rclpy.time.Time())
                return float(tf.transform.translation.x), float(tf.transform.translation.y)
            except Exception:
                continue
        return None

    def get_range(marker):
        # Distance camera→marker (metres) from PnP; bigger = farther away.
        if marker is None:
            return None
        tvec = marker.get('tvec')
        if tvec is not None:
            tx, ty, tz = tvec.flatten()
            return math.sqrt(float(tx) ** 2 + float(ty) ** 2 + float(tz) ** 2)
        return None

    t0 = time.time()
    last_check = t0
    win_start_xy = get_xy()
    stalled_windows = 0

    # Auto-direction: we want to move AWAY from the marker (range increasing).
    # Start with the ROS convention (-x = backward), then verify against the
    # marker range and flip once if we're actually getting closer.
    direction = -1.0
    dir_locked = False
    range_ref = None

    while rclpy.ok():
        if time.time() - t0 > BACKUP_TIMEOUT:
            _stop(cmd_pub)
            nav.warn(f'[{label}] Back-off timed out.')
            return False

        rclpy.spin_once(tracker, timeout_sec=0.02)
        twist = Twist()
        twist.linear.x = direction * BACKUP_SPEED

        # Keep the marker centered so the camera keeps looking at it while reversing.
        m = tracker.get_marker(marker_id)
        if m is not None:
            bearing = m['err_x']
            tvec = m.get('tvec')
            if tvec is not None:
                tx, _, tz = tvec.flatten()
                if abs(tz) > 1e-4:
                    bearing = math.atan2(float(tx), float(tz))
            ang = BACKUP_KP_ANG * bearing
            twist.angular.z = max(-BACKUP_MAX_ANG, min(BACKUP_MAX_ANG, ang))

        cmd_pub.publish(twist)

        now = time.time()

        # Warm-up: let the robot accelerate before we start judging stalls.
        if now - t0 < BACKUP_WARMUP:
            win_start_xy = get_xy()
            last_check = now
            if range_ref is None:
                range_ref = get_range(m)
            time.sleep(0.03)
            continue

        # After warm-up, verify direction once: if range shrank, we're going the
        # wrong way (toward the marker) — flip.
        if not dir_locked:
            r_now = get_range(m)
            if r_now is not None and range_ref is not None:
                delta = r_now - range_ref
                if delta < -BACKUP_DIR_RANGE_EPS:
                    direction = -direction
                    nav.warn(f'[{label}] Wrong way (range {range_ref:.2f}→{r_now:.2f}m). '
                             f'Flipping backward direction.')
                    dir_locked = True
                    range_ref = r_now
                    win_start_xy = get_xy()
                    last_check = now
                    stalled_windows = 0
                    time.sleep(0.03)
                    continue
                elif delta > BACKUP_DIR_RANGE_EPS:
                    nav.info(f'[{label}] Direction OK (range {range_ref:.2f}→{r_now:.2f}m, moving away).')
                    dir_locked = True
            # If range unknown/unchanged, keep current direction and keep checking.

        if now - last_check >= BACKUP_STALL_WINDOW:
            xy = get_xy()
            if xy is not None and win_start_xy is not None:
                moved = math.hypot(xy[0] - win_start_xy[0], xy[1] - win_start_xy[1])
                nav.info(f'[{label}] Back-off moved {moved:.3f}m in last '
                         f'{BACKUP_STALL_WINDOW:.1f}s (stalled_windows={stalled_windows}).')
                if moved < BACKUP_STALL_DIST:
                    stalled_windows += 1
                    # Require consecutive stalled windows to avoid a single bad TF sample.
                    if stalled_windows >= BACKUP_STALL_WINDOWS_REQUIRED:
                        _stop(cmd_pub)
                        nav.info(f'[{label}] Blocked — cannot move backward anymore. Stopped.')
                        return True
                else:
                    stalled_windows = 0
            win_start_xy = xy
            last_check = now

        time.sleep(0.03)

    _stop(cmd_pub)
    return False


def goto_face_on_position(nav, tracker, marker_id, label) -> bool:
    """Phase 1 — Nav2 to the standoff pose directly in front of the marker."""
    goal = compute_face_on_goal(marker_id)
    if goal is None:
        nav.warn(f'[{label}] Phase 1 (position): no face-on goal for marker {marker_id}.')
        return False

    gx, gy, gyaw = goal
    nav.info(f'[{label}] Phase 1 (position) — Nav2 in front of marker {marker_id} '
             f'at ({gx:.3f}, {gy:.3f}) yaw={gyaw:.0f}°...')
    nav.clearAllCostmaps()
    time.sleep(0.3)
    pose = nav.getPoseStamped([gx, gy], gyaw)
    nav.startToPose(pose)
    while not nav.isTaskComplete():
        rclpy.spin_once(tracker, timeout_sec=0.05)
        time.sleep(0.05)

    nav.info(f'[{label}] Phase 1 done — settling {POST_NAV_SETTLE_TIMEOUT:.1f}s...')
    _wait_for_marker(tracker, marker_id, POST_NAV_SETTLE_TIMEOUT, nav=nav, label=label)
    return True


def goto_approach(nav, position, heading):
    nav.clearAllCostmaps()
    time.sleep(0.5)
    pose = nav.getPoseStamped(position, heading)
    nav.startToPose(pose)

def startup_sequence(nav, tracker, cmd_pub):
    nav.info('[STARTUP] Set init to spawn pose.')
    nav.setInitialPose(nav.getPoseStamped(SPAWN_POSE, SPAWN_HEADING))
    nav.waitUntilNav2Active()
    nav.info(f'Nav2 ACTIVE. Enabling camera scan for dock ArUco marker (ID {DOCK_MARKER_ID})...')

    seen = False
    t0 = time.time()
    while time.time() - t0 < 15.0:
        rclpy.spin_once(tracker, timeout_sec=0.05)
        if tracker.get_marker(DOCK_MARKER_ID) is not None:
            seen = True
            break

    if not seen:
        if search_marker_360(nav, tracker, cmd_pub, DOCK_MARKER_ID):
            seen = True

    if seen:
        visual_align(nav, tracker, cmd_pub, DOCK_MARKER_ID, approach=False)
        nav.info('[STARTUP] Dock confirmed.')
    else:
        nav.warn('[STARTUP] Could not confirm dock.')

    nav.info('[STARTUP] Complete.')

def compute_face_on_goal(marker_id, approach_dist=APPROACH_DIST):
    """
    Return (x, y, yaw_deg) in map frame for the standoff position that is
    directly in front of marker_id at approach_dist metres, facing the marker.

    Strategy: use the known marker global TF (get_marker_global_tf) instead of
    the noisy per-frame detection so the goal is always exact.

    South-rail markers (X_map < 8.0) face +X_map  → robot stands at
       marker_X + dist, same Y, heading SOUTH (180°).
    North-rail markers (X_map ≥ 8.0) face -X_map  → robot stands at
       marker_X - dist, same Y, heading NORTH (0°).
    Dock marker is a special case (face -Y_map from kitchen side).
    """
    T = get_marker_global_tf(marker_id)
    if T is None:
        return None
    mx, my = T[0, 3], T[1, 3]
    if marker_id == DOCK_MARKER_ID:
        # Dock marker faces -Y_map (toward kitchen): robot arrives from -Y_map side
        return mx, my - approach_dist, 90.0   # EAST heading (face +Y_map toward dock)
    elif mx < 8.0:   # south-rail markers (1, 3, 4, 6)
        return mx + approach_dist, my, 180.0  # SOUTH heading
    else:            # north-rail markers (2, 5)
        return mx - approach_dist, my, 0.0    # NORTH heading


def _search_then_align(nav, tracker, cmd_pub, marker_id, label):
    """
    1. Find marker (quick check / 360).
    2. AMCL pose correction (gated).
    3. Phase 1 — POSITION: Nav2 to standoff directly in front of the marker.
    4. Phase 2 — VISUAL: bearing → yaw → width.
    """
    tracker.set_correction_target(marker_id)
    try:
        nav.info(f'[{label}] Quick detect check ({QUICK_DETECT_TIMEOUT:.1f}s) for '
                 f'marker {marker_id}...')
        found = _wait_for_marker(
            tracker, marker_id, QUICK_DETECT_TIMEOUT, nav=nav, label=label)
        if found:
            nav.info(f'[{label}] Marker {marker_id} already decoded — skip rotation.')
        else:
            nav.info(f'[{label}] Not decoded (seen_ids={tracker.list_recent_ids() or "[]"}) '
                     f'— starting 360 rotation search...')
            found = search_marker_360(nav, tracker, cmd_pub, marker_id)

        if not found:
            nav.warn(f'[{label}] Marker {marker_id} never found — skip position+visual align.')
            return

        # --- Phase 1: Nav2 to the standoff pose in front of the marker (no teleport) ---
        if not goto_face_on_position(nav, tracker, marker_id, label):
            nav.warn(f'[{label}] Phase 1 failed — skipping visual align.')
            return

        # --- Phase 2: bearing → yaw → width only ---
        visual_align(nav, tracker, cmd_pub, marker_id, approach=True)

        # --- Phase 3: reverse (camera still on marker) until blocked ---
        back_off_until_blocked(nav, tracker, cmd_pub, marker_id, label)

    finally:
        tracker.clear_correction_target()


def deliver_to(nav, name, tracker, cmd_pub):
    dest = DESTINATIONS[name]
    marker_id = dest['id']
    position, heading = dest['approach']

    nav.info(f'── Delivering to {name} (ArUco ID {marker_id}) ──')
    goto_approach(nav, position, heading)
    _run_nav_primitive(nav)
    nav.info(f'[{name}] Arrived at approach point. Initiating Visual Alignment...')
    _search_then_align(nav, tracker, cmd_pub, marker_id, name)
    nav.info(f'[{name}] Delivery complete.')


def return_to_dock(nav, tracker, cmd_pub):
    position, heading = DOCK_APPROACH
    nav.info('── Returning to Dock ──')
    goto_approach(nav, position, heading)
    _run_nav_primitive(nav)
    nav.info('[Dock] Arrived. Aligning...')
    _search_then_align(nav, tracker, cmd_pub, DOCK_MARKER_ID, 'Dock')
    nav.info('[Dock] Returned. Complete.')

def main(args=None):
    rclpy.init(args=args)

    nav = NavigatorWithSim()
    tracker = ArucoTracker()
    cmd_pub = nav.create_publisher(Twist, CMD_VEL_TOPIC, 10)

    try:
        startup_sequence(nav, tracker, cmd_pub)

        names = list(DESTINATIONS.keys())
        menu = names + ['Return to Dock', 'Exit']

        nav.info('Welcome to the restaurant delivery service.')
        while rclpy.ok():
            opts = 'Choose a destination (enter a number):\n'
            for i, label in enumerate(menu):
                opts += f'    {i}. {label}\n'
            raw = input(f'{opts}Selection: ')

            try:
                idx = int(raw)
            except ValueError:
                nav.error(f'Invalid selection: {raw}')
                continue

            if idx < 0 or idx >= len(menu):
                nav.error(f'Out of range: {idx}')
                continue

            choice = menu[idx]
            if choice == 'Exit':
                break
            elif choice == 'Return to Dock':
                return_to_dock(nav, tracker, cmd_pub)
            else:
                deliver_to(nav, choice, tracker, cmd_pub)

    except KeyboardInterrupt:
        nav.info('Interrupted by user.')
    finally:
        if rclpy.ok():
            try:
                _stop(cmd_pub)
            except Exception:
                pass
            tracker.destroy_node()
            rclpy.shutdown()

if __name__ == '__main__':
    main()
