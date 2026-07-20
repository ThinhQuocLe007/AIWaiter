#!/usr/bin/env python3

"""
TarkBot Robot ROS2 Node.
Main node for publishing robot sensor data and subscribing to velocity commands.

This node:
1. Connects to OpenCTR board via serial port
2. Receives 25-byte sensor data packets at 50Hz
3. Parses and converts raw data to SI units
4. Publishes: Odometry, IMU, Battery voltage, TF transforms
5. Subscribes to: cmd_vel (geometry_msgs/Twist)

Copyright 2022-2024 XTARK ROBOTIS CO., LTD.
Licensed under the Apache License, Version 2.0 (the "License")
"""

import rclpy
from rclpy.node import Node
from rclpy.time import Time
import math
import time
import struct
from typing import Optional

# ROS message types
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32
from tf2_ros import TransformBroadcaster

# Local modules
from .serial_protocol import SerialProtocol
from .data_converter import DataConverter


class TarkbotRobotNode(Node):
    """
    ROS2 node for TarkBot robot driver.
    Manages serial communication, data parsing, and ROS message publishing.
    """

    def __init__(self):
        """Initialize the TarkBot robot node."""
        super().__init__('tarkbot_robot_node')

        # Node parameters
        self.declare_parameter('robot_port', '/dev/ttyACM0')
        self.declare_parameter('robot_port_baud', 230400)
        self.declare_parameter('robot_type', 'r20_twd')
        self.declare_parameter('pub_odom_tf', True)
        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_footprint')
        self.declare_parameter('imu_frame', 'imu_link')
        self.declare_parameter('odom_topic', 'odom')
        self.declare_parameter('imu_topic', 'imu')
        self.declare_parameter('bat_topic', 'bat_vol')
        self.declare_parameter('cmd_vel_topic', 'cmd_vel')
        self.declare_parameter('debug_hex', False)

        # Get parameters
        self.robot_port = self.get_parameter('robot_port').value
        self.robot_port_baud = self.get_parameter('robot_port_baud').value
        self.robot_type = self.get_parameter('robot_type').value
        self.pub_odom_tf = self.get_parameter('pub_odom_tf').value
        self.odom_frame = self.get_parameter('odom_frame').value
        self.base_frame = self.get_parameter('base_frame').value
        self.imu_frame = self.get_parameter('imu_frame').value
        self.debug_hex = self.get_parameter('debug_hex').value

        odom_topic = self.get_parameter('odom_topic').value
        imu_topic = self.get_parameter('imu_topic').value
        bat_topic = self.get_parameter('bat_topic').value
        cmd_vel_topic = self.get_parameter('cmd_vel_topic').value

        self.get_logger().info(f"TarkBot Robot ROS2 Node Starting...")
        self.get_logger().info(f"Serial port: {self.robot_port} @ {self.robot_port_baud} baud")
        self.get_logger().info(f"Robot type: {self.robot_type}")
        if self.debug_hex:
            self.get_logger().info("HEX debug enabled: raw X-Protocol frames will be printed")

        # Initialize serial communication
        self.serial_proto = SerialProtocol(self.robot_port, self.robot_port_baud)
        self.data_converter = DataConverter()

        # Data storage
        self.last_imu_data = None
        self.last_velocity_data = None
        self.last_battery_data = None
        self.last_timestamp = 0.0

        # IMU calibration
        self.is_calibrating = True
        self.calibration_samples = []
        self.gyro_z_bias = 0.0

        # Odometry integration
        self.odom_x = 0.0
        self.odom_y = 0.0
        self.odom_theta = 0.0
        self.last_odom_timestamp = time.time()

        # IMU orientation quaternion (from Mahony AHRS filter)
        self.imu_quat = (1.0, 0.0, 0.0, 0.0)  # w, x, y, z

        # Publishers
        self.odom_publisher = self.create_publisher(Odometry, odom_topic, 50)
        self.imu_publisher = self.create_publisher(Imu, imu_topic, 50)
        self.bat_publisher = self.create_publisher(Float32, bat_topic, 10)
        self.tf_broadcaster = TransformBroadcaster(self)

        # Subscriber
        self.cmd_vel_subscription = self.create_subscription(
            Twist, cmd_vel_topic, self.cmd_vel_callback, 100)

        # Timer for checking connection and publishing data
        self.create_timer(0.02, self.timer_callback)  # 50 Hz

    def start(self) -> bool:
        """
        Start robot driver.
        
        Returns:
            True if successful, False otherwise
        """
        # Open serial port
        if not self.serial_proto.open():
            self.get_logger().error(f"Failed to open serial port {self.robot_port}")
            return False

        self.get_logger().info(f"Serial port {self.robot_port} opened successfully")

        # Start receiving data
        self.serial_proto.start_receive(self.on_data_received)
        # if self.debug_hex:
        #     self.serial_proto.set_raw_frame_callback(self.on_raw_frame)

        # Send robot type to controller
        if not self.serial_proto.send_robot_type(self.robot_type):
            self.get_logger().warn("Failed to send robot type")
        else:
            self.get_logger().info(
                "Robot type check sent. OpenCTR firmware kinematics are compile-time fixed; "
                "this value is used for type match indication."
            )

        self.get_logger().info("TarkBot Robot initialized and running!")
        return True

    def stop(self):
        """Stop robot driver and cleanup."""
        self.get_logger().info("Stopping TarkBot Robot...")

        # Send stop command
        try:
            self.serial_proto.send_stop_command()
        except Exception as e:
            self.get_logger().warn(f"Error sending stop command: {e}")

        # Close serial port
        self.serial_proto.close()
        self.get_logger().info("TarkBot Robot stopped")

    def on_data_received(self, payload: bytes):
        """
        Callback when data frame is received from OpenCTR board.
        
        Args:
            payload: 20-byte sensor data payload
        """
        try:
            current_time = time.time()
            sensor_data = self.data_converter.parse_sensor_data(payload, current_time)

            self.last_imu_data = sensor_data.imu
            self.last_velocity_data = sensor_data.velocity
            self.last_battery_data = sensor_data.battery
            self.last_timestamp = current_time

            # Gyro Z Calibration phase (collect first 100 samples)
            if self.is_calibrating:
                self.calibration_samples.append(sensor_data.imu.gyro_z)
                if len(self.calibration_samples) >= 100:  # 2 seconds at 50Hz
                    self.gyro_z_bias = sum(self.calibration_samples) / 100.0
                    self.is_calibrating = False
                    self.get_logger().info(f"IMU Calibration Complete! Gyro Z Bias: {self.gyro_z_bias:+.5f} rad/s")
            else:
                # Apply bias calibration
                sensor_data.imu.gyro_z -= self.gyro_z_bias

            if self.debug_hex:
                self._log_oled_equivalent(payload, sensor_data)

            # Update orientation quaternion using complementary filter
            dt = current_time - self.last_odom_timestamp
            if dt > 0 and dt < 0.1:  # Sanity check
                self.imu_quat = self.data_converter.calculate_imu_quaternion(
                    sensor_data.imu.gyro_x,
                    sensor_data.imu.gyro_y,
                    sensor_data.imu.gyro_z,
                    sensor_data.imu.acc_x,
                    sensor_data.imu.acc_y,
                    sensor_data.imu.acc_z,
                    dt,
                    self.imu_quat
                )

            # Update odometry
            self._update_odometry(sensor_data, dt)
            self.last_odom_timestamp = current_time

        except Exception as e:
            self.get_logger().error(f"Error processing sensor data: {e}")

    def _log_oled_equivalent(self, payload: bytes, sensor_data):
        """
        Print values equivalent to OpenCTR OLED fields.

        Notes:
        - Battery raw value in protocol is x100 volts (e.g. 1249 -> 12.49V)
        - Gyro Z raw value is int16 from firmware IMU data
        """
        if len(payload) < 20:
            return

        gyro_z_raw = struct.unpack('>h', payload[10:12])[0]
        bat_raw_x100 = struct.unpack('>H', payload[18:20])[0]
        vol_v = bat_raw_x100 / 100.0
        gyro_z_rad_s = gyro_z_raw * self.data_converter.GYRO_RATIO

        if not self.is_calibrating:
            gyro_z_rad_s -= self.gyro_z_bias
            cal_status = "(CAL)"
        else:
            cal_status = "(RAW)"

        self.get_logger().info(
            f"DECODE -> Vol:{vol_v:6.2f}V  Gyz:{gyro_z_rad_s:+.5f}rad/s {cal_status} "
            f"|  vel(vx,vy,w)=({sensor_data.velocity.linear_x:+.3f}, "
            f"{sensor_data.velocity.linear_y:+.3f}, {sensor_data.velocity.angular_z:+.3f})"
        )

    def on_raw_frame(self, frame: bytes):
        """Optional debug callback to print full validated frame bytes in hex."""
        hex_str = ' '.join(f'{b:02X}' for b in frame)
        self.get_logger().info(f"RX_HEX: {hex_str}")

    def _update_odometry(self, sensor_data, dt: float):
        """
        Update odometry by integrating velocity data.
        
        Args:
            sensor_data: Parsed sensor data
            dt: Time delta since last update (seconds)
        """
        if dt <= 0 or dt > 0.1:
            return

        # Get velocities
        vx = sensor_data.velocity.linear_x
        # Non-holonomic constraint (differential drive): lateral body velocity should be ~0.
        # Keep world-frame y motion caused by heading changes via vx, but remove spurious vy drift.
        vy = 0.0
        vw = sensor_data.velocity.angular_z

        # Integrate position (simple Euler integration)
        # For differential drive/mecanum wheels in world frame
        cos_theta = math.cos(self.odom_theta)
        sin_theta = math.sin(self.odom_theta)

        # Transform from body frame to world frame
        vx_world = vx * cos_theta - vy * sin_theta
        vy_world = vx * sin_theta + vy * cos_theta

        self.odom_x += vx_world * dt
        self.odom_y += vy_world * dt
        self.odom_theta += vw * dt

        # Normalize theta
        self.odom_theta = math.atan2(math.sin(self.odom_theta),
                                      math.cos(self.odom_theta))

    def timer_callback(self):
        """
        Timer callback at 50Hz.
        Publishes sensor data if available.
        """
        if not self.serial_proto.is_connected:
            return

        current_time = self.get_clock().now()

        # Publish odometry
        if self.last_velocity_data is not None:
            self._publish_odometry(current_time)

        # Publish IMU
        if self.last_imu_data is not None:
            self._publish_imu(current_time)

        # Publish battery voltage
        if self.last_battery_data is not None:
            self._publish_battery(current_time)

    def _publish_odometry(self, ros_time: Time):
        """
        Publish odometry message.
        
        Args:
            ros_time: ROS timestamp
        """
        msg = Odometry()
        msg.header.stamp = ros_time.to_msg()
        msg.header.frame_id = self.odom_frame
        msg.child_frame_id = self.base_frame

        # Position
        msg.pose.pose.position.x = self.odom_x
        msg.pose.pose.position.y = self.odom_y
        msg.pose.pose.position.z = 0.0

        # Orientation from integrated yaw (matching ROS1: setRPY(0,0,angular_z))
        half_yaw = self.odom_theta * 0.5
        msg.pose.pose.orientation.w = math.cos(half_yaw)
        msg.pose.pose.orientation.x = 0.0
        msg.pose.pose.orientation.y = 0.0
        msg.pose.pose.orientation.z = math.sin(half_yaw)

        # Velocity
        msg.twist.twist.linear.x = self.last_velocity_data.linear_x
        # Enforce the constraint by sending vy=0 to EKF.
        msg.twist.twist.linear.y = 0.0
        msg.twist.twist.linear.z = 0.0
        msg.twist.twist.angular.x = 0.0
        msg.twist.twist.angular.y = 0.0
        msg.twist.twist.angular.z = self.last_velocity_data.angular_z

        # Covariance: dynamic based on motion state (matching ROS1 for robot_pose_ekf)
        vx = self.last_velocity_data.linear_x
        vy = self.last_velocity_data.linear_y
        vw = self.last_velocity_data.angular_z
        non_holonomic_vy_variance = 1e-5  # covariance matrix is 6x6; vy is at index 7 (row=1,col=1)
        if vx == 0 and vy == 0 and vw == 0:
            # Static: trust encoder more, lower odom covariance
            msg.pose.covariance = [1e-9, 0.0, 0.0, 0.0, 0.0, 0.0,
                                   0.0, 1e-3, 1e-9, 0.0, 0.0, 0.0,
                                   0.0, 0.0, 1e6, 0.0, 0.0, 0.0,
                                   0.0, 0.0, 0.0, 1e6, 0.0, 0.0,
                                   0.0, 0.0, 0.0, 0.0, 1e6, 0.0,
                                   0.0, 0.0, 0.0, 0.0, 0.0, 1e-9]
            msg.twist.covariance = [1e-9, 0.0, 0.0, 0.0, 0.0, 0.0,
                                    0.0, 1e-3, 1e-9, 0.0, 0.0, 0.0,
                                    0.0, 0.0, 1e6, 0.0, 0.0, 0.0,
                                    0.0, 0.0, 0.0, 1e6, 0.0, 0.0,
                                    0.0, 0.0, 0.0, 0.0, 1e6, 0.0,
                                    0.0, 0.0, 0.0, 0.0, 0.0, 1e-9]
            # Trust the vy=0 constraint strongly to prevent lateral slip in EKF.
            msg.twist.covariance[7] = non_holonomic_vy_variance
        else:
            # Moving: trust IMU more, higher odom covariance
            msg.pose.covariance = [1e-3, 0.0, 0.0, 0.0, 0.0, 0.0,
                                   0.0, 1e-3, 0.0, 0.0, 0.0, 0.0,
                                   0.0, 0.0, 1e6, 0.0, 0.0, 0.0,
                                   0.0, 0.0, 0.0, 1e6, 0.0, 0.0,
                                   0.0, 0.0, 0.0, 0.0, 1e6, 0.0,
                                   0.0, 0.0, 0.0, 0.0, 0.0, 0.1]  # Was 1e3! Trust wheel yaw
            msg.twist.covariance = [1e-3, 0.0, 0.0, 0.0, 0.0, 0.0,
                                    0.0, 1e-3, 0.0, 0.0, 0.0, 0.0,
                                    0.0, 0.0, 1e6, 0.0, 0.0, 0.0,
                                    0.0, 0.0, 0.0, 1e6, 0.0, 0.0,
                                    0.0, 0.0, 0.0, 0.0, 1e6, 0.0,
                                    0.0, 0.0, 0.0, 0.0, 0.0, 0.1]  # Was 1e3! Now trusts wheel yaw
            # Trust the vy=0 constraint strongly to prevent lateral slip in EKF.
            msg.twist.covariance[7] = non_holonomic_vy_variance

        self.odom_publisher.publish(msg)

        # Publish TF if enabled
        if self.pub_odom_tf:
            self._publish_odom_tf(ros_time)

    def _publish_odom_tf(self, ros_time: Time):
        """
        Publish odometry TF transform.
        
        Args:
            ros_time: ROS timestamp
        """
        t = TransformStamped()
        t.header.stamp = ros_time.to_msg()
        t.header.frame_id = self.odom_frame
        t.child_frame_id = self.base_frame

        # Translation
        t.transform.translation.x = self.odom_x
        t.transform.translation.y = self.odom_y
        t.transform.translation.z = 0.0

        # Rotation from integrated yaw (matching ROS1)
        half_yaw = self.odom_theta * 0.5
        t.transform.rotation.w = math.cos(half_yaw)
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = math.sin(half_yaw)

        self.tf_broadcaster.sendTransform(t)

    def _publish_imu(self, ros_time: Time):
        """
        Publish IMU message.
        
        Args:
            ros_time: ROS timestamp
        """
        msg = Imu()
        msg.header.stamp = ros_time.to_msg()
        msg.header.frame_id = self.imu_frame

        # Orientation: only use yaw from Mahony filter (matching ROS1)
        # ROS1: orientation.x = 0; orientation.y = 0; (zero roll/pitch)
        w, x, y, z = self.imu_quat
        msg.orientation.w = w
        msg.orientation.x = 0.0
        msg.orientation.y = 0.0
        msg.orientation.z = z

        # Angular velocity (from gyroscope)
        msg.angular_velocity.x = self.last_imu_data.gyro_x
        msg.angular_velocity.y = self.last_imu_data.gyro_y
        msg.angular_velocity.z = self.last_imu_data.gyro_z

        # Linear acceleration (from accelerometer)
        msg.linear_acceleration.x = self.last_imu_data.acc_x
        msg.linear_acceleration.y = self.last_imu_data.acc_y
        msg.linear_acceleration.z = self.last_imu_data.acc_z

        # Use realistic covariance values to avoid over-trusting noisy IMU data.
        msg.orientation_covariance = [1e6, 0.0, 0.0,
                          0.0, 1e6, 0.0,
                          0.0, 0.0, 0.2]
        msg.angular_velocity_covariance = [1e6, 0.0, 0.0,
                           0.0, 1e6, 0.0,
                           0.0, 0.0, 0.02]
        msg.linear_acceleration_covariance = [0.4, 0.0, 0.0,
                              0.0, 0.4, 0.0,
                              0.0, 0.0, 0.4]

        self.imu_publisher.publish(msg)

    def _publish_battery(self, ros_time: Time):
        """
        Publish battery voltage.
        
        Args:
            ros_time: ROS timestamp
        """
        msg = Float32()
        msg.data = self.last_battery_data.voltage
        self.bat_publisher.publish(msg)

    def cmd_vel_callback(self, msg: Twist):
        """
        Callback for cmd_vel subscription.
        
        Args:
            msg: Twist message containing velocity commands
        """
        # Extract velocity commands
        vx = msg.linear.x
        vy = msg.linear.y
        vw = msg.angular.z

        # Apply deadzone to ignore tiny joystick drift inputs
        if abs(vx) < 0.05: vx = 0.0
        if abs(vy) < 0.05: vy = 0.0
        if abs(vw) < 0.05: vw = 0.0

        # Send to robot
        if not self.serial_proto.send_velocity_command(vx, vy, vw):
            self.get_logger().warn("Failed to send velocity command")


def main(args=None):
    """Main function to start the ROS2 node."""
    rclpy.init(args=args)

    node = TarkbotRobotNode()

    # Start the robot driver
    if not node.start():
        node.get_logger().error("Failed to start robot driver")
        rclpy.shutdown()
        return

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Keyboard interrupt received")
    finally:
        node.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
