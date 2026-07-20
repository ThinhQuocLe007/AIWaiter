import os

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    tarkbot_share = get_package_share_directory('tarkbot_robot')

    # ── URDF / TF ──────────────────────────────────────────────────────
    urdf_file = os.path.join(tarkbot_share, 'urdf', 'robot.urdf')
    with open(urdf_file, 'r') as infp:
        robot_desc = infp.read()

    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_desc}]
    )

    joint_state_publisher_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen'
    )

    # ── RP Lidar ───────────────────────────────────────────────────────
    rplidar_node = Node(
        package='rplidar_ros',
        executable='rplidar_composition',
        name='rplidar_node',
        output='screen',
        parameters=[{
            'serial_port': '/dev/ttyUSB0',
            'frame_id': 'laser_link',
            'angle_compensate': True,
            'scan_mode': 'Standard',
            'serial_baudrate': 115200
        }]
    )

    # ── EKF Visualization (robot_node, EKF, path publisher, IMU TF) ──
    ekf_launch_file = os.path.join(
        tarkbot_share, 'launch', 'ekf_visualization.launch.py'
    )
    ekf_visualization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(ekf_launch_file)
    )

    # ── SLAM Toolbox ──────────────────────────────────────────────────
    slam_params_file = os.path.join(
        tarkbot_share, 'config', 'slam_toolbox_params.yaml'
    )
    slam_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slam_params_file, {'use_sim_time': False}],
    )

    return LaunchDescription([
        # 1. TF tree
        robot_state_publisher_node,
        joint_state_publisher_node,
        # 2. Sensor
        rplidar_node,
        # 3. Odometry + EKF
        ekf_visualization,
        # 4. SLAM
        slam_node,
    ])
