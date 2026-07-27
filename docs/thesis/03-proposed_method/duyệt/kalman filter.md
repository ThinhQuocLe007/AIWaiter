# CHAPTER 3 — PROPOSED METHOD (I): ROBOT CONTROL AND NAVIGATION ON ROS2
*(Report content — the actual text to put in the thesis. Writing notes live in `thesis-writing.md`.)*

> **Report-style, impersonal** (no "the group" / "we"). This chapter is algorithm and configuration only. The physical build, the ROS2 robot model (URDF, TF tree, node/topic graph), the numeric platform constants, and the simulation runs are presented in Chapter 5. Method equations here use symbols; their measured values are reported in the implementation section of Chapter 5.

This chapter presents the control and navigation method of the robot on ROS2: estimating the robot's own motion by fusing the wheel encoders with the IMU, building and reusing a two-dimensional map of the service area, localizing the robot and refining its stop with a fixed visual marker, and driving it autonomously along a dedicated service lane from the kitchen to any table. The robot operates on a service lane that is physically separated from the customer area, so its environment contains no pedestrians; only occasional objects that accidentally enter the lane must be handled. The map used throughout is two-dimensional. The chapter opens with the system requirements, then follows the data as it flows from the wheels and the IMU up to a navigation goal.

---

## 3.1 System Requirements

- Map building: A 2D map of the service area must be built by fusing several onboard sensors — the LiDAR, the RGB-D camera, the IMU, and the wheel encoders — through a SLAM pipeline, so that the resulting map is accurate and consistent enough to be reused for localization and navigation.
- Localization and navigation: On the built map, the robot must localize itself reliably and drive autonomously along the service lane from the kitchen to any requested table. It must also detect and safely avoid dynamic objects that unexpectedly enter the lane.
- Precision docking: On arrival at the kitchen station and at each table, the robot must refine its pose against a fixed ArUco marker to achieve an accurate and repeatable final stop.
- Safety and operating constraints: The robot must operate on flat indoor floor within the dedicated lane, keep a safe distance from obstacles, and stop safely whenever the lane is blocked or a target marker cannot be found.

---

## 3.2 Encoder–IMU Sensor Fusion with an Extended Kalman Filter

### 3.2.1 Wheel Odometry from the Encoders

Each driven wheel carries a Hall-effect quadrature encoder. As a wheel turns, its encoder emits pulses on two offset channels; counting the pulses gives the amount of rotation, and the ordering of the two channels gives its direction. The number of counts produced per full revolution of the wheel is

$$
N = P \cdot 4 \cdot G,
$$

where $P$ is the encoder resolution in pulses per revolution, the factor $4$ comes from quadrature decoding (both edges of both channels are counted), and $G$ is the gear ratio between the encoder shaft and the wheel.

One count therefore corresponds to a fixed arc length at the wheel rim, $d_{\text{tick}} = \pi D / N$, where $N$ is the counts-per-wheel-revolution defined above and $D$ is the wheel diameter, so that if a wheel produces $\Delta n$ counts in a time interval $\Delta t$, its linear speed is

$$
V = \frac{\pi D}{N} \cdot \frac{\Delta n}{\Delta t}.
$$

Applying this to each wheel gives the two wheel speeds $V_A$ and $V_B$. The forward kinematics of the differential drive derived in Section 2.2 then convert them into the body-frame velocities of the robot,

$$
V_x = \frac{V_A + V_B}{2}, \qquad V_y = 0, \qquad V_\omega = \frac{V_B - V_A}{W},
$$

where $V_y = 0$ is the non-holonomic constraint of the two-wheel drive and the yaw rate is the wheel-speed difference divided by the wheel track $W$. These three quantities form the wheel-odometry measurement supplied to the filter,

$$
\mathbf{z}_{\text{odom}} =
\begin{bmatrix}
V_x \\
V_y \\
V_\omega
\end{bmatrix}
=
\begin{bmatrix}
\frac{V_A + V_B}{2} \\
0 \\
\frac{V_B - V_A}{W}
\end{bmatrix}.
$$

Integrated on its own over an Euler step $\Delta t$, this velocity yields a pose $(x, y, \psi)$,

$$
\begin{aligned}
x &\leftarrow x + V_x \cos\psi \, \Delta t, \\
y &\leftarrow y + V_x \sin\psi \, \Delta t, \\
\psi &\leftarrow \psi + V_\omega \, \Delta t,
\end{aligned}
$$

with the heading wrapped to $(-\pi, \pi]$ by $\psi \leftarrow \operatorname{atan2}(\sin\psi, \cos\psi)$. This integrated pose is the raw wheel-odometry estimate; it is reported for reference but, as explained below, only the velocity $\mathbf{z}_{\text{odom}}$ is fused, since integrated wheel pose accumulates drift. The time-critical part of this computation — counting pulses, scaling them into wheel speeds, and running the kinematics and the motor loop at a fixed rate — is performed by the STM32 microcontroller on the base and transmitted over a serial link; the ROS2 driver on the onboard computer converts the values to SI units and publishes the odometry message. The encoder resolution, gear ratio, wheel diameter, and wheel track are fixed parameters of the base platform and are summarized in Chapter 5; this work uses them as given and builds the estimation and navigation stack on top from ROS2 upward.

Wheel odometry alone drifts, chiefly from wheel slip and small errors in the assumed wheel geometry, and because it only ever adds new motion onto the previous estimate it cannot correct a past mistake. The heading in particular accumulates error over repeated turns. For this reason the wheel odometry is fused with the IMU rather than used on its own.

### 3.2.2 IMU Measurement Model

The IMU is a six-axis MPU6050, combining a three-axis gyroscope and a three-axis accelerometer. Both sensors output their readings in the robot body frame as raw 16-bit signed integers, and the chip has no magnetometer, so it provides no absolute heading.

The gyroscope measures the body's angular velocity about the three body axes,

$$
\boldsymbol{\omega}_B = \big[\, \omega_x,\; \omega_y,\; \omega_z \,\big]^{\mathsf T},
$$

where $\omega_x$, $\omega_y$, and $\omega_z$ are the angular velocities about the body `x`, `y`, and `z` axes — that is, the roll, pitch, and yaw rates. Each component is delivered as a raw integer and converted to physical units by a fixed scale factor,

$$
\omega = s_g \, \omega_{\text{raw}}, \qquad s_g = \frac{\Omega_{\max}}{2^{15}},
$$

where $\omega$ is the angular velocity in rad/s, $\omega_{\text{raw}}$ the raw integer reading, $s_g$ the gyroscope scale factor, $\Omega_{\max}$ the configured full-scale range of the gyroscope, and $2^{15}$ the magnitude of the signed 16-bit range over which the raw integer is spread.

The accelerometer measures the body's linear acceleration along the three body axes,

$$
\mathbf{a}_B = \big[\, a_x,\; a_y,\; a_z \,\big]^{\mathsf T},
$$

where $a_x$, $a_y$, and $a_z$ are the accelerations along the body `x`, `y`, and `z` axes. Each component is converted in the same way by its own scale factor,

$$
a = s_a \, a_{\text{raw}}, \qquad s_a = \frac{A_{\max}}{2^{15}},
$$

where $a$ is the acceleration in m/s², $a_{\text{raw}}$ the raw integer reading, $s_a$ the accelerometer scale factor, and $A_{\max}$ the configured full-scale range of the accelerometer.

On the robot, the MPU6050 is configured with a full-scale range of $A_{\max} = \pm 2\,g$ for the accelerometer and $\Omega_{\max} = \pm 500\,^\circ/\text{s}$ for the gyroscope; the resulting numeric scale factors are reported in Chapter 5. Its raw axes are remapped to the ROS body convention (forward `x`, left `y`, up `z`) by a fixed permutation and sign change in the base firmware.

Even at rest the gyroscope reports a small constant offset, or bias, on its vertical axis, which would otherwise integrate into a growing heading error. This bias is estimated by averaging $M$ vertical-axis samples taken while the robot is stationary,

$$
b_g = \frac{1}{M}\sum_{k=1}^{M}\omega_{z,k},
$$

where $b_g$ is the estimated bias, $M$ the number of stationary samples, and $\omega_{z,k}$ the $k$-th vertical-axis reading. Subtracting the bias gives the yaw-rate measurement used by the filter,

$$
V_\omega = \omega_z - b_g + n_\omega,
$$

where $\omega_z$ is the raw vertical-axis angular velocity, $n_\omega$ the gyroscope measurement noise, and $V_\omega$ the resulting yaw-rate measurement. This $V_\omega$ is the same physical quantity — the robot's turning rate about its vertical axis — as the $V_\omega$ of the kinematic model in Section 2.2, but the two sensors obtain it in different ways: the IMU measures the yaw rate directly with its gyroscope, whereas the wheel odometry of Section 3.2.1 infers the same rate indirectly from the difference of the two wheel speeds. Having two independent measurements of one yaw rate is precisely what makes the sources complementary, and they are combined in the sensor fusion of Section 3.2.3 to yield a more accurate and drift-resistant estimate. This yaw rate is the only quantity taken from the IMU. The accelerometer reading is converted and available but is not used in the encoder–IMU fusion; the robot's absolute heading is instead anchored by the map-based localization of Section 3.4.

### 3.2.3 Fusion with the Extended Kalman Filter

The wheel odometry (Section 3.2.1) gives accurate translation but drifts with slip; the IMU (Section 3.2.2) gives a clean, slip-independent yaw rate but no absolute reference. Fusing them well requires more than averaging their outputs — an estimator must carry a state together with a measure of how uncertain that estimate is, and revise both whenever a new reading arrives. The Kalman filter, and its non-linear extension the Extended Kalman Filter (EKF), provide exactly this recursive machinery. Both are presented below in general form first, and then applied to this robot.

**Idea.** The Kalman filter is a recursive estimator that combines several uncertain sources into one more certain estimate of a system's state. It represents its knowledge at each step $k$ as a **Gaussian**, summarized by a best estimate $\hat{\mathbf{x}}_k$ (the mean) and a covariance $\mathbf{P}_k$ (the uncertainty; off-diagonal entries record correlations between state variables, so one measurement also sharpens the others). The filter works in **two stages**: a **prediction** step, which projects the estimate forward with a motion model, and an **update** step, which corrects that prediction with each sensor reading, leaning toward whichever is currently more certain.

**Prediction.** The prediction step projects the current estimate one time step forward using only the motion model, before any new sensor reading is taken into account. It answers, from what was known at step $k-1$, where the system should be at step $k$ and how much certainty is lost along the way.

The first equation predicts the **state**:

$$
\hat{\mathbf{x}}_k = \mathbf{F}_k\,\hat{\mathbf{x}}_{k-1} + \mathbf{B}_k\,\vec{\mathbf{u}}_k
$$

The second predicts the **covariance**:

$$
\mathbf{P}_k = \mathbf{F}_k\,\mathbf{P}_{k-1}\,\mathbf{F}_k^{\mathsf T} + \mathbf{Q}_k
$$

Where:

- $\hat{\mathbf{x}}_k$, $\mathbf{P}_k$ are the predicted estimate and its covariance
- $\mathbf{F}_k$ is the state-transition matrix (the motion model); applied to the covariance as $\mathbf{F}_k\mathbf{P}_{k-1}\mathbf{F}_k^{\mathsf T}$ it propagates the uncertainty the same way
- $\mathbf{B}_k$, $\vec{\mathbf{u}}_k$ are the control matrix and control vector, adding any known external command
- $\mathbf{Q}_k$ is the process-noise covariance, the uncertainty for everything the model misses

Because no measurement is used, the prediction is necessarily less certain than the estimate it came from — which is why $\mathbf{Q}_k$ is added, not subtracted.

**Update.** The update step corrects the prediction each time a sensor reading arrives, blending model and measurement into a single, sharper estimate. It pulls the drifting prediction back toward reality using the information the sensor actually provides.

The first equation corrects the **state**, nudging the prediction toward the reading:

$$
\hat{\mathbf{x}}'_k = \hat{\mathbf{x}}_k + \mathbf{K}'\big(\vec{\mathbf{z}}_k - \mathbf{H}_k\,\hat{\mathbf{x}}_k\big)
$$

The second corrects the **covariance**, shrinking it because the measurement removes uncertainty:

$$
\mathbf{P}'_k = \mathbf{P}_k - \mathbf{K}'\,\mathbf{H}_k\,\mathbf{P}_k
$$

The third is the **Kalman gain**, the weight used in the two equations above:

$$
\mathbf{K}' = \mathbf{P}_k\,\mathbf{H}_k^{\mathsf T}\big(\mathbf{H}_k\,\mathbf{P}_k\,\mathbf{H}_k^{\mathsf T} + \mathbf{R}_k\big)^{-1}
$$

Where:

- $\hat{\mathbf{x}}'_k$, $\mathbf{P}'_k$ are the corrected estimate and its covariance, fed back into the next round. The prime ($'$) marks an **updated** (post-measurement) value, as opposed to the unprimed **predicted** value $\hat{\mathbf{x}}_k$, $\mathbf{P}_k$ from the prediction step
- $\mathbf{H}_k$ is the observation matrix, mapping the state into what the sensor should read
- $\vec{\mathbf{z}}_k$ is the measurement; $\mathbf{R}_k$ is the measurement-noise covariance (small = trusted sensor)
- $\vec{\mathbf{z}}_k - \mathbf{H}_k\hat{\mathbf{x}}_k$ is the innovation, the difference between the reading and what was expected
- $\mathbf{K}'$ is the Kalman gain, deciding how much of the innovation to apply

In one dimension the gain is $K = p_k/(p_k+r_k)$, between $0$ and $1$: a precise sensor ($r_k$ small) gives $K\to 1$ (follow the reading), a noisy one gives $K\to 0$ (ignore it). $\mathbf{P}'_k$ shrinks because the measurement removes uncertainty.

**From the Kalman filter to the EKF.** The linear filter above assumes both models are matrices. Many real systems do not fit that template: whenever a process or measurement genuinely depends on a product of state variables, a trigonometric function of the state, or some other curved relationship, no constant matrix can describe it exactly. The **Extended Kalman Filter (EKF)** keeps the same predict–update loop but replaces the two model matrices with non-linear functions: a process model $\mathbf{f}$ in place of $\mathbf{F}_k\hat{\mathbf{x}}_{k-1}$, and a measurement model $\mathbf{h}$ in place of $\mathbf{H}_k\hat{\mathbf{x}}_k$. The process and measurement noise are still described by $\mathbf{Q}_k$ and $\mathbf{R}_k$, exactly as in the linear filter.

A covariance cannot be pushed through a non-linear function directly, so the EKF linearizes: it expands each function in a **Taylor series** around the current estimate, keeps only the first-order term, and drops the rest — replacing the curved function locally by its tangent. The slope of that tangent is the **Jacobian**, the matrix of first partial derivatives.

The first Jacobian linearizes the **process model**:

$$
\mathbf{F}_k = \left.\frac{\partial \mathbf{f}}{\partial \mathbf{x}}\right|_{\hat{\mathbf{x}}'_{k-1}}
$$

The second linearizes the **measurement model**:

$$
\mathbf{H}_k = \left.\frac{\partial \mathbf{h}}{\partial \mathbf{x}}\right|_{\hat{\mathbf{x}}_k}
$$

Where:

- each entry is a partial derivative, $\partial f_a/\partial x_b$ for $\mathbf{F}_k$ and $\partial h_a/\partial x_b$ for $\mathbf{H}_k$
- $\mathbf{F}_k$ is evaluated at $\hat{\mathbf{x}}'_{k-1}$, the previous step's updated estimate (the point the process model starts from)
- $\mathbf{H}_k$ is evaluated at the current predicted estimate $\hat{\mathbf{x}}_k$ (where the measurement is compared)

$\mathbf{f}$ and $\mathbf{h}$ are never replaced by their Jacobians — the state prediction and the innovation always call them directly. $\mathbf{F}_k$ and $\mathbf{H}_k$ are separate, auxiliary matrices used only to propagate the covariance and form the Kalman gain, replacing the constant matrices of the linear filter in those two roles.

**EKF algorithm.** Initialized with $\hat{\mathbf{x}}_0$, $\mathbf{P}_0$, the full cycle repeats at each step $k$.

*Predict* — the first equation predicts the **state**, the second the **covariance**:

$$
\hat{\mathbf{x}}_k = \mathbf{f}(\hat{\mathbf{x}}'_{k-1}, \Delta t)
$$

$$
\mathbf{P}_k = \mathbf{F}_k\,\mathbf{P}'_{k-1}\,\mathbf{F}_k^{\mathsf T} + \mathbf{Q}_k
$$

*Update* — the first equation is the **Kalman gain**, the second corrects the **state**, and the third corrects the **covariance**:

$$
\mathbf{K}' = \mathbf{P}_k\,\mathbf{H}_k^{\mathsf T}\big(\mathbf{H}_k\,\mathbf{P}_k\,\mathbf{H}_k^{\mathsf T} + \mathbf{R}_k\big)^{-1}
$$

$$
\hat{\mathbf{x}}'_k = \hat{\mathbf{x}}_k + \mathbf{K}'\big(\vec{\mathbf{z}}_k - \mathbf{h}(\hat{\mathbf{x}}_k)\big)
$$

$$
\mathbf{P}'_k = \mathbf{P}_k - \mathbf{K}'\,\mathbf{H}_k\,\mathbf{P}_k
$$

The result $\hat{\mathbf{x}}'_k$, $\mathbf{P}'_k$ feeds back into the next step, and the cycle repeats. (Bold $\mathbf{x}$ denotes the state vector; italic $x$ denotes its position component, once the robot's specific state is defined below.)

**Applying the EKF to this robot.** The robot is a two-wheel differential-drive (TWD) platform, equipped with a LiDAR, an RGB-D camera, a six-axis IMU, and a Hall-effect quadrature encoder on each driven wheel. This stage fuses only two of these sensors — the **wheel encoders** (Section 3.2.1) and the **IMU** (Section 3.2.2) — into a single, smooth estimate of the robot's own motion, the *fused odometry*; the LiDAR and camera are reserved for mapping and localization in Sections 3.3–3.4. The fusion is not hand-written: it is carried out by an Extended Kalman Filter, the `ekf_filter_node` of the ROS2 `robot_localization` package, which runs exactly the predict–update algorithm above. The node is configured entirely through a parameter file (`ekf.yaml`) rather than through code, and its output is the filtered odometry together with the `odom → base_footprint` transform that mapping, localization, and navigation all consume.

The settings in that file that fix the shape of the estimation problem are collected in Table 3.1.

**Table 3.1 — Key `ekf.yaml` settings and their role in the filter.**

| Parameter | Value | Role |
|---|---|---|
| `two_d_mode` | `true` | Planar estimate only; height, roll, pitch held at zero. |
| `frequency` | `50.0` Hz | Predict–update rate, matched to the 50 Hz firmware loop. |
| `world_frame` / `base_link_frame` | `odom` / `base_footprint` | Local odometry instance; publishes `odom → base_footprint` TF. |
| `odom0` + `odom0_config` | `odom`; $V_x, V_y, V_\omega$ | Wheel odometry supplies the three body-frame velocities. |
| `imu0` + `imu0_config` | `imu`; $V_\omega$ only | Only yaw rate is used, because orientation has no magnetometer to bound its drift. |
| `publish_acceleration` | `false` | Accelerometer excluded from the estimate. |
| `odom0_twist_rejection_threshold` | `2.5` | Rejects odometry-twist spikes (wheel slip). |
| `imu0_angular_velocity_rejection_threshold` | `1.2` | Rejects IMU yaw-rate spikes (electrical noise). |
| `sensor_timeout` / `reset_on_time_jump` | `0.1` s / `true` | Stability when a source stalls or timestamps jump. |
| `process_noise_covariance` | matrix $\mathbf{Q}_k$ | Sets how far the constant-velocity assumption may drift between predictions. |
| `initial_estimate_covariance` | matrix $\mathbf{P}_0$ | Sets the starting confidence per state: small for the known initial pose, large for the unobserved ones. |

The measurement-noise covariances $\mathbf{R}_{\text{odom}}$ and $\mathbf{R}_{\text{imu}}$ are not set in this file but are attached to each message by the base driver; their values are reported, with $\mathbf{Q}_k$ and $\mathbf{P}_0$, in Chapter 5.

With this configuration, the process model that advances the state turns out to be non-linear, while both measurement models turn out to be linear. The next subsections derive $\mathbf{f}$, $\mathbf{F}_k$, $\mathbf{h}_{\text{odom}}$, $\mathbf{h}_{\text{imu}}$, and their observation matrices explicitly, and show why.

**State vector.** Because the robot moves on a flat floor, the filter runs in planar mode (`two_d_mode`). In this mode the out-of-plane quantities, namely the height, the roll angle, and the pitch angle, along with the vertical velocity and the out-of-plane angular rates, are held fixed and dropped from the estimate, since they carry no useful information for a robot confined to a level surface. The estimated state then reduces to the planar pose and the body-frame velocities,

$$
\mathbf{s} = \big[\, x,\; y,\; \psi,\; V_x,\; V_y,\; V_\omega \,\big]^{\mathsf T},
$$

where:

- $x$, $y$ are the robot's position in the world (`odom`) frame;
- $\psi$ is the heading (yaw), the robot's orientation in the world frame;
- $V_x$, $V_y$ are the forward and sideways velocities expressed in the robot body frame;
- $V_\omega$ is the yaw rate, the same body-frame turning rate used in the kinematic model of Section 2.2 and measured by both sources in Sections 3.2.1 and 3.2.2;
- the superscript $\mathsf T$ denotes the transpose, so that $\mathbf{s}$ is a column vector.

The first three entries $(x, y, \psi)$ are the pose the rest of the stack consumes; the last three $(V_x, V_y, V_\omega)$ are kept in the state so that the two velocity measurements can be fused and then integrated into that pose. $V_y$ remains a free state here, but it is pulled toward zero by the odometry measurement, since a differential-drive robot cannot move sideways; this non-holonomic constraint is detailed in the measurement models below.

**Process model.** The process model $\mathbf{f}$ states how the state is expected to evolve over one step of duration $\Delta t$ when no noise is present, and it plays the role of the function $\mathbf{f}$ in the State Extrapolation Equation above. Two ideas define it. First, the body-frame velocities are rotated into the world frame by the current heading $\psi$ and integrated to advance the position. Second, the velocities themselves are carried forward unchanged, on the assumption that they vary slowly between steps, with any real change absorbed by the process noise $\mathbf{Q}$. Written out for the six-element state, this is

$$
\mathbf{f}(\mathbf{s}, \Delta t) =
\begin{bmatrix}
x + (V_x \cos\psi - V_y \sin\psi)\,\Delta t \\
y + (V_x \sin\psi + V_y \cos\psi)\,\Delta t \\
\psi + V_\omega \, \Delta t \\
V_x \\
V_y \\
V_\omega
\end{bmatrix},
$$

where each row propagates one component of the state:

- the first two rows advance the world-frame position. The groups $V_x \cos\psi - V_y \sin\psi$ and $V_x \sin\psi + V_y \cos\psi$ are the body velocities $V_x$, $V_y$ rotated into the world frame by the heading $\psi$ (a planar rotation by $\psi$), and multiplying by $\Delta t$ turns that world-frame velocity into a displacement, which is added to the previous position;
- the third row advances the heading by integrating the yaw rate, $\psi + V_\omega\,\Delta t$;
- the last three rows carry the body velocities $V_x$, $V_y$, $V_\omega$ forward unchanged, which is the constant-velocity assumption.

This model is non-linear, because the position update contains $\sin\psi$ and $\cos\psi$. As set out above, the EKF therefore works not with $\mathbf{f}$ itself but with its Jacobian. Differentiating each row of $\mathbf{f}$ with respect to each state component, that is forming $\mathbf{F} = \partial \mathbf{f}/\partial \mathbf{s}$, a $6\times 6$ matrix whose entry in row $a$ and column $b$ is $\partial f_a / \partial s_b$, gives the process Jacobian used in the Covariance Extrapolation Equation,

$$
\mathbf{F} =
\begin{bmatrix}
1 & 0 & (-V_x \sin\psi - V_y \cos\psi)\,\Delta t & \cos\psi\,\Delta t & -\sin\psi\,\Delta t & 0 \\
0 & 1 & (\;\;V_x \cos\psi - V_y \sin\psi)\,\Delta t & \sin\psi\,\Delta t & \cos\psi\,\Delta t & 0 \\
0 & 0 & 1 & 0 & 0 & \Delta t \\
0 & 0 & 0 & 1 & 0 & 0 \\
0 & 0 & 0 & 0 & 1 & 0 \\
0 & 0 & 0 & 0 & 0 & 1
\end{bmatrix},
$$

evaluated at the current estimate $\hat{\mathbf{s}}_{k-1\mid k-1}$. Its structure can be read column by column:

- the diagonal is all ones, because each state component still depends on its own previous value: the position and heading through the leading $x$, $y$, $\psi$ terms, and the velocities through the three constant-velocity rows;
- the third column holds the derivatives with respect to the heading $\psi$, namely $(-V_x \sin\psi - V_y \cos\psi)\,\Delta t$ and $(V_x \cos\psi - V_y \sin\psi)\,\Delta t$, obtained by differentiating the rotated position update with respect to $\psi$. This is the only place the non-linearity appears, since it is the only column that depends on the estimate rather than on constants;
- the fourth and fifth columns hold the derivatives with respect to the body velocities $V_x$ and $V_y$, the rotation terms $\cos\psi\,\Delta t$, $-\sin\psi\,\Delta t$, $\sin\psi\,\Delta t$, and $\cos\psi\,\Delta t$, which link a change in body velocity to the world-frame displacement it produces over the step;
- the entry $\Delta t$ in the third row and sixth column links the yaw rate $V_\omega$ to the heading change it produces over the step.

So $\mathbf{F}$ differs from the identity only through the couplings introduced by integrating motion over one step, and reduces to the identity everywhere else, reflecting that the model changes nothing but the position and heading.

**Measurement models.** A measurement model $\mathbf{h}_{\text{odom}}$ or $\mathbf{h}_{\text{imu}}$ states what its source should read for a given state, so that its prediction $\mathbf{h}(\hat{\mathbf{s}}_{k\mid k-1})$ can be compared with the actual reading $\mathbf{z}_k$ to form the innovation $\mathbf{y}_k$. Both sources here observe quantities that are already part of the state, so each model reduces to selecting the relevant components,

$$
\mathbf{h}_{\text{odom}}(\mathbf{s}) =
\begin{bmatrix}
V_x \\
V_y \\
V_\omega
\end{bmatrix},
\qquad
\mathbf{h}_{\text{imu}}(\mathbf{s}) = \big[\, V_\omega \,\big],
$$

where:

- $\mathbf{h}_{\text{odom}}(\mathbf{s})$ returns the three body-frame velocities $V_x$, $V_y$, $V_\omega$, matching the twist that the wheel odometry of Section 3.2.1 supplies as $\mathbf{z}_{\text{odom}}$;
- $\mathbf{h}_{\text{imu}}(\mathbf{s})$ returns the single yaw rate $V_\omega$, matching the gyroscope measurement of Section 3.2.2.

Because each output is one state component with no trigonometric terms, these models are linear, so their Jacobians $\mathbf{H}_{\text{odom}} = \partial \mathbf{h}_{\text{odom}} / \partial \mathbf{s}$ and $\mathbf{H}_{\text{imu}} = \partial \mathbf{h}_{\text{imu}} / \partial \mathbf{s}$ are constant and consist only of ones and zeros, each row holding a single $1$ in the column of the state it observes,

$$
\mathbf{H}_{\text{odom}} =
\begin{bmatrix}
0 & 0 & 0 & 1 & 0 & 0 \\
0 & 0 & 0 & 0 & 1 & 0 \\
0 & 0 & 0 & 0 & 0 & 1
\end{bmatrix},
\qquad
\mathbf{H}_{\text{imu}} =
\begin{bmatrix} 0 & 0 & 0 & 0 & 0 & 1 \end{bmatrix},
$$

where the three rows of $\mathbf{H}_{\text{odom}}$ pick out columns four, five, and six of the state ($V_x$, $V_y$, $V_\omega$), and the single row of $\mathbf{H}_{\text{imu}}$ picks out column six ($V_\omega$). Substituted for $\mathbf{H}_k$ above, these matrices route each measurement to exactly the states it informs, correcting the position and heading only indirectly, through their coupling to the velocities in $\mathbf{P}$.

Two design choices stand out. The odometry reports $V_y$ as a measured $0$ with an extremely small variance, so the non-holonomic constraint — a differential-drive robot cannot move sideways — is effectively enforced on the estimate, not merely suggested. The IMU, meanwhile, contributes only the yaw rate $V_\omega$; its absolute heading is left unfused, since the platform has no magnetometer to bound it and that heading would otherwise drift during long rotations.

$V_\omega$ is therefore the one quantity both sources observe, so it is fused twice per cycle — once from the encoders, once from the gyroscope — each weighted by its own measurement-noise covariance, so the fused yaw rate settles nearer whichever reading is trusted more.

**Fusion behaviour and output.** Running the recursion, the gain $\mathbf{K}_k$ weights each source by its relative uncertainty, so the estimate leans on the encoders for smooth translation and on the IMU for rotation. $\mathbf{R}_{\text{odom}}$ and $\mathbf{R}_{\text{imu}}$ encode this trust, and $\mathbf{Q}$ sets how far the constant-velocity assumption may be stretched between steps.

The odometry covariance is not fixed but set adaptively by the base driver: tightened when the wheels report no motion, so a stationary robot leans on the encoders and does not wander, and relaxed while driving, where slip makes them less reliable. Numerical values, along with the rejection thresholds, are reported in Chapter 5.

One consequence follows directly: the heading $\psi$ is never measured by any source. It comes only from integrating the fused yaw rate, $\psi_k = \psi_{k-1} + V_\omega\,\Delta t$, and so it still drifts slowly in the `odom` frame. This is acceptable because the robot's *absolute* heading and position are anchored separately by the map-based localization of Section 3.4.

The filter publishes the fused estimate on its output odometry topic and broadcasts the `odom → base_footprint` transform, which mapping, localization, and navigation all consume as the robot's smooth local motion estimate.

> 🖼️ **Figure 3.1 — Encoder–IMU fusion on the robot.** Block diagram: wheel-speed and IMU signals from the base → SI conversion and gyro bias removal → yaw rate taken directly → EKF predict/update loop → fused `/odometry/filtered` + `odom → base_footprint` TF. *(Redraw with the real topic names.)*
> 🖼️ **Figure 3.2 — Evidence (data lives in Ch.5).** The same closed test path plotted as encoder-only vs. EKF-fused trajectory, with the return-to-start error table.

---

## 3.3 Map Building with RTAB-Map

Autonomous driving requires a map of the service area and a way to stay localized on it. Both are produced by RTAB-Map, configured here for the robot's LiDAR-and-camera combination. RTAB-Map does not compute its own motion: it takes the fused encoder-and-IMU odometry of Section 3.2 as the backbone of its pose graph, refines the geometric links between poses by matching successive LiDAR scans, and uses the RGB-D camera to recognize previously visited places so that accumulated drift can be corrected by loop closure. The camera therefore contributes to the *consistency* of the map rather than to its geometry, and the map delivered to the rest of the stack is a single **two-dimensional occupancy grid** of free and blocked space.

The mapping run is performed once, offline, before deployment. The robot is driven slowly along the whole length of the service lane under manual (teleoperation) control, including a return pass so that the start of the lane is revisited and at least one loop closure is triggered; the resulting graph is optimized into a globally consistent 2D grid, which is saved and reused for every subsequent trip. The parameters that were tuned for this environment — the grid resolution, the maximum usable LiDAR range, the loop-closure and proximity-detection settings, and the update rate — are listed with their chosen values and the reason for each in the parameter table below.

Because the map is two-dimensional and the lane is separated from the customer area, the camera's role is confined to loop closure during mapping and to marker detection during docking (Section 3.4); it is not used to build a 3D model of the environment.

> 🖼️ **Figure 3.3 — RTAB-Map wiring on the robot.** The LiDAR scan, the RGB and aligned-depth image streams, and the fused `/odom` feeding the RTAB-Map node, which outputs the 2D occupancy grid. *(Use the real remapped topic names.)*
> 📌 Parameter table (fill from the real config): grid resolution, max LiDAR range, loop-closure detection rate/threshold, proximity detection, memory-management settings. Point out one actual loop closure on the built map (screenshot → Ch.5). A LiDAR-only mapping option also exists on the robot; state which map is used for navigation.

---

## 3.4 Localization and ArUco-Based Docking

Once the map exists, the robot must know where it is on it, and — because a food-service robot has to stop accurately at a fixed point — it must be able to refine that pose at the places where precision matters. Localization on the map and precise stopping are handled together in this section, the first by map-based localization, the second by fixed ArUco markers.

### 3.4.1 Map-Based Localization

For normal operation RTAB-Map is switched from mapping to localization mode: it loads the previously built map and, instead of adding new nodes, matches the current LiDAR and camera observations against the stored graph to estimate the robot's pose on the map. In this mode it publishes the transform from the map frame to the `odom` frame, so that the globally corrected map pose and the smooth local odometry of Section 3.2 are combined into a single, consistent estimate of where the robot is.

### 3.4.2 Initial Pose from the Home ArUco Marker

Map-based localization needs a starting pose. Rather than setting this by hand, the robot obtains it automatically at its home station in the kitchen, where a fixed ArUco marker is placed at a known location on the map. On start-up the RGB-D camera detects this marker, computes the robot's pose relative to it, and — since the marker's position on the map is known — converts that into the robot's absolute initial pose. This removes the manual pose-initialization step and guarantees that every mission starts from the same, accurately known point.

### 3.4.3 Per-Table ArUco Re-Localization

Map-based localization is accurate enough to bring the robot to the vicinity of a table, but the small residual error of SLAM and odometry is too large for reliably placing a tray at a fixed spot. To close this gap, a fixed ArUco marker is mounted at each table. When the robot reaches the target table, the camera detects that table's marker and computes the robot's pose relative to it; because the marker provides an absolute, local reference exactly where precision is needed, this measurement re-localizes the robot far more accurately than the map alone, allowing it to complete a precise final stop. If the marker cannot be found, the robot does not force the approach: it stops safely at a defined distance and reports the failure.

> ✏️ **Not yet implemented — write as planned.** The final-approach docking *controller* that drives the robot from the detected-marker pose to the exact stop point (a short non-holonomic approach respecting $V_y = 0$, with marker-lost handling and a safe stop distance) is future work; only the marker detection and pose computation are described as running once they are. Report only what actually runs when Chapter 5 is written.

---

## 3.5 Autonomous Navigation with Nav2

Driving the robot from its current pose to a table goal is handled by the ROS2 navigation stack, Nav2. A goal is a pose on the map — the docking point of a requested table — and Nav2 turns it into safe motion in two layers: a global planner that computes a path across the whole map, and a local controller that follows that path while reacting to what the sensors see. Both operate on costmaps derived from the map and the live LiDAR.

**Global and local planning.** The global planner searches the static map for a path from the robot's current pose to the goal along the service lane. The local controller then tracks this path, issuing body-frame velocity commands; because the robot is a non-holonomic two-wheel drive, the controller commands only forward speed and yaw rate ($V_y = 0$) and turns in place when it must change heading sharply, rather than moving sideways. The controller parameters — the look-ahead distance, the desired and maximum speeds, and the rule for slowing down in tight sections — are taken from the navigation configuration and listed with their values in the table below.

**Costmaps and obstacle handling.** The static layer of the costmap comes from the 2D map; an inflation layer around obstacles keeps the robot at a safe distance; and an obstacle layer, fed by the live LiDAR scan, marks anything currently in the lane. Since the service lane is physically separated from the customer area, the robot does not need pedestrian detection or social navigation; the obstacle layer's purpose is to detect the occasional object that unexpectedly enters the lane and to stop or route the robot safely around it. The costmap parameters — the robot radius, the inflation radius, and the grid resolution — are chosen for the width of the lane and are given in the table.

**Trip orchestration.** In operation, navigation is driven by the backend of Chapter 4. The dispatcher issues a table goal to Nav2; Nav2 plans and drives the robot along the lane to the table; on arrival the per-table ArUco re-localization of Section 3.4.3 refines the stop; and the outcome is reported back to the backend, which advances the order. This hand-off is the explicit bridge between the navigation stack of this chapter and the AI system of the next.

> ✏️ **Status: basic Nav2 is running.** Write the planner, controller, and costmap exactly as configured; mark advanced recovery behaviours and any further tuning as planned until implemented.
> 🖼️ **Figure 3.4 — Nav2 flow on the robot.** goal → global planner (global costmap) → local controller (local costmap) → `/cmd_vel`, with the trip-orchestration hand-off to the backend and the ArUco re-localization at arrival.
> 📌 Parameter tables (fill from the real `nav2_params.yaml`): controller type and its look-ahead / speed settings; costmap robot radius, inflation, resolution, and the LiDAR obstacle source.

---
