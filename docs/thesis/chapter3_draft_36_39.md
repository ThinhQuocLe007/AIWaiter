# Chapter 3 — Draft Sections 3.6 to 3.9

> **Status:** working draft, written from the real robot only (`robot_ws/src/real/tarkbot_robot/`, branch `phongros2`).
> Any capability that exists only in `robot_ws/src/sim/` is stated explicitly as *not yet merged to the real platform*.
> **Numbering:** follows the working structure (3.5 = Encoder–IMU EKF fusion). Renumber when merging into `outline.md`.
> `[TODO]` marks values to be filled from experiments; `[FIGURE]` marks figures to be produced.

---

## 3.6 Map Building with RTAB-Map

Section 3.5 established a locally consistent state estimate by fusing two proprioceptive sources. That estimate drifts without bound: it has no external reference. This section introduces the second fusion layer of the system, in which two *exteroceptive* sensors — a 2D LiDAR and an RGB-D camera — are fused into a single metric map of the restaurant, and in which the drift of the state estimator is bounded by loop closure.

The input odometry for this layer is `/odometry/filtered`, the output of the EKF described in §3.5. The mapping layer therefore consumes the previous layer rather than re-deriving pose from raw sensors — the two fusion stages are cascaded, not parallel.

### 3.6.1 Two Mapping Approaches Considered

Two SLAM front-ends were configured and evaluated on the same platform before selecting one for the deployed system.

| Criterion | SLAM Toolbox | RTAB-Map |
|---|---|---|
| Sensors | 2D LiDAR only | 2D LiDAR **+ RGB-D** |
| SLAM formulation | 2D pose-graph | Graph-SLAM (RGB-D + LiDAR) |
| Optimizer | Ceres (`SPARSE_NORMAL_CHOLESKY`, `SCHUR_JACOBI`) | g2o/TORO |
| Loop closure cue | Scan correlation | **Visual Bag-of-Words** + LiDAR spatial proximity |
| Map storage | Serialized pose-graph | SQLite database (`rtabmap.db`) |
| Strength | Lightweight, stable | Robust closure where LiDAR geometry is ambiguous |
| Role in this work | Baseline / fallback | **Deployed system** |

SLAM Toolbox was configured in asynchronous mapping mode at 0.05 m/pixel resolution with a 12 m maximum laser range, using scan-matching with update thresholds of 0.3 m travel and 0.3 rad heading. It produces usable maps and is retained as a fallback path.

It was not selected because its only loop-closure cue is scan correlation. A restaurant floor is close to the worst case for that cue: repeated table-and-chair clusters, long featureless walls, and a repetitive layout produce laser scans that are nearly identical at geometrically distinct locations. RTAB-Map's visual Bag-of-Words closure resolves these locations by image texture, which differs even where geometry does not.

> **Note on the baseline.** SLAM Toolbox is presented as an evaluated alternative rather than a discarded attempt. Chapter 5 reports maps produced by both, so the selection is supported by measurement rather than by argument alone.

### 3.6.2 RTAB-Map Configuration

RTAB-Map runs as a single node subscribing to both sensor streams and the fused odometry:

| RTAB-Map input | Source topic |
|---|---|
| `rgb/image` | `/camera/camera/color/image_raw` |
| `rgb/camera_info` | `/camera/camera/color/camera_info` |
| `depth/image` | `/camera/camera/aligned_depth_to_color/image_raw` |
| `scan` | `/scan` |
| `odom` | `/odometry/filtered` — **output of the EKF (§3.5)** |

Synchronisation uses `approx_sync: true` with queue sizes of 50, and `frame_id: base_footprint`.

**Division of labour between the two sensors.** A design decision worth stating explicitly: `Grid/Sensor` is set to `0`, meaning the occupancy grid is built **from the LiDAR alone**. The RGB-D camera contributes to the pose graph — through visual loop closure — but never writes cells into the map. This keeps the grid geometrically clean (depth data is noisy at range and produces spurious occupied cells) while still gaining the camera's advantage where it matters, namely place recognition.

| Occupancy grid | Value | Rationale |
|---|---|---|
| `Grid/Sensor` | `0` | Grid from LiDAR only |
| `Grid/RangeMax` | 10.0 m | Room is ≈9.5 m; truncating longer rays suppresses ghost geometry |
| `Grid/RangeMin` | 0.15 m | Rejects returns from the robot's own body |
| `Grid/RayTracing` | `true` | Clears free space along each ray |

| Registration / graph | Value | Rationale |
|---|---|---|
| `Reg/Strategy` | `1` (ICP) | Geometric registration on laser data |
| `Reg/Force3DoF` | `true` | Constrains the problem to (x, y, yaw) |
| `RGBD/NeighborLinkRefining` | `true` | Refines odometry using consecutive scans |
| `RGBD/ProximityBySpace` | `true` | LiDAR-based proximity detection |
| `RGBD/OptimizeFromGraphEnd` | `false` | Keeps the map origin fixed |
| `RGBD/OptimizeMaxError` | `3.0` | Rejects false closures that would distort the graph |
| `Rtabmap/DetectionRate` | 2.0 Hz | Raised from 0.5 Hz for a denser graph |
| `RGBD/LinearUpdate` / `AngularUpdate` | 0.05 m / 0.05 rad | New-node thresholds |

### 3.6.3 Loop-Closure Tuning

The default ICP settings failed to close the loop on the first mapping runs. The failure was diagnosed rather than worked around, and the diagnosis is reported here because it illustrates a general trade-off.

**Symptom.** At the point where the robot returned to a previously mapped area, RTAB-Map rejected the candidate closure with a correspondence ratio of ≈0.066 against a required 0.1, accompanied by a *"Cannot compute transform"* error.

**Cause.** The pose predicted from odometry at the moment of revisit had already drifted further than the ICP correspondence search window of 0.1 m. ICP therefore found too few point correspondences to compute a transform — the closure was not rejected because the place was wrong, but because the search window was too narrow to reach it.

**Resolution.** Three coupled changes:

| Parameter | Before | After | Effect |
|---|---|---|---|
| `Icp/MaxCorrespondenceDistance` | 0.1 m | **0.3 m** | Widens the correspondence search to cover accumulated drift |
| `Icp/Iterations` | default | **30** | Allows convergence within the wider window |
| `Icp/CorrespondenceRatio` | 0.3 | **0.1** | Accepts closure at ≥10% overlap |

Remaining ICP settings: `Icp/VoxelSize` 0.05 m (matching map resolution), `Icp/PointToPlane` true with `PointToPlaneK` 20 (point-to-plane converges faster than point-to-point), `Icp/Epsilon` 0.001.

**Interpretation.** Each change trades strictness for closure capability. A wider correspondence window and a lower overlap requirement admit closures that a stricter configuration would reject — but they also admit a larger class of *false* closures. This is why `RGBD/OptimizeMaxError = 3.0` matters: it is the safeguard that makes the relaxation acceptable, discarding any closure whose optimisation error indicates it has distorted the graph. The pair should be described together; relaxing ICP without the error guard would be unsound.

`[FIGURE]` Occupancy grid of the deployed environment, with the loop-closure link annotated.
`[FIGURE]` Pose graph before and after loop closure, showing the correction applied.
`[TODO]` Map dimensions, number of graph nodes, number of accepted closures, mapping run duration.

---

## 3.7 Localization with RTAB-Map

Once the map exists, the robot must determine its pose within it at run time. This layer produces the `map → odom` transform; the EKF of §3.5 produces `odom → base_footprint`. The two are complementary and neither is redundant: the EKF supplies a smooth, high-rate local estimate, while this layer anchors that estimate to the map and corrects its accumulated drift.

```
map → odom             published by RTAB-Map (this section)
odom → base_footprint  published by the EKF (§3.5)
base_footprint → laser_link / camera_link   published by robot_state_publisher (URDF)
```

### 3.7.1 Localization Mode

The system does not run a separate localization algorithm. It runs **the same RTAB-Map node in localization mode**, against the database produced in §3.6, with the same two sensors. The consequence is that the features used to localize are by construction the features that were used to map — there is no representation mismatch between mapping and localization.

| Parameter | Value | Meaning |
|---|---|---|
| `Mem/IncrementalMemory` | `false` | The stored map is never modified |
| `Mem/InitWMWithAllNodes` | `true` | Loads the whole map into working memory, so **visual relocalization works from any position** |
| `map_always_update` | `false` | Map held static during operation |
| `Rtabmap/DetectionRate` | **5.0 Hz** | Raised from 2.0 Hz (mapping) for smooth navigation tracking |
| `subscribe_depth` / `subscribe_scan` | `true` / `true` | Identical sensor set to mapping |
| `Grid/Sensor` | `0` | LiDAR-only grid, matching mapping |
| `Reg/Strategy` | `1` (ICP) | Matching mapping |
| `Reg/Force3DoF` | `true` | 2D constraint |

`Mem/InitWMWithAllNodes: true` is the parameter that makes global relocalization possible: with the entire map resident, the robot can recover its pose from any location rather than only from locations near its last known estimate.

### 3.7.2 Why RTAB-Map Rather Than AMCL

AMCL is the conventional choice for 2D localization in ROS 2 and was the default expectation for this platform. It was not used.

| Aspect | AMCL | RTAB-Map localization |
|---|---|---|
| Algorithm | Monte Carlo Localization (particle filter) | Graph-based localization + feature matching |
| Sensors | **2D LiDAR only** | 2D LiDAR **+ RGB-D** |
| Symmetric corridors / bare walls | **Prone to false convergence** — scans repeat | Visual Bag-of-Words separates visually distinct places |
| Recovery when lost | Requires particle redistribution | Global visual relocalization |
| Map source | `.pgm` + `.yaml` via `map_server` | SQLite `rtabmap.db`, publishes `/map` directly |

The decisive argument is environmental. A restaurant is a lidar-ambiguous environment by construction: identical tables at regular spacing, long flat walls, and a repeating layout. A particle filter observing only 2D range data can converge confidently on the wrong table row, and once converged there is no cue in the data to contradict it. Adding a camera adds an independent cue that does distinguish those locations.

A practical consequence follows: the system uses **no `map_server`**. The static layer of the global costmap (§3.8.2) subscribes to `/map` published by RTAB-Map itself, which requires `map_subscribe_transient_local: True` to receive the transient-local QoS map.

### 3.7.3 Guarding Against Mislocalization

Visual relocalization is powerful and, for that reason, dangerous: a strong but wrong place match can teleport the pose estimate across the map. Two parameters constrain this.

| Parameter | Value | Function |
|---|---|---|
| `RGBD/OptimizeMaxError` | `3.0` | Rejects loop/proximity links producing large graph error |
| `RGBD/MaxOdomCacheSize` | `30` | **Validates each localization against recent odometry**, rejecting jumps inconsistent with how the robot has actually moved |

`RGBD/MaxOdomCacheSize` is the more interesting of the two, and it closes the loop back to §3.5: the EKF estimate is not merely a consumer of localization, it is also the *evidence* against which a candidate localization is checked. A visually plausible but physically impossible correction — one implying the robot moved further than odometry says it did — is discarded. The two layers cross-validate.

### 3.7.4 ArUco-Based Pose Correction — Designed and Validated in Simulation

A fiducial-marker correction layer was designed and validated in Gazebo. **It has not yet been merged onto the real platform**, and no claim about the physical robot's docking accuracy is made in this work. It is documented here because it completes the localization design and because the porting requirements are a concrete result.

**Principle.** ArUco markers at surveyed positions act as absolute landmarks. Each detection yields a camera-to-marker transform by PnP; combined with the marker's known map pose and the camera-to-base transform, this yields an absolute robot pose:

```
T_map_base = T_map_marker · (T_cam_marker)⁻¹ · T_cam_base
```

**Reliability gating.** A pose derived from a single visual detection is accepted only after four independent checks — rejecting oblique views where PnP is ill-conditioned, implausible position or heading jumps, and range inconsistency between the observed and mapped marker distance (which detects misread marker IDs). The measurement is further weighted by a covariance that scales quadratically with both viewing distance and obliqueness, so that a distant or oblique detection influences the estimate less than a close, face-on one.

**Simulation result.** In Gazebo the layer corrects accumulated localization error at the approach pose and reduces residual heading error at the marker. `[TODO]` Quantitative results — see Chapter 5.

**Why it is not yet on the real robot.** The barrier is architectural rather than incidental, and stating it precisely is part of the contribution:

| Obstacle | Detail |
|---|---|
| EKF frame | The EKF runs `world_frame: odom` and therefore accepts no absolute map-frame pose. A correction cannot simply be fused. |
| Localization backend | The simulation corrects AMCL via `/initialpose`; the real robot uses RTAB-Map, which has no equivalent particle reset. |
| Marker survey | Simulation marker poses come from the Gazebo world; on the real robot each marker must be surveyed against the RTAB-Map database. |
| Camera calibration | Simulation provides ideal intrinsics; the physical RealSense requires calibration including distortion. |

The most promising path — recommended in §6.3 as future work — is to inject markers into RTAB-Map as **graph landmarks** rather than as filter resets, which preserves the existing architecture instead of competing with it for the `map → odom` transform.

### 3.7.5 Initialization Procedure

Localization currently requires a manual initial pose:

1. Launch the localization stack.
2. Set the robot's starting pose in RViz using **2D Pose Estimate**.
3. Wait for `/map` and the `map → odom` transform to stabilise.
4. Launch navigation.

Step 2 is a genuine operational limitation, not an implementation detail — see §3.9. Removing it is one of the motivations for the marker layer of §3.7.4, since a marker at the docking station would supply the initial pose automatically.

---

## 3.8 Autonomous Navigation with Nav2

Navigation consumes everything the previous layers produce: the map from §3.6, the `map → odom` transform from §3.7, and `/odometry/filtered` from §3.5. This section introduces the system's third fusion layer, which operates not on pose but on **perception of obstacles**.

### 3.8.1 Costmap-Level Sensor Fusion

This is the second most significant technical decision in the robot stack, after the EKF design of §3.5.

**The problem.** The 2D LiDAR scans a **single horizontal plane at 0.22 m** above the floor. Two classes of obstacle are invisible to it:

- **Below the plane** — flared chair legs, boxes on the floor, thresholds
- **Above the plane** — table edges, overhanging trays, a person's arm

Both are common in a restaurant, and both are collision hazards for a robot whose only obstacle sensor sits at a fixed height.

**The solution.** A `depthimage_to_laserscan` node converts the RealSense depth image into a synthetic scan on `/scan_depth`, covering the near field that the LiDAR plane misses:

| Parameter | Value |
|---|---|
| `scan_time` | 0.066 s |
| `range_min` / `range_max` | 0.35 / 2.5 m |
| `scan_height` | 8 image rows |
| `output_frame_id` | `camera_color_optical_frame` |

**Asymmetric fusion.** The two sources are not fused identically into both costmaps — a deliberate choice:

| Costmap | Observation sources | Rationale |
|---|---|---|
| **Local** | `/scan` **+** `/scan_depth` | Near-field collision avoidance needs the most complete picture available |
| **Global** | `/scan` only | Long-horizon planning; depth data is too short-range (2.5 m) and too noisy to be useful, and would inject transient obstacles into the global plan |

The depth source is additionally height-limited to `max_obstacle_height: 0.8 m`, restricting it to obstacles the robot can physically strike.

`[FIGURE]` LiDAR scan plane at 0.22 m versus depth-camera coverage, showing the blind zones each covers for the other.

### 3.8.2 Costmap Configuration

**Local costmap** — rolling window, `global_frame: odom`:

| Parameter | Value |
|---|---|
| Size / resolution | 4 × 4 m / 0.05 m |
| Update / publish frequency | 10.0 / 2.0 Hz |
| `robot_radius` | 0.12 m |
| `inflation_radius` | **0.45 m** |
| `cost_scaling_factor` | 2.5 |
| Plugins | `obstacle_layer`, `inflation_layer` |

| Source | Topic | `max_obstacle_height` | Raytrace max/min | Obstacle max/min |
|---|---|---|---|---|
| `scan` | `/scan` | 2.0 m | 3.0 / 0.15 m | 2.5 / 0.15 m |
| `depth_scan` | `/scan_depth` | **0.8 m** | 3.0 / 0.35 m | 2.5 / 0.35 m |

**Global costmap** — `global_frame: map`, 1.0 Hz, `track_unknown_space: true`, `inflation_radius` **0.55 m** (wider than local, biasing global plans away from walls), sources `/scan` only, plugins `static_layer` + `obstacle_layer` + `inflation_layer`.

Note the inflation radius (0.45–0.55 m) against the robot radius (0.12 m). The inflation layer, not the controller's obstacle critic, is doing most of the collision-avoidance work — a point returned to in §3.8.4.

### 3.8.3 Global Planner

| Parameter | Value |
|---|---|
| Plugin | `nav2_navfn_planner/NavfnPlanner` |
| `use_astar` | **`true`** (A*, not Dijkstra) |
| `tolerance` | 0.25 m |
| `allow_unknown` | `true` |
| `expected_planner_frequency` | 20.0 Hz |

A* is selected over the default Dijkstra because the environment is known and goals are distant relative to cell size, so the heuristic materially reduces expansion without affecting path quality.

### 3.8.4 Local Controller — DWB

The controller runs at 20 Hz. Velocity limits encode the differential-drive constraint directly:

| Parameter | Value |
|---|---|
| `min_vel_x` / `max_vel_x` | −0.26 / 0.26 m/s |
| `min_vel_y` / `max_vel_y` | **0.0 / 0.0** — no lateral motion |
| `max_vel_theta` | 1.0 rad/s |
| `acc_lim_x` / `decel_lim_x` | 2.5 / −2.5 m/s² |
| `acc_lim_theta` / `decel_lim_theta` | 3.2 / −3.2 rad/s² |

**Trajectory sampling.** With `vx_samples: 20` and `vtheta_samples: 20`, DWB evaluates up to **400 candidate trajectories** per control cycle, each simulated `sim_time: 1.7 s` forward, scoring each and selecting the best collision-free candidate. `short_circuit_trajectory_evaluation: True` abandons evaluation of clearly poor candidates early.

**Critic weights.**

| Critic | Scale | Role |
|---|---|---|
| `PathAlign` | **32.0** | Align heading with the global path |
| `PathDist` | **32.0** | Stay close to the global path |
| `RotateToGoal` | **32.0** | Rotate to goal heading on arrival |
| `GoalAlign` | 24.0 | Align heading toward the goal |
| `GoalDist` | 24.0 | Make progress toward the goal |
| `BaseObstacle` | **0.02** | Penalise proximity to obstacles |
| `Oscillation` | — | Suppress back-and-forth motion |

**Analysis — worth stating explicitly in the report.** `BaseObstacle` is weighted **1600× lower** than `PathAlign` and `PathDist`. The controller is therefore tuned so that *following the global path dominates almost absolutely*, and obstacle avoidance is delivered indirectly through the inflation layer of §3.8.2 rather than through the controller's own obstacle critic.

This is a defensible tuning for the deployment context and should be argued as such rather than presented as an accident. The robot operates in a narrow dedicated service lane. Predictable, repeatable lane-following is more valuable there than reactive swerving, which in a confined lane risks driving the robot into a boundary while avoiding a transient obstacle. The cost of the choice is reduced agility around unexpected obstacles, which is acceptable precisely because the lane is separated from customers.

**Progress and goal checking.**

| Component | Parameters |
|---|---|
| `SimpleProgressChecker` | `required_movement_radius` 0.10 m; `movement_time_allowance` 30.0 s |
| `SimpleGoalChecker` | `xy_goal_tolerance` **0.35 m**; `yaw_goal_tolerance` **0.35 rad** (≈20°); `stateful` True |

The goal tolerance of 0.35 m / 20° defines the arrival accuracy of the navigation layer alone. It is deliberately loose: Nav2 is responsible for getting the robot *to the table*, not for final precision alignment. Closing that residual is the role of the marker layer discussed in §3.7.4, which is why arrival accuracy and docking accuracy must be reported as separate quantities in Chapter 5.

### 3.8.5 Behaviour Tree and Recovery

Navigation is orchestrated by Nav2's default behaviour trees (`navigate_to_pose_w_replanning_and_recovery.xml`), with `bt_loop_duration: 10 ms`, `global_frame: map`, `robot_base_frame: base_footprint`, and `odom_topic: /odometry/filtered`.

The behaviour server provides `spin`, `backup`, `drive_on_heading`, `wait`, and `assisted_teleop`, running at 10 Hz with `simulate_ahead_time: 3.0 s` and recovery rotation limited to 0.8 rad/s.

### 3.8.6 Output Conditioning

A velocity smoother conditions `/cmd_vel` before it reaches the driver, at 20 Hz in `OPEN_LOOP` mode, enforcing the same velocity and acceleration envelope as the controller and applying a deadband of `[0.01, 0.0, 0.05]`. A path smoother (`nav2_smoother::SimpleSmoother`) refines the global plan before execution.

This matters for the platform: unsmoothed velocity steps on a differential-drive base cause wheel slip, and wheel slip is exactly the disturbance the EKF of §3.5 was configured to reject. The smoother reduces the disturbance at its source rather than relying on the filter to absorb it.

---

## 3.9 Operational Constraints

The following constraints are properties of the deployed system. They are recorded here because they define the conditions under which the Chapter 5 experiments are valid, and because several of them motivate the future work of Chapter 6.

| # | Constraint | Consequence |
|---|---|---|
| 1 | **Gyroscope calibration** — the robot must be completely stationary for the first ~2 s after the driver node starts, while 100 samples are averaged to estimate gyro bias | Motion during startup corrupts the bias estimate for the entire session. Every experimental run must begin from rest. |
| 2 | **Mapping wipes the database** — RTAB-Map mapping runs with `-d` | An existing map cannot be extended; each mapping run produces a new map from scratch. |
| 3 | **Manual initial pose** — localization requires "2D Pose Estimate" in RViz at every startup (§3.7.5) | The system is not able to start autonomously. |
| 4 | **Mandatory startup order** — localization must run and stabilise before navigation is launched | Starting navigation first yields an undefined `map → odom` transform. |
| 5 | **`imu_static_tf` is identity** — the `base_footprint → imu_link` transform is set to (0,0,0,0,0,0) | Because the EKF consumes only `vyaw`, which is invariant to translation, a positional offset is harmless; a **rotational** mounting offset would not be, and would require this transform to be measured. |

**Known configuration inconsistency.** `Icp/MaxCorrespondenceDistance` is 0.3 m during mapping (§3.6.3) but 0.1 m during localization, although the localization configuration is annotated as matching mapping. Since the 0.1 m window is the value that caused loop-closure failures during mapping, it is the first candidate to investigate for any localization loss observed in Chapter 5. `[TODO]` Confirm whether raising the localization window improves relocalization reliability, and report the result.

**Environmental assumptions.** Indoor, flat floor, previously mapped environment, dedicated service lane physically separated from customers. No pedestrian detection or social navigation is implemented; the lane separation is what makes this acceptable.

---

## Notes for Merging

1. **Chapter 2 boundary.** Chapter 2 now carries the theory (differential-drive kinematics, EKF formulation, SLAM and graph optimization fundamentals). These sections deliberately state *configuration and rationale* only, and do not restate the general equations. Check for duplication when merging.
2. **The fusion spine.** Sections 3.5 to 3.8 are written to read as one argument — proprioceptive fusion (3.5) → exteroceptive fusion for mapping (3.6) → the same for localization (3.7) → obstacle perception fusion (3.8). Preserve the linking sentences at the start of each section; they carry the chapter's thesis.
3. **Design challenges.** Once C1–C5 are finalised in §3.2, add the explicit mapping: C3 → §3.6/§3.7, C5 (sensor coverage gap) → §3.8.1, C2 (non-holonomic constraint) → §3.8.4.
4. **Simulation.** Only §3.7.4 refers to simulation-only work, and it is labelled. If Chapter 5 reports simulation results elsewhere, keep the same framing: validated in simulation, not yet merged.
