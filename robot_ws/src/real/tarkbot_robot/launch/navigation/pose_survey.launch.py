#!/usr/bin/env python3

"""One-shot waypoint survey: localization → pose_record → RViz (with the ArUco image).

Use this to (re)measure ``tarkbot_robot/config/floorplan.json``. Nav2 is deliberately NOT
started — surveying is done by driving the robot manually, and a live Nav2 would only
fight the teleop.

``pose_record`` prints ``[PASTE table]`` / ``[PASTE dock]`` lines holding the marker's
solved map pose plus a *computed* face-on approach point (``standoff`` metres out along
the marker normal, yaw pointing back at the marker) — see ``pose_record`` for why the
approach must be computed rather than parked-and-copied.

::

    ros2 launch tarkbot_robot pose_survey.launch.py
    ros2 launch tarkbot_robot pose_survey.launch.py standoff:=0.6
    ros2 launch tarkbot_robot pose_survey.launch.py use_rviz:=false

Then, in another terminal, drive::

    ros2 run teleop_twist_keyboard teleop_twist_keyboard

RTAB-Map needs to know roughly where it starts: either place the robot on the dock and
seed ``/initialpose``, or use RViz's "2D Pose Estimate" tool (already in the config).
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg = get_package_share_directory('tarkbot_robot')
    nav_dir = os.path.join(pkg, 'launch', 'navigation')
    rviz_config = os.path.join(pkg, 'rviz', 'pose_survey.rviz')

    use_rviz = LaunchConfiguration('use_rviz')
    standoff = LaunchConfiguration('standoff')
    rtabmap_log_level = LaunchConfiguration('rtabmap_log_level')

    declare_use_rviz = DeclareLaunchArgument(
        'use_rviz', default_value='true',
        description='Launch RViz2 with the survey config (map + TF + ArUco image)')
    declare_standoff = DeclareLaunchArgument(
        'standoff', default_value='0.8',
        description='Metres in front of the marker the computed approach point sits')
    declare_rtabmap_log_level = DeclareLaunchArgument(
        'rtabmap_log_level', default_value='warn',
        description='Muted by default so the [SURVEY] lines stay readable; :=info to debug')

    # A survey is read off the console, so RTAB-Map's 5 Hz per-cycle telemetry is muted by
    # default here (it is not muted for delivery runs). Pass rtabmap_log_level:=info to
    # watch relocalization if the numbers look untrustworthy.
    loc = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav_dir, 'rtabmap_localization.launch.py')),
        launch_arguments={'rtabmap_log_level': rtabmap_log_level}.items(),
    )

    recorder = Node(
        package='tarkbot_robot',
        executable='pose_record',
        name='pose_record',
        output='screen',
        parameters=[{
            'standoff': ParameterValue(standoff, value_type=float),
        }],
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        condition=IfCondition(use_rviz),
    )

    return LaunchDescription([
        declare_use_rviz,
        declare_standoff,
        declare_rtabmap_log_level,
        loc,
        # Let the camera/TF tree come up before the recorder starts asking for transforms.
        TimerAction(period=6.0, actions=[recorder, rviz]),
    ])
