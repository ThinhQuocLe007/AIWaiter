# 2.2 Kinematic Model of the Two-Wheel Differential Drive Robot

The robot studied in this thesis is a small indoor service robot for a restaurant. Its job is to move to each table and interact with customers there, letting them place their orders by voice, moving on a flat floor along narrow aisles between tables. This means it has to make short trips, turn to face a table, and stop in a tight space, but it never needs to move sideways. Looking back at the drive types above, Ackermann steering is not a good fit here, since it cannot turn on the spot and needs open space to turn around. Omnidirectional drive could move sideways, but that ability is not needed for this task, and it would add cost and mechanical complexity for nothing. Differential drive, on the other hand, can turn on the spot to face a table, is simple and cheap to build, and is easy to model and control. For these reasons, the two-wheel differential drive (TWD) is chosen as the drive type for the robot in this thesis, and the rest of this section builds its kinematic model.

The kinematic model links the speed of the two wheels to the motion of the whole robot, in two directions. The inverse model turns a target robot velocity into wheel-speed commands, which is what the robot's controller needs to carry out a velocity command. The forward model turns measured wheel speeds back into robot motion, which is the basis of wheel odometry.

The robot has two wheels of equal size, mounted on the same axle on the left and right of the body. One or more free caster wheels support the robot without limiting its motion. Each driven wheel is powered on its own, so the robot moves only from the speed difference between the two wheels. If both wheels turn at the same speed, the robot goes straight. If they turn at different speeds, it follows a curve. If they turn at the same speed but in opposite directions, the robot spins in place, turning around the middle point of the axle. This middle point, called , is used as the robot's reference point.

> Figure 2.3 — [Top-view geometry of the differential drive] *(the group's own redrawn figure: turning centre and reference point , wheel track , left/right wheel speeds , body-frame vectors , turning radius , arc paths , and turn angle ; caption + cited source `[n]`).*

Table 2.1 lists the symbols used in this section.

A differential drive robot cannot move straight sideways. In the robot's own frame, the sideways speed is always zero:

This is called a non-holonomic constraint. It means the robot can only move along the direction it is facing while it turns, so this limit must be kept in mind in both the kinematic model and the motion planning that comes later.

When the robot follows a curve, both wheels and the point turn about the same centre with the same turning rate , but each one moves along a circle of a different radius. The left wheel moves on radius , the right wheel on , and point on radius . In a time the robot turns through an angle . Since angle = arc length / radius, and all three points share the same angle :

where , , and are the distances travelled by the left wheel, the point , and the right wheel. Dividing by gives the same relation for the speeds:

and from this the turning radius is simply

Solving the relations above for each wheel speed gives the speeds needed to reach a target forward speed and turning rate :

This is what the base controller uses when it receives a velocity command. The other way round, if the wheel speeds are known, the robot's forward speed and turning rate are found by adding and subtracting the two equations above:

Together with , these two results fully describe how the robot moves in the plane, and they are the basis of wheel odometry.

