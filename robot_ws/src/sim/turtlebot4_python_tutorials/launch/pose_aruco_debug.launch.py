import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    pkg_turtlebot4_ignition_bringup = get_package_share_directory('turtlebot4_ignition_bringup')

    # Arguments
    world_arg = DeclareLaunchArgument('world', default_value='restaurant', description='Ignition World')

    # Include turtlebot4_ignition.launch.py
    turtlebot4_ignition_launch = PathJoinSubstitution(
        [pkg_turtlebot4_ignition_bringup, 'launch', 'turtlebot4_ignition.launch.py']
    )

    tb4_ignition = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([turtlebot4_ignition_launch]),
        launch_arguments={
            'world': LaunchConfiguration('world'),
            'nav2': 'false',
            'slam': 'false',
            'localization': 'true',
            'rviz': 'true'
        }.items()
    )

    # Custom Debug Node
    pose_aruco_debug_node = Node(
        package='turtlebot4_python_tutorials',
        executable='pose_aruco_debug',
        name='pose_aruco_debug',
        output='screen'
    )

    ld = LaunchDescription()
    ld.add_action(world_arg)
    ld.add_action(tb4_ignition)
    ld.add_action(pose_aruco_debug_node)

    return ld
