#!/usr/bin/env python3

import math
import sys
import threading
import time
# pyrefly: ignore [missing-import]
import numpy as np

# pyrefly: ignore [missing-import]
import cv2
from cv_bridge import CvBridge

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from geometry_msgs.msg import Twist, TransformStamped, PoseWithCovarianceStamped
from sensor_msgs.msg import Image, CameraInfo
import tf2_ros

# pyrefly: ignore [missing-import]
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

# Heading (deg about map Z) = direction from the approach point straight at the
# marker, so the camera (front) faces the ArUco and the robot's rear faces the
# table. Computed from each marker's map pose (get_marker_global_tf); the old
# coarse cardinal value is kept in a comment for reference.
DESTINATIONS = {
    'Table 1': {'id': 1, 'approach': ([8.730,  1.301],  178.5)},  # was SOUTH (180)
    'Table 2': {'id': 2, 'approach': ([7.233,  0.314],    1.2)},  # was NORTH (0)
    'Table 3': {'id': 3, 'approach': ([8.741, -0.694],  178.5)},  # was SOUTH (180)
    'Table 4': {'id': 4, 'approach': ([8.700, -3.152], -176.5)},  # was SOUTH (180)
    'Table 5': {'id': 5, 'approach': ([7.257, -4.309],    2.1)},  # was NORTH (0)
    'Table 6': {'id': 6, 'approach': ([8.679, -5.178], -177.4)},  # was SOUTH (180)
}

DOCK_APPROACH = ([0.0, 0.0], TurtleBot4Directions.NORTH)

DETECT_MAX_AGE = 1.0               
SEARCH_ANGULAR_SPEED = -0.10 # rad/s (~7°/s). Negative = counter-clockwise. Lower = slower marker search sweep.
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
ALIGN_CENTER_TOL = 0.01
ALIGN_YAW_TOL = 0.25
ALIGN_FWD_GATE = 0.20              
ALIGN_STOP_WIDTH = 0.2
# Accept width in [ALIGN_STOP_WIDTH - tol, +∞) — not a hard separate 0.12 cutoff.
ALIGN_WIDTH_TOL = 0.03
ALIGN_TIMEOUT = 30.0
ALIGN_LOST_TIMEOUT = 3.5
ALIGN_LOG_PERIOD = 1.0

# Ablation switch. True  = full pipeline (heading + yaw_tolerance + visual_align).
#                  False = test ONLY the precise heading + Nav2 yaw_tolerance;
#                          visual_align/search are skipped so you can read the
#                          raw arrival error ([Arrival] err_x) and decide whether
#                          align actually earns its keep.
ENABLE_VISUAL_ALIGN = True

# Pose-correction gates (reject bad / false-ID snaps like tables→dock).
CORRECTION_MAX_YAW = 0.40         # ~14° — PnP unreliable when too oblique
CORRECTION_MAX_JUMP = 0.30         # metres; refuse teleporting AMCL across the map
CORRECTION_MAX_YAW_JUMP = 0.15     # rad (~8.6°); reject massive orientation updates that cause spinning
CORRECTION_RANGE_TOL = 0.5        # |map_dist_to_marker - cam_range| must be within this

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
        
        # Parse command line arguments manually to allow --correction-amcl:=false, --correction-ekf:=true
        corr_amcl = True
        corr_ekf = False
        for arg in sys.argv:
            if 'correction-amcl' in arg or 'correction_amcl' in arg:
                val = arg.replace(':=', ':').replace('=', ':').split(':')[-1].lower()
                corr_amcl = (val == 'true')
            elif 'correction-ekf' in arg or 'correction_ekf' in arg:
                val = arg.replace(':=', ':').replace('=', ':').split(':')[-1].lower()
                corr_ekf = (val == 'true')

        self.declare_parameter('correction_amcl', corr_amcl)
        self.declare_parameter('correction_ekf', corr_ekf)
        
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
        self.ekf_pose_pub = self.create_publisher(PoseWithCovarianceStamped, '/set_pose', 10)

        self.get_logger().info(f'[ArUco] Subscribed: {CAMERA_TOPIC} and {CAMERA_INFO_TOPIC} | AMCL Correction: {corr_amcl} | EKF Correction: {corr_ekf}')

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
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            self.get_logger().info(f'[ArUco] Detected IDs: {[int(x[0]) for x in ids]}')
            for i in range(len(ids)):
                marker_id = int(ids[i][0])
                c = corners[i][0]
                
                # 3D Pose Estimation
                success, rvec, tvec = cv2.solvePnP(self.obj_pts, c, self.camera_matrix, self.dist_coeffs)
                if success:
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

                    if get_marker_global_tf(marker_id) is not None:
                        if now - getattr(self, '_last_correction_time', 0.0) > 1.0:
                            if self.trigger_pose_correction(marker_id):
                                self._last_correction_time = now

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
        curr_yaw = None
        try:
            tf_map_base = self.tf_buffer.lookup_transform(
                'map', 'base_link', rclpy.time.Time())
            curr_x = float(tf_map_base.transform.translation.x)
            curr_y = float(tf_map_base.transform.translation.y)
            
            q_curr = tf_map_base.transform.rotation
            siny_cosp = 2 * (q_curr.w * q_curr.z + q_curr.x * q_curr.y)
            cosy_cosp = 1 - 2 * (q_curr.y * q_curr.y + q_curr.z * q_curr.z)
            curr_yaw = math.atan2(siny_cosp, cosy_cosp)
            
            self.get_logger().info(
                f'---> BEFORE CORRECTION: Robot at x={curr_x:.3f}, y={curr_y:.3f}')
        except Exception:
            pass

        is_navigating = (self._correction_target is not None)
        max_jump = CORRECTION_MAX_JUMP if is_navigating else 2.5
        max_yaw_jump = CORRECTION_MAX_YAW_JUMP if is_navigating else 1.0

        if curr_x is not None:
            jump = math.hypot(new_x - curr_x, new_y - curr_y)
            map_dist = math.hypot(mx - curr_x, my - curr_y)
            if jump > max_jump:
                self.get_logger().warn(
                    f'[Correct] Reject id={marker_id}: jump {jump:.2f}m > '
                    f'{max_jump}m '
                    f'(would snap to x={new_x:.3f}, y={new_y:.3f}). '
                    f'Likely wrong ID or AMCL already lost — not applying.')
                return False
            if abs(map_dist - cam_range) > CORRECTION_RANGE_TOL:
                self.get_logger().warn(
                    f'[Correct] Reject id={marker_id}: range mismatch '
                    f'map_dist_to_marker={map_dist:.2f}m vs cam_range={cam_range:.2f}m '
                    f'(tol {CORRECTION_RANGE_TOL}m). Wrong marker ID?')
                return False
            
            if curr_yaw is not None:
                new_yaw = math.atan2(T_map_base[1, 0], T_map_base[0, 0])
                yaw_jump = abs(math.atan2(math.sin(new_yaw - curr_yaw), math.cos(new_yaw - curr_yaw)))
                if yaw_jump > max_yaw_jump:
                    self.get_logger().warn(
                        f'[Correct] Reject id={marker_id}: yaw jump {math.degrees(yaw_jump):.1f}° > '
                        f'{math.degrees(max_yaw_jump)}°')
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

        # Calculate dynamic covariance based on distance and angle to marker
        # Base variances (when robot is at standoff 0.8m and looking face-on)
        base_pos_var = 0.01  # translation variance (x, y, z)
        base_yaw_var = 0.01  # rotation variance (roll, pitch, yaw)
        
        # Distance weight: scale quadratically with distance relative to standard approach distance of 0.8m
        scale_pos = (cam_range / 0.8) ** 2
        var_x = base_pos_var * scale_pos
        var_y = base_pos_var * scale_pos
        var_z = base_pos_var * scale_pos
        
        # Angle weight: scale quadratically with marker yaw angle relative to threshold 0.25
        scale_yaw = (1.0 + abs(marker_yaw) / 0.25) ** 2
        var_roll = base_yaw_var * scale_yaw
        var_pitch = base_yaw_var * scale_yaw
        var_yaw = base_yaw_var * scale_yaw
        
        cov = np.zeros((6, 6))
        cov[0, 0] = var_x
        cov[1, 1] = var_y
        cov[2, 2] = var_z
        cov[3, 3] = var_roll
        cov[4, 4] = var_pitch
        cov[5, 5] = var_yaw
        pose_msg.pose.covariance = cov.flatten().tolist()
        correction_amcl = self.get_parameter('correction_amcl').get_parameter_value().bool_value
        correction_ekf = self.get_parameter('correction_ekf').get_parameter_value().bool_value

        if correction_amcl:
            self.initialpose_pub.publish(pose_msg)
            self.get_logger().info(
                f'---> AFTER CORRECTION (AMCL): Published new pose x={new_x:.3f}, y={new_y:.3f} '
                f'(id={marker_id}, width={width:.2f}, yaw={marker_yaw:+.2f}, '
                f'cam_range={cam_range:.2f}m)')
        if correction_ekf:
            self.ekf_pose_pub.publish(pose_msg)
            self.get_logger().info(
                f'---> AFTER CORRECTION (EKF): Published new pose x={new_x:.3f}, y={new_y:.3f} '
                f'(id={marker_id}, width={width:.2f}, yaw={marker_yaw:+.2f}, '
                f'cam_range={cam_range:.2f}m)')
        return True

def _stop(cmd_pub):
    cmd_pub.publish(Twist())

def _run_nav_primitive(nav: TurtleBot4Navigator):
    while not nav.isTaskComplete():
        time.sleep(0.1)

def goto_approach(nav, position, heading):
    nav.clearAllCostmaps()
    time.sleep(0.5)
    pose = nav.getPoseStamped(position, heading)
    nav.startToPose(pose)

def startup_sequence(nav, tracker, cmd_pub):
    nav.info('[STARTUP] Set init to spawn pose.')
    nav.setInitialPose(nav.getPoseStamped(SPAWN_POSE, SPAWN_HEADING))
    nav.waitUntilNav2Active()
    nav.info('Nav2 ACTIVE. [STARTUP] Complete.')

def search_marker(nav, tracker, cmd_pub, marker_id):
    """Bounded ±SEARCH_SWEEP_RAD sweep to bring marker_id into view.

    Only a fallback for when the marker is not already in the camera FOV on
    arrival (e.g. AMCL drifted). Returns True as soon as it is detected.
    """
    if tracker.get_marker(marker_id) is not None:
        return True
    nav.info(f'[Search] Marker {marker_id} not visible — sweeping '
             f'±{math.degrees(SEARCH_SWEEP_RAD):.0f}°.')
    speed = abs(SEARCH_ANGULAR_SPEED)
    twist = Twist()
    # Sweep +SEARCH_SWEEP_RAD one way, then back across to -SEARCH_SWEEP_RAD.
    for direction, span in ((+1.0, SEARCH_SWEEP_RAD), (-1.0, 2 * SEARCH_SWEEP_RAD)):
        swept = 0.0
        last = time.time()
        while swept < span and rclpy.ok():
            if tracker.get_marker(marker_id) is not None:
                cmd_pub.publish(Twist())
                nav.info(f'[Search] Found marker {marker_id}.')
                return True
            now = time.time()
            swept += speed * (now - last)
            last = now
            twist.angular.z = direction * speed
            cmd_pub.publish(twist)
            time.sleep(0.05)
        cmd_pub.publish(Twist())
    found = tracker.get_marker(marker_id) is not None
    if not found:
        nav.warn(f'[Search] Marker {marker_id} not found after sweep.')
    return found

def visual_align(nav, tracker, cmd_pub, marker_id):
    """Rotate in place until marker_id is horizontally centered in the camera.

    Centering err_x -> 0 means the robot's heading points straight at the marker,
    which is exactly the 'heading not straight to the ArUco' problem. Rotation
    only: marker_yaw (viewing obliqueness) needs translation and is left to the
    approach pose, so it is logged for diagnostics but not driven here.
    """
    nav.info(f'[Align] Centering on marker {marker_id}.')
    twist = Twist()
    start = time.time()
    last_seen = start
    last_log = 0.0
    while rclpy.ok():
        now = time.time()
        if now - start > ALIGN_TIMEOUT:
            nav.warn(f'[Align] Timeout ({ALIGN_TIMEOUT}s) — stopping.')
            break

        m = tracker.get_marker(marker_id)
        if m is None:
            if now - last_seen > ALIGN_LOST_TIMEOUT:
                nav.warn('[Align] Marker lost — aborting align.')
                break
            cmd_pub.publish(Twist())  # hold still and wait to re-acquire
            time.sleep(0.05)
            continue

        last_seen = now
        err_x = m['err_x']       # >0: marker is right of image centre
        yaw = m['marker_yaw']    # obliqueness, logged only

        if abs(err_x) < ALIGN_CENTER_TOL:
            cmd_pub.publish(Twist())
            nav.info(f'[Align] Locked: err_x={err_x:+.3f} (yaw={yaw:+.2f}).')
            break

        # Marker right of centre (err_x>0) -> rotate clockwise (angular.z<0).
        ang = -ALIGN_KP_ANG * err_x
        ang = max(-ALIGN_MAX_ANG, min(ALIGN_MAX_ANG, ang))
        twist.angular.z = ang
        twist.linear.x = 0.0
        cmd_pub.publish(twist)

        if now - last_log > ALIGN_LOG_PERIOD:
            nav.info(f'[Align] err_x={err_x:+.3f}, yaw={yaw:+.2f}, ang={ang:+.2f}')
            last_log = now
        time.sleep(0.05)

    cmd_pub.publish(Twist())  # ensure fully stopped

def _acquire_and_align(nav, tracker, cmd_pub, marker_id, label):
    """After Nav2 arrival: brief settle, log the raw arrival error, then
    (optionally) search + visual-align. Set ENABLE_VISUAL_ALIGN=False to measure
    the heading + yaw_tolerance changes on their own."""
    settle = time.time()
    while time.time() - settle < POST_NAV_SETTLE_TIMEOUT:
        if tracker.get_marker(marker_id) is not None:
            break
        time.sleep(0.05)

    # Objective arrival metric — pure Nav2 heading, before any search/align.
    # |err_x| ~ 0 means the robot is already pointing straight at the marker.
    m = tracker.get_marker(marker_id)
    if m is not None:
        nav.info(f'[Arrival] err_x={m["err_x"]:+.3f}, marker_yaw={m["marker_yaw"]:+.2f} '
                 f'(marker {marker_id}, before search/align)')
    else:
        nav.warn(f'[Arrival] Marker {marker_id} NOT visible on arrival '
                 f'(heading too far off, or occluded).')

    if not ENABLE_VISUAL_ALIGN:
        nav.info('[Align] DISABLED (ablation test) — heading left as Nav2 arrival.')
        return

    if tracker.get_marker(marker_id) is None:
        search_marker(nav, tracker, cmd_pub, marker_id)

    if tracker.get_marker(marker_id) is not None:
        visual_align(nav, tracker, cmd_pub, marker_id)
    else:
        nav.warn(f'[{label}] Could not acquire marker {marker_id} — skipping align.')

def deliver_to(nav, name, tracker, cmd_pub):
    dest = DESTINATIONS[name]
    marker_id = dest['id']
    position, heading = dest['approach']

    nav.info(f'── Delivering to {name} (ArUco ID {marker_id}) ──')
    tracker.set_correction_target(marker_id)
    goto_approach(nav, position, heading)
    _run_nav_primitive(nav)
    nav.info(f'[{name}] Reached approach pose — acquiring marker.')
    _acquire_and_align(nav, tracker, cmd_pub, marker_id, name)
    nav.info(f'[{name}] Delivery complete.')
    tracker.clear_correction_target()

def return_to_dock(nav, tracker, cmd_pub):
    position, heading = DOCK_APPROACH
    nav.info('── Returning to Dock ──')
    tracker.set_correction_target(DOCK_MARKER_ID)
    goto_approach(nav, position, heading)
    _run_nav_primitive(nav)
    nav.info('[Dock] Reached approach pose — acquiring marker.')
    _acquire_and_align(nav, tracker, cmd_pub, DOCK_MARKER_ID, 'Dock')
    nav.info('[Dock] Returned to Dock.')
    tracker.clear_correction_target()

def main(args=None):
    rclpy.init(args=args)

    nav = NavigatorWithSim()
    tracker = ArucoTracker()
    cmd_pub = nav.create_publisher(Twist, CMD_VEL_TOPIC, 10)

    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(tracker)
    tracker_thread = threading.Thread(target=executor.spin, daemon=True)
    tracker_thread.start()

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
