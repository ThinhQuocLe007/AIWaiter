## 5.3 ROS 2 Navigation Experiments

Four experiments were designed against the robot control and localisation stack of Chapter 3: the accuracy
of EKF-fused odometry over repeated service cycles, the quality and queryability of the RTAB-Map
environment map, navigation success and ArUco docking precision on the kitchen-to-table route across six
tables, and goal switching when the backend issues a second destination while the robot is already in
motion. The last addresses the integration gap of §2.2.5, where a waypoint is chosen by an external system
reacting to a live business event rather than by an operator.

None were run. They require the assembled robot operating in the mapped service environment, and that
hardware time was not available within the period covered by this report. The corresponding objectives are
recorded as not evaluated in §5.6.1 rather than as unmet, and the protocols are carried into Chapter 6 so
the measurements can be taken without redesign.

The dispatch half of the last experiment is exercised in §5.5, where a task reaches a robot over its
WebSocket connection and the resulting state transitions complete, with a mock robot in place of the
physical one. What remains unmeasured is physical execution: whether the robot reaches the table, how
accurately it docks, and how much odometry drift accumulates over a service shift.
