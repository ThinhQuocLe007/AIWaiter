# 2.1 Overview of Mobile Robots

A mobile robot is a robot that can move around on its own to do a task, unlike a fixed robot arm that always stays in one place. Because it has to move, a mobile robot needs a way to drive its wheels and a way to sense where it is going. The kind of wheels and drive it uses decides how it moves, how it is controlled, and how hard it is to build.

Wheeled robots are usually grouped into three main drive mechanisms [n]:

Differential drive: the wheels on the left and right side are each driven by their own motor, with one or more free caster wheels for support. The robot moves by changing the speed of each side: same speed on both sides makes it go straight, different speeds make it turn, and equal but opposite speeds make it spin in place. This mechanism is simple to build and control.

Ackermann steering: this mechanism works like a car, where the front wheels turn to steer while the rear wheels drive the robot forward. It runs smoothly at higher speed but cannot spin in place, and it needs some open space to turn around.

Omnidirectional drive: special wheels, each turned at an angle around the body, let the robot move in any direction and spin at the same time, without needing to turn first. This freedom of movement comes with a more complex mechanical design and control compared to a differential-drive robot.

> Figure 2.1 — [Common types of wheeled mobile robots] (top-view sketch of the three drive mechanisms above; drawn by the group; caption + source [n]).

Based on how they move, wheeled robots are also put into two groups. A robot that can move in any direction at any moment, including straight sideways, is called holonomic, the omnidirectional - drive robot above is an example. A robot that cannot move sideways and can only move along the direction it is facing while turning is called non-holonomic, the differential - drive and Ackermann - steering robots above are examples. For a non - holonomic robot, the sideways speed in its own body frame is always zero:

This limit has to be taken into account when building the robot's motion model and when planning how it moves.

No matter which drive type is used, a robot that moves around indoors by itself usually follows the same five steps [n]:

Perception: reading data from sensors such as LiDAR, camera, IMU, and wheel encoders to understand the surroundings and its own motion.

Localization: figuring out where the robot is and which way it is facing.

Mapping: building a map of the surroundings, either beforehand or at the same time as localization (SLAM).

Planning: working out a safe path from where the robot is now to where it needs to go.

Control: turning that path into actual wheel speeds, in a way the robot's drive type can actually do.

> Figure 2.2 — [Steps of indoor autonomous navigation] (block diagram: perception → localization → mapping → planning → control; drawn by the group).

