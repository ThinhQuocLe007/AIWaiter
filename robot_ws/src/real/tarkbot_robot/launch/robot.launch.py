#!/usr/bin/env python3

"""
ROS2 Launch file for TarkBot Robot.
Launches the robot driver node using parameters from robot.yaml.

Usage:
    ros2 launch tarkbot_robot robot.launch.py
"""

from launch import LaunchDescription
from launch.actions import SetEnvironmentVariable
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    """Generate launch description for TarkBot robot."""
    # Robot node with YAML config file only.
    # Edit config/robot.yaml to change runtime parameters.
    config_file = os.path.join(
        get_package_share_directory('tarkbot_robot'), 'config', 'robot.yaml')

    robot_node = Node(
        package='tarkbot_robot',
        executable='robot_node',
        name='tarkbot_robot_node',
        output='screen',
        parameters=[config_file]
    )

    log_format = SetEnvironmentVariable(
        'RCUTILS_CONSOLE_OUTPUT_FORMAT',
        '[{severity}] [{name}]: {message}'
    )

    return LaunchDescription([log_format, robot_node])
