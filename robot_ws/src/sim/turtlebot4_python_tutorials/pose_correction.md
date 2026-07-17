I'm building a ROS-based mobile robot localization and docking system. 
Here is the architecture I need implemented:

## Context
- The robot navigates a map with 7 known locations, each marked by a 
  unique ArUco ID facing that location.
- Each marker's pose is known and fixed in the map frame (a static 
  {marker_id: pose_in_map} lookup table).
- The robot uses odometry (and optionally IMU) for dead-reckoning 
  navigation between locations.
- Goal: navigate to a target location (e.g. location 3) and align the 
  robot precisely facing its corresponding ArUco marker.

## Requirements

### 1. Continuous ArUco detection during navigation
Run ArUco detection continuously (throttled, e.g. 5-10 Hz) throughout 
the robot's movement, not only when arriving near the target. Any 
marker detected — target or not (IDs 1,2,4,5,6,7 while heading to 
target 3) — should be used to correct global pose, since all marker 
poses are known landmarks.

### 2. Pose correction via EKF, not via reset topics
- Do NOT use AMCL's `/initialpose` or robot_localization's `/set_pose` 
  for routine correction — these reset the entire filter state/particle 
  set and cause pose jumps. Reserve them only for rare manual 
  relocalization (e.g. robot completely lost).
- Instead, publish each ArUco-derived pose estimate (converted to the 
  map or odom frame as appropriate) as a `geometry_msgs/PoseWithCovarianceStamped` 
  message on a dedicated topic (e.g. `/aruco_pose`), with covariance 
  reflecting detection confidence (larger covariance for far/oblique 
  detections, smaller for close/frontal ones).
- Configure this topic as an additional pose input source in 
  `ekf_localization_node` (or `ukf_localization_node`) from the 
  `robot_localization` package, alongside odometry/IMU. This allows 
  continuous predict (odom/IMU) + update (ArUco) cycles, giving smooth, 
  weighted correction instead of hard resets.
- Apply Mahalanobis-distance gating (`rejection_threshold`) to reject 
  outlier detections before fusion (e.g. motion blur, false ID reads).
- If detections arrive at high frequency while the robot is nearly 
  stationary, throttle updates or average frames to avoid correlated-noise 
  overconfidence in the filter.

### 3. Two-stage localization/servoing pipeline
- **Global localization (background, continuous):** fuse ALL visible 
  markers into the EKF to correct global pose (x, y, theta) and reduce 
  odometry drift throughout the journey — not just near the target.
- **Fine alignment / docking (local, triggered near target):** once 
  the robot enters the vicinity of the target location, switch to a 
  visual servoing control loop that uses ONLY the target marker's pose 
  (e.g. marker ID 3) to drive the robot's final approach until it is 
  squarely facing the marker within tolerance.
- Include a fallback "search" state: if the robot reaches the estimated 
  target position but the target marker is not in view (due to residual 
  drift or occlusion), perform a search behavior (e.g. rotate in place 
  or small lateral scan) until the marker is (re)detected.

### 4. ID validation
Before fusing any detection, validate the marker ID against the known 
dictionary/lookup table to avoid fusing an incorrect landmark pose due 
to ID misread at distance or oblique angles.

## Deliverables
Please help me implement/configure:
1. The ArUco detection + pose estimation node publishing to `/aruco_pose` 
   with dynamic covariance based on detection quality.
2. The `robot_localization` EKF YAML configuration adding `/aruco_pose` 
   as a fused pose source.
3. A state machine (or behavior tree) node that switches between 
   "global navigation," "fine alignment / visual servoing to target 
   marker," and "search" states.
4. Outlier gating logic (Mahalanobis distance) applied before publishing 
   to `/aruco_pose`.

Tech stack: [ROS1/ROS2 — specify], [robot base type — differential drive/omni], 
[camera type], [existing odom/IMU setup].