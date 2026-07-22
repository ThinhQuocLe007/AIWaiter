import os

"""
Localization stack: driver, EKF, sensors, RTAB-Map.

Terminal 1 (start first):
    ros2 launch tarkbot_robot rtabmap_localization.launch.py

    IMPORTANT: In RViz, use "2D Pose Estimate" to set the robot's
    initial position on the map before driving.

Terminal 2 (after /map and map->odom TF are stable):
    ros2 launch tarkbot_robot navigation.launch.py use_rviz:=true
"""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('tarkbot_robot')
    tarkbot_launch_dir = os.path.join(pkg_share, 'launch')

    default_rtabmap_params = os.path.join(
        pkg_share, 'config', 'rtabmap_localization_params.yaml')

    rtabmap_params_file = LaunchConfiguration('rtabmap_params_file')
    rtabmap_log_level = LaunchConfiguration('rtabmap_log_level')

    declare_rtabmap_params = DeclareLaunchArgument(
        'rtabmap_params_file',
        default_value=default_rtabmap_params,
        description='RTAB-Map localization parameter file')
    # RTAB-Map prints one 'Rate=… delay=…' line per iteration — at Rtabmap/DetectionRate 5.0
    # that is 5 lines/s, which buries every other node. 'warn' keeps the errors and the
    # relocalization failures, drops the per-cycle telemetry.
    declare_rtabmap_log_level = DeclareLaunchArgument(
        'rtabmap_log_level',
        default_value='info',
        description='ROS log level for the rtabmap node (info | warn | error)')

    ekf_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tarkbot_launch_dir, 'ekf_visualization.launch.py')
        )
    )

    sensors_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tarkbot_launch_dir, 'sensors.launch.py')
        )
    )

    rtabmap_node = Node(
        package='rtabmap_slam',
        executable='rtabmap',
        name='rtabmap',
        output='screen',
        parameters=[rtabmap_params_file],
        arguments=['--ros-args', '--log-level',
                   ['rtabmap:=', rtabmap_log_level]],
        remappings=[
            # RGB-D camera topics — SAME as mapping (rtabmap_slam.launch.py) so the map's
            # visual data can be used to relocalize.
            ('rgb/image', '/camera/camera/color/image_raw'),
            ('rgb/camera_info', '/camera/camera/color/camera_info'),
            ('depth/image', '/camera/camera/aligned_depth_to_color/image_raw'),
            ('scan', '/scan'),
            ('odom', '/odometry/filtered'),
        ],
    )

    # Visualization-only node: publishes /aruco_debug_image for RViz2.
    # Pose correction is done inside RTAB-Map (RGBD/MarkerDetection); this node
    # does not touch localization.
    aruco_debug_node = Node(
        package='tarkbot_robot',
        executable='aruco_debug',
        name='aruco_debug',
        output='screen',
    )

    return LaunchDescription([
        declare_rtabmap_params,
        declare_rtabmap_log_level,
        ekf_launch,
        sensors_launch,
        rtabmap_node,
        aruco_debug_node,
    ])
