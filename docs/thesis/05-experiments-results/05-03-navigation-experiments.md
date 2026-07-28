## 5.3 ROS 2 Navigation Experiments

The navigation experiments planned for this section evaluate the robot control and localisation
stack described in Chapter 3: the accuracy of EKF-fused odometry over repeated service cycles,
the quality and queryability of the RTAB-Map environment map, navigation success and ArUco
docking precision on the kitchen-to-table route, and the coupling between backend-issued
navigation goals and the robot's execution of them.

These experiments require the assembled robot operating in the mapped service environment, and
that hardware time was not available within the period covered by this report. No navigation
results are therefore presented here, and the corresponding objectives are recorded as not
evaluated in the scorecard in §5.6.1 rather than being reported as unmet.

The experimental design is fixed and is stated here so that the measurements can be carried out
without redesign.

**Odometry accuracy.** Ten to twenty return trips over the kitchen to table to kitchen route, at
varied table distances, recording the filtered odometry topic and comparing the start and end
pose. Metrics: return-to-start error in centimetres and root-mean-square trajectory error against
ground truth. Ablation: encoder-only against EKF-fused, with and without IMU yaw. This validates
the odometry requirement in §3.1 and addresses the gap identified in §2.2.2, where prior work
validates sensor fusion in laboratory conditions rather than across repeated service cycles whose
cumulative drift must stay bounded for the docking marker to remain detectable.

**Map building and localisation.** One offline mapping run followed by localisation-only runs,
measuring loop closure events, localisation drift over time and map resolution. Beyond map
quality, the experiment must verify that the map is queryable as navigation infrastructure by an
external system: that the backend can resolve a table identifier to a waypoint pose and can
resolve the dock pose. That queryability, rather than map accuracy alone, is the gap identified
in §2.2.4.

**Navigation and docking.** Five to ten trials per table across six tables, sending a navigation
goal, driving, re-localising against the ArUco marker on final approach, and measuring the
resulting pose. Metrics: navigation success rate, docking error in centimetres and degrees, and
marker detection rate. Ablation: with and without ArUco correction on the final approach, which
isolates the contribution of the marker over SLAM localisation alone.

**Dynamic goal assignment.** Ten sequences in which the backend issues a navigation goal, the
robot begins executing it, and a second goal is issued mid-route. Metrics: goal switch latency
and correct arrival at the revised destination. This is the experiment that addresses the central
integration gap identified in §2.2.5, where navigation stacks reliably drive to a waypoint but
the waypoint is chosen by an operator or a fixed schedule rather than by an external system
reacting to live business events.

The infrastructure these experiments depend on is exercised in §5.5.2, where the dispatcher
assigns a task to a robot over its WebSocket connection and tracks the resulting state
transitions through to completion with a mock robot in place of the physical one. What remains
unmeasured is the physical execution: whether the robot reaches the table, how accurately it
docks, and how much odometry drift accumulates over a service shift.
