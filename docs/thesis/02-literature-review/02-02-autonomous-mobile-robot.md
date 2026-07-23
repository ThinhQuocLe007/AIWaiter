## 2.2 Autonomous Mobile Robot

> *A robot that delivers food must reach the right table at a moment that is not known in advance — the destination is decided by an AI agent responding to live restaurant events. This section surveys the technologies that make autonomous indoor navigation possible: odometry and sensor fusion, SLAM and localization, path planning and control, and fiducial-marker docking. Each of these is an off-the-shelf component; for each, the section presents the available options, what distinguishes them, and what the published evaluations do and do not establish. Two capabilities are not off-the-shelf — coupling navigation goals to an external agent, and binding a docking marker to a business entity — and for those the section identifies the gap in prior work.*
>
> **Cross-refs:** §2.1 (overview — commercial robot limitations), §2.8 (edge compute platform), §3.1 (navigation requirements), §3.4–§3.7 (proposed navigation method), §5.2 (navigation experiments)
> **Citations:** [2.2.1]–[2.2.34]; final numbering assigned when all Ch.2 references are merged. Bibliographic entries for this section are pending — see `references.md`.
> **Figures and tables:** keyed section-scoped (`Table 2.2a`, `Figure 2.2a`, …) so that this section can be edited independently. Flatten to sequential chapter numbering on merge, in order of first appearance — the same convention used for citations.

---

A robot that delivers food in a restaurant must answer one question repeatedly: *where should I go next?* The answer changes with every business event — a party is seated at table 3, an order for table 5 is marked complete in the kitchen, the session at table 2 is paid and the table is vacated. The navigation target is not fixed; it is a function of live restaurant state managed by an external AI agent.

Answering that question reliably requires a stack of four capabilities, each surveyed below: an estimate of where the robot is relative to where it started (§2.2.1), a map of the environment and a means of localizing within it (§2.2.2), a planner and controller that convert a goal pose into wheel velocities (§2.2.3), and a short-range correction that achieves the precision the final approach demands (§2.2.4). Every one of these capabilities is available as a mature, open-source ROS2 component, and the survey below is therefore oriented toward selection: what options exist, what distinguishes them, and which properties matter for a restaurant service lane. Section 2.2.5 then examines the academic ROS2 delivery robots that assemble these same components, and identifies what they consistently leave unaddressed.

---

### 2.2.1 Wheel Odometry and Sensor Fusion

A differential-drive robot estimates its motion through two complementary sensor modalities. Wheel encoders provide relative displacement; an inertial measurement unit (IMU) provides angular rate and linear acceleration. Neither is sufficient alone. Encoders accumulate drift that grows without bound — each wheel slip on a smooth floor, each uneven tile, each in-place rotation introduces error that no subsequent encoder reading can correct. An IMU measures angular rate independently of wheel-ground contact, but consumer-grade MEMS devices exhibit gyroscope bias, a near-constant offset that integrates into a growing heading error, and accelerometer noise severe enough that double-integration to position is unusable beyond a few seconds [2.2.1]–[2.2.2].

For a differential-drive platform whose encoders produce P pulses per revolution through a gear ratio G, the number of counts per wheel revolution is N = P × 4 × G under quadrature decoding, and the distance per count follows from the wheel diameter D. Wheel linear velocities are computed from counts accumulated over a fixed interval, and the forward kinematics of the differential drive give the body-frame velocities [2.2.3]:

$$V_x = \frac{V_A + V_B}{2}, \quad V_\omega = \frac{V_B - V_A}{W}$$

where V_A and V_B are the left and right wheel linear velocities and W is the wheel track width. Integrating these over time yields pose. The structural limitation is that encoders measure wheel *rotation*, not wheel *displacement*: slip, skid, and surface irregularity produce motion the encoders never observe, and error introduced this way is never recovered because dead reckoning has no external reference against which to correct.

The IMU on this class of platform is typically an MPU6050 or equivalent six-degree-of-freedom MEMS device, reporting angular velocity and linear acceleration as raw 16-bit integers that require factory scale factors to convert to SI units [2.2.4]. Its gyroscope yields a heading estimate that is independent of wheel-ground contact and therefore degrades under exactly the conditions where encoder heading is worst. Its accelerometer observes the gravity vector at rest, providing an absolute tilt reference, but contributes little to planar position estimation.

Combining the two is a state-estimation problem, and four approaches appear in the mobile robotics literature. The complementary filter blends the two sources in the frequency domain with a fixed gain — trusting the gyroscope over short intervals and the encoders over long ones — and is computationally trivial, but it carries no model of how confident either sensor is at a given instant [2.2.7]. The Extended Kalman Filter maintains an explicit state vector, typically [x, y, ψ, V_x, V_y, V_ω] for a planar robot, and alternates prediction against a motion model with correction against incoming measurements, weighting each by its covariance [2.2.5]. The Unscented Kalman Filter replaces the EKF's analytic linearization with sigma-point propagation, avoiding Jacobian computation and handling strong nonlinearity more gracefully at higher computational cost [2.2.8]. Visual-inertial odometry fuses camera imagery with IMU data to produce a drift-rate substantially lower than wheel-inertial fusion, but consumes GPU resources and degrades in low-texture or poorly lit scenes [2.2.9].

The `robot_localization` package provides configurable ROS2 implementations of both the EKF and the UKF, including a `two_d_mode` that constrains the state to planar motion and zeroes the out-of-plane terms [2.2.6]. In a typical differential-drive configuration, encoder velocities enter as one measurement source and IMU angular velocity as another; IMU-derived absolute yaw is normally excluded when no magnetometer is present, because integrated gyroscope heading drifts independently of the filter state and fusing it injects that drift into the estimate.

**Table 2.2a** — Odometry and sensor-fusion approaches for a planar differential-drive platform.

| Approach | Sensors fused | Drift behaviour | Relative compute | ROS2 implementation | Documented limitation |
|---|---|---|:---:|---|---|
| Encoder dead reckoning | Encoders only | Unbounded; grows with distance and with every slip event | Negligible | `diff_drive_controller` | Observes wheel rotation, not displacement; slip is invisible |
| Complementary filter | Encoders + IMU gyro | Bounded short-term heading; long-term drift persists | Very low | `imu_complementary_filter` | Fixed gain; no covariance model, so sensor confidence cannot vary with conditions |
| Extended Kalman Filter | Encoders + IMU (+ optional GNSS, visual) | Reduced heading drift; position drift bounded only by external correction | Low–moderate | `robot_localization` (`ekf_node`) | Requires covariance tuning; linearization error grows under aggressive manoeuvres |
| Unscented Kalman Filter | Same as EKF | Comparable to EKF for planar motion | Moderate | `robot_localization` (`ukf_node`) | Higher cost for marginal benefit when motion is close to linear |
| Visual-inertial odometry | Camera + IMU | Lowest drift rate of the four | High (GPU) | `rtabmap_odom`, VINS-family | Requires texture and stable lighting; competes for GPU with other edge workloads |

No proprioceptive method is drift-free, and the differences among these approaches are differences in how quickly drift accumulates rather than in whether it does. That reframes what separates them. An odometry estimate in a system that also carries a map and a docking marker is not required to be globally accurate — only accurate enough between the external corrections those two supply, the map bounding drift over a service cycle (§2.2.2) and the marker bounding it at the point where precision is actually needed (§2.2.4). What the approaches in Table 2.2a differ in, then, is chiefly what they cost to obtain that local accuracy: in computation, in the sensing they require, and in the tuning each demands before it performs as documented.

---

### 2.2.2 SLAM, Map Building, and Localization

Simultaneous Localization and Mapping addresses a circular dependency: localizing requires a map, and building a map requires knowing where the robot is [2.2.10]. Modern systems separate a front end, which processes sensor data and aligns consecutive observations, from a back end, which optimizes a graph of poses subject to constraints and detects loop closures — revisits to previously mapped locations that allow accumulated drift to be redistributed across the whole trajectory.

A 2D LiDAR such as the RPLiDAR A2M8 produces a planar scan of range measurements at fixed angular resolution, typically several hundred points per revolution at 5–10 Hz [2.2.11]. Consecutive scans are aligned by scan matching, most commonly a variant of Iterative Closest Point, which recovers the rigid transform minimizing the distance between corresponding points [2.2.13]. Accumulated scans populate an occupancy grid. LiDAR mapping is insensitive to illumination and geometrically accurate within the scan plane, but scan matching becomes ill-conditioned wherever geometry repeats: a long corridor with parallel walls, or a room of regularly spaced tables and chairs, produces scans that are nearly identical at locations that are metrically distinct.

An RGB-D camera such as the Intel RealSense D435 supplies registered colour and depth imagery at 30 Hz [2.2.12]. Its contribution to mapping is less about geometry — the LiDAR is more accurate in-plane — than about *place recognition*. Visual features quantized into a bag-of-words vocabulary allow a system to recognize a previously visited location from appearance alone, independently of the current pose estimate and independently of whether the local geometry is ambiguous [2.2.19]. Where LiDAR scan correlation cannot distinguish two structurally identical locations, image texture usually can.

Five SLAM implementations are available for ROS2 and span this design space. GMapping applies a Rao-Blackwellized particle filter to 2D laser data and was the ROS1 default; it has no explicit loop-closure mechanism and its ROS2 support is community-maintained rather than official [2.2.14]. Hector SLAM performs scan matching without requiring odometry, which suits platforms lacking encoders, but likewise offers no loop closure and drifts in featureless environments [2.2.15]. Cartographer introduced submap-based graph SLAM with branch-and-bound scan matching for loop-closure search and remains a strong 2D and 3D system, though its ROS2 maintenance has lagged the core stack [2.2.16]. SLAM Toolbox is the ROS2 tier-one 2D solution, implementing a pose graph optimized with Ceres, with loop closure detected by scan correlation and maps serialized as pose graphs [2.2.17]. RTAB-Map performs graph SLAM over both LiDAR and RGB-D input, detects loop closures through visual bag-of-words in addition to LiDAR spatial proximity, optimizes with g²o or GTSAM, and manages memory through a working-memory / long-term-memory partition that keeps real-time performance bounded as the map grows [2.2.18], [2.2.20].

**Table 2.2b** — 2D SLAM implementations available for ROS2.

| System | Sensors | Formulation | Loop-closure cue | Map storage | Behaviour in repetitive geometry |
|---|---|---|---|---|---|
| GMapping | 2D LiDAR | Rao-Blackwellized particle filter | None explicit | Occupancy grid | Degrades; no mechanism to correct a mistaken revisit |
| Hector SLAM | 2D LiDAR (no odometry required) | Scan matching only | None | Occupancy grid | Drifts without bound in featureless corridors |
| Cartographer | 2D/3D LiDAR (+ IMU) | Submap graph SLAM | Branch-and-bound scan matching | Submap serialization | Better than correlation alone, still geometry-only |
| SLAM Toolbox | 2D LiDAR | Pose graph, Ceres optimizer | Scan correlation | Serialized pose graph | Ambiguous where scans repeat at distinct locations |
| RTAB-Map | 2D LiDAR **+ RGB-D** | Graph SLAM, g²o/GTSAM | **Visual bag-of-words** + LiDAR proximity | SQLite database | Appearance resolves locations that geometry cannot |

Once a map exists, operation shifts from building it to localizing within it, and the same distinction between geometric and appearance-based place recognition reappears. Adaptive Monte Carlo Localization maintains a particle distribution over poses, weighting particles by the agreement between the expected and observed laser scan, and is the long-standing ROS default paired with a static map served from a `.pgm` and `.yaml` pair [2.2.26]. Its failure mode is the one the geometry predicts: in a symmetric or repetitive environment, the particle cloud can converge confidently on the wrong hypothesis, and recovery requires redistributing particles globally. RTAB-Map can instead run in a localization mode that holds the stored graph fixed and relocalizes against it using the same visual and geometric matching used during mapping, which permits global relocalization from an arbitrary starting pose.

**Table 2.2c** — Localization against a prior map.

| Approach | Algorithm | Sensors | Map source | Behaviour in symmetric geometry | Recovery when lost |
|---|---|---|---|---|---|
| Odometry only | Dead reckoning | Encoders (+ IMU) | None | n/a — no map reference | None; error is permanent |
| AMCL | Monte Carlo particle filter | 2D LiDAR | `.pgm` + `.yaml` via `map_server` | Prone to confident false convergence where scans repeat | Global particle redistribution |
| RTAB-Map localization mode | Graph matching + visual bag-of-words | 2D LiDAR + RGB-D | `rtabmap.db`; publishes `/map` directly | Visual appearance separates geometrically identical places | Global visual relocalization |

**[Figure 2.2a — Why geometric place recognition fails in a dining room: two laser scans captured at metrically distinct locations in a regularly spaced table layout, shown overlaid to illustrate that scan correlation cannot separate them, alongside the corresponding camera images, which differ clearly in texture.]**

The discriminating condition for a restaurant is the one both tables converge on. A dining room is close to the worst case for purely geometric place recognition: tables and chairs form repeating clusters, walls are long and featureless, and the service lane presents the same profile at many points along its length. Where these systems divide is therefore not in metric mapping accuracy, on which they are broadly comparable, but in whether they carry a second and non-geometric cue for recognising a place — and, having lost track of where they are, whether they can recover without a person supplying an initial pose. The published evaluations are drawn largely from office corridors, warehouse aisles, and outdoor campuses; none characterises the repeating-cluster geometry that a dining room presents, which is precisely the condition under which the two cues diverge.

---

### 2.2.3 Autonomous Navigation

With a map and a pose within it, the navigation stack must convert a goal pose into wheel velocities. Navigation2 is the standard ROS2 framework for this and decomposes the problem into a global planner, a local controller, a costmap layer, and a behaviour tree that orchestrates the lifecycle and its recoveries [2.2.21].

The global planner searches the static costmap — the occupancy grid inflated by the robot's footprint — for a path minimizing a cost that penalizes both length and obstacle proximity. NavFn computes a Dijkstra or A* solution over a potential field and is fast and robust, but produces paths without regard to kinematic feasibility; for a differential-drive robot this is acceptable, because the platform can rotate in place to acquire any required heading. The Smac family adds planners that respect kinematic constraints — a hybrid-A* variant producing smooth, drivable paths for car-like platforms, and a state-lattice variant for arbitrary motion primitives — at a cost in planning time that is only repaid when the platform genuinely cannot turn in place.

The local controller executes the global path by emitting velocity commands at control rate. The Dynamic Window Approach samples candidate velocity pairs within the platform's kinematic limits and scores each against a weighted set of critics — progress toward the goal, clearance from obstacles, alignment with the path, and forward speed — selecting the best-scoring command [2.2.22]. The Timed Elastic Band formulates trajectory following as an optimization over a time-parameterized sequence of poses, supporting car-like kinematics and explicit time-optimality at the cost of a substantially larger parameter set [2.2.23]. Regulated Pure Pursuit follows the path geometrically, regulating linear speed by path curvature and obstacle proximity; it has few parameters and predictable behaviour, which makes it well suited to constrained environments where the path is known to be collision-free by construction [2.2.24].

**Table 2.2d** — Nav2 global planners and local controllers.

| Component | Method | Kinematic model | Suits non-holonomic TWD | Tuning burden |
|---|---|---|:---:|---|
| NavFn (global) | Dijkstra / A* on potential field | Holonomic path, heading acquired by rotation | ✓ (rotation in place is available) | Low |
| Smac Hybrid-A* (global) | Kinematically feasible A* | Ackermann / car-like | Unnecessary — no turning-radius constraint | Moderate |
| Smac State Lattice (global) | Search over motion primitives | Arbitrary, primitive-defined | Unnecessary at this scale | High |
| DWB (local) | Velocity sampling with weighted critics | Differential drive native; V_y constrained to 0 | ✓ | Moderate — critic weights |
| TEB (local) | Time-parameterized trajectory optimization | Differential and car-like | ✓, but over-specified | High — large parameter set |
| Regulated Pure Pursuit (local) | Geometric path following, curvature-regulated | Differential drive | ✓ | Low |

A two-wheel differential-drive platform is non-holonomic: lateral velocity is structurally zero, and every lateral correction decomposes into a rotation followed by a translation. This constrains the controller — only velocity pairs satisfying the differential-drive model may be sampled — but it also *relaxes* the global planner's requirements, since a platform that can rotate in place does not need a planner that respects a minimum turning radius. Around both, Nav2's behaviour tree sequences the navigation lifecycle and its recoveries: when progress stalls, it triggers a clearing rotation, then a larger in-place rotation, then a full replan, and finally aborts and reports failure [2.2.25]. That final step is worth noting, because it is the only point at which the stack admits it cannot proceed — and what it does with that admission is emit a status, leaving the question of what should happen next entirely outside the navigation system.

**[Figure 2.2b — The navigation stack and its goal interface: sensing feeds odometry fusion, which feeds SLAM and localization, which feed the global planner, local controller, and behaviour tree. The goal source sits above the stack, outside it. In prior work this input is a human operator; the coupling this thesis proposes replaces it with an AI agent emitting goals as side effects of restaurant business events.]**

What the surveyed work does not provide is the interface above the stack. In every academic deployment reviewed, the goal is operator-initiated: a human selects a waypoint on a map, or a hard-coded sequence steps through a fixed tour, and Nav2 executes it [2.2.19]. Reported navigation success rates above 90% in controlled indoor environments describe the quality of that execution, not the origin of the goal. Coupling the goal interface to a non-human source raises requirements that operator-driven navigation never encounters: goals arrive asynchronously as side effects of business events rather than at moments a human chooses; a goal may need to preempt one already in flight when a higher-priority delivery is dispatched; the goal carries business context — which order, which session — that must survive the round trip and be reported back on arrival; and a navigation failure must surface as a recoverable task state rather than as a message on an operator's screen. No prior work reviewed here connects Nav2 to a goal source with these properties; the coupling proposed in §3.7 is designed to satisfy them.

---

### 2.2.4 Fiducial Marker Docking

Localization against a SLAM map carries residual error — map discretization, accumulated odometry drift between corrections, and the localization filter's own uncertainty combine to produce a pose estimate that may be off by several centimetres even under good conditions. For most of a delivery this is irrelevant. It becomes relevant at the final approach, where a lateral offset means the robot does not square up to the table and the customer must reach awkwardly across the tray. A fiducial marker — a visual pattern of known geometry and known position — provides an absolute local reference at exactly the point where the requirement is tightest.

A square fiducial encodes an integer identifier in a binary grid bordered by a black frame. Detection proceeds by extracting candidate contours from the image, rectifying each to a frontal square, and decoding the interior bit pattern against a dictionary; a marker whose decoded pattern is not a dictionary member is rejected, which suppresses false positives from incidental rectangular structure in the scene. Because the marker's physical side length is known, its four detected corners give four 3D–2D correspondences, and Perspective-n-Point estimation recovers the full six-degree-of-freedom transform between camera and marker [2.2.31]. The solution is well conditioned when the marker subtends a sufficient portion of the image and degrades as the marker becomes small, oblique, or motion-blurred.

**[Figure 2.2c — Perspective-n-Point pose estimation from a square fiducial: the four detected marker corners in the image plane, their known 3D coordinates in the marker frame, and the recovered six-degree-of-freedom camera-to-marker transform, with coordinate axes annotated.]**

Four marker families appear in the robotics literature. ArUco provides configurable dictionaries with selectable size and inter-marker Hamming distance and ships within OpenCV, which makes it the most widely available option in ROS2 [2.2.27]. AprilTag uses a lexicographic coding system engineered for a low false-positive rate and detects reliably at greater range and steeper viewing angles, at higher detector cost [2.2.28]. ARTag established much of the approach but has been largely superseded [2.2.29]. STag adds an elliptical refinement stage that stabilizes the recovered pose under oblique views, with a correspondingly smaller ecosystem [2.2.30]. ChArUco interleaves a chessboard with ArUco markers so that saddle-point corners can be refined to sub-pixel accuracy, yielding the most accurate pose of the group but requiring a physically larger target than a table-mounted marker practically allows.

**Table 2.2e** — Square fiducial marker families.

| Family | Coding | Pose accuracy | Range / oblique robustness | Occlusion tolerance | ROS2 availability |
|---|---|:---:|:---:|:---:|---|
| ArUco | Configurable dictionary, Hamming-separated | Good | Moderate | Low — a lost corner defeats detection | Native in OpenCV; several wrappers |
| AprilTag | Lexicographic, low false-positive rate | Good | **High** | Low | `apriltag_ros`, actively maintained |
| ARTag | Forward error correction | Moderate | Moderate | Low | Largely superseded |
| STag | Elliptical refinement stage | **High** under oblique views | High | Low | Limited ecosystem |
| ChArUco | Chessboard + ArUco hybrid | **Highest** (sub-pixel corners) | Moderate | Moderate — partial board still usable | Native in OpenCV |

What separates these families in the published comparisons — detection range, robustness at steep viewing angles, resistance to false positives across large dictionaries — is largely exercised at the margins of their operating envelope. A marker mounted at a known table, observed from roughly one metre at near-frontal incidence, sits well inside that envelope for every family listed. The dimensions on which the literature most sharply distinguishes these systems are therefore not the dimensions on which a short, frontal, indoor docking approach depends. What such an approach does depend on — how a detector behaves when the marker is absent, partially occluded, or motion-blurred, and whether that condition is reported distinguishably from a successful detection rather than as a low-confidence pose — is not a dimension the comparative literature reports at all.

Prior work using these markers treats each one as a geometric target: a pose in space that the robot must reach, whether a charging dock or a delivery drop-off point. In a restaurant, a marker carries an identity in the business domain as well as a pose. Marker 5 is not merely a docking pose; it is table B3, currently occupied by an active session, which has an outstanding order. A pose correction alone does not establish that the food on the tray belongs to the party at the table now in front of the robot. Making that check possible requires the marker identifier to be resolvable by the backend at docking time — marker to table to session to order — so that arrival triggers a verification and not only a geometric correction. No prior system reviewed binds fiducial markers to business entities in this way; the docking design in §3.6 does so.

---

### 2.2.5 Prior ROS2 Delivery Robot Research

Academic projects have demonstrated ROS2 delivery robots across several service contexts — campus cafeteria food delivery, hospital ward medication transport, and office document delivery [2.2.32]–[2.2.34]. The hardware convergence is striking: 2D LiDAR, RGB-D camera, IMU, and wheel encoders, on a differential-drive or mecanum base. The software convergence is equally strong: a SLAM package for mapping, Nav2 for planning and control, and fiducial markers for terminal precision. These systems establish that autonomous indoor delivery is achievable with open components, reporting navigation success rates above 90% in controlled environments.

**Table 2.2f** — Prior ROS2 delivery robot systems, by the two dimensions that distinguish them from the system proposed here.

| System class | Typical sensing | Mapping / navigation | Terminal precision | **Goal source** | **Conversational interaction** |
|---|---|---|---|---|:---:|
| Campus cafeteria delivery [2.2.32] | 2D LiDAR + RGB-D + IMU | Cartographer or RTAB-Map → Nav2 | Fiducial marker | Operator selects destination | ✗ |
| Hospital medication transport [2.2.33] | 2D LiDAR + RGB-D + IMU | SLAM → Nav2, fixed ward waypoints | Fiducial marker or manual handover | Fixed route or operator | ✗ |
| Office document delivery [2.2.34] | 2D LiDAR + IMU | SLAM → Nav2 | Fiducial marker | Fixed tour sequence | ✗ |
| Commercial service robots (§2.1) | LiDAR + RGB-D | Proprietary SLAM + planner | Proprietary | Touchscreen, selected by staff | ✗ (pre-recorded greeting only) |
| **This work** | 2D LiDAR + RGB-D + IMU | RTAB-Map → Nav2 | Fiducial marker, business-verified | **AI agent, from live restaurant events** | **✓** |

Read across the two rightmost columns, the pattern is uniform. In every case the destination is chosen by a person — an operator selecting on a screen, a technician defining a tour, a member of staff pressing a table number — and in no case does the robot take any part in the exchange that produced the delivery. The robot drives to a table and stops. It cannot take an order, answer a question about a dish, confirm a selection, or accept payment. The navigation problem in these systems is solved; the interaction problem is not addressed, and consequently the question of where navigation goals should come from has never had to be asked.

---

Across the surveyed work these four capabilities compose into a functioning delivery robot, and the reported navigation success rates confirm that the composition is reliable. It holds together, however, on an assumption that is never stated because in an operator-driven system it requires no defence: that the entity deciding where the robot should go is a human being.

That assumption shapes every interface at the top of the stack. A goal is something a person supplies at a moment of their own choosing, so no provision exists for one arriving asynchronously, preempting another already in flight, or carrying a business context that must be returned on arrival. A marker is something a person has already reasoned about before dispatching the robot, so the marker itself carries no business meaning and needs none. A navigation failure is something a person observes and resolves, so it surfaces as a message on a screen rather than as state that another component could act upon.

Substituting an autonomous agent for the operator invalidates all three premises simultaneously. The requirements that follow — goals that arrive asynchronously, preempt, and carry order and session context; markers that resolve to business entities at docking time; failures that surface as reassignable task state — have not been addressed in combination by any system reviewed here.
