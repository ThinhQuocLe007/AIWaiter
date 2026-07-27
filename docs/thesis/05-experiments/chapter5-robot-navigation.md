# CHAPTER 5: EXPERIMENTS AND RESULTS (excerpt: robot navigation)

> **Status:** draft v5; robot-navigation section only; results **[TBD]**. Real demo: **one dock** (ArUco 6) + **Table 1** (ArUco 1). Sensor and stack configuration match the proposed navigation design.

---

## 5.2 ROS2 Navigation Experiments

Development follows **simulation first, then real hardware**. The navigation stack is exercised in Ignition Gazebo on a PC, then repeated on the TarkBot platform. Real-world tests below use one dock and one table; metrics focus on return-to-start error, map/localization quality, and navigation plus docking success.

---

### 5.2.1 Simulation Environment

Before field trials, the restaurant scenario is reproduced in **Ignition Gazebo** using the packages under `robot_ws/src/sim/`. A **TurtleBot 4** model (`turtlebot4_description`) represents a differential-drive mobile base with a simulated 2-D LiDAR and RGB-D camera mounted at the same logical positions as the real robot. The world file `restaurant.sdf` defines the kitchen hub, service lane, six table stations, and textured **ArUco** markers (IDs 0-6) on walls. A **ROS-Ignition bridge** forwards velocity commands, laser scans, and odometry into ROS 2 Humble so the same SLAM, localization, and Nav2 launch files used in simulation (`turtlebot4_navigation`) can drive the robot through dock-to-table delivery scripts (`food_delivery`). Simulation validates launch graphs, map building, and navigation behaviour at low cost; the **real** robot uses a separate workspace tree (`src/real/tarkbot_robot`) with the XTARK base and the measured floorplan of the physical lane.

> 🖼️ **Figure 5.1: Simulated restaurant world in Ignition Gazebo** (TurtleBot 4 in the service lane, dock and table markers visible). **[TBD]**

---

### 5.2.2 Odometry Accuracy Test

- **Goal:** Measure drift of the deployed EKF-fused odometry (wheel encoders and IMU) over one kitchen-to-table-to-kitchen delivery loop, checking whether return-to-start error stays within the service thresholds.
- **Dataset:** 10-20 closed paths: dock → Table 1 → dock, at service speed.
- **Methodology:** Record pose from `/odometry/filtered` at the dock before and after the loop; report position and heading error. Scoring uses odometry only (map pose is not used as ground truth).
- **Metrics:** Return-to-start error: position (cm), heading (deg).

**Table 5.1: Odometry return-to-start error.**

| Trials | Position (cm) mean ± std | Heading (deg) mean ± std |
|--------|--------------------------|---------------------------|
| 10-20 | **[TBD]** | **[TBD]** |

> 🖼️ **Figure 5.2: Overlaid odometry paths.** **[TBD]**

---

### 5.2.3 Map Building and Localization Test

- **Goal:** Assess RTAB-Map occupancy-grid quality and localization accuracy on repeated dock ↔ Table 1 trips in the service lane.
- **Dataset:** One offline mapping lap (dock revisit for loop closure); five localization transits on the saved map.
- **Methodology:** *Mapping:* teleop the lane, export `restaurant.pgm`, count loop closures (ICP + ArUco). *Localization:* seed the pose at the dock from the known starting pose, then log pose at each table/dock arrival versus surveyed coordinates.
- **Metrics:** Loop-closure count; grid resolution; localization drift (cm).

**Table 5.2: Mapping summary.**

| Duration | Loop closures (geom. / ArUco) | Resolution | Consistency |
|----------|-------------------------------|------------|-------------|
| **[TBD]** min | **[TBD]** / **[TBD]** | 0.05 m | **[TBD]** |

**Table 5.3: Localization drift (5 transits).**

| Checkpoint | $\lvert \Delta x \rvert$ (cm) | $\lvert \Delta y \rvert$ (cm) | $\lvert \Delta \psi \rvert$ (deg) |
|------------|-------------------------------|-------------------------------|-----------------------------------|
| Table 1 arrival | **[TBD]** | **[TBD]** | **[TBD]** |
| Dock return | **[TBD]** | **[TBD]** | **[TBD]** |

> 🖼️ **Figure 5.3: Occupancy grid with dock and Table 1.** **[TBD]**

**Analysis.** **[TBD]**

---

### 5.2.4 Navigation and Docking Test

- **Goal:** Run the full Nav2 delivery cycle dock → Table 1 → dock, and compare Table 1 arrival quality **with** versus **without** the last-metre ArUco visual align that corrects lateral offset, range, and heading after the planner stop.
- **Dataset:** Two batches of 5-10 runs each on the same surveyed dock and table poses: batch A with `ENABLE_VISUAL_ALIGN = True`, batch B with `ENABLE_VISUAL_ALIGN = False` (Nav2-only arrival; `[Arrival]` log lines).
- **Methodology:** Each run: localize at dock → Nav2 to Table 1 approach → (optional align) → Nav2 back to dock. Record Nav2 success rate, full-cycle trip time, and **docking error at Table 1**: lateral offset, range versus standoff, and heading. Align-off runs stop measuring at Nav2 success; align-on runs measure after visual align completes (or phase budget expires).
- **Metrics:** Navigation success rate (%); trip time (s); Table 1 docking error (cm, deg).

**Table 5.4: With visual align (`ENABLE_VISUAL_ALIGN = True`).**

| Trials | Nav success | Trip time (s) | Lateral err (cm) | Range err (cm) | $\lvert \Delta \psi \rvert$ (deg) |
|--------|-------------|---------------|------------------|----------------|-----------------------------------|
| 5-10 | **[TBD]** | **[TBD]** | **[TBD]** | **[TBD]** | **[TBD]** |

**Table 5.5: Without visual align (Nav2 only).**

| Trials | Nav success | Trip time (s) | Lateral err (cm) | Range err (cm) | $\lvert \Delta \psi \rvert$ (deg) |
|--------|-------------|---------------|------------------|----------------|-----------------------------------|
| 5-10 | **[TBD]** | **[TBD]** | **[TBD]** | **[TBD]** | **[TBD]** |

**Analysis.** **[TBD]** Compare the two tables; state how much align reduces lateral, range, and heading error at Table 1, and whether docking precision meets the delivery requirement when align is enabled.

---

### 5.2.5 Summary

**Table 5.6: Traceability.**

| Objective | Experiment | Result |
|-----------|------------|--------|
| EKF-fused odometry return-to-start accuracy | Odometry accuracy test | **[TBD]** cm |
| RTAB-Map map quality and localization drift | Map building and localization test | **[TBD]** |
| Nav2 delivery success and Table 1 docking precision | Navigation and docking test | **[TBD]** % / **[TBD]** cm |

**Discussion.** **[TBD]** Sim-first development; real evaluation on one dock and one table; limitations (IMU drift, ArUco lighting) are noted for the conclusion.
