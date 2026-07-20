#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    package_share = get_package_share_directory('tarkbot_robot')
    robot_config = os.path.join(package_share, 'config', 'robot.yaml')
    default_ekf_config = os.path.join(package_share, 'config', 'ekf.yaml')

    ekf_params_file = LaunchConfiguration('ekf_params_file')

    log_format = SetEnvironmentVariable(
        'RCUTILS_CONSOLE_OUTPUT_FORMAT',
        '[{severity}] [{name}]: {message}'
    )

    declare_ekf_params_file = DeclareLaunchArgument(
        'ekf_params_file',
        default_value=default_ekf_config,
        description='Path to EKF YAML parameter file'
    )

    robot_node = Node(
        package='tarkbot_robot',
        executable='robot_node',
        name='tarkbot_robot_node',
        output='screen',
        parameters=[robot_config, {'pub_odom_tf': False}]
    )

    ekf_node = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        parameters=[ekf_params_file],
        remappings=[('odometry/filtered', '/odometry/filtered')]
    )

    path_node = Node(
        package='tarkbot_robot',
        executable='path_publisher',
        name='path_publisher',
        output='screen',
        parameters=[{
            'odom_topic': '/odometry/filtered',
            'path_topic': '/filtered_path',
            'path_frame': 'odom',
        }]
    )

    # RViz IMU display needs a TF chain from imu_link to the fixed frame.
    # Update these values if your IMU is not mounted at base_footprint origin.
    imu_static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='imu_static_tf',
        output='screen',
        arguments=['0', '0', '0', '0', '0', '0', 'base_footprint', 'imu_link']
    )

    return LaunchDescription([
        log_format,
        declare_ekf_params_file,
        robot_node,
        imu_static_tf,
        ekf_node,
        path_node,
    ])