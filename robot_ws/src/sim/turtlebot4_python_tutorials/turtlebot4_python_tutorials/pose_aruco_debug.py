#!/usr/bin/env python3

import math
import time
import numpy as np

import cv2
from cv_bridge import CvBridge

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from geometry_msgs.msg import TransformStamped, PoseWithCovarianceStamped
from sensor_msgs.msg import Image, CameraInfo
import tf2_ros

ARUCO_DICT_TYPE = cv2.aruco.DICT_4X4_50
CAMERA_TOPIC = '/camera/color/image_raw'
CAMERA_INFO_TOPIC = '/camera/color/camera_info'
DEBUG_IMAGE_TOPIC = '/aruco_debug_image'

class PoseArucoDebugNode(Node):
    def __init__(self):
        super().__init__('pose_aruco_debug')

        # TF setup for printing pose
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # ArUco setup
        self.bridge = CvBridge()
        self.camera_matrix = None
        self.dist_coeffs = None
        
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)
        self.aruco_params = cv2.aruco.DetectorParameters_create()

        # Subscribers
        self.create_subscription(CameraInfo, CAMERA_INFO_TOPIC, self._camera_info_cb, qos_profile_sensor_data)
        self.create_subscription(Image, CAMERA_TOPIC, self._image_cb, qos_profile_sensor_data)
        
        # Publishers
        self.debug_pub = self.create_publisher(Image, DEBUG_IMAGE_TOPIC, 10)
        self.initial_pose_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)

        # Timers
        self.pose_timer = self.create_timer(1.0, self.print_pose)
        self.init_pose_timer = self.create_timer(3.0, self._publish_initial_pose)
        
        self.last_pose = None
        self.initial_pose_sent = False
        self.get_logger().info('Pose and ArUco Debug Node started.')

    def _publish_initial_pose(self):
        if not self.initial_pose_sent:
            msg = PoseWithCovarianceStamped()
            msg.header.frame_id = 'map'
            msg.header.stamp = self.get_clock().now().to_msg()
            
            # The AMCL map frame is rotated and translated relative to the Gazebo world frame.
            # Spawn in Gazebo: x=-1.95, y=-8.0, yaw=1.5708 (facing +Y_world)
            # Map frame: X_map = Y_world + 8.0 = 0.0
            #            Y_map = -X_world - 1.95 = 0.0
            #            Yaw_map = 0.0 (since facing +Y_world is +X_map)
            msg.pose.pose.position.x = 0.0
            msg.pose.pose.position.y = 0.0
            msg.pose.pose.position.z = 0.0
            
            yaw = 0.0
            msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
            msg.pose.pose.orientation.w = math.cos(yaw / 2.0)
            
            # small covariance
            msg.pose.covariance[0] = 0.05
            msg.pose.covariance[7] = 0.05
            msg.pose.covariance[35] = 0.05
            
            self.initial_pose_pub.publish(msg)
            self.get_logger().info('Published initial pose (0.0, 0.0, 0.0) to initialize AMCL.')
            self.initial_pose_sent = True
            self.init_pose_timer.cancel()

    def _camera_info_cb(self, msg: CameraInfo):
        if self.camera_matrix is None:
            self.camera_matrix = np.array(msg.k).reshape((3, 3))
            self.dist_coeffs = np.array(msg.d)
            self.get_logger().info('Received CameraInfo')

    def _image_cb(self, msg: Image):
        if self.camera_matrix is None:
            return

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().warn(f'cv_bridge error: {e}')
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.aruco_params)

        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            for i in range(len(ids)):
                marker_id = int(ids[i][0])
                c = corners[i][0]
                xs, ys = c[:, 0], c[:, 1]
                cv2.putText(frame, f'id={marker_id}',
                            (int(xs.min()), max(20, int(ys.min()) - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)
            self.get_logger().info(f'Detected ArUco IDs: {[int(x[0]) for x in ids]}')

        # Publish debug image continuously
        try:
            debug_msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            debug_msg.header = msg.header
            self.debug_pub.publish(debug_msg)
        except Exception as e:
            self.get_logger().warn(f'Publish debug image error: {e}')

    def euler_from_quaternion(self, x, y, z, w):
        """Convert quaternion into euler angles (roll, pitch, yaw)"""
        t0 = +2.0 * (w * x + y * z)
        t1 = +1.0 - 2.0 * (x * x + y * y)
        roll_x = math.atan2(t0, t1)
        
        t2 = +2.0 * (w * y - z * x)
        t2 = +1.0 if t2 > +1.0 else t2
        t2 = -1.0 if t2 < -1.0 else t2
        pitch_y = math.asin(t2)
        
        t3 = +2.0 * (w * z + x * y)
        t4 = +1.0 - 2.0 * (y * y + z * z)
        yaw_z = math.atan2(t3, t4)
        
        return roll_x, pitch_y, yaw_z

    def print_pose(self):
        try:
            trans = self.tf_buffer.lookup_transform('map', 'base_link', rclpy.time.Time())
            t = trans.transform.translation
            q = trans.transform.rotation
            _, _, yaw = self.euler_from_quaternion(q.x, q.y, q.z, q.w)
            
            # Print only if pose has changed significantly
            current_pose = (t.x, t.y, yaw)
            if self.last_pose is None or \
               abs(current_pose[0] - self.last_pose[0]) > 0.05 or \
               abs(current_pose[1] - self.last_pose[1]) > 0.05 or \
               abs(current_pose[2] - self.last_pose[2]) > 0.05:
                
                self.get_logger().info(f'Robot Pose (map -> base_link): x={t.x:.3f}, y={t.y:.3f}, yaw={yaw:.3f}')
                self.last_pose = current_pose
        except Exception as e:
            pass # Suppress warning while map is not ready

def main(args=None):
    rclpy.init(args=args)
    node = PoseArucoDebugNode()
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
