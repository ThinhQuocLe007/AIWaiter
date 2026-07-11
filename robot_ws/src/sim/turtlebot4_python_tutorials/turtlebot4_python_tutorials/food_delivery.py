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
    'Table 1': {'id': 1, 'approach': ([7.99985, 1.36319], TurtleBot4Directions.SOUTH)},
    'Table 2': {'id': 2, 'approach': ([8.05419, 0.33537], TurtleBot4Directions.NORTH)},
    'Table 3': {'id': 3, 'approach': ([7.97830, -0.64879], TurtleBot4Directions.SOUTH)},
    'Table 4': {'id': 4, 'approach': ([7.92656, -3.28752], TurtleBot4Directions.SOUTH)},
    'Table 5': {'id': 5, 'approach': ([7.98864, -4.28860], TurtleBot4Directions.NORTH)},
    'Table 6': {'id': 6, 'approach': ([8.00802, -5.27848], TurtleBot4Directions.SOUTH)},
}

DOCK_APPROACH = ([0.0, 0.0], TurtleBot4Directions.NORTH)

DETECT_MAX_AGE = 1.0               
SEARCH_ANGULAR_SPEED = 0.45        
SEARCH_TIMEOUT = 2 * math.pi / SEARCH_ANGULAR_SPEED + 6.0

ALIGN_KP_ANG = 1.3                 
ALIGN_MAX_ANG = 0.5                
ALIGN_FWD_SPEED = 0.10             
ALIGN_CENTER_TOL = 0.06            
ALIGN_FWD_GATE = 0.20              
ALIGN_STOP_WIDTH = 0.34            
ALIGN_TIMEOUT = 30.0
ALIGN_LOST_TIMEOUT = 2.5           

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
        T_world_marker[:3, :3] = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
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

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)
        self.aruco_params = cv2.aruco.DetectorParameters_create()

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
                    # Draw Axes
                    cv2.drawFrameAxes(frame, self.camera_matrix, self.dist_coeffs, rvec, tvec, MARKER_SIZE)
                    
                    # Store 2D info for visual alignment
                    xs, ys = c[:, 0], c[:, 1]
                    cx, cy = float(xs.mean()), float(ys.mean())
                    bbox_w = float(xs.max() - xs.min())
                    bbox_h = float(ys.max() - ys.min())
                    h, w = gray.shape[:2]

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
                        
                    # Opportunistic continuous localization to fix drift
                    if now - self.last_correction_time > 3.0:
                        if bbox_w / w > 0.05: # Marker is large enough to trust
                            self.trigger_pose_correction(marker_id)
                            self.last_correction_time = now

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
            'rvec': rvec, 'tvec': tvec, 'frame_id': frame_id
        }

    def trigger_pose_correction(self, marker_id):
        m = self.get_marker(marker_id)
        if m is None:
            self.get_logger().warn(f'Cannot correct pose: Marker {marker_id} not recently seen.')
            return

        T_map_marker = get_marker_global_tf(marker_id)
        if T_map_marker is None:
            self.get_logger().warn(f'No global pose known for marker {marker_id}')
            return

        rmat, _ = cv2.Rodrigues(m['rvec'])
        T_cam_marker = np.eye(4)
        T_cam_marker[:3, :3] = rmat
        T_cam_marker[:3, 3] = m['tvec'].flatten()

        try:
            tf_cam_base = self.tf_buffer.lookup_transform(m['frame_id'], 'base_link', rclpy.time.Time())
            t = tf_cam_base.transform.translation
            q = tf_cam_base.transform.rotation
            from scipy.spatial.transform import Rotation # if available, else manual
            # To keep it standard, let's just use manual matrix
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
            return

        # T_map_base = T_map_marker * T_cam_marker^-1 * T_cam_base
        T_map_base = T_map_marker @ invert_tf(T_cam_marker) @ T_cam_base

        # Log current pose
        try:
            tf_map_base = self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
            curr_t = tf_map_base.transform.translation
            self.get_logger().info(f'---> BEFORE CORRECTION: Robot at x={curr_t.x:.3f}, y={curr_t.y:.3f}')
        except:
            pass

        # Publish initialpose
        pose_msg = PoseWithCovarianceStamped()
        pose_msg.header.frame_id = 'map'
        pose_msg.header.stamp = self.get_clock().now().to_msg()
        pose_msg.pose.pose.position.x = T_map_base[0, 3]
        pose_msg.pose.pose.position.y = T_map_base[1, 3]
        pose_msg.pose.pose.position.z = T_map_base[2, 3]
        
        quat = rot_to_quat(T_map_base[:3, :3])
        pose_msg.pose.pose.orientation.x = quat[0]
        pose_msg.pose.pose.orientation.y = quat[1]
        pose_msg.pose.pose.orientation.z = quat[2]
        pose_msg.pose.pose.orientation.w = quat[3]

        # Small covariance to force AMCL update
        cov = np.zeros((6, 6))
        np.fill_diagonal(cov, 0.01)
        pose_msg.pose.covariance = cov.flatten().tolist()

        self.initialpose_pub.publish(pose_msg)
        self.get_logger().info(f'---> AFTER CORRECTION: Published new pose x={T_map_base[0, 3]:.3f}, y={T_map_base[1, 3]:.3f}')


def _stop(cmd_pub):
    cmd_pub.publish(Twist())

def _run_nav_primitive(nav: TurtleBot4Navigator):
    while not nav.isTaskComplete():
        time.sleep(0.1)

def search_marker_360(nav, tracker, cmd_pub, marker_id) -> bool:
    nav.info(f'[Search] Marker {marker_id} not visible — rotating once to search...')
    twist = Twist()
    twist.angular.z = SEARCH_ANGULAR_SPEED
    t0 = time.time()
    while rclpy.ok() and (time.time() - t0) < SEARCH_TIMEOUT:
        cmd_pub.publish(twist)
        rclpy.spin_once(tracker, timeout_sec=0.02)
        if tracker.get_marker(marker_id) is not None:
            _stop(cmd_pub)
            nav.info(f'[Search] Found marker {marker_id}.')
            return True
        time.sleep(0.03)
    _stop(cmd_pub)
    nav.warn(f'[Search] Completed one turn but still did not find marker {marker_id}.')
    return False

def visual_align(nav, tracker, cmd_pub, marker_id, approach=True) -> bool:
    nav.info(f'[Align] Aligning with marker {marker_id}...')
    t0 = time.time()
    last_seen = time.time()
    last_err = 0.0

    while rclpy.ok():
        if time.time() - t0 > ALIGN_TIMEOUT:
            _stop(cmd_pub)
            nav.warn('[Align] Timed out.')
            return False

        rclpy.spin_once(tracker, timeout_sec=0.02)
        m = tracker.get_marker(marker_id)
        twist = Twist()

        if m is None:
            if time.time() - last_seen > ALIGN_LOST_TIMEOUT:
                _stop(cmd_pub)
                nav.warn(f'[Align] Marker {marker_id} lost.')
                return False
            twist.angular.z = math.copysign(0.25, -last_err) if abs(last_err) > 1e-3 else 0.25
            cmd_pub.publish(twist)
            time.sleep(0.03)
            continue

        last_seen = time.time()
        err = m['err_x']
        last_err = err
        width = m['width_ratio']

        centered = abs(err) < ALIGN_CENTER_TOL
        close_enough = width >= ALIGN_STOP_WIDTH

        if centered and (not approach or close_enough):
            _stop(cmd_pub)
            nav.info(f'[Align] Done: err={err:+.3f}, width={width:.2f}.')
            tracker.trigger_pose_correction(marker_id)
            return True

        twist.angular.z = max(-ALIGN_MAX_ANG, min(ALIGN_MAX_ANG, -ALIGN_KP_ANG * err))
        if approach and abs(err) < ALIGN_FWD_GATE and not close_enough:
            twist.linear.x = ALIGN_FWD_SPEED

        cmd_pub.publish(twist)
        time.sleep(0.03)

    _stop(cmd_pub)
    return False

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

def deliver_to(nav, name, tracker, cmd_pub):
    dest = DESTINATIONS[name]
    marker_id = dest['id']
    position, heading = dest['approach']

    nav.info(f'── Delivering to {name} (ArUco ID {marker_id}) ──')
    goto_approach(nav, position, heading)
    _run_nav_primitive(nav)
    nav.info(f'[{name}] Arrived at approach point. Initiating Visual Alignment...')
    visual_align(nav, tracker, cmd_pub, marker_id, approach=False)
    nav.info(f'[{name}] Delivery complete.')

def return_to_dock(nav, tracker, cmd_pub):
    position, heading = DOCK_APPROACH
    nav.info('── Returning to Dock ──')
    goto_approach(nav, position, heading)
    _run_nav_primitive(nav)
    nav.info('[Dock] Arrived. Aligning...')
    visual_align(nav, tracker, cmd_pub, DOCK_MARKER_ID, approach=False)
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
