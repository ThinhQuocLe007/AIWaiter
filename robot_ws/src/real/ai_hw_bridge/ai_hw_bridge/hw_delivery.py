"""hw_delivery — motion SEAM for the AI Waiter real-robot task bridge.

⚠️  NAVIGATION IS OUT OF SCOPE HERE. The real Nav2 + RTAB-Map + ArUco motion is merged
    from the tarkbot workspace by whoever owns navigation. This module only provides the
    minimal surface ``task_bridge`` imports, so the DATA-SYNC path (WS role=robot +
    battery/pose heartbeats + task lifecycle) can be built and tested on the web BEFORE
    real motion exists.

Public surface (same names as the sim's food_delivery, so task_bridge stays a copy of
the sim bridge):
    NavigatorReal, ArucoTracker, CMD_VEL_TOPIC, DESTINATIONS,
    startup_sequence(nav, tracker, cmd_pub)
    deliver_to(nav, name, tracker, cmd_pub)     # STUB — nav owner replaces with tarkbot Nav2
    return_to_dock(nav, tracker, cmd_pub)       # STUB — nav owner replaces with tarkbot Nav2

What is REAL here (data-sync, not navigation):
    * ArucoTracker keeps a live TF buffer → task_bridge reads map->base_link for heartbeat.
What is STUB (navigation owner fills from tarkbot):
    * deliver_to / return_to_dock — currently just log + return (arrived fires immediately),
      which lets the web binding + task lifecycle be exercised without a map. Replace with
      Nav2 NavigateToPose(approach pose) + ArUco align.
    * DESTINATIONS waypoints, SPAWN_POSE — measured on the real map later (nav-merge §3.1).
    * ArucoTracker.get_marker — marker detect/align (nav owner).
"""

import rclpy
from rclpy.node import Node
import tf2_ros

CMD_VEL_TOPIC = '/cmd_vel'

# Table -> ArUco marker id (used by the nav owner's real deliver_to). Waypoints intentionally
# omitted here — they belong with the real Nav2 motion measured on the restaurant map.
DESTINATIONS = {
    'Table 1': {'id': 1},
    'Table 2': {'id': 2},
    'Table 3': {'id': 3},
    'Table 4': {'id': 4},
    'Table 5': {'id': 5},
    'Table 6': {'id': 6},
}


class NavigatorReal(Node):
    """Placeholder navigator node. The nav owner swaps this for a Nav2 BasicNavigator
    (nav2_simple_commander) subclass. Kept as a plain Node so the bridge builds/runs for
    data-sync testing without pulling in the Nav2 stack."""

    def __init__(self):
        super().__init__('ai_hw_navigator')

    def info(self, msg):
        self.get_logger().info(msg)

    def warn(self, msg):
        self.get_logger().warn(msg)


class ArucoTracker(Node):
    """Owns the live TF buffer for task_bridge's heartbeat. Marker detection is the nav
    owner's job — ``get_marker`` returns None until that is wired."""

    def __init__(self):
        super().__init__('aruco_tracker')
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self._correction_target = None
        self.get_logger().info('[ArUco] tracker up (TF live; marker detect = nav owner TODO)')

    def get_marker(self, marker_id):
        return None

    def set_correction_target(self, marker_id):
        self._correction_target = marker_id

    def clear_correction_target(self):
        self._correction_target = None


# ─────────────────────────────────────── motion stubs (nav owner replaces from tarkbot)
def startup_sequence(nav, tracker, cmd_pub):
    """Nav owner: set initial pose + wait for Nav2 active (RTAB-Map localizer)."""
    nav.info('[STARTUP] motion stub — Nav2 bring-up is the nav owner\'s job. Ready.')


def deliver_to(nav, name, tracker, cmd_pub):
    """STUB: no real motion. Returns immediately so task_bridge reports `arrived` and the
    web binding/lifecycle can be tested. Nav owner replaces with Nav2 approach + ArUco align."""
    nav.info(f'[STUB] deliver_to({name}) — no motion (nav not wired). Reporting arrival.')


def return_to_dock(nav, tracker, cmd_pub):
    """STUB: no real motion. Nav owner replaces with Nav2 drive-to-dock + ArUco align."""
    nav.info('[STUB] return_to_dock — no motion (nav not wired).')
