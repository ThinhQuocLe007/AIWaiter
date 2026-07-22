#!/usr/bin/env python3

"""One-shot demo: localization → Nav2 → deliver_test (Table 1, optional return to dock).

Starts stacks in order with short delays so RTAB-Map / Nav2 come up before the motion
node. Place the robot at **dock (ArUco 6)** before launch — ``deliver_test`` publishes
that pose on ``/initialpose`` (no manual 2D Pose Estimate required).

::

    ros2 launch tarkbot_robot deliver_test.launch.py
    ros2 launch tarkbot_robot deliver_test.launch.py return_dock:=true
    ros2 launch tarkbot_robot deliver_test.launch.py use_rviz:=false table_id:=1
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg = get_package_share_directory('tarkbot_robot')
    nav_dir = os.path.join(pkg, 'launch', 'navigation')

    use_rviz = LaunchConfiguration('use_rviz')
    table_id = LaunchConfiguration('table_id')
    return_dock = LaunchConfiguration('return_dock')

    declare_use_rviz = DeclareLaunchArgument(
        'use_rviz', default_value='true',
        description='Launch RViz with the Nav2 config')
    declare_table_id = DeclareLaunchArgument(
        'table_id', default_value='1',
        description='Dining table id (demo: 1). Dock is ArUco/floorplan dock (id 6).')
    declare_return_dock = DeclareLaunchArgument(
        'return_dock', default_value='false',
        description='After table delivery, drive back to dock (ArUco 6)')

    loc = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav_dir, 'rtabmap_localization.launch.py')),
    )

    nav = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav_dir, 'navigation.launch.py')),
        launch_arguments={'use_rviz': use_rviz}.items(),
    )

    deliver = Node(
        package='tarkbot_robot',
        executable='deliver_test',
        name='deliver_test',
        output='screen',
        parameters=[{
            'table_id': ParameterValue(table_id, value_type=int),
            'return_dock': ParameterValue(return_dock, value_type=bool),
        }],
    )

    return LaunchDescription([
        declare_use_rviz,
        declare_table_id,
        declare_return_dock,
        # Order: loc now → Nav2 after sensors warm up → deliver_test (waits on TF/Nav2).
        loc,
        TimerAction(period=5.0, actions=[nav]),
        TimerAction(period=12.0, actions=[deliver]),
    ])
