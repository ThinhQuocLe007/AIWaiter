#!/usr/bin/env python3

"""The whole REAL robot, one command: localization → Nav2 → dispatcher bridge.

This is ``deliver_test.launch.py``'s sibling for the web demo: same two stacks underneath, but
the top node is ``ai_hw_bridge/task_bridge`` (driven by the backend over WebSocket) instead of a
hard-coded table. Place the robot at the **dock (ArUco 6)** before launching — the bridge
publishes that pose on ``/initialpose``, so no manual "2D Pose Estimate" in RViz.

::

    ros2 launch ai_hw_bridge ai_waiter.launch.py server_host:=100.66.165.221:8000
    ros2 launch ai_hw_bridge ai_waiter.launch.py server_host:=... robot_id:=robo-2 use_rviz:=false

The backend must already be running on ``server_host`` (``make backend`` on the server). The
robot appears on the panel as soon as this connects — pin + chấm minimap live from the first
heartbeat, before Nav2 is even finished coming up.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    nav_dir = os.path.join(
        get_package_share_directory('tarkbot_robot'), 'launch', 'navigation')

    server_host = LaunchConfiguration('server_host')
    robot_id = LaunchConfiguration('robot_id')
    use_rviz = LaunchConfiguration('use_rviz')
    default_table = LaunchConfiguration('default_table')

    declare_server_host = DeclareLaunchArgument(
        'server_host', default_value='127.0.0.1:8000',
        description='host:port of the orchestrator backend (make backend)')
    declare_robot_id = DeclareLaunchArgument(
        'robot_id', default_value='robo-1',
        description='Must match a row in the backend fleet (seed_robots)')
    declare_use_rviz = DeclareLaunchArgument(
        'use_rviz', default_value='true',
        description='Launch RViz with the Nav2 config')
    declare_default_table = DeclareLaunchArgument(
        'default_table', default_value='1',
        description='Table served when the guest sits at one with no waypoint (0 = refuse)')

    loc = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav_dir, 'rtabmap_localization.launch.py')),
    )

    nav = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav_dir, 'navigation.launch.py')),
        launch_arguments={'use_rviz': use_rviz}.items(),
    )

    bridge = Node(
        package='ai_hw_bridge',
        executable='task_bridge',
        name='task_bridge',
        output='screen',
        parameters=[{
            'server_host': ParameterValue(server_host, value_type=str),
            'robot_id': ParameterValue(robot_id, value_type=str),
            'default_table': ParameterValue(default_table, value_type=int),
        }],
    )

    return LaunchDescription([
        declare_server_host,
        declare_robot_id,
        declare_use_rviz,
        declare_default_table,
        # Same staggering as deliver_test: sensors/RTAB-Map first, Nav2 once they are warm, then
        # the bridge — which waits on map->base_footprint + bt_navigator itself anyway.
        loc,
        TimerAction(period=5.0, actions=[nav]),
        TimerAction(period=12.0, actions=[bridge]),
    ])
