## 2.2 Autonomous Robot Navigation

> **Status:** draft v1
> **Cross-refs:** §3.3–§3.6 (proposed navigation system), §5.2 (navigation experiments)
> **Scope note:** This section surveys the theoretical foundations and existing approaches to autonomous indoor robot navigation — the technologies that enable a robot to know where it is, build a map of its environment, plan a path, and dock precisely at a target. All content is conceptual and survey-level; the group's specific implementation (platform constants, tuned parameters, URDF model, EKF configuration) is described in §3.3–§3.6. Prior academic ROS2 delivery robot projects are surveyed in §2.2.5.
> **Citations:** [2.2.1]–[2.2.20]; final numbering assigned when all Ch.2 references are merged.
> **Figures needed:** Fig 2.2 — encoder–IMU fusion block diagram (predict-update loop). Fig 2.3 — RTAB-Map pipeline diagram. Fig 2.4 — Nav2 architecture block diagram. Fig 2.5 — ArUco marker detection with overlaid pose axes. Fig 2.6 — generic ROS2 delivery robot architecture.

---

For a mobile robot to operate autonomously in a restaurant environment — to leave the kitchen, travel along a service lane, and arrive precisely at a customer's table — it must solve a sequence of interdependent problems. It must know where it is at every moment, using internal sensors that measure its own motion. It must build and maintain a representation of the environment, a map that tells it where walls, tables, and obstacles are. It must compute a safe path through that map and follow it, adjusting continuously for unexpected obstacles. And when it reaches the vicinity of its target, it must make a final precise approach — general localization is not accurate enough to stop at exactly the right position for a customer to comfortably reach their food.

These four problems — state estimation, mapping, path planning, and precision docking — form the core of autonomous robot navigation. Each has been studied extensively in the mobile robotics literature, and each has mature open-source implementations available in the Robot Operating System (ROS2) ecosystem. This section surveys the theoretical foundations of each area, the existing technologies and algorithms, and — critically — the gap between what prior academic ROS2 delivery robot projects have achieved and what a fully integrated restaurant service robot requires.

---

### 2.2.1 Wheel Odometry and Sensor Fusion

Wheel odometry is the most fundamental form of robot localization: estimating the robot's pose (position and orientation) by counting how far each wheel has turned. It is dead reckoning — each pose estimate is computed incrementally from the previous one, so any measurement error accumulates without bound over time.

**Encoder-based velocity estimation.** A differential-drive robot has two independently driven wheels. Each motor is equipped with an incremental encoder — typically a Hall-effect sensor that produces a fixed number of pulses per motor shaft revolution, denoted *P* (pulses per revolution, PPR). The motor drives the wheel through a gearbox with reduction ratio *G*. The encoder signal is processed in quadrature (4× decoding), so the total encoder ticks per wheel revolution is *N = P × 4 × G* [2.2.1].

At each control cycle (typically 50 Hz for a microcontroller-driven base), the change in encoder count Δ*n* is measured, and the wheel's linear velocity is computed as *V = πD/N × Δn/Δt*, where *D* is the wheel diameter and Δ*t* is the cycle duration [2.2.2]. For a two-wheel differential-drive (TWD) platform, the forward kinematics translate left and right wheel velocities (*V_A*, *V_B*) into body-frame velocities:

*V_x = (V_A + V_B) / 2* &emsp; (forward velocity)  
*V_ω = (V_B − V_A) / W* &emsp; (angular velocity)

where *W* is the wheel track (distance between the two drive wheels). The TWD platform is non-holonomic: *V_y = 0* — it cannot move laterally. The robot's global pose is updated by integrating these body-frame velocities over time using Euler integration with heading wrap [2.2.3].

**Drift accumulation.** The fundamental limitation of wheel odometry is drift. Each encoder measurement has quantization noise (finite PPR means the smallest measurable rotation is one tick). Wheel slip — caused by smooth floors, uneven surfaces, or rapid acceleration — introduces unmeasured motion. These errors compound with distance traveled: a 1% velocity error over a 10-meter path produces a 10 cm position error. For restaurant-scale navigation (kitchen-to-table trips of 3–5 meters), encoder-only odometry may accumulate 5–15 cm of error — insufficient for precise table approach [2.2.4].

**Inertial Measurement Unit (IMU).** An IMU measures angular velocity (gyroscope, 3 axes) and linear acceleration (accelerometer, 3 axes) at high frequency (typically 100–200 Hz). Consumer-grade IMUs such as the MPU6050 — widely used in educational and hobbyist robotics — provide ±250 to ±2000 °/s gyroscope range and ±2g to ±16g accelerometer range [2.2.5]. The gyroscope suffers from bias: even when stationary, it reports a non-zero angular rate. This bias drifts over time (temperature-dependent) and integrates into a growing heading error. Without a magnetometer for absolute heading reference, consumer-grade IMU yaw is relative-only and drifts at ~0.5–2 °/min after bias calibration [2.2.6].

**Extended Kalman Filter (EKF) sensor fusion.** Neither encoder odometry nor IMU data is individually sufficient — odometry accumulates position drift, IMU yaw drifts without magnetometer correction. The Extended Kalman Filter combines both sensor streams into a single fused state estimate that is more accurate than either source alone [2.2.7]. The EKF maintains a state vector — typically *[x, y, ψ, V_x, V_y, V_ω]* — and operates in two alternating phases: **predict** (advance the state estimate using the motion model and encoder velocities) and **update** (correct the state using IMU angular velocity measurements). The Kalman gain — computed from the process noise and measurement noise covariance matrices — determines how much weight to give each sensor at each timestep.

The `robot_localization` package in ROS2 provides a configurable EKF implementation widely used for mobile robot sensor fusion [2.2.8]. In `two_d_mode`, the state is constrained to planar motion (x, y, yaw). The package accepts multiple sensor input types (`odom0` for wheel velocities, `imu0` for angular velocity and linear acceleration) and publishes the fused output as the `/odometry/filtered` topic and the `odom → base_footprint` TF transform.

**Differential-drive kinematic model.** The theoretical foundation of TWD kinematics is covered extensively in mobile robotics textbooks [2.2.9] and is summarized here. The key parameters are wheel diameter *D*, wheel track *W*, encoder resolution *P* (PPR), and gear ratio *G*. The relationship between encoder ticks and linear displacement per wheel is *d_tick = πD / N* where *N = P × 4 × G*. The instantaneous center of rotation (ICR) for a TWD lies on the wheel axis; the turning radius *R = W/2 × (V_A + V_B) / (V_B − V_A)*. When *V_A = V_B*, the robot moves straight (*R → ∞*). When *V_A = −V_B*, the robot rotates in place (*R = 0*). These two special cases — straight-line motion and in-place rotation — are the primary motion primitives used in restaurant navigation along a service lane.

---

### 2.2.2 SLAM and Map Building

Simultaneous Localization and Mapping (SLAM) addresses the chicken-and-egg problem of autonomous navigation: to localize itself, the robot needs a map; to build a map, the robot needs to know where it is. SLAM algorithms solve both simultaneously — as the robot moves through an unknown environment, it incrementally builds a map while tracking its own pose within that map [2.2.10].

**The SLAM pipeline.** All SLAM systems share a common structure. The **front-end** processes raw sensor data into features or measurements — extracting geometric landmarks from LiDAR scans, detecting visual features (e.g., ORB, SIFT, SURF) from camera images, or computing scan-matched pose increments between consecutive LiDAR frames. The **back-end** performs global optimization — constructing a graph where nodes represent robot poses and edges represent spatial constraints (odometry measurements, loop closures), then solving for the maximum-likelihood configuration of all poses and landmarks simultaneously [2.2.11].

**LiDAR-based SLAM.** A 2D LiDAR (Light Detection and Ranging) sensor such as the RPLiDAR A2M8 provides a 360° planar scan of distance measurements — typically at 4,000–8,000 points per second, with an angular resolution of ~0.5° and a range of 12–16 meters [2.2.12]. LiDAR-only SLAM systems (Cartographer, Hector SLAM, Karto SLAM) match consecutive scans via scan-to-scan or scan-to-map alignment to estimate incremental motion. The resulting map is a 2D occupancy grid — a regular grid of cells, each labeled as free (0), occupied (100), or unknown (−1). LiDAR SLAM is robust (works in darkness, insensitive to visual texture) but has a critical limitation: it can only match geometry. A long straight corridor with featureless walls provides no distinctive reference for loop closure — the robot cannot tell one section of wall from another [2.2.13].

**Visual SLAM and RTAB-Map.** An RGB-D camera such as the Intel RealSense D435 adds visual information to the SLAM pipeline. The D435 uses active stereo infrared projection to produce depth images (up to 10 m range, 87°×58° field of view) synchronized with RGB color frames [2.2.14]. RTAB-Map (Real-Time Appearance-Based Mapping) is a graph-based SLAM framework that fuses LiDAR geometry with RGB-D visual features [2.2.15]. Its key contribution is **visual loop closure detection** via a bag-of-words (BoW) vocabulary: each RGB image is converted into a sparse vector of visual word frequencies. When the robot revisits a previously seen location, the BoW signature matches the stored signature for that location, triggering a loop closure constraint in the pose graph. The back-end optimizer (g2o or GTSAM) then corrects the entire trajectory to satisfy this new constraint, eliminating accumulated drift.

RTAB-Map's memory management — a working memory of recent nodes and a long-term memory of loop-closure candidates retrieved by BoW similarity — enables operation in large environments without unbounded memory growth. By combining LiDAR geometry (reliable in darkness, accurate at range) with RGB-D loop closure (distinctive at visually rich locations), RTAB-Map produces more accurate and robust maps than either sensor modality alone [2.2.16].

**Map representation.** The output of the SLAM pipeline for navigation purposes is a 2D occupancy grid map — a grayscale image where each pixel value encodes the probability of occupancy. This map serves as the static layer in the Nav2 costmap architecture (§2.2.3). The map is built during an offline mapping run (teleoperation) and then loaded for subsequent autonomous navigation. RTAB-Map also supports localization mode — loading a previously saved map and localizing against it in real time without modifying it.

---

### 2.2.3 Autonomous Navigation

Once a map exists and the robot can localize within it, the Navigation2 (Nav2) stack handles the problem of moving from the current pose to a goal pose while avoiding obstacles [2.2.17].

**Global planning.** The global planner computes a geometric path from the robot's current position to the goal on the static costmap (the pre-built occupancy grid). It uses a graph search algorithm — typically A* or Dijkstra — on a cost-aware representation of the map where occupied cells have infinite traversal cost and free cells have zero cost. The output is a sequence of waypoints that the local controller will then follow. In a restaurant service lane, the global path is typically a simple curve along the lane from kitchen to the specified table position [2.2.18].

**Local planning and control.** The Dynamic Window Approach (DWB) is the default local planner in Nav2. At each control cycle, DWB samples a set of candidate velocity commands *(V_x, V_ω)* from the robot's achievable velocity space (bounded by maximum linear and angular velocities and accelerations). Each candidate is forward-simulated for a short time horizon, and the resulting trajectory is scored against multiple criteria [2.2.19]: progress toward the global goal, obstacle clearance (distance to the nearest obstacle in the local costmap), alignment with the global path, and velocity smoothness (penalizing rapid acceleration changes). The velocity command with the highest composite score is published to the motor controller.

For non-holonomic TWD platforms, *V_y = 0* is enforced — the robot cannot move laterally. In-place rotation (*V_x = 0, V_ω ≠ 0*) handles heading correction when the robot arrives at a waypoint or needs to reorient.

**Costmaps.** Nav2 uses a layered costmap architecture. The **static layer** is the pre-built occupancy grid from §2.2.2 — it represents fixed environment geometry (walls, columns). The **inflation layer** expands obstacle boundaries by the robot's inscribed radius plus a safety margin, so the planner treats the robot's entire footprint as a no-go zone. The **obstacle layer** incorporates live sensor data (LiDAR scans) into the costmap, enabling the robot to detect and avoid objects that were not present during mapping — an object accidentally left in the service lane, a chair pushed out of position [2.2.20]. Each layer contributes independently to the master costmap, which the local planner queries at each cycle.

**Behavior trees for recovery.** Nav2 uses behavior trees to implement recovery behaviors. When the local planner fails to find a valid trajectory (e.g., blocked path, trapped in a corner), the behavior tree triggers recovery actions: in-place rotation to clear the local costmap, backing up to create space, or replanning with a higher-cost tolerance. If all recovery actions fail, the navigation goal is aborted and a failure status is reported [2.2.17].

**Domain-specific constraints for restaurants.** Restaurant service-lane navigation has two distinguishing characteristics: (a) the path is repetitive — kitchen to any of 6 fixed tables and back, (b) the lane is physically separated from customer foot traffic, so dynamic obstacle handling is needed only for occasional objects entering the lane (a fallen utensil, a misplaced chair), not for pedestrian avoidance. These constraints inform the Nav2 parameter tuning described in §3.6.

---

### 2.2.4 Fiducial Marker Docking

SLAM-based localization, even with RTAB-Map's loop-closure correction, carries residual position error of 2–5 cm under ideal conditions and more under real-world factors (wheel slip, LiDAR noise, imperfect calibration). For a restaurant delivery robot, 5 cm of error at a 60 cm-wide table approach position may cause the robot to stop out of the customer's comfortable reach [2.2.21]. A secondary absolute reference is needed for the final approach — one that is independent of the robot's accumulated localization error.

**ArUco markers.** An ArUco marker is a square black-and-white fiducial marker with a binary code embedded in its interior grid. The marker size, dictionary (set of valid codes), and unique ID are known in advance. Detection proceeds through a standard OpenCV pipeline: adaptive thresholding → contour extraction → polygon approximation → perspective correction (unwarping the detected square to a canonical view) → bit-pattern decoding to recover the marker ID [2.2.22]. Markers are printed on durable material and affixed at known positions — in a restaurant, one marker per table at a fixed offset from the table's center.

**Pose estimation.** Once a marker is detected and identified, Perspective-n-Point (PnP) pose estimation computes the 6-DoF camera pose relative to the marker. The 3D coordinates of the marker's four corners (in the marker's own coordinate frame) are known by construction. The 2D image coordinates of those four corners are measured by the detector. PnP solves for the rotation and translation that project the 3D corner points onto the 2D image plane — a minimization problem typically solved iteratively via the Levenberg-Marquardt algorithm [2.2.23]. The result is the camera-to-marker transform, which, combined with the known camera-to-robot transform (from URDF calibration) and the known marker-to-table offset, gives the robot's pose relative to the table.

**Why ArUco for docking.** SLAM localization accumulates error along the entire trajectory from kitchen to table. The ArUco marker provides an absolute local reference — its detected pose is computed from a single camera frame, independent of all prior SLAM history. A marker detection at 0.5 m from the table can achieve sub-centimeter lateral and depth accuracy in ideal lighting, sufficient for the final approach [2.2.24]. The marker is only needed during the final approach; during lane navigation (§2.2.3), SLAM-based localization alone is adequate.

**Limitations.** ArUco detection degrades under three conditions: (a) low or directional lighting — the D435's active IR projector helps in low light but can wash out the marker at close range, (b) high viewing angle — ArUco detection fails when the marker is viewed at >60° from perpendicular, and (c) partial occlusion — if a customer's hand or plate partially blocks the marker, the four-corner detection may fail. These limitations inform the docking robustness handling described in §3.5.

---

### 2.2.5 Prior ROS2 Delivery Robot Research

The academic robotics community has demonstrated autonomous indoor delivery using ROS/ROS2 on a variety of platforms. Unlike the closed commercial products surveyed in §2.1, ROS2-based research robots are fully programmable, enabling integration of custom perception, planning, and interaction modules [2.2.25].

**Standard architecture.** The typical academic ROS2 delivery robot consists of a differential-drive or omnidirectional mobile base, a 2D LiDAR (RPLiDAR or Hokuyo), an RGB-D camera (Intel RealSense D435 or Kinect), an IMU (built-in or external), and an onboard computer (NVIDIA Jetson or Intel NUC). The ROS2 navigation stack follows the same pipeline described in §2.2.1–§2.2.4: encoder + IMU data fused via `robot_localization` EKF → RTAB-Map or Cartographer SLAM for mapping and localization → Nav2 for global planning and local control → ArUco markers for precision docking at target locations [2.2.26].

**Demonstrated applications.** University teams have deployed ROS2 delivery robots in campus cafeterias (food delivery to tables), hospital wards (medication delivery to patient rooms), office buildings (document and package delivery), and hotel lobbies (luggage transport). These projects demonstrate the feasibility of autonomous indoor delivery at the scale of 10–50 tables or rooms [2.2.27]. Key metrics reported in the literature include navigation success rates of 85–95%, mean trip times of 30–90 seconds for distances of 10–30 meters, and docking accuracy of 2–5 cm positional error [2.2.28].

**What prior systems lack.** Despite demonstrated navigation capability, all prior academic ROS2 delivery robot projects share a defining limitation: **they handle physical movement but have no conversational layer**. The robot can autonomously drive from a serving station to a designated table, but once it arrives, it has no means to interact with the customer. There is no voice interface for ordering, no natural-language understanding, no integration with a kitchen display system or payment flow. The navigation problem is solved in isolation; the interaction problem — the reason the robot was sent to the table in the first place — is unaddressed [2.2.29].

This gap is precisely what this thesis fills: connecting an autonomous ROS2-based navigation stack (§3.3–§3.6) to a conversational AI agent (§4.3) through a backend orchestrator (§4.5) that binds robot state to restaurant operations. The navigation system proposed in Chapter 3 is not novel in its individual components (wheel odometry, EKF fusion, RTAB-Map, Nav2, ArUco — all are established technologies). The novelty lies in the integration: tuning these components for a restaurant service-lane environment and connecting them to an AI system that gives the robot a purpose beyond movement.

---

### References (for §2.2)

[2.2.1] Siegwart, R., Nourbakhsh, I. R., & Scaramuzza, D. (2011). *Introduction to Autonomous Mobile Robots* (2nd ed.). MIT Press. Chapter 3: Mobile Robot Kinematics.

[2.2.2] Borenstein, J., Everett, H. R., & Feng, L. (1996). "Where am I? Sensors and Methods for Mobile Robot Positioning." *University of Michigan Technical Report*, 119–164.

[2.2.3] Dudek, G., & Jenkin, M. (2010). *Computational Principles of Mobile Robotics* (2nd ed.). Cambridge University Press. Chapter 2: Locomotion.

[2.2.4] Thrun, S., Burgard, W., & Fox, D. (2005). *Probabilistic Robotics*. MIT Press. Chapter 5: Mobile Robot Localization.

[2.2.5] InvenSense. (2013). *MPU-6000 and MPU-6050 Product Specification*. TDK Corporation.

[2.2.6] Woodman, O. J. (2007). "An Introduction to Inertial Navigation." *University of Cambridge Computer Laboratory Technical Report*, UCAM-CL-TR-696.

[2.2.7] Kalman, R. E. (1960). A new approach to linear filtering and prediction problems. *Journal of Basic Engineering, 82*(1), 35–45.

[2.2.8] Moore, T., & Stouch, D. (2016). A generalized Extended Kalman Filter implementation for the Robot Operating System. In *Intelligent Autonomous Systems 13* (pp. 335–348). Springer.

[2.2.9] Lynch, K. M., & Park, F. C. (2017). *Modern Robotics: Mechanics, Planning, and Control*. Cambridge University Press. Chapter 13: Wheeled Mobile Robots.

[2.2.10] Durrant-Whyte, H., & Bailey, T. (2006). Simultaneous localization and mapping: Part I. *IEEE Robotics & Automation Magazine, 13*(2), 99–110.

[2.2.11] Grisetti, G., Kümmerle, R., Stachniss, C., & Burgard, W. (2010). A tutorial on graph-based SLAM. *IEEE Intelligent Transportation Systems Magazine, 2*(4), 31–43.

[2.2.12] SLAMTEC. (2022). *RPLiDAR A2M8 — Low Cost 360 Degree Laser Range Scanner — Datasheet*. Shanghai SLAMTEC Co., Ltd.

[2.2.13] Hess, W., Kohler, D., Rapp, H., & Andor, D. (2016). Real-time loop closure in 2D LIDAR SLAM. In *2016 IEEE International Conference on Robotics and Automation (ICRA)* (pp. 1271–1278).

[2.2.14] Intel Corporation. (2022). *Intel RealSense D400 Series Product Family — Datasheet*. Revision 012.

[2.2.15] Labbé, M., & Michaud, F. (2019). RTAB-Map as an open-source lidar and visual simultaneous localization and mapping library for large-scale and long-term online operation. *Journal of Field Robotics, 36*(2), 416–446.

[2.2.16] Labbé, M., & Michaud, F. (2014). Online global loop closure detection for large-scale multi-session graph-based SLAM. In *2014 IEEE/RSJ International Conference on Intelligent Robots and Systems* (pp. 2661–2666).

[2.2.17] Macenski, S., Martín, F., White, R., & Clavero, J. G. (2020). The Marathon 2: A Navigation System. In *2020 IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)*.

[2.2.18] Macenski, S., Foote, T., Gerkey, B., Lalancette, C., & Woodall, W. (2022). Robot Operating System 2: Design, architecture, and uses in the wild. *Science Robotics, 7*(66), eabm6074.

[2.2.19] Fox, D., Burgard, W., & Thrun, S. (1997). The dynamic window approach to collision avoidance. *IEEE Robotics & Automation Magazine, 4*(1), 23–33.

[2.2.20] Marder-Eppstein, E., Berger, E., Foote, T., Gerkey, B., & Konolige, K. (2010). The Office Marathon: Robust navigation in an indoor office environment. In *2010 IEEE International Conference on Robotics and Automation* (pp. 300–307).

[2.2.21] Garrido-Jurado, S., Muñoz-Salinas, R., Madrid-Cuevas, F. J., & Marín-Jiménez, M. J. (2014). Automatic generation and detection of highly reliable fiducial markers under occlusion. *Pattern Recognition, 47*(6), 2280–2292.

[2.2.22] Romero-Ramirez, F. J., Muñoz-Salinas, R., & Medina-Carnicer, R. (2018). Speeded-up detection of squared fiducial markers. *Image and Vision Computing, 76*, 38–47.

[2.2.23] Lepetit, V., Moreno-Noguer, F., & Fua, P. (2009). EPnP: An accurate O(n) solution to the PnP problem. *International Journal of Computer Vision, 81*(2), 155–166.

[2.2.24] Olson, E. (2011). AprilTag: A robust and flexible visual fiducial system. In *2011 IEEE International Conference on Robotics and Automation* (pp. 3400–3407).

[2.2.25] Gatesichapakorn, S., Takamatsu, J., & Ruchanurucks, M. (2019). ROS based autonomous mobile robot navigation using 2D LiDAR and RGB-D camera. In *2019 First International Symposium on Instrumentation, Control, Artificial Intelligence, and Robotics (ICA-SYMP)* (pp. 151–154).

[2.2.26] Koubaa, A. (Ed.). (2019). *Robot Operating System (ROS): The Complete Reference* (Vol. 4). Springer.

[2.2.27] Quigley, M., Gerkey, B., & Smart, W. D. (2015). *Programming Robots with ROS: A Practical Introduction to the Robot Operating System*. O'Reilly Media.

[2.2.28] Macenski, S., Singh, S., Martín, F., & Clavero, J. G. (2023). Regulated Pure Pursuit and DWB: 12 000 Hours of Autonomous Navigation Experience. *IEEE Access, 11*, 83171–83186.

[2.2.29] Panta, N. P., Shrestha, P., Panta, P., & Basnet, S. (2024). Development and testing of autonomous mobile robot for material handling purpose using ROS2, SLAM, and Nav2. *Tribhuvan University Central Library*.
