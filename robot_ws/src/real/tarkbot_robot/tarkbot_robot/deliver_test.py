#!/usr/bin/env python3

"""Field-test Nav2 + visual align without the web dispatcher.

Demo convention: **Table 1** (ArUco 1) = dining table; **dock** (ArUco 6) = home.
On startup, ``startup_sequence`` publishes ``/initialpose`` at the dock — always place the
robot at dock (ArUco 6) before launching.

Prefer the all-in-one launch (loc → Nav2 → this node)::

    ros2 launch tarkbot_robot deliver_test.launch.py
    ros2 launch tarkbot_robot deliver_test.launch.py return_dock:=true

Or run alone after localization + Nav2 are already up::

    ros2 run tarkbot_robot deliver_test --ros-args -p table_id:=1
    ros2 run tarkbot_robot deliver_test --ros-args -p table_id:=1 -p return_dock:=true
"""

from __future__ import annotations

import rclpy
from geometry_msgs.msg import Twist
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from tarkbot_robot.visual_delivery import (
    ArucoTracker,
    CMD_VEL_TOPIC,
    DESTINATIONS,
    NavigatorReal,
    deliver_to,
    load_floorplan,
    return_to_dock,
    startup_sequence,
)


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


class DeliverTestNode(Node):
    def __init__(self):
        super().__init__('deliver_test')
        self.declare_parameter('table_id', 1)
        self.declare_parameter('return_dock', False)
        self.declare_parameter('floorplan_path', '')


def main(args=None):
    rclpy.init(args=args)
    helper = DeliverTestNode()
    table_id = int(helper.get_parameter('table_id').value)
    return_dock = _as_bool(helper.get_parameter('return_dock').value)
    floorplan_path = str(helper.get_parameter('floorplan_path').value).strip()

    if floorplan_path:
        path = load_floorplan(floorplan_path)
    else:
        path = load_floorplan()
    helper.get_logger().info(f'Floorplan: {path}')
    helper.get_logger().info(
        'Demo: Table 1 = service table (ArUco 1); dock = ArUco 6.')

    name = f'Table {table_id}'
    if name not in DESTINATIONS:
        helper.get_logger().error(
            f'Unknown {name}. Known: {sorted(DESTINATIONS)}. Demo table: 1.')
        helper.destroy_node()
        rclpy.shutdown()
        return

    nav = NavigatorReal()
    tracker = ArucoTracker()
    cmd_pub = helper.create_publisher(Twist, CMD_VEL_TOPIC, 10)

    executor = MultiThreadedExecutor()
    executor.add_node(helper)
    executor.add_node(tracker)
    # NavigatorReal must NOT be added — BasicNavigator spins itself.

    import threading
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    try:
        startup_sequence(nav, tracker, cmd_pub)
        helper.get_logger().info(f'Delivering to {name}…')
        ok = deliver_to(nav, name, tracker, cmd_pub)
        if not ok:
            helper.get_logger().error(f'{name}: Nav2 failed — not returning to dock.')
        else:
            helper.get_logger().info(f'{name}: done (align finished or skipped).')
            if return_dock:
                helper.get_logger().info('Returning to dock (ArUco 6)…')
                return_to_dock(nav, tracker, cmd_pub)
    finally:
        executor.shutdown()
        helper.destroy_node()
        tracker.destroy_node()
        nav.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
