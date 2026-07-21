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
    parameters = [{
        'frame_id': 'base_footprint',
        'subscribe_depth': True,
        'subscribe_scan': True,
        'approx_sync': True,
        'sync_queue_size': 50,
        'topic_queue_size': 50,

        # ArUco marker detection: markers are added to the graph as landmarks
        # so they get baked into the saved map (~/.ros/rtabmap.db) during mapping.
        # Re-detecting them in localization corrects drift. Marker IDs must be
        # non-zero/unique (id 0 is used internally as "invalid").
        'RGBD/MarkerDetection': 'true',
        'Marker/Dictionary': '0',        # 0 = DICT_4X4_50 (same as sim)
        'Marker/Length': '0.15',         # marker side length in meters (measure real marker)

        # Optimize for 2D mapping using Lidar for occupancy grid
        'Grid/Sensor': '0',
        'Grid/RangeMax': '10.0',          # limit noisy far returns (room ~9.5 m) -> less ghosting
        'Grid/RangeMin': '0.15',          # drop very-close returns off the robot body
        'Grid/RayTracing': 'true',
        'RGBD/ProximityBySpace': 'true',
        'RGBD/OptimizeFromGraphEnd': 'false',

        # More frequent graph nodes -> smaller motion between scans -> less drift/ghosting
        'Rtabmap/DetectionRate': '2.0',   # was 0.5
        'RGBD/LinearUpdate': '0.05',
        'RGBD/AngularUpdate': '0.05',

        # Reject wrong loop closures that WARP the graph (a major ghosting source)
        'RGBD/OptimizeMaxError': '3.0',

        # Use ICP (Lidar) for registration refinement
        'Reg/Strategy': '1',
        'Reg/Force3DoF': 'true',
        'RGBD/NeighborLinkRefining': 'true',
        'Icp/VoxelSize': '0.05',
        # Loops were REJECTED with corrRatio ~0.066 < 0.1 ("Cannot compute transform"):
        # the odom guess at loop time drifts > old 0.1 m window, so ICP found too few
        # correspondences. Widen the search so loop closures can actually be accepted.
        'Icp/MaxCorrespondenceDistance': '0.3',  # was 0.1 -> allow matching despite drift
        'Icp/PointToPlane': 'true',
        'Icp/PointToPlaneK': '20',
        'Icp/Iterations': '30',           # more iterations -> converge over the wider window
        'Icp/Epsilon': '0.001',
        'Icp/CorrespondenceRatio': '0.1', # accept loops with >=10% overlap (was too strict at 0.3)
        'RGBD/ProximityPathMaxNeighbors': '10',

        'map_always_update': False,
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
