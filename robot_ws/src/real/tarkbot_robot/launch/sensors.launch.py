import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    # Path to the URDF file
    urdf_file = os.path.join(
        get_package_share_directory('tarkbot_robot'),
        'urdf', 'robot.urdf'
    )
    
    with open(urdf_file, 'r') as infp:
        robot_desc = infp.read()

    # Robot State Publisher Node
    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_desc}]
    )

    # Joint State Publisher Node (publishes 0.0 for continuous wheel joints)
    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen'
    )

    # RPLidar Node (using the parameters you provided)
    rplidar_node = Node(
        package='rplidar_ros',
        executable='rplidar_composition',
        name='rplidar_node',
        output='screen',
        parameters=[{
            'serial_port': '/dev/ttyUSB0',
            'frame_id': 'laser_link', # Update to match URDF
            'angle_compensate': True,
            'scan_mode': 'Standard',
            'serial_baudrate': 115200
        }]
    )

    # RealSense Camera Launch Inclusion
    # camera_link is defined in robot.urdf (base_link -> camera_link).
    # Driver publishes camera_link -> optical frames.
    realsense_launch_dir = os.path.join(
        get_package_share_directory('realsense2_camera'), 'launch')
    
    realsense_node = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(realsense_launch_dir, 'rs_launch.py')
        ),
        launch_arguments={
            # Color
            'enable_color': 'true',

            # Depth
            'enable_depth': 'true',
            'pointcloud.enable': 'true',
            'pointcloud.ordered_pc': 'true',
            'align_depth.enable': 'true',
            'enable_sync': 'true',

            'rgb_camera.color_profile': '640x480x15',
            'rgb_camera.color_format': 'BGR8',
            'depth_module.depth_profile': '640x480x15',
        }.items()
    )

    return LaunchDescription([
        robot_state_publisher_node,
        joint_state_publisher_node,
        rplidar_node,
        realsense_node,
    ])
