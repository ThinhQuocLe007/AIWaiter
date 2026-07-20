#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
import math

class EKFMonitor(Node):
    def __init__(self):
        super().__init__('ekf_monitor')
        self.subscription = self.create_subscription(
            Odometry,
            '/odometry/filtered',
            self.odom_callback,
            10
        )
        self.get_logger().info("EKF Monitor Started. Listening to /odometry/filtered...")

    def odom_callback(self, msg):
        # Extract X and Y position
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y

        # Extract yaw from quaternion
        q = msg.pose.pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        yaw_rad = math.atan2(siny_cosp, cosy_cosp)
        yaw_deg = math.degrees(yaw_rad)
        
        # Extract angular velocity Z
        wz = msg.twist.twist.angular.z

        # Print cleanly in a single line
        self.get_logger().info(
            f"EKF -> X: {x:+.3f}m | Y: {y:+.3f}m | Yaw: {yaw_deg:+06.2f} deg | V_Yaw: {wz:+.3f} rad/s"
        )

def main(args=None):
    rclpy.init(args=args)
    node = EKFMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
