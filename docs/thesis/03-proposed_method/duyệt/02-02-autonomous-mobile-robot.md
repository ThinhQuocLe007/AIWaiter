## 2.2 Autonomous Mobile Robot

> *A robot that delivers food must reach the right table at a moment that is not known in advance, because the destination is decided at runtime by the restaurant system the robot serves rather than by an operator choosing a waypoint. This section surveys the technologies that make autonomous indoor navigation possible: the differential-drive kinematic model, wheel odometry and its fusion with inertial sensing through an extended Kalman filter, the ROS2 middleware that hosts the stack, SLAM and localization, path planning and control, and fiducial-marker docking. Each of these is an off-the-shelf component; for each, the section presents the available options, what distinguishes them, and what the published evaluations do and do not establish. Two capabilities are not off-the-shelf, namely coupling navigation goals to an external operational system and binding a docking marker to a business entity, and for those the section identifies the gap in prior work.*
>
> **Cross-refs:** §2.1 (overview: commercial robot limitations), §2.8 (edge compute platform), §3.1 (navigation requirements), §3.4–§3.7 (proposed navigation method), §5.2 (navigation experiments)
> **Citations:** [2.2.1]–[2.2.34]; final numbering assigned when all Ch.2 references are merged. Bibliographic entries for this section are pending; see `references.md`.
> **Figures and tables:** keyed section-scoped (`Table 2.2a`, `Figure 2.2a`, …) so that this section can be edited independently. Flatten to sequential chapter numbering on merge, in order of first appearance, following the same convention as the citations.

---

A robot that delivers food in a restaurant must answer one question repeatedly: *where should I go next?* Every business event changes the answer. A party is seated at table 3 and needs someone to take its order; the kitchen marks an order for table 5 complete; the session at table 2 is paid and the table is vacated. The navigation target is therefore a function of live restaurant state rather than a fixed route, and no navigation stack resolves that state on its own. It has to come from the system the robot is embedded in, one in which voice interaction, the order and payment lifecycle, kitchen progress, and fleet dispatch all write to a single operational record. Navigation goals are derived from that record and pushed to the robot at runtime. This work builds that end-to-end system (§4.7); the present section surveys the navigation components it drives.

Answering it reliably depends on a motion model and a software framework that come before any navigation capability. The motion model is the kinematic one that ties the two wheel speeds to the motion of the body (§2.2.1), and the odometry that estimates that motion by fusing the wheel encoders with an inertial sensor through an extended Kalman filter (§2.2.2). On top of that, ROS2 is the middleware that connects the sensors, algorithms, and controllers into a single running system (§2.2.3). The navigation capabilities then follow: a map of the environment and a means of localizing within it (§2.2.4), a planner and controller that convert a goal pose into wheel velocities (§2.2.5), and a short-range fiducial correction that achieves the precision the final approach demands (§2.2.6). Every one of these is available as a mature, open-source ROS2 component, so the survey is oriented toward selection: what options exist, what distinguishes them, and which properties matter for a restaurant service lane. Section 2.2.7 then examines the academic ROS2 delivery robots that assemble these same components, and identifies what they consistently leave unaddressed.

---

### 2.2.1 Kinematic Model of the Two-Wheel Differential Drive Robot

The capabilities surveyed in this section all act on the robot through one model, which ties the two wheel speeds to the motion of the body. A two-wheel differential-drive platform carries two independently driven wheels on a common axle, with one or more free casters for support, and it moves only from the difference between the two wheel speeds. Equal speeds send it straight, unequal speeds bend it onto a curve, and equal but opposite speeds spin it in place about the midpoint of the axle. That midpoint is the reference point O, where the model expresses the robot's motion. Table 2.2a lists the symbols used throughout.

**Table 2.2a.** Symbols of the differential-drive kinematic model.


| Symbol          | Meaning                                                                    | Unit  |
| --------------- | -------------------------------------------------------------------------- | ----- |
| $V_x$           | Forward body speed at the reference point O (forward positive)             | m/s   |
| $V_y$           | Lateral body speed ($V_y = 0$ for this drive)                              | m/s   |
| $V_\omega$      | Yaw rate about O (counter-clockwise positive)                              | rad/s |
| $V_A, V_B$      | Linear speed of the left and right wheel                                   | m/s   |
| $W$             | Wheel track, the distance between the two wheels                           | m     |
| $R$             | Turning radius, from the turning centre to O                               | m     |
| $S_L, S_M, S_R$ | Arc lengths travelled by the left wheel, O, and the right wheel in time$t$ | m     |
| $\theta$        | Angle turned through in time$t$                                            | rad   |

**[Figure 2.2a. Top-view geometry of the two-wheel differential drive: the turning centre and reference point O, the wheel track W, the left and right wheel speeds $V_A$ and $V_B$, the body-frame velocities $V_x$, $V_y$, $V_\omega$, the turning radius R, and the three arcs $S_L$, $S_M$, $S_R$ swept through the angle $\theta$.]**

A two-wheel differential drive has no way to move sideways. In the robot's own body frame the lateral velocity is always zero,

$$
V_y = 0,
$$

which is the non-holonomic constraint. The robot can only translate along the direction it faces while it rotates, and this restriction has to be respected both in the motion model here and in the planning and control of the later sections.

When the robot follows a curve, both wheels and the body reference point O turn about a common centre at the same angular rate $V_\omega$, each tracing a circle of a different radius: the left wheel on $R - W/2$, the right wheel on $R + W/2$, and the point O on $R$, where $W$ is the wheel track width and $R$ is the turning radius measured to O. Over an interval t the robot sweeps through an angle $\theta$, and since an angle equals arc length divided by radius, the three arcs share that angle,

$$
\theta = \frac{S_L}{R - W/2} = \frac{S_M}{R} = \frac{S_R}{R + W/2},
$$

with $S_L = V_A\,t$, $S_M = V_x\,t$, and $S_R = V_B\,t$ the distances travelled by the left wheel, the point O, and the right wheel over that interval. Dividing through by t leaves the same relation among the speeds,

$$
V_\omega = \frac{V_A}{R - W/2} = \frac{V_x}{R} = \frac{V_B}{R + W/2},
$$

from which the turning radius is simply $R = V_x / V_\omega$.

These relations run in both directions. Solving them for the wheel speeds gives the inverse model, which the base controller applies to carry out a commanded body velocity $(V_x, V_\omega)$:

$$
V_A = V_x - \frac{W}{2}\,V_\omega, \qquad V_B = V_x + \frac{W}{2}\,V_\omega,
$$

where $V_A$ and $V_B$ are the left and right wheel linear velocities. Adding and subtracting the same two equations gives the forward model, which recovers the body velocity from measured wheel speeds and is the basis of wheel odometry:

$$
V_x = \frac{V_B + V_A}{2}, \qquad V_\omega = \frac{V_B - V_A}{W}.
$$

Together with $V_y = 0$, these describe the robot's planar motion completely, and integrating the body velocities over time yields the pose that wheel odometry accumulates. The next subsection turns that forward model into a measured estimate and examines the drift it accumulates.

---

### 2.2.2 Odometry and Sensor Fusion

For a mobile robot to navigate autonomously, it must continuously estimate its pose (position and orientation). This process is known as odometry, where the robot starts from a known pose and incrementally estimates its motion using measurements from onboard sensors. Because the estimate is obtained solely from the robot's own motion without any external reference, odometry is a form of dead reckoning.

Odometry can be derived from different sensing modalities. Wheel odometry estimates motion from wheel encoder measurements, inertial odometry integrates IMU measurements, visual (or visual-inertial) odometry tracks motion between successive camera images, while laser odometry estimates motion by registering consecutive LiDAR scans. Each approach differs in accuracy, computational cost, and susceptibility to drift. This work uses wheel odometry as the primary source of translational motion because the robot operates on a flat indoor floor where wheel encoders provide reliable distance measurements.

The principal limitation of odometry is drift. Since the current pose estimate is obtained by accumulating previous motion estimates, any measurement error becomes part of the estimate and continues to propagate over time. For wheel odometry, drift mainly results from wheel slip, imperfect wheel geometry, and encoder quantization. Consequently, the estimated pose gradually diverges from the robot's true position during long-distance operation.

A common solution is sensor fusion, where multiple sensors with complementary error characteristics are combined to obtain a more reliable estimate. Wheel encoders provide accurate short-term translational motion but are sensitive to wheel slip, whereas an IMU measures rotational motion independently of wheel-ground contact and captures rapid turns accurately. However, integrating gyroscope measurements causes the IMU heading to drift over time. By combining encoder and IMU measurements, the weaknesses of one sensor are compensated by the strengths of the other.

A widely used sensor-fusion algorithm is the Extended Kalman Filter (EKF). The EKF recursively estimates the robot state by alternating between a prediction step, which propagates the state using a motion model, and an update step, which corrects the prediction using incoming sensor measurements according to their estimated uncertainties. Unlike the standard Kalman filter, which assumes linear system dynamics, the EKF handles the nonlinear kinematics of mobile robots by linearizing the motion and measurement models around the current state estimate.

The ROS2 robot_localization package provides configurable implementations of both the EKF and the Unscented Kalman Filter (UKF), including a `two_d_mode` that constrains the state to planar motion. In a typical differential-drive robot, wheel encoder velocities and IMU angular velocity are fused by the EKF to estimate the robot state. Absolute IMU yaw is normally excluded when no magnetometer is available because the integrated gyroscope heading drifts independently of the filter state, and incorporating this measurement would degrade the estimate. The resulting fused odometry provides a smoother and more robust estimate than wheel odometry alone.

**Table 2.2b.** Odometry and sensor-fusion approaches for a planar differential-drive platform.


| Approach                 | Sensors fused                            | Drift behaviour                                                           | Relative compute | ROS2 implementation               | Documented limitation                                                             |
| ------------------------ | ---------------------------------------- | ------------------------------------------------------------------------- | :--------------: | --------------------------------- | --------------------------------------------------------------------------------- |
| Encoder dead reckoning   | Encoders only                            | Unbounded; grows with distance and with every slip event                  |    Negligible    | `diff_drive_controller`           | Observes wheel rotation, not displacement; slip is invisible                      |
| Complementary filter     | Encoders + IMU gyro                      | Bounded short-term heading; long-term drift persists                      |     Very low     | `imu_complementary_filter`        | Fixed gain; no covariance model, so sensor confidence cannot vary with conditions |
| Extended Kalman Filter   | Encoders + IMU                           | Reduced heading drift; position drift bounded only by external correction | Low to moderate  | `robot_localization` (`ekf_node`) | Requires covariance tuning; linearization error grows under aggressive manoeuvres |
| Unscented Kalman Filter  | Same as EKF                              | Comparable to EKF for planar motion                                       |     Moderate     | `robot_localization` (`ukf_node`) | Higher cost for marginal benefit when motion is close to linear                   |
| Visual-inertial odometry | Camera + IMU                             | Lowest drift rate of the four                                             |    High (GPU)    | `rtabmap_odom`, VINS-family       | Requires texture and stable lighting; competes for GPU with other edge workloads  |

None of the four approaches in Table 2.2b removes drift; they differ in how fast it accumulates and in what it costs to slow it down. Cost matters more than raw accuracy here, because odometry is not the only correction in this stack: the SLAM map bounds its drift over a service cycle (§2.2.4), and the fiducial marker bounds it again at the final approach (§2.2.6), so the odometry only has to stay accurate between those two fixes. On that criterion the four separate by what each one demands in order to reach the required local accuracy. The complementary filter is cheapest but has no explicit uncertainty, so its output cannot be weighted against another correction in a principled way. Visual-inertial odometry drifts the least but needs a GPU that competes with other workloads on the robot's onboard computer. The unscented Kalman filter costs more than the extended Kalman filter for a benefit that mostly disappears once the motion is close to linear, which it usually is for a differential-drive robot on a flat floor. The extended Kalman filter tracks an explicit uncertainty estimate at moderate cost and is natively supported by the ROS2 `robot_localization` package, and its predict and update recursion is set out in full below.

The Kalman filter is a recursive estimator that combines several uncertain sources into one more certain estimate of a system's state. It represents its knowledge at each step $k$ as a Gaussian, summarized by a best estimate $\hat{\mathbf{x}}_k$ (the mean) and a covariance $\mathbf{P}_k$ (the uncertainty; off-diagonal entries record correlations between state variables, so one measurement also sharpens the others). The filter works in two stages: a prediction step, which projects the estimate forward with a motion model, and an update step, which corrects that prediction with each sensor reading, leaning toward whichever is currently more certain.

**Prediction.** The prediction step projects the current estimate one time step forward using only the motion model, before any new sensor reading is taken into account. It answers, from what was known at step $k-1$, where the system should be at step $k$ and how much certainty is lost along the way.

The first equation predicts the state:

$$
\hat{\mathbf{x}}_k = \mathbf{F}_k\,\hat{\mathbf{x}}_{k-1} + \mathbf{B}_k\,\vec{\mathbf{u}}_k
$$

The second predicts the covariance:

$$
\mathbf{P}_k = \mathbf{F}_k\,\mathbf{P}_{k-1}\,\mathbf{F}_k^{\mathsf T} + \mathbf{Q}_k
$$

Where:

- $\hat{\mathbf{x}}_k$, $\mathbf{P}_k$ are the predicted estimate and its covariance
- $\mathbf{F}_k$ is the state-transition matrix (the motion model); applied to the covariance as $\mathbf{F}_k\mathbf{P}_{k-1}\mathbf{F}_k^{\mathsf T}$ it propagates the uncertainty the same way
- $\mathbf{B}_k$, $\vec{\mathbf{u}}_k$ are the control matrix and control vector, adding any known external command
- $\mathbf{Q}_k$ is the process-noise covariance, the uncertainty for everything the model misses

Because no measurement is used, the prediction is necessarily less certain than the estimate it came from, which is why $\mathbf{Q}_k$ is added rather than subtracted.

**Update.** The update step corrects the prediction each time a sensor reading arrives, blending model and measurement into a single, sharper estimate. It pulls the drifting prediction back toward reality using the information the sensor actually provides.

The first equation corrects the state, moving the prediction toward the reading:

$$
\hat{\mathbf{x}}'_k = \hat{\mathbf{x}}_k + \mathbf{K}'\big(\vec{\mathbf{z}}_k - \mathbf{H}_k\,\hat{\mathbf{x}}_k\big)
$$

The second corrects the covariance, which shrinks because the measurement removes uncertainty:

$$
\mathbf{P}'_k = \mathbf{P}_k - \mathbf{K}'\,\mathbf{H}_k\,\mathbf{P}_k
$$

The third is the Kalman gain, the weight used in the two equations above:

$$
\mathbf{K}' = \mathbf{P}_k\,\mathbf{H}_k^{\mathsf T}\big(\mathbf{H}_k\,\mathbf{P}_k\,\mathbf{H}_k^{\mathsf T} + \mathbf{R}_k\big)^{-1}
$$

Where:

- $\hat{\mathbf{x}}'_k$, $\mathbf{P}'_k$ are the corrected estimate and its covariance, fed back into the next round. The prime ($'$) marks an updated (post-measurement) value, as opposed to the unprimed predicted value $\hat{\mathbf{x}}_k$, $\mathbf{P}_k$ from the prediction step
- $\mathbf{H}_k$ is the observation matrix, mapping the state into what the sensor should read
- $\vec{\mathbf{z}}_k$ is the measurement; $\mathbf{R}_k$ is the measurement-noise covariance (small = trusted sensor)
- $\vec{\mathbf{z}}_k - \mathbf{H}_k\hat{\mathbf{x}}_k$ is the innovation, the difference between the reading and what was expected
- $\mathbf{K}'$ is the Kalman gain, deciding how much of the innovation to apply

In one dimension the gain is $K = p_k/(p_k+r_k)$, between $0$ and $1$: a precise sensor ($r_k$ small) gives $K\to 1$ (follow the reading), a noisy one gives $K\to 0$ (ignore it). $\mathbf{P}'_k$ shrinks because the measurement removes uncertainty.

**From the Kalman filter to the EKF.** The linear filter above assumes both models are matrices. Many real systems do not fit that template: whenever a process or measurement genuinely depends on a product of state variables, a trigonometric function of the state, or some other curved relationship, no constant matrix can describe it exactly. The **Extended Kalman Filter (EKF)** keeps the same predict and update loop but replaces the two model matrices with non-linear functions: a process model $\mathbf{f}$ in place of $\mathbf{F}_k\hat{\mathbf{x}}_{k-1}$, and a measurement model $\mathbf{h}$ in place of $\mathbf{H}_k\hat{\mathbf{x}}_k$. The process and measurement noise are still described by $\mathbf{Q}_k$ and $\mathbf{R}_k$, exactly as in the linear filter.

A covariance cannot be pushed through a non-linear function directly, so the EKF linearizes: it expands each function in a Taylor series around the current estimate, keeps only the first-order term, and drops the rest, replacing the curved function locally by its tangent. The slope of that tangent is the Jacobian, the matrix of first partial derivatives.

The first Jacobian linearizes the process model:

$$
\mathbf{F}_k = \left.\frac{\partial \mathbf{f}}{\partial \mathbf{x}}\right|_{\hat{\mathbf{x}}'_{k-1}}
$$

The second linearizes the measurement model:

$$
\mathbf{H}_k = \left.\frac{\partial \mathbf{h}}{\partial \mathbf{x}}\right|_{\hat{\mathbf{x}}_k}
$$

Where:

- each entry is a partial derivative, $\partial f_a/\partial x_b$ for $\mathbf{F}_k$ and $\partial h_a/\partial x_b$ for $\mathbf{H}_k$
- $\mathbf{F}_k$ is evaluated at $\hat{\mathbf{x}}'_{k-1}$, the previous step's updated estimate (the point the process model starts from)
- $\mathbf{H}_k$ is evaluated at the current predicted estimate $\hat{\mathbf{x}}_k$ (where the measurement is compared)

$\mathbf{f}$ and $\mathbf{h}$ are never replaced by their Jacobians: the state prediction and the innovation always call them directly. $\mathbf{F}_k$ and $\mathbf{H}_k$ are separate, auxiliary matrices used only to propagate the covariance and form the Kalman gain, replacing the constant matrices of the linear filter in those two roles.

**EKF algorithm.** Initialized with $\hat{\mathbf{x}}_0$, $\mathbf{P}_0$, the full cycle repeats at each step $k$.

*Predict.* The first equation predicts the state, the second the covariance:

$$
\hat{\mathbf{x}}_k = \mathbf{f}(\hat{\mathbf{x}}'_{k-1}, \Delta t)
$$

$$
\mathbf{P}_k = \mathbf{F}_k\,\mathbf{P}'_{k-1}\,\mathbf{F}_k^{\mathsf T} + \mathbf{Q}_k
$$

*Update.* The first equation is the Kalman gain, the second corrects the state, and the third corrects the covariance:

$$
\mathbf{K}' = \mathbf{P}_k\,\mathbf{H}_k^{\mathsf T}\big(\mathbf{H}_k\,\mathbf{P}_k\,\mathbf{H}_k^{\mathsf T} + \mathbf{R}_k\big)^{-1}
$$

$$
\hat{\mathbf{x}}'_k = \hat{\mathbf{x}}_k + \mathbf{K}'\big(\vec{\mathbf{z}}_k - \mathbf{h}(\hat{\mathbf{x}}_k)\big)
$$

$$
\mathbf{P}'_k = \mathbf{P}_k - \mathbf{K}'\,\mathbf{H}_k\,\mathbf{P}_k
$$

The result $\hat{\mathbf{x}}'_k$, $\mathbf{P}'_k$ feeds back into the next step, and the cycle repeats. (Bold $\mathbf{x}$ denotes the state vector; italic $x$ denotes its position component, once the robot's specific state is defined in §3.3.)

**The EKF in the ROS2 stack.** The ROS2 `robot_localization` package provides this prediction and update recursion as a configurable node, so a differential-drive platform can obtain fused odometry without implementing the filter itself. Which states the filter estimates, which sensors it fuses, and how far it trusts each one are set through a parameter file rather than in code. Its output is a filtered odometry stream together with the `odom → base_footprint` transform that mapping, localization, and navigation all read. How this filter is instantiated on the robot of this thesis, with its state vector, its sensor selection, and its covariance values, is a design matter set out in §3.3.



**[Figure 2.2b. The extended Kalman filter as a predict/update loop: a motion model advances the state and inflates its covariance, each incoming measurement corrects both through the Kalman gain, and the corrected estimate feeds back into the next prediction.]**

---

### 2.2.3 Robot Operating System (ROS2)

The kinematic model, the odometry, and the filter of the previous subsections are useful only once they run together, and the components surveyed in the rest of this section, the SLAM package, the planner, the controller, and the marker detector, are separate programs that must exchange data continuously while they run. A modern robot is therefore not a single program but many small ones running at once: one reads the LiDAR, another computes odometry, another plans a path, another drives the motors. Writing that as one monolithic application would be fragile and hard to reuse, so it is built on a robotics middleware instead. ROS2, the second-generation Robot Operating System, is that middleware. Despite the name, ROS2 is not an operating system; it is a framework of communication tools and conventions that let independent programs cooperate as one robot.

In ROS2 each independent program is a node, and a running robot is a collection of nodes that do not call each other directly. They communicate through a few well-defined patterns. The most common is the topic, a named channel that one node publishes to and any number of others subscribe to, so the LiDAR driver publishes scans on a topic while the mapping and navigation nodes read them without needing to know which node produced them. For request-and-reply exchanges ROS2 provides services, and for long-running goals that report progress and can be cancelled, such as "navigate to this pose," it provides actions, which is the interface the navigation stack of §2.2.5 exposes. Underneath these patterns sits DDS (Data Distribution Service), an industry-standard layer that handles discovery and message delivery across the network and removes the single central master that the first-generation ROS depended on.

Because a robot carries many sensors and moving parts, each with its own position, ROS2 also standardises how spatial relationships are described. The TF (transform) system tracks every coordinate frame, the world, the map, the robot body, and each sensor, along with how they relate over time, so that a point measured in one frame can be expressed in any other. That is exactly what fusing a LiDAR scan, a camera detection, and an odometry estimate requires. The physical layout underlying those frames, the links, joints, wheel spacing, and sensor mounts, is declared in a URDF (Unified Robot Description Format) file that supplies both the TF tree and the geometric model used for visualisation and simulation.

ROS2 rather than the original ROS is the standard choice for new work of this kind, for reasons that matter to a service robot. The DDS layer removes the central point of failure and gives more configurable, real-time-capable message delivery across several machines, and the ecosystem of ready-made packages, from sensor drivers to SLAM and navigation, removes most of the code that would otherwise be written from scratch. Every navigation component surveyed below is distributed as a ROS2 package, which is why the survey treats them as off-the-shelf parts to be selected and configured rather than reimplemented.

**[Figure 2.2c. ROS2 publish/subscribe communication: sensor-driver nodes publish to named topics that processing and navigation nodes subscribe to, with services and actions carrying request/reply and long-running-goal interactions, all over the DDS transport layer.]**

---

### 2.2.4 SLAM, Map Building, and Localization

Simultaneous Localization and Mapping addresses a circular dependency: localizing requires a map, and building a map requires knowing where the robot is [2.2.10]. Modern systems separate a front end, which processes sensor data and aligns consecutive observations, from a back end, which optimizes a graph of poses subject to constraints and detects loop closures, that is, revisits to previously mapped locations that allow accumulated drift to be redistributed across the whole trajectory.

A graph is the structure most modern 2D systems use to hold that estimate, and the mapping and localization of Chapter 3 build directly on it. Each node of the graph is a robot pose at one instant; each edge is a constraint between two poses, contributed either by odometry between consecutive nodes or by a sensor match between nodes that are not adjacent in time. No constraint is exact, so each carries an information weight that sets how tightly it should be believed. The back end then looks for the poses that best satisfy every constraint at once, that is, the poses that minimize the total weighted disagreement,

$$
\mathbf{x}^\star = \arg\min_{\mathbf{x}} \sum_{(i,j)} \mathbf{e}_{ij}(\mathbf{x})^{\mathsf T}\,\boldsymbol{\Omega}_{ij}\,\mathbf{e}_{ij}(\mathbf{x}),
$$

where $\mathbf{e}_{ij}$ is the error of the constraint between poses $i$ and $j$ and $\boldsymbol{\Omega}_{ij}$ is its information weight, the inverse of that constraint's measurement covariance. This weighted least-squares objective is the standard formulation of graph-based SLAM, and under Gaussian constraint noise the poses that minimize it are the maximum a posteriori estimate of the trajectory [2.2.10a]. A loop closure is one such constraint, added when the robot recognizes a place it has already mapped, and it is what lets the optimizer pull a drifted trajectory back onto itself rather than leave the error to grow.

Recognizing that place is a probabilistic decision, which is where a Bayesian estimate enters the mapping problem. An appearance-based system maintains a probability over the hypothesis that the current view matches each past location and updates it as a Bayes filter: a prior over where the robot could be, a likelihood from how well the current image matches each stored one, and a posterior that is accepted as a closure only once it passes a confidence threshold. Treating the match as a probability rather than a hard decision prevents a single mistaken resemblance in a repetitive room from corrupting the whole graph. The subsections that follow compare the SLAM systems that implement these ideas and the localization methods that reuse the finished map.

A 2D LiDAR such as the RPLiDAR A2M8 produces a planar scan of range measurements at fixed angular resolution, typically several hundred points per revolution at 5–10 Hz [2.2.11]. Consecutive scans are aligned by scan matching, most commonly a variant of Iterative Closest Point, which recovers the rigid transform minimizing the distance between corresponding points [2.2.13]. Accumulated scans populate an occupancy grid. LiDAR mapping is insensitive to illumination and geometrically accurate within the scan plane, but scan matching becomes ill-conditioned wherever geometry repeats: a long corridor with parallel walls, or a room of regularly spaced tables and chairs, produces scans that are nearly identical at locations that are metrically distinct.

An RGB-D camera such as the Intel RealSense D435 supplies registered colour and depth imagery up to 30 Hz [2.2.12]. Its contribution to mapping is *place recognition* rather than geometry, since the LiDAR is more accurate in the scan plane. Visual features quantized into a bag-of-words vocabulary allow a system to recognize a previously visited location from appearance alone, independently of the current pose estimate and independently of whether the local geometry is ambiguous [2.2.19]. Where LiDAR scan correlation cannot distinguish two structurally identical locations, image texture usually can.

Five SLAM implementations are available for ROS2 and span this design space. GMapping applies a Rao-Blackwellized particle filter to 2D laser data and was the ROS1 default; it has no explicit loop-closure mechanism and its ROS2 support is community-maintained rather than official [2.2.14]. Hector SLAM performs scan matching without requiring odometry, which suits platforms lacking encoders, but likewise offers no loop closure and drifts in featureless environments [2.2.15]. Cartographer introduced submap-based graph SLAM with branch-and-bound scan matching for loop-closure search and remains a strong 2D and 3D system, though its ROS2 maintenance has lagged the core stack [2.2.16]. SLAM Toolbox is the ROS2 tier-one 2D solution, implementing a pose graph optimized with Ceres, with loop closure detected by scan correlation and maps serialized as pose graphs [2.2.17]. RTAB-Map performs graph SLAM over both LiDAR and RGB-D input, detects loop closures through visual bag-of-words in addition to LiDAR spatial proximity, optimizes with g²o or GTSAM, and manages memory through a working-memory / long-term-memory partition that keeps real-time performance bounded as the map grows [2.2.18], [2.2.20].

**Table 2.2c.** 2D SLAM implementations available for ROS2.


| System       | Sensors                         | Formulation                       | Loop-closure cue                      | Native saved format         | Behaviour in repetitive geometry                     |
| ------------ | ------------------------------- | --------------------------------- | ------------------------------------- | --------------------------- | ---------------------------------------------------- |
| GMapping     | 2D LiDAR                        | Rao-Blackwellized particle filter | None explicit                         | Occupancy grid (`.pgm`/`.yaml`) | Degrades; no mechanism to correct a mistaken revisit |
| Hector SLAM  | 2D LiDAR (no odometry required) | Scan matching only                | None                                  | Occupancy grid (`.pgm`/`.yaml`) | Drifts without bound in featureless corridors        |
| Cartographer | 2D/3D LiDAR (+ IMU)             | Submap graph SLAM                 | Branch-and-bound scan matching        | Submap stream (`.pbstream`) | Better than correlation alone, still geometry-only   |
| SLAM Toolbox | 2D LiDAR                        | Pose graph, Ceres optimizer       | Scan correlation                      | Pose graph (`.posegraph`)   | Ambiguous where scans repeat at distinct locations   |
| RTAB-Map     | 2D LiDAR + RGB-D                | Graph SLAM, g2o/GTSAM             | Visual bag-of-words + LiDAR proximity | SQLite database (`.db`)     | Appearance resolves locations that geometry cannot   |

Once a map exists, operation shifts from building it to localizing within it, and the same distinction between geometric and appearance-based place recognition reappears. Adaptive Monte Carlo Localization maintains a particle distribution over poses, weighting particles by the agreement between the expected and observed laser scan, and is the long-standing ROS default paired with a static map served from a `.pgm` and `.yaml` pair [2.2.26]. Its failure mode is the one the geometry predicts: in a symmetric or repetitive environment, the particle cloud can converge confidently on the wrong hypothesis, and recovery requires redistributing particles globally. RTAB-Map can instead run in a localization mode that holds the stored graph fixed and relocalizes against it using the same visual and geometric matching used during mapping, which permits global relocalization from an arbitrary starting pose.

**Table 2.2d.** Localization against a prior map.


| Approach                   | Algorithm                            | Sensors          | Map source                              | Behaviour in symmetric geometry                            | Recovery when lost             |
| -------------------------- | ------------------------------------ | ---------------- | --------------------------------------- | ---------------------------------------------------------- | ------------------------------ |
| Odometry only              | Dead reckoning                       | Encoders (+ IMU) | None                                    | n/a (no map reference)                                     | None; error is permanent       |
| AMCL                       | Monte Carlo particle filter          | 2D LiDAR         | `.pgm` + `.yaml` via `map_server`       | Prone to confident false convergence where scans repeat    | Global particle redistribution |
| RTAB-Map localization mode | Graph matching + visual bag-of-words | 2D LiDAR + RGB-D | `rtabmap.db`; publishes `/map` directly | Visual appearance separates geometrically identical places | Global visual relocalization   |

**[Figure 2.2d. Why geometric place recognition fails in a dining room: two laser scans captured at metrically distinct locations in a regularly spaced table layout, shown overlaid to illustrate that scan correlation cannot separate them, alongside the corresponding camera images, which differ clearly in texture.]**

Table 2.2c and Table 2.2d converge on the same discriminating condition for a restaurant. A dining room is close to the worst case for purely geometric place recognition: tables and chairs form repeating clusters, walls are long and featureless, and the service lane presents the same profile at many points along its length. On metric mapping accuracy these systems are broadly comparable, so they divide on two other properties. The first is whether a system carries a second, non-geometric cue for recognising a place. The second is whether it can recover after losing track without a person supplying an initial pose. The evaluations published for these systems are drawn largely from office corridors, warehouse aisles, and outdoor campuses, and none of them evaluates the repeating-cluster geometry of a dining room, which is the condition under which the two cues diverge.

Among the five systems surveyed, RTAB-Map satisfies both properties where the others satisfy at most one. It is the only entry in Table 2.2c that adds a visual appearance cue to the laser map, and the only entry in Table 2.2d that recovers a lost pose through global visual relocalization rather than by scattering particles and waiting for them to reconverge. The systems are close on metric mapping accuracy, but on the two properties a dining room actually tests, RTAB-Map is the strongest of the group.

RTAB-Map, short for Real-Time Appearance-Based Mapping, is an open-source graph SLAM system that fuses an RGB-D camera, a 2D laser, and wheel-inertial odometry into a single pose graph [2.2.18]. The incoming streams are first synchronized, and each new keyframe becomes a node in short-term memory, linked to the node before it by the odometry measured between them. Two mechanisms then look for links back to older nodes: proximity detection from the laser geometry, and appearance-based loop closure, which compares the current image against past ones through the bag-of-words Bayes filter described earlier in this section. Every link that passes is handed to a graph optimization that corrects the whole trajectory and publishes the map-to-odom transform the navigation stack reads, while a parallel map-assembling stage renders the optimized graph into the 2D occupancy grid used for planning.

RTAB-Map keeps this running in real time as the map grows through the way it manages memory. Only a bounded working memory of recent and frequently seen nodes is kept available for the loop-closure search; the rest are moved out to a long-term memory and brought back only when the robot returns to that part of the map. The search for a loop closure therefore runs against a roughly constant number of nodes however large the full map becomes, which keeps the method within the compute budget of an onboard computer across a long service session.

**[Figure 2.2e. RTAB-Map architecture (`rtabmap_ros/rtabmap`): synchronized RGB-D, laser, and odometry inputs entering short-term memory; loop-closure and proximity detection running over a bounded working memory backed by long-term-memory node transfer; graph optimization publishing the map-to-odom transform; and global map assembling producing the 2D occupancy grid alongside the other map outputs.]**

---

### 2.2.5 Autonomous Navigation

With a map and a pose within it, the navigation stack must convert a goal pose into wheel velocities. Navigation2 is the standard ROS2 framework for this and decomposes the problem into a global planner, a local controller, a costmap layer, and a behaviour tree that orchestrates the lifecycle and its recoveries [2.2.21].

The global planner searches the static costmap, the occupancy grid inflated by the robot's footprint, for a path minimizing a cost that penalizes both length and obstacle proximity. NavFn computes a Dijkstra or A* solution over a potential field and is fast and robust, but produces paths without regard to kinematic feasibility; for a differential-drive robot this is acceptable, because the platform can rotate in place to acquire any required heading. The Smac family adds planners that respect kinematic constraints: a hybrid-A* variant producing smooth, drivable paths for car-like platforms, and a state-lattice variant for arbitrary motion primitives. Both cost more planning time, which is only repaid when the platform genuinely cannot turn in place.

The local controller executes the global path by emitting velocity commands at control rate. The Dynamic Window Approach samples candidate velocity pairs within the platform's kinematic limits and scores each against a weighted set of critics (progress toward the goal, clearance from obstacles, alignment with the path, and forward speed), then issues the best-scoring command [2.2.22]. The Timed Elastic Band formulates trajectory following as an optimization over a time-parameterized sequence of poses, supporting car-like kinematics and explicit time-optimality at the cost of a substantially larger parameter set [2.2.23]. Regulated Pure Pursuit follows the path geometrically, regulating linear speed by path curvature and obstacle proximity; it has few parameters and predictable behaviour, which makes it well suited to constrained environments where the path is known to be collision-free by construction [2.2.24].

**Table 2.2e.** Nav2 global planners and local controllers.


| Component                      | Method                                        | Kinematic model                                 |           Suits non-holonomic TWD           | Tuning burden               |
| ------------------------------ | --------------------------------------------- | ----------------------------------------------- | :-----------------------------------------: | --------------------------- |
| NavFn (global)                 | Dijkstra / A* on potential field              | Holonomic path, heading acquired by rotation    |     ✓ (rotation in place is available)     | Low                         |
| Smac Hybrid-A* (global)        | Kinematically feasible A*                     | Ackermann / car-like                            | Unnecessary (no turning-radius constraint) | Moderate                    |
| Smac State Lattice (global)    | Search over motion primitives                 | Arbitrary, primitive-defined                    |          Unnecessary at this scale          | High                        |
| DWB (local)                    | Velocity sampling with weighted critics       | Differential drive native; V_y constrained to 0 |                     ✓                     | Moderate (critic weights)  |
| TEB (local)                    | Time-parameterized trajectory optimization    | Differential and car-like                       |           ✓, but over-specified           | High (large parameter set) |
| Regulated Pure Pursuit (local) | Geometric path following, curvature-regulated | Differential drive                              |                     ✓                     | Low                         |

A two-wheel differential-drive platform is non-holonomic: lateral velocity is structurally zero, and every lateral correction decomposes into a rotation followed by a translation. This constrains the controller, which may sample only velocity pairs satisfying the differential-drive model, but it also *relaxes* the global planner's requirements, since a platform that can rotate in place does not need a planner that respects a minimum turning radius. Around both, Nav2's behaviour tree sequences the navigation lifecycle and its recoveries: when progress stalls, it triggers a clearing rotation, then a larger in-place rotation, then a full replan, and finally aborts and reports failure [2.2.25]. That final step matters here, because it is the only point at which the stack reports that it cannot proceed, and all it produces is a status. What should happen next is left entirely outside the navigation system.

**[Figure 2.2f. The navigation stack and its goal interface: sensing feeds odometry fusion, which feeds SLAM and localization, which feed the global planner, local controller, and behaviour tree. The goal source sits above the stack, outside it. In prior work this input is a human operator; the coupling this thesis proposes replaces it with an AI agent emitting goals as side effects of restaurant business events.]**

What the surveyed work does not provide is the interface above the stack. In every academic deployment reviewed, the goal is operator-initiated: a human selects a waypoint on a map, or a hard-coded sequence steps through a fixed tour, and Nav2 executes it [2.2.19]. Reported navigation success rates above 90% in controlled indoor environments describe the quality of that execution, not the origin of the goal. Coupling the goal interface to a non-human source raises requirements that operator-driven navigation never encounters: goals arrive asynchronously as side effects of business events rather than at moments a human chooses; a goal may need to preempt one already in flight when a higher-priority delivery is dispatched; the goal carries business context (which order, which session) that must survive the round trip and be reported back on arrival; and a navigation failure must surface as a recoverable task state rather than as a message on an operator's screen. None of the work surveyed in this section connects Nav2 to a goal source with these properties; the coupling proposed in §3.7 is designed to satisfy them.

---

### 2.2.6 Fiducial Marker Docking

Localization against a SLAM map carries residual error. Map discretization, accumulated odometry drift between corrections, and the localization filter's own uncertainty combine into a pose estimate that may be off by several centimetres even under good conditions. For most of a delivery this does not matter. It matters at the final approach, where a lateral offset means the robot does not square up to the table and the customer must reach awkwardly across the tray. A fiducial marker, a visual pattern of known geometry and known position, provides an absolute local reference at the point where the requirement is tightest.

A square fiducial encodes an integer identifier in a binary grid bordered by a black frame. Detection proceeds by extracting candidate contours from the image, rectifying each to a frontal square, and decoding the interior bit pattern against a dictionary; a marker whose decoded pattern is not a dictionary member is rejected, which suppresses false positives from incidental rectangular structure in the scene. Because the marker's physical side length is known, its four detected corners give four 3D–2D correspondences, and Perspective-n-Point estimation recovers the full six-degree-of-freedom transform between camera and marker [2.2.31]. The solution is well conditioned when the marker subtends a sufficient portion of the image and degrades as the marker becomes small, oblique, or motion-blurred.

**[Figure 2.2g. Perspective-n-Point pose estimation from a square fiducial: the four detected marker corners in the image plane, their known 3D coordinates in the marker frame, and the recovered six-degree-of-freedom camera-to-marker transform, with coordinate axes annotated.]**

Five marker families appear in the robotics literature. ArUco provides configurable dictionaries with selectable size and inter-marker Hamming distance and ships within OpenCV, which makes it the most widely available option in ROS2 [2.2.27]. AprilTag uses a lexicographic coding system engineered for a low false-positive rate and detects reliably at greater range and steeper viewing angles, at higher detector cost [2.2.28]. ARTag established much of the approach but has been largely superseded [2.2.29]. STag adds an elliptical refinement stage that stabilizes the recovered pose under oblique views, with a correspondingly smaller ecosystem [2.2.30]. ChArUco interleaves a chessboard with ArUco markers so that saddle-point corners can be refined to sub-pixel accuracy, yielding the most accurate pose of the group but requiring a physically larger target than a table-mounted marker practically allows.

**Table 2.2f.** Square fiducial marker families.


| Family   | Coding                                     |          Pose accuracy          | Range / oblique robustness |          Occlusion tolerance          | ROS2 availability                   |
| -------- | ------------------------------------------ | :-----------------------------: | :------------------------: | :------------------------------------: | ----------------------------------- |
| ArUco    | Configurable dictionary, Hamming-separated |              Good              |          Moderate          | Low (a lost corner defeats detection) | Native in OpenCV; several wrappers  |
| AprilTag | Lexicographic, low false-positive rate     |              Good              |          **High**          |                  Low                  | `apriltag_ros`, actively maintained |
| ARTag    | Forward error correction                   |            Moderate            |          Moderate          |                  Low                  | Largely superseded                  |
| STag     | Elliptical refinement stage                |  **High** under oblique views  |            High            |                  Low                  | Limited ecosystem                   |
| ChArUco  | Chessboard + ArUco hybrid                  | **Highest** (sub-pixel corners) |          Moderate          | Moderate (partial board still usable) | Native in OpenCV                    |

The published comparisons separate these families on detection range, robustness at steep viewing angles, and resistance to false positives across large dictionaries. All three are exercised at the margins of the operating envelope, and a marker mounted at a known table, observed from roughly one metre at near-frontal incidence, sits well inside that envelope for every family listed. The dimensions on which the literature most sharply distinguishes these systems are therefore not the dimensions a short, frontal, indoor docking approach depends on. Such an approach depends instead on how a detector behaves when the marker is absent, partially occluded, or motion-blurred, and on whether that condition is reported distinguishably from a successful detection rather than as a low-confidence pose. The comparative literature does not report that dimension.

With the discriminating dimensions inactive at this operating point, the selection falls to availability and integration cost rather than to a detection-performance margin the approach never exercises. On those grounds ArUco is the strongest of the group: its detector ships inside OpenCV, which the vision stack already depends on for camera handling, so no additional detector package enters the build; its dictionaries are generated offline at a chosen size and inter-marker Hamming distance, which fixes the identifier space for a known and small set of tables; and its ROS2 wrappers are established. AprilTag's advantage at long range and steep incidence, and STag's under oblique views, buy robustness the near-frontal one-metre approach does not need, while ChArUco's sub-pixel accuracy requires a target physically larger than a table will carry. The docking design in §3.6 adopts ArUco on this basis.

Prior work using these markers treats each one as a geometric target: a pose in space that the robot must reach, whether a charging dock or a delivery drop-off point. In a restaurant, each table carries its own marker, so the identifier the detector decodes is not only an index into a dictionary but a reference to a business entity: the marker mounted at a given table stands for that table, for whichever session is currently seated there, and for that session's outstanding order. A pose correction alone does not establish that the food on the tray belongs to the party at the table now in front of the robot. Making that check possible requires the marker identifier to be resolvable by the backend at docking time, from marker to table to session to order, so that arrival triggers a verification as well as a geometric correction. Among the systems surveyed here, none binds fiducial markers to business entities in this way; the docking design in §3.6 does so.

---

### 2.2.7 Prior ROS2 Delivery Robot Research

Academic projects have demonstrated ROS2 delivery robots in several service contexts: campus cafeteria food delivery, hospital ward medication transport, and office document delivery [2.2.32]–[2.2.34]. The hardware is largely the same across them, namely 2D LiDAR, RGB-D camera, IMU, and wheel encoders on a differential-drive or mecanum base. So is the software: a SLAM package for mapping, Nav2 for planning and control, and fiducial markers for terminal precision. These systems establish that autonomous indoor delivery is achievable with open components, and they report navigation success rates above 90% in controlled environments.

**Table 2.2g.** Prior ROS2 delivery robot systems, by the two dimensions that distinguish them from the system proposed here.


| System class                           | Typical sensing        | Mapping / navigation               | Terminal precision                 | **Goal source**                           | **Conversational interaction** |
| -------------------------------------- | ---------------------- | ---------------------------------- | ---------------------------------- | ----------------------------------------- | :-----------------------------: |
| Campus cafeteria delivery [2.2.32]     | 2D LiDAR + RGB-D + IMU | Cartographer or RTAB-Map → Nav2   | Fiducial marker                    | Operator selects destination              |               ✗               |
| Hospital medication transport [2.2.33] | 2D LiDAR + RGB-D + IMU | SLAM → Nav2, fixed ward waypoints | Fiducial marker or manual handover | Fixed route or operator                   |               ✗               |
| Office document delivery [2.2.34]      | 2D LiDAR + IMU         | SLAM → Nav2                       | Fiducial marker                    | Fixed tour sequence                       |               ✗               |
| Commercial service robots (§2.1)      | LiDAR + RGB-D          | Proprietary SLAM + planner         | Proprietary                        | Touchscreen, selected by staff            | ✗ (pre-recorded greeting only) |
| **This work**                          | 2D LiDAR + RGB-D + IMU | RTAB-Map → Nav2                   | Fiducial marker, business-verified | **AI agent, from live restaurant events** |             **✓**             |

The two rightmost columns read the same way in every row. A person picks the destination, whether an operator selecting on a screen, a technician defining a tour, or a member of staff pressing a table number, and the robot plays no part in the exchange that led to the delivery; it drives to a table and stops. It cannot take an order, answer a question about a dish, confirm a choice, or accept payment. These systems address navigation without addressing interaction, so the question of where the navigation goals should come from does not arise for them.

---

Across the surveyed work these capabilities add up to a functioning delivery robot, and the reported navigation success rates show the combination is reliable. It works, however, on an assumption that an operator-driven system never has to state: that a human decides where the robot goes.

That assumption shapes everything above the navigation stack. Because a person issues each goal at a moment of their own choosing, the system never has to handle a goal that arrives on its own, interrupts one already in flight, or carries order details that must be returned when the robot arrives. Because a person has already decided which table matters, the marker only has to mark a place and carries no business meaning. Because a person watches for failures and resolves them, a failure only has to appear as a message on a screen rather than as state that another component can act on.

If an autonomous agent replaces that person, all three consequences reverse. Goals then arrive on their own, interrupt each other, and must carry order and session context; markers must resolve to tables, sessions, and orders at docking time; and failures must become task state that can be reassigned. Among the systems surveyed here, none reports all three together.
