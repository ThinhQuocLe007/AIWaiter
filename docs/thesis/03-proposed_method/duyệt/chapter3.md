# CHAPTER 3 — PROPOSED METHOD (I): ROBOT CONTROL AND NAVIGATION ON ROS2

> **Report-style, impersonal** (no "the group" / "we"). This chapter presents the method together with the configuration values it was deployed with, so that every design decision can be read with the number that implements it. Chapter 5 does not introduce new settings; it verifies and evaluates the behaviour produced by the ones given here. Theory that is common knowledge (differential-drive kinematics, the Kalman recursion, graph SLAM fundamentals) is established in Chapter 2 and is referenced here rather than repeated.

This chapter presents the control and navigation method of the robot on ROS2. The presentation follows the data as it flows upward: from the wheel encoders and the IMU into a fused estimate of the robot's own motion, from the LiDAR and the RGB-D camera into a two-dimensional map of the service area, from that map into a localized pose corrected by fixed visual markers, and finally from a table request into autonomous motion along the service lane. The robot operates on a lane that is physically separated from the customer area, so its environment contains no pedestrians and only occasional objects that accidentally enter the lane must be handled. The map used throughout is two-dimensional.

---



## 3.1 System Requirements

- **Map building:** The SLAM method must build a 2D map of the service area by fusing several onboard sensors, namely the LiDAR, the IMU, the wheel encoders and the RGB-D camera, so that the resulting map is accurate and consistent enough to be reused for localization and navigation.
- **Smooth motion:** The robot must move smoothly at a stable speed, without vibration or jerk, since it carries food and drink on an open tray.
- **Fast localization:** The system must localize accurately and respond quickly in a visually and geometrically repetitive environment, and must be able to recover its pose after a temporary loss.
- **Accurate arrival:** The robot must re-detect fixed ArUco markers built into the map to correct accumulated drift, so that its pose near a marked table stays accurate and arrival there is repeatable rather than left to odometry drift.
- **Safety and operating constraints:** The robot must operate on flat indoor floor inside the dedicated lane, keep a safe clearance from obstacles, and stop safely whenever the lane is blocked or a target marker cannot be found.

---



## 3.2 Robot Platform Specification

The platform is a purchased two-wheel differential-drive (TWD) base. The contribution of this work begins at the ROS2 layer and above; the mechanical build, the motor drive and the low-level firmware are used as supplied. The physical and electronic properties that the methods of this chapter depend on are collected in Table 3.1.

**Table 3.1 — Robot platform specification.**


| Group            | Item                                          | Value                                                                                                              |
| ---------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Chassis          | Drive configuration                           | Two-wheel differential drive, one passive caster                                                                   |
|                  | Body radius / height                          | 0.114 m / 0.106 m                                                                                                  |
|                  | Wheel radius / diameter $D$                   | 0.0362 m / 0.0724 m                                                                                                |
|                  | Wheel width                                   | 0.053 m                                                                                                            |
|                  | Wheel track $W$                               | 0.206 m                                                                                                            |
|                  | Caster                                        | Sphere, radius 0.015 m, 0.09 m forward of the body centre                                                          |
|                  | Footprint radius used by the navigation stack | 0.12 m                                                                                                             |
| Sensor mounting  | LiDAR scan plane                              | 0.22 m above `base_link`                                                                                           |
|                  | RGB-D camera                                  | 0.10 m forward, 0.17655 m above `base_link`                                                                        |
| LiDAR            | Model                                         | Slamtec RPLIDAR A2M8, 360° 2D scanner                                                                              |
|                  | Interface                                     | USB serial, 115200 baud, standard scan mode                                                                        |
|                  | Range used for mapping                        | 0.15 m to 10.0 m                                                                                                   |
| RGB-D camera     | Model                                         | Intel RealSense D435                                                                                               |
|                  | Colour stream                                 | 640 × 480 at 15 fps                                                                                                |
|                  | Depth stream                                  | 640 × 480 at 15 fps, aligned to the colour frame                                                                   |
| IMU              | Model                                         | MPU6050, six-axis, no magnetometer                                                                                 |
|                  | Accelerometer full-scale range $A_{\max}$     | ±2 g, 16-bit signed                                                                                                |
|                  | Gyroscope full-scale range $\Omega_{\max}$    | ±500 °/s, 16-bit signed                                                                                            |
| Encoders         | Type                                          | Hall-effect quadrature, one per driven wheel                                                                       |
|                  | Resolution $P$                                | 1024 pulses per revolution                                                                                         |
|                  | Gear ratio $G$                                | 1 : 30                                                                                                             |
|                  | Counts per wheel revolution $N = 4PG$         | 122 880                                                                                                            |
| Base controller  | Board / MCU                                   | OpenCTR (Robot Controller H40), STM32F407VET6, 168 MHz Cortex-M4                                                   |
|                  | Supply input                                  | 7–17 V wide-voltage input, 80 A electronic (MOS) switch                                                            |
|                  | Motor / servo drives                          | Four quadrature-encoder motor ports, six PWM servo channels                                                        |
|                  | Auxiliary interfaces                          | On-board IMU, buzzer, OLED, 3× TTL serial, SBUS, SPI/I²C, SWD download                                             |
|                  | Link to the onboard computer                  | USB serial, 230400 baud                                                                                            |
|                  | Telemetry frame / rate                        | 25-byte binary frame, 50 Hz                                                                                        |
| Onboard computer | Model                                         | NVIDIA Jetson Orin Nano, 8 GB                                                                                      |
|                  | Middleware                                    | ROS2                                                                                                               |
| Power            | Battery                                       | 12.6 V (nominal 12 V) 10 000 mAh polymer lithium pack, T-plug                                                      |
|                  | Protection                                    | Over-discharge, over-current and over-voltage protection board                                                     |
|                  | Discharge current                             | 10 A continuous, 20 A peak                                                                                         |
|                  | Distribution                                  | 12 V direct to the motor driver and to the onboard computer (12 V @ 5 A port); DC-DC 5 V @ 5 A rail for the servos |
|                  | Telemetry                                     | Pack voltage reported by the base at 50 Hz                                                                         |


Two consequences of this table shape the rest of the chapter. First, the IMU has no magnetometer, so nothing on the robot measures absolute heading; heading must therefore be anchored by the map (Section 3.5) rather than by the inertial sensor. Second, the LiDAR observes a single horizontal plane at 0.22 m, so obstacles above and below that plane are invisible to it; this gap is closed by the camera in Section 3.6.

### 3.2.1 Sensing and Compute Components

Three devices carry the perception and computation that the rest of this chapter depends on. Their numeric properties are collected in Table 3.1; this subsection describes what each one contributes and how it is used, without repeating the figures given there.

**Slamtec RPLIDAR A2M8.** The primary geometric sensor is a 360° rotating 2D laser scanner. It measures range by laser triangulation over a full revolution, producing a planar scan of the room several times a second in a single horizontal plane 0.22 m above the floor. Because it measures distance directly and does not rely on ambient light, its geometry stays stable across the lighting changes common in a dining room, and within its plane it is accurate enough to serve as the sole source of the occupancy grid built in Section 3.4 and of the global costmap in Section 3.6.1. Its one structural limit is that it sees only that horizontal plane: obstacles above or below the beam are invisible to it, which is the gap the depth camera fills in Section 3.6.1. It connects to the onboard computer over a USB serial link and runs through its stock ROS2 driver without modification.

**Intel RealSense D435.** The RGB-D camera provides the two things the LiDAR cannot. Its colour stream carries visual appearance, which drives place recognition and ArUco marker detection during mapping and localization (Sections 3.4 and 3.5) and lets the robot separate locations that look identical to a 2D scan. Its depth stream is collapsed into a synthetic laser scan over the near field, covering the low and overhanging obstacles that fall outside the LiDAR plane (Section 3.6.1). The camera projects an infrared pattern and recovers depth from a stereo pair, so it works in ordinary indoor lighting but is trusted only over the near-to-mid range where that depth stays accurate. Its combined colour and depth bandwidth is the one reason the platform needs a USB 3.0 port rather than only USB 2.0.

**NVIDIA Jetson Orin Nano (8 GB).** The onboard computer runs the whole system on one board: the ROS2 navigation stack of this chapter on the CPU, and the GPU-accelerated workloads (RTAB-Map's visual feature matching here, and the speech and language models of Chapter 4) on its integrated GPU. Its 8 GB of memory is unified, meaning the CPU and GPU share one pool rather than each holding its own, so perception, navigation, and speech inference all draw from the same 8 GB. What can run at once is therefore limited by memory, not by compute, and that limit shapes the workload split of Chapter 4. Every other device connects back to it, so it is also the hub through which the system communicates, which Section 3.2.2 takes up.

### 3.2.2 System Interconnection

The onboard computer is that hub. The RPLIDAR reaches it over a USB serial link, the RealSense D435 over USB 3.0, and the OpenCTR base controller over a USB serial link at 230400 baud. The base controller in turn drives the two differential-drive wheels, each with a Hall-effect quadrature encoder, and reads the on-board MPU6050 IMU, so those measurements arrive at the computer inside the base telemetry frame described in Section 3.3.1 rather than over separate buses. Power is distributed from the 12.6 V battery in parallel: directly to the motor driver, to the onboard computer through its 12 V @ 5 A port, and through a DC-DC converter to the 5 V servo rail, with the pack voltage reported back to the computer in the same telemetry frame. Figure 3.1 shows these data and power paths.

> 🖼️ **Figure 3.1 — Hardware connection diagram.** Block diagram of the robot's electronics with the Jetson Orin Nano at the centre and three data links leaving it: USB 3.0 to the Intel RealSense D435, USB serial to the Slamtec RPLIDAR A2M8, and USB serial at 230400 baud to the OpenCTR base controller; the base controller shown driving the two driven wheels with their encoders and reading the on-board MPU6050 IMU. Power drawn as a separate set of lines from the 12.6 V battery: to the motor driver, to the Jetson's 12 V @ 5 A port, and through a DC-DC 5 V converter to the servo rail.

---



## 3.3 Encoder–IMU Sensor Fusion with an Extended Kalman Filter



### 3.3.1 Wheel Odometry from the Encoders

Each driven wheel carries a Hall-effect quadrature encoder. As the wheel turns, the encoder emits pulses on two offset channels; counting the pulses gives the amount of rotation and the ordering of the channels gives its direction. The number of counts produced per full wheel revolution is

$$
N = 4 P G,
$$

where $N$ is the number of counts per wheel revolution, $P$ is the encoder resolution in pulses per revolution, the factor $4$ comes from quadrature decoding (both edges of both channels are counted), and $G$ is the gear ratio between the encoder shaft and the wheel. One count therefore corresponds to a fixed arc length at the wheel rim,

$$
d_{\text{tick}} = \frac{\pi D}{N},
$$

with $D$ the wheel diameter, so that a wheel $i$ producing $\Delta n_i$ counts in an interval $\Delta t$ turns at a linear speed of

$$
V_i = \frac{\pi D}{N}\cdot\frac{\Delta n_i}{\Delta t}, \qquad i \in A, B,
$$

where $A$ and $B$ denote the left and the right driven wheel.

With the platform values of Table 3.1, namely $P = 1024$ pulses per revolution, $G = 30$ and a wheel diameter of $D = 0.0724$ m, this gives $N = 122880$ counts per wheel revolution and a rim resolution of $d_{\text{tick}} = 1.85\ \mu\text{m}$ per count. The resolution of the encoders is therefore far finer than any error the odometry actually suffers from; the limiting factors are slip and wheel-geometry error, not quantization.

The forward kinematics of the differential drive established in Section 2.2 convert the two wheel speeds into the body-frame velocities of the robot,

$$
V_x = \frac{V_A + V_B}{2}, \qquad V_y = 0, \qquad V_\omega = \frac{V_B - V_A}{W},
$$

where:

- $V_x$ is the forward velocity of the body, in m/s;
- $V_y$ is the lateral velocity, held at zero by the non-holonomic constraint of the two-wheel drive;
- $V_\omega$ is the yaw rate, in rad/s, obtained as the wheel-speed difference divided by the wheel track $W$.

These three quantities form the wheel-odometry measurement supplied to the filter,

$$
\mathbf{z}*{\text{odom}} = \big[ V_x, V_y, V*\omega \big]^{\mathsf T} + \mathbf{n}_{\text{odom}},
$$

where $\mathbf{n}*{\text{odom}}$ is the odometry measurement noise, whose covariance $\mathbf{R}*{\text{odom}}$ is given in Section 3.3.3.

Integrated on its own over an Euler step, this velocity yields a pose,

$$
\begin{aligned}
x &\leftarrow x + V_x\cos\psi\Delta t, 
y &\leftarrow y + V_x\sin\psi\Delta t, 
\psi &\leftarrow \psi + V_\omega\Delta t,
\end{aligned}
$$

with the heading wrapped to $(-\pi,\pi]$. This integrated pose is published for reference, but only the velocity $\mathbf{z}_{\text{odom}}$ is fused, because an integrated wheel pose accumulates drift that the filter cannot later undo. Pulse counting, scaling into wheel speeds and the motor control loop all run at a fixed 50 Hz on the STM32 of the base and are transmitted over the serial link; the ROS2 driver on the onboard computer converts the values to SI units and publishes the odometry message.

Wheel odometry alone drifts, chiefly from wheel slip and from small errors in the assumed wheel geometry, and because it only ever adds new motion onto the previous estimate it can never correct a past mistake. The heading is the worst affected, since every turn contributes error that is never removed. For this reason the wheel odometry is fused with the IMU rather than used on its own.

### 3.3.2 IMU Measurement Model

The IMU is a six-axis MPU6050 combining a three-axis gyroscope and a three-axis accelerometer. Both sensors report in the robot body frame as raw 16-bit signed integers, and the chip carries no magnetometer, so it provides no absolute heading.

**Gyroscope.** The gyroscope measures the body's angular velocity about the three body axes,

$$
\boldsymbol{\omega}_B = \big[ \omega_x, \omega_y, \omega_z \big]^{\mathsf T},
$$

where $\omega_x$, $\omega_y$ and $\omega_z$ are the angular velocities about the body `x`, `y` and `z` axes, that is the roll, pitch and yaw rates. Each component arrives as a raw integer and is converted to physical units by the **gyroscope scale factor**,

$$
\omega_j = s_g\omega_{j,\text{raw}}, \qquad s_g = \frac{\Omega_{\max}}{2^{15}}, \qquad j \in x, y, z,
$$

where:

- $\omega_j$ is the converted angular velocity about body axis $j$, in rad/s, so that $\omega_z$ is the yaw rate about the vertical axis;
- $\omega_{j,\text{raw}}$ is the raw integer reading of that axis;
- $s_g$ is the gyroscope scale factor, in rad/s per count;
- $\Omega_{\max}$ is the magnitude of the configured full-scale range of the gyroscope, $500{}^{\circ}/\text{s}$ for a configured range of $\pm 500{}^{\circ}/\text{s}$ on this robot;
- $2^{15}$ is the magnitude of the signed 16-bit range over which the raw integer is spread.

**Accelerometer.** The accelerometer measures the body's linear acceleration along the three body axes,

$$
\mathbf{a}_B = \big[ a_x, a_y, a_z \big]^{\mathsf T},
$$

where $a_x$, $a_y$ and $a_z$ are the accelerations along the body `x`, `y` and `z` axes. Each component is converted in the same way by the **accelerometer scale factor**,

$$
a_j = s_aa_{j,\text{raw}}, \qquad s_a = \frac{A_{\max}}{2^{15}}, \qquad j \in x, y, z,
$$

where:

- $a_j$ is the converted acceleration along body axis $j$, in m/s²;
- $a_{j,\text{raw}}$ is the raw integer reading of that axis;
- $s_a$ is the accelerometer scale factor, in m/s² per count;
- $A_{\max}$ is the magnitude of the configured full-scale range of the accelerometer, $2g$ for a configured range of $\pm 2g$ on this robot.

**Numeric values.** Substituting the two configured ranges gives the scale factors the driver applies to every incoming sample,

$$
s_g = \frac{500{}^{\circ}/\text{s}}{2^{15}} = 2.663\times10^{-4}\ \text{rad/s per count},
$$

$$
s_a = \frac{2g}{2^{15}} = 5.981\times10^{-4}\ \text{m/s}^2\ \text{per count},
$$

with $g$ taken as $9.8\ \text{m/s}^2$ to match the constant used in the base firmware. The raw sensor axes are remapped to the ROS body convention (forward `x`, left `y`, up `z`) by a fixed permutation in the base firmware, so no further axis transform is applied on the ROS2 side.

**Bias on the yaw axis.** Of the six converted readings above, only the yaw rate $\omega_z$ is used by the estimator, for the reason given at the end of this subsection. Even at rest the gyroscope reports a small constant offset, or bias, on that axis, which would otherwise integrate into a growing heading error. The bias is estimated by averaging $M$ samples of $\omega_z$ collected while the robot is stationary,

$$
b_g = \frac{1}{M}\sum_{k=1}^{M}\omega_{z,k},
$$

where $b_g$ is the estimated bias, $M$ the number of stationary samples and $\omega_{z,k}$ the $k$-th converted reading of $\omega_z$. The bias is subtracted from every subsequent reading, giving the single-element IMU measurement supplied to the filter,

$$
\mathbf{z}*{\text{imu}} = \big[ \omega_z - b_g \big] + n*\omega,
$$

where $n_\omega$ is the gyroscope measurement noise, whose variance $\mathbf{R}_{\text{imu}}$ is given in Section 3.3.3.

The quantity this measurement carries is the yaw rate $V_\omega$, the same physical quantity that appears in the wheel-odometry measurement $\mathbf{z}_{\text{odom}}$ above and in the kinematic model of Section 2.2. The two sources obtain it differently: the gyroscope measures the turning rate directly, whereas the wheel odometry infers it indirectly from the difference of the two wheel speeds. Having two independent measurements of one quantity is precisely what makes the sources complementary, and Section 3.3.3 fuses them.

The yaw rate is the only quantity taken from the IMU. The accelerometer is converted and published but is not fused, and the orientation produced on the base by a complementary attitude filter is not fused either, because without a magnetometer nothing bounds its drift during long rotations. The robot's absolute heading is instead anchored by the map-based localization of Section 3.5.

### 3.3.3 Fusion with the Extended Kalman Filter

The wheel odometry gives accurate translation but drifts with slip; the IMU gives a clean, slip-independent yaw rate but no absolute reference. The two are combined by the Extended Kalman Filter presented in Section 2.x, implemented by the `robot_localization` package and configured entirely through a parameter file.

**State vector.** Because the robot moves on a flat floor, the filter runs in planar mode: height, roll, pitch and the out-of-plane rates are held fixed and dropped from the estimate. The state reduces to the planar pose and the body-frame velocities,

$$
\mathbf{s} = \big[ x, y, \psi, V_x, V_y, V_\omega \big]^{\mathsf T},
$$

where:

- $x$, $y$ are the position of the robot in the `odom` frame, in metres;
- $\psi$ is the heading, or yaw angle, in that same frame;
- $V_x$, $V_y$, $V_\omega$ are the body-frame velocities already defined in Section 3.3.1.

The first three entries are the pose that the rest of the stack consumes; the last three are kept so that the two velocity measurements can be fused and then integrated into that pose. Note that the last three state components carry the same symbols as the measurements of Sections 3.3.1 and 3.3.2, and deliberately so: both sources observe quantities that are already part of the state, which is what makes the measurement models below pure selections.

**Process model.** Over one step of duration $\Delta t$ the body velocities are rotated into the world frame by the current heading and integrated to advance the position, while the velocities themselves are carried forward unchanged under a constant-velocity assumption, with any real change absorbed by the process noise:

$$
\mathbf{f}(\mathbf{s},\Delta t) =
\begin{bmatrix}
x + (V_x\cos\psi - V_y\sin\psi)\Delta t 
y + (V_x\sin\psi + V_y\cos\psi)\Delta t 
\psi + V_\omega\Delta t 
V_x  V_y  V_\omega
\end{bmatrix}.
$$

The model is non-linear through $\sin\psi$ and $\cos\psi$ in the position update, which is why the extended form of the filter is required; its Jacobian $\mathbf{F} = \partial\mathbf{f}/\partial\mathbf{s}$ differs from the identity only in the couplings introduced by integrating motion over one step.

**Measurement models.** Both sources observe quantities that are already state components, so each model reduces to a selection,

$$
\mathbf{h}*{\text{odom}}(\mathbf{s}) = \big[V_x,V_y,V*\omega\big]^{\mathsf T},
\qquad
\mathbf{h}*{\text{imu}}(\mathbf{s}) = \big[V*\omega\big],
$$

where $\mathbf{h}*{\text{odom}}$ predicts what the wheel odometry $\mathbf{z}*{\text{odom}}$ of Section 3.3.1 should read and $\mathbf{h}*{\text{imu}}$ predicts what the gyroscope measurement $\mathbf{z}*{\text{imu}}$ of Section 3.3.2 should read, each difference $\mathbf{z} - \mathbf{h}(\mathbf{s})$ forming the innovation that the update step applies. Both models are linear, so their Jacobians $\mathbf{H}*{\text{odom}}$ and $\mathbf{H}*{\text{imu}}$ are constant matrices of ones and zeros, each row holding a single $1$ in the column of the state it observes,

$$
\mathbf{H}*{\text{odom}} =
\begin{bmatrix}
0 & 0 & 0 & 1 & 0 & 0 
0 & 0 & 0 & 0 & 1 & 0 
0 & 0 & 0 & 0 & 0 & 1
\end{bmatrix},
\qquad
\mathbf{H}*{\text{imu}} =
\begin{bmatrix} 0 & 0 & 0 & 0 & 0 & 1 \end{bmatrix},
$$

so that the three rows of $\mathbf{H}*{\text{odom}}$ pick out $V_x$, $V_y$ and $V*\omega$ and the single row of $\mathbf{H}*{\text{imu}}$ picks out $V*\omega$. The position and the heading are therefore never corrected directly by either sensor; they are corrected indirectly, through the coupling between the velocities and the pose held in the covariance $\mathbf{P}$. The yaw rate $V_\omega$ is the one quantity both sources observe, so it is fused twice per cycle, each contribution weighted by its own measurement-noise covariance, $\mathbf{R}*{\text{odom}}$ and $\mathbf{R}*{\text{imu}}$.

**Configuration.** Because the robot moves on a flat floor, the filter runs with `two_d_mode` set to `true`, which is what reduces the estimate to the planar state written above: height, roll, pitch and the out-of-plane rates are held at zero rather than estimated. The rest of the settings in this category follow from the platform and leave no real choice. The filter predicts and updates at 30 Hz, treats a source silent for more than 0.1 s as unavailable, buffers each input against jitter in arrival time, and reinitializes when timestamps jump backwards. It runs as a local odometry instance, estimating the pose of `base_footprint` in the `odom` frame, and it publishes the `odom → base_footprint` transform itself instead of leaving it to the base driver. The accelerometer is unused, so gravity removal and acceleration publishing are both switched off. Table 3.2 lists the settings that were genuinely chosen, with the reason for each; the complete parameter file is reproduced in Appendix x.

**Table 3.2 — Extended Kalman Filter design settings.**


| Parameter                                   | Value                    | Reason                                                                                                                                            |
| ------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `odom0_config`                              | $V_x$, $V_y$, $V_\omega$ | Only the twist of the wheel odometry is fused; its integrated pose is ignored, so that pose and twist are not both taken from one source.         |
| `imu0_config`                               | $V_\omega$ only          | Only the gyroscope yaw rate is fused; orientation is excluded for want of a magnetometer.                                                         |
| `odom0_twist_rejection_threshold`           | 2.5                      | Discards odometry-twist spikes caused by wheel slip.                                                                                              |
| `imu0_angular_velocity_rejection_threshold` | 1.2                      | Discards gyroscope spikes caused by vibration or electrical noise. The tighter value reflects the gyroscope being the cleaner of the two sources. |
| `process_noise_covariance`                  | matrix $\mathbf{Q}$      | Sets how far the constant-velocity assumption may drift between predictions.                                                                      |
| `initial_estimate_covariance`               | matrix $\mathbf{P}_0$    | Small for the known initial pose, large for the unobserved states.                                                                                |


Both thresholds are counted in standard deviations, not in raw sensor units. Before each update, the filter already has a prediction for what the sensor should read, together with how uncertain that prediction is. When the actual reading comes in, the filter checks how many standard deviations away it falls from the prediction, and throws the reading away if it falls too far. A wheel-odometry reading is discarded once it is more than 2.5 standard deviations from what the filter expected, and a gyroscope reading once it is more than 1.2 away. Measuring the gap this way, instead of with a fixed number like "0.1 m/s," lets the same threshold work whether the filter is currently confident or unsure. A low threshold rejects more noise but also risks throwing away a genuine sudden acceleration.

The measurement-noise covariances are not set in this file. They are attached to every message by the base driver, which sets them adaptively rather than fixing them: the odometry covariance is tightened when the wheels report no motion, so that a stationary robot leans on the encoders and does not wander, and relaxed while driving, where slip makes them less reliable. The lateral velocity is a separate case. Since a differential-drive robot cannot move sideways, the driver reports $V_y$ as a measured zero with a very small variance, which turns the non-holonomic constraint into an enforced property of the estimate rather than a hint.

In the parameter file, $\mathbf{Q}$ and $\mathbf{P}_0$ are not written as the six-by-six matrices used above. `robot_localization` always works with its full state of fifteen quantities, which is position, orientation, their rates, and linear acceleration, each on all three axes, so both matrices are declared as 15-by-15 in the file even though `two_d_mode` only lets six of those states move. The other nine, everything tied to $z$, roll, and pitch, are forced back to zero after every predict and update step regardless of what covariance is assigned to them. Table 3.3 lists only the six diagonal entries that actually affect the published estimate; the remaining off-diagonal entries are zero throughout, so each state and each measurement is treated as independent.

**Table 3.3 — Covariance values, planar diagonal entries.**


| Matrix                           | $x$       | $y$       | $\psi$    | $V_x$     | $V_y$     | $V_\omega$ |
| -------------------------------- | --------- | --------- | --------- | --------- | --------- | ---------- |
| $\mathbf{Q}$, process noise      | 0.02      | 0.02      | 0.05      | 0.03      | 0.03      | 0.04       |
| $\mathbf{P}_0$, initial estimate | $10^{-3}$ | $10^{-3}$ | $10^{-2}$ | $10^{-2}$ | $10^{-2}$ | $10^{-2}$  |


The nine out-of-plane entries, not shown above since `two_d_mode` holds them at zero regardless, follow one pattern in the file: a process noise between 0.02 and 0.06 in $\mathbf{Q}$, paired with an initial covariance of $10^6$ in $\mathbf{P}_0$, which is the value `robot_localization` uses to mark a state as unconstrained. One entry breaks the pattern: vertical acceleration is given an initial covariance of $10^{-1}$ instead of $10^6$. Since that state is zeroed out by `two_d_mode` anyway, it has no effect on the estimate, but it is worth checking against the intended configuration.

The yaw rate is the one state both sources observe, and the two variances that meet there are $0.1$ for the odometry while driving against $0.02$ for the IMU. The gyroscope is therefore trusted about five times more than the wheels for rotation, which is the intended division of labour: the encoders carry translation, the IMU carries rotation.

One consequence follows directly. The heading $\psi$ is never measured by any source; it comes only from integrating the fused yaw rate, and so it still drifts slowly in the `odom` frame. This is accepted by design, because the absolute pose is anchored separately by the localization layer of Section 3.5.

> 🖼️ **Figure 3.2 — Encoder–IMU fusion.** Block diagram: wheel speeds and IMU readings from the base, SI conversion and gyro bias removal in the driver, adaptive covariance assignment, the EKF predict–update loop, and the fused odometry plus `odom → base_footprint` transform consumed by mapping, localization and navigation.

---



## 3.4 Map Building with RTAB-Map

The robot operates indoors, on a fixed floor plan that does not change from one service to the next, so a map built once in advance remains valid for every trip; this is the assumption that justifies building the map offline rather than mapping continuously as an outdoor robot would have to. The map is built once, before deployment, by driving the robot slowly along the whole service lane under manual control, including a return pass so that the start of the lane is revisited and at least one loop closure is triggered. The resulting graph is optimized into a globally consistent two-dimensional occupancy grid, which is saved and reused for every subsequent trip.

RTAB-Map builds this map as a pose graph, taking geometry from the LiDAR, appearance from the RGB-D camera, and fixed ArUco markers as landmarks. Chapter 2 covers why this method was chosen over LiDAR-only and vision-only alternatives; the rest of this section takes the method as settled and describes how it is configured and how its loop closure was tuned for this floor.

### 3.4.1 Mapping Configuration

RTAB-Map is configured through a single parameter file. Table 3.4 lists the parameters that shape the mapping run, with the value used and the reason for it; settings left at their RTAB-Map defaults are omitted unless the default itself is a decision worth recording.

**Table 3.4 — RTAB-Map configuration for mapping.**


| Group           | Parameter                                    | Value                 | Purpose                                                                                                         |
| --------------- | -------------------------------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------- |
| Inputs          | `subscribe_depth` / `subscribe_scan`         | true / true           | Both the RGB-D camera and the LiDAR feed the graph.                                                             |
|                 | `frame_id`                                   | `base_footprint`      | The frame the filter of Section 3.3 and the costmaps also use.                                                  |
|                 | Odometry source                              | fused odometry (§3.3) | The backbone of the pose graph; pose is not re-derived from raw sensors.                                        |
| Memory          | `Mem/IncrementalMemory`                      | true                  | New observations are added to the graph as the robot drives the lane.                                           |
| Occupancy grid  | `Grid/Sensor`                                | 0 (LiDAR)             | The grid is built from laser returns only; depth noise at range would write ghost cells.                        |
|                 | `Grid/CellSize`                              | 0.05 m                | Grid resolution; matches the navigation costmaps of Section 3.6.                                                |
|                 | `Grid/RangeMax` / `Grid/RangeMin`            | 10.0 m / 0.15 m       | Covers the 9.5 m room; the lower bound rejects returns from the robot's own body.                               |
| Graph           | `Rtabmap/DetectionRate`                      | 2.0 Hz                | Keeps the graph dense; mapping runs offline, so there is no real-time cost to trade against.                    |
|                 | `RGBD/LinearUpdate` / `RGBD/AngularUpdate`   | 0.05 m / 0.05 rad     | New-node thresholds in translation and rotation.                                                                |
|                 | `RGBD/OptimizeFromGraphEnd`                  | false                 | Keeps the map origin fixed rather than re-anchoring at the newest node.                                         |
| Registration    | `Reg/Strategy` / `Reg/Force3DoF`             | 1 (ICP) / true        | Geometric registration on laser data, constrained to $(x, y, \psi)$.                                            |
|                 | `RGBD/ProximityBySpace`                      | true                  | Detects revisits by spatial proximity as well as by appearance.                                                 |
|                 | `Icp/VoxelSize`                              | 0.05 m                | Downsamples each scan before matching; matches the grid resolution.                                             |
|                 | `Icp/MaxCorrespondenceDistance`              | 0.3 m                 | Widened beyond the 0.1 m default; see Section 3.4.2.                                                            |
|                 | `Icp/Iterations` / `Icp/CorrespondenceRatio` | 30 / 0.1              | Converge inside the wider window; accept a match at 10% overlap.                                                |
|                 | `Icp/PointToPlane` / `PointToPlaneK`         | true / 20             | Point-to-plane converges faster on planar indoor geometry.                                                      |
| Visual features | Whole group                                  | defaults              | GFTT/BRIEF detector, 500 features per image, PnP with 20 minimum inliers, no depth cut-off; see the note below. |
| Markers         | `RGBD/MarkerDetection`                       | true                  | Inserts each detected marker into the graph as a landmark node.                                                 |
|                 | `Marker/Dictionary` / `Marker/Length`        | 0 (4×4) / 0.15 m      | The dictionary must match Section 3.5; the known size makes one detection yield a metric pose.                  |
| Robustness      | `RGBD/OptimizeMaxError`                      | 3.0                   | Rejects any candidate link whose optimization error would distort the graph.                                    |


The visual-feature group stays at its defaults. This is intentional, not accidental. These parameters balance recognition quality against processing load. Since mapping is offline, cost doesn't matter here. But once the settings run real-time, two of them deserve tuning first if processing gets tight. Lowering `Kp/MaxFeatures` directly cuts per-image cost. Capping Vis/MaxDepth removes the noisy far points from the RealSense, cutting cost while improving accuracy.

### 3.4.2 Loop Closure and Landmark Constraints

Two mechanisms correct the pose graph during mapping, both stored in the same map database. Geometric loop closure matches the current laser scan against stored geometry when the robot revisits an area, adding a constraint that cancels the drift accumulated since. ArUco markers add a second, independent constraint: each detected marker is inserted into the graph as a **landmark node**.

The ICP registration was tuned for this floor rather than left at its defaults. The correspondence search was widened from 0.1 m to 0.3 m to cover the drift accumulated between revisits, the iteration limit raised to 30 to converge inside that wider window, and the required overlap ratio lowered from 0.3 to 0.1 to accept a partially overlapping revisit. Matching also uses a 0.05 m voxel size, matching the grid resolution, and a point-to-plane metric with 20 neighbours per normal, which converges faster on planar indoor geometry. Each setting trades strictness for closure capability, admitting more false closures along with the true ones.

Geometric closure alone is not reliable here: identical tables at regular spacing and long flat walls make distinct locations look alike in the laser scan, and visual appearance is no steadier, since it shifts with lighting, occlusion, and the room being rearranged. Printed ArUco markers of known size, fixed at selected locations and detected inside the SLAM node, cover this gap. A marker's identity is decoded directly from its pattern, so recognizing it needs no threshold and cannot be confused with another place, and its known size yields a full relative pose from a single detection by solving PnP on the four corners. Its only limit is coverage: it helps only where a marker is installed and visible, so it supplements the geometric closure rather than replacing it. 

Looser registration admits more false closures, so `RGBD/OptimizeMaxError`, set to 3.0, guards every candidate link, loop, proximity, or landmark, rejecting any whose optimization error would distort the graph.

> 🖼️ **Figure 3.3 — Mapping pipeline.** Data-flow diagram: LiDAR scan, RGB and aligned depth images, and fused odometry entering the RTAB-Map node; three parallel constraint sources inside it (ICP on laser geometry, visual bag-of-words place recognition, ArUco landmark detection) feeding one pose graph; graph optimization; and the two outputs, the 2D occupancy grid and the saved map database containing the marker landmarks.
> 🖼️ **Figure 3.4 — Effect of loop closure.** The pose graph and the occupancy grid before and after a loop closure is accepted, with the corrected drift annotated. Screenshots from the real mapping run.

---



## 3.5 Localization and ArUco-Based Pose Correction

Localization answers where the robot is on the saved restaurant map while it moves. No single sensor provides both a smooth, high-rate pose and a position that stays correct over long distances, so the problem is handled in **two cooperating layers**:

1. **Local odometry** (Section 3.3) — wheel encoders fused with the IMU publish a fast `odom → base_footprint` estimate. It is accurate over short stretches and is what the motion controller tracks, but it drifts over time.
2. **Global localization** — RTAB-Map compares live LiDAR and camera data to the map built in Section 3.4 and publishes a slower `map → odom` correction that cancels that drift.

> 🖼️ **Figure 3.5 — Localization workflow.** Operator seeds pose at dock → RTAB-Map loads saved map → parallel cues (laser geometry, visual appearance, ArUco landmarks) refine pose → validated corrections update `map → odom`; EKF carries `odom → base_footprint` between updates.

### 3.5.1 How RTAB-Map Localizes

At run time, RTAB-Map reloads the **same pose graph** produced during the offline mapping session. The graph is read-only: no new places are added while the robot serves tables. The full graph is kept in memory so that the robot can relocalize anywhere on the floor, not only near where it was last seen.

The occupancy grid that Nav2 uses for global planning is republished from this graph while localization runs — there is no separate static map file served by another node in the deployed flow. Inputs match mapping: 2D laser scans for geometry, RGB-D frames for visual place recognition, and fused odometry as the backbone between nodes. Pose updates run at a **higher rate than during mapping** (5 Hz versus 2 Hz) so that corrections keep up with navigation.

When the environment looks repetitive — long straight walls, evenly spaced tables — laser matching alone can lock onto the wrong place. Visual appearance from the camera breaks that symmetry. **ArUco markers** at the dock and at tables add a third cue: each tag has a unique identity baked into the map as a landmark, so a single sighting can pull the estimate back toward a known position without an abrupt jump. Suspect matches are rejected when they would distort the graph or disagree sharply with recent odometry.

### 3.5.2 Startup

Before any navigation goal is accepted, the operator places the robot at the **kitchen dock** with the dock marker in view. Software then seeds localization at the dock pose stored in the shared floorplan (Section 3.6), sending the seed several times with a short pause so that the global transform stabilizes. The stack waits until a full `map → base_footprint` chain exists and Nav2 is ready. This replaces the manual “2D Pose Estimate” step in a visualization tool with a repeatable procedure tied to a physical landmark.

### 3.5.3 ArUco in the Pose Graph (vs Last-Metre Align)

During localization, detected ArUco tags are **not** applied as a hard reset of position. Each sighting becomes a soft **landmark constraint** in the pose graph: the optimizer weighs it against laser and odometry already in the graph, nudging the robot toward the surveyed marker location rather than teleporting it.

This is distinct from the **last-metre visual alignment** of Section 3.6.3. RTAB-Map marker handling corrects **global** drift on the map. The alignment phase after navigation only **rotates** the base so the tag is centred in the camera; it does not publish a new map pose. Together, the two stages address different errors at different scales.

Nav2 consumes localization through the standard transform chain:

$$
\texttt{map} \xrightarrow{\text{RTAB-Map}} \texttt{odom} \xrightarrow{\text{EKF}} \texttt{base\_footprint} \xrightarrow{\text{URDF}} \texttt{sensors}.
$$

The EKF owns the fast segment; RTAB-Map owns the slow global correction; the planner and controller see the result as a single pose.

---



## 3.6 Autonomous Navigation with Nav2

Navigation turns a table request into safe motion along the service lane. It consumes the map and pose estimates from Sections 3.3 and 3.5: a fixed occupancy grid in the `map` frame, a corrected `map → odom` transform, and fused wheel–IMU odometry for short-horizon tracking. Operationally, localization must already be running before the navigation stack starts; a depth-to-scan converter is then started alongside Nav2 so that near-field obstacles visible to the camera but not to the LiDAR plane can still be avoided locally.

The end-to-end workflow has four stages:

1. **Goal assignment** — the backend (Chapter 4) maps a business event such as “deliver to table 1” to an approach pose on the floorplan.
2. **Global planning** — Nav2 computes a path across the full map to that pose.
3. **Local execution** — a differential-drive controller follows the path while watching a rolling window around the robot for obstacles.
4. **Last-metre alignment** — after coarse arrival, the robot rotates in place until the table’s ArUco marker is centred in the camera; this step adjusts heading only and does not publish a new pose.

> 🖼️ **Figure 3.6 — Navigation workflow.** Floorplan goal → global path on the static map → local tracking with dual sensing → velocity smoothing → wheels; after arrival, optional marker search and in-place align.

### 3.6.1 Obstacle Perception for Navigation

The LiDAR sees a single horizontal slice of the world. Legs of furniture, low boxes, and overhanging table edges can sit above or below that slice and would be missed if navigation relied on laser alone. The depth camera therefore supplies a second, short-range “virtual scan” built from several rows of the depth image. That scan is trusted only over the near field where stereo depth is reliable.

The two scans are not treated equally everywhere. **Local** avoidance — what the robot might hit in the next few seconds — uses both laser and depth so that low or high obstacles in the lane are seen in time. **Global** planning — the route across the whole restaurant — uses laser only, because depth reaches only a few metres and would otherwise paint short-lived ghost obstacles onto a plan that must stay stable over the whole trip. Around every detected obstacle, an inflation band keeps the planned path and the executed trajectory away from walls and furniture. The robot is modelled with a slightly conservative footprint radius so that the planned clearance matches the physical base.

### 3.6.2 Goals, Planning, and Control

**Where goals come from.** Table and dock positions are not embedded in launch files. They live in one shared floorplan description used by the backend, the robot bridge, and the on-robot delivery logic, so every subsystem agrees on the same coordinates. Each destination stores two geometric ideas:

- the **marker** — where the printed ArUco tag sits on the map (for localization landmarks, the management minimap, and the alignment camera); and
- the **approach** — where Nav2 should drive to: a standoff point in front of the marker, facing it squarely.

The approach point is deliberately not the pose recorded when someone manually drove the robot to the table during surveying. The final alignment step can only rotate in place to centre the tag in the image; it cannot fix an oblique arrival. New destinations are therefore measured with a dedicated survey procedure that waits until localization is stable before recording coordinates.

**Global planning.** Given the approach pose, a grid-based planner searches for a least-cost path on the static map. Paths may cross cells marked unknown if necessary. A smoothing pass straightens the polyline before execution.

**Local control.** A sampling controller evaluates many short forward-and-turn commands each cycle, keeps only trajectories that stay collision-free on the local grid, and scores the rest for staying on the path, progressing toward the goal, and finishing with the correct heading. The base is forward-only with in-place rotation — matching the non-holonomic TWD constraint from Section 2.2. Commanded speeds are limited to a modest service speed suitable for an open tray, then passed through a smoother so that step changes in velocity do not excite wheel slip (which would disturb the odometry filter of Section 3.3).

**Arrival and recovery.** Declaring “goal reached” is intentionally a two-step idea: the controller must be allowed to rotate toward the final heading while the robot is still close to the goal, and only then may the stack report success. If progress stalls — for example because localization jitter briefly blocks the controller — Nav2’s behaviour tree can replan, spin in place, back up slightly, or wait before retrying. A progress watchdog abandons a goal if the robot stops moving for too long.

### 3.6.3 Last-Metre Visual Alignment

Nav2 delivers the robot to the neighbourhood of the approach pose. A separate alignment phase then squares the robot with the destination marker before the table is considered ready for customer interaction. This phase is **not** a second localization system: it sends rotation commands only and never overrides the map pose.

Typical sequence:

1. **Coarse arrival** — navigation ends when the robot is within the approach zone, or after a short grace period if the goal checker keeps adjusting position near the target.
2. **Settle and measure** — the robot pauses briefly while the camera checks whether the marker is already visible; arrival error is logged for evaluation in Chapter 5.
3. **Search (if needed)** — if the tag is out of view, the base performs a bounded in-place sweep until the marker appears or the search budget expires.
4. **Align** — proportional rotation drives the horizontal offset of the tag in the image toward zero. Alignment stops when the tag is centred, when the marker is lost for several seconds, or when a shared time budget for the whole post-arrival phase runs out.

If alignment does not finish in time, the robot keeps its current heading and reports arrival anyway. Waiting indefinitely at a occupied table is worse than serving from a slightly imperfect heading. The alignment step can be switched off during experiments that measure pure navigation error without visual correction.

> 🖼️ **Figure 3.7 — Approach vs marker geometry.** Top view: marker in front of the table, standoff approach on the normal, and final in-place rotation to face the tag.

---

