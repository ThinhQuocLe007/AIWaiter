#!/usr/bin/env python3

import math

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry, Path
from rclpy.node import Node


class PathPublisher(Node):
    def __init__(self):
        super().__init__('path_publisher')

        self.declare_parameter('odom_topic', '/odometry/filtered')
        self.declare_parameter('path_topic', '/filtered_path')
        self.declare_parameter('path_frame', 'odom')
        self.declare_parameter('min_translation', 0.02)
        self.declare_parameter('min_rotation', 0.05)
        self.declare_parameter('max_path_points', 5000)

        odom_topic = self.get_parameter('odom_topic').value
        path_topic = self.get_parameter('path_topic').value
        self.path_frame = self.get_parameter('path_frame').value
        self.min_translation = float(self.get_parameter('min_translation').value)
        self.min_rotation = float(self.get_parameter('min_rotation').value)
        self.max_path_points = int(self.get_parameter('max_path_points').value)

        self.path_msg = Path()
        self.last_pose = None

        self.path_publisher = self.create_publisher(Path, path_topic, 10)
        self.create_subscription(Odometry, odom_topic, self.odom_callback, 50)

    def odom_callback(self, msg: Odometry):
        pose = msg.pose.pose

        if self.last_pose is not None and not self._should_append_pose(pose):
            return

        pose_stamped = PoseStamped()
        pose_stamped.header = msg.header
        pose_stamped.header.frame_id = self.path_frame or msg.header.frame_id
        pose_stamped.pose = pose

        self.path_msg.header.stamp = msg.header.stamp
        self.path_msg.header.frame_id = pose_stamped.header.frame_id
        self.path_msg.poses.append(pose_stamped)

        if len(self.path_msg.poses) > self.max_path_points:
            self.path_msg.poses = self.path_msg.poses[-self.max_path_points:]

        self.last_pose = pose
        self.path_publisher.publish(self.path_msg)

    def _should_append_pose(self, pose) -> bool:
        dx = pose.position.x - self.last_pose.position.x
        dy = pose.position.y - self.last_pose.position.y
        distance = math.hypot(dx, dy)

        yaw = self._yaw_from_quaternion(pose.orientation)
        last_yaw = self._yaw_from_quaternion(self.last_pose.orientation)
        yaw_delta = math.atan2(math.sin(yaw - last_yaw), math.cos(yaw - last_yaw))

        return distance >= self.min_translation or abs(yaw_delta) >= self.min_rotation

    @staticmethod
    def _yaw_from_quaternion(quat) -> float:
        siny_cosp = 2.0 * (quat.w * quat.z + quat.x * quat.y)
        cosy_cosp = 1.0 - 2.0 * (quat.y * quat.y + quat.z * quat.z)
        return math.atan2(siny_cosp, cosy_cosp)


def main(args=None):
    rclpy.init(args=args)
    node = PathPublisher()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()