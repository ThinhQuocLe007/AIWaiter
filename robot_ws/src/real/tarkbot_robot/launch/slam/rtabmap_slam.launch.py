import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    tarkbot_launch_dir = os.path.join(
        get_package_share_directory('tarkbot_robot'), 'launch')

    # Include EKF launch
    ekf_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tarkbot_launch_dir, 'ekf_visualization.launch.py')
        )
    )

    # Include sensors launch
    sensors_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tarkbot_launch_dir, 'sensors.launch.py')
        )
    )

    # RTAB-Map parameters
    # Tuned for EKF where yaw rate is IMU-only (wheels supply vx/vy only).
    # Neighbor ICP corrects residual odom drift between nodes; loop closures stay
    # strict enough to avoid warping the graph into ghost walls.
    parameters = [{
        'frame_id': 'base_footprint',
        'subscribe_depth': True,
        'subscribe_scan': True,
        'approx_sync': True,
        
        # ArUco marker detection: markers are added to the graph as landmarks
        # so they get baked into the saved map (~/.ros/rtabmap.db) during mapping.
        # Re-detecting them in localization corrects drift. Marker IDs must be
        # non-zero/unique (id 0 is used internally as "invalid").
        'RGBD/MarkerDetection': 'true',
        'Marker/Dictionary': '0',        # 0 = DICT_4X4_50 (same as sim)
        'Marker/Length': '0.15',         # marker side length in meters (measure real marker)

        # Occupancy from LiDAR only; clip range to cut far-scan smear
        'Grid/Sensor': '0',
        'Grid/RangeMax': '8.0',
        'Grid/RangeMin': '0.20',
        'Grid/RayTracing': 'true',
        'Grid/NoiseFilteringRadius': '0.05',
        'Grid/NoiseFilteringMinNeighbors': '2',
        'RGBD/ProximityBySpace': 'true',
        'RGBD/OptimizeFromGraphEnd': 'false',

        # Dense nodes while teleoping slowly (0.1 m/s / 0.32 rad/s)
        'Rtabmap/DetectionRate': '1.0',
        'RGBD/LinearUpdate': '0.05',
        'RGBD/AngularUpdate': '0.03',

        # Reject wrong loop closures that WARP the graph (a major ghosting source)
        'RGBD/OptimizeMaxError': '3.0',

        # ICP (LiDAR) registration: refine neighbor links hard; keep loops stricter
        'Reg/Strategy': '1',
        'Reg/Force3DoF': 'true',
        'RGBD/NeighborLinkRefining': 'true',
        'Icp/VoxelSize': '0.05',
        # IMU-only yaw should keep the odom guess closer than wheel-wz fusion,
        # so the correspondence window can be tighter than the old 0.3 m rescue.
        'Icp/MaxCorrespondenceDistance': '0.20',
        'Icp/PointToPlane': 'true',
        'Icp/PointToPlaneK': '20',
        'Icp/Iterations': '40',
        'Icp/Epsilon': '0.001',
        'Icp/CorrespondenceRatio': '0.15',
        'RGBD/ProximityPathMaxNeighbors': '10',
        'RGBD/LocalRadius': '5.0',
        'Mem/STMSize': '30',
        
        'Vis/MinInliers': '15',
    }]

    # RTAB-Map node
    rtabmap_node = Node(
        package='rtabmap_slam', executable='rtabmap', output='screen',
        parameters=parameters,
        remappings=[
            ('rgb/image', '/camera/camera/color/image_raw'),
            ('rgb/camera_info', '/camera/camera/color/camera_info'),
            ('depth/image', '/camera/camera/aligned_depth_to_color/image_raw'),
            ('scan', '/scan'),
            ('odom', '/odometry/filtered'),
        ],
        arguments=['-d'] # Delete database on start for a fresh map
    )

    # Visualization-only node: publishes /aruco_debug_image so you can confirm in
    # RViz2 that markers are being seen (and thus baked into the map) while mapping.
    aruco_debug_node = Node(
        package='tarkbot_robot', executable='aruco_debug',
        name='aruco_debug', output='screen',
    )

    return LaunchDescription([
        ekf_launch,
        sensors_launch,
        rtabmap_node,
        aruco_debug_node,
    ])
