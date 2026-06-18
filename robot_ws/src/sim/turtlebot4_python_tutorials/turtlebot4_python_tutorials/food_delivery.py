#!/usr/bin/env python3

# Copyright 2023 Clearpath Robotics, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @author Hilary Luo (hluo@clearpathrobotics.com)
# Modified: Restaurant world — ArUco-assisted mail delivery
#
# Logic:
#   1. On spawn: set init to the fixed spawn pose (the simulation is
#      deterministic). Enable the camera to scan the dock ArUco marker
#      (ID 0). If it is not visible, rotate once to search for it; if it
#      is found, align with it and keep init = spawn.
#   2. Select a table: Nav2/AMCL sends the robot to the table approach
#      pose and stops. No ArUco scanning at the table yet.
#   3. Return to Dock: Nav2 sends the robot back to the spawn pose and
#      stops. No ArUco scanning at the dock yet.
#
# Heading convention (restaurant map):
#   yaw 0   = NORTH = +X       yaw 90  = WEST  = +Y
#   yaw 180 = SOUTH = -X       yaw 270 = EAST  = -Y

import math
import threading
import time

import cv2
from cv_bridge import CvBridge

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from geometry_msgs.msg import Twist
from sensor_msgs.msg import Image

from turtlebot4_navigation.turtlebot4_navigator import (
    TurtleBot4Directions,
    TurtleBot4Navigator,
)

# ============================================================
# CONFIG — matches the saved SLAM map frame
# ============================================================
SPAWN_POSE = [0.0, 0.0]
# If the SLAM map was started with the robot at spawn and facing the dock marker,
# that spawn direction becomes yaw=0 in the saved map frame.
SPAWN_HEADING = TurtleBot4Directions.NORTH

ARUCO_DICT_TYPE = cv2.aruco.DICT_4X4_50
CAMERA_TOPIC = '/oakd/rgb/preview/image_raw'
CMD_VEL_TOPIC = '/cmd_vel'

DOCK_MARKER_ID = 0

# Each destination: marker_id + hallway approach pose (facing the marker).
# The robot stands ~0.55 m from the wall and faces the marker so the camera can see it.
DESTINATIONS = {
    'Table 1': {'id': 1, 'approach': ([7.99985, 1.36319], TurtleBot4Directions.SOUTH)},
    'Table 2': {'id': 2, 'approach': ([8.05419, 0.33537], TurtleBot4Directions.NORTH)},
    'Table 3': {'id': 3, 'approach': ([7.97830, -0.64879], TurtleBot4Directions.SOUTH)},
    'Table 4': {'id': 4, 'approach': ([7.92656, -3.28752], TurtleBot4Directions.SOUTH)},
    'Table 5': {'id': 5, 'approach': ([7.98864, -4.28860], TurtleBot4Directions.NORTH)},
    'Table 6': {'id': 6, 'approach': ([8.00802, -5.27848], TurtleBot4Directions.SOUTH)},
}

# Dock approach point in the saved SLAM map frame.
DOCK_APPROACH = ([0.0, 0.0], TurtleBot4Directions.NORTH)
DOCK_BACKUP_DIST = 0.0             # dock approach already matches the spawn pose

# ---- Search / alignment parameters ----
DETECT_MAX_AGE = 1.0               # seconds — ignore stale detections
SEARCH_ANGULAR_SPEED = 0.45        # rad/s while rotating to search 360°
SEARCH_TIMEOUT = 2 * math.pi / SEARCH_ANGULAR_SPEED + 6.0

ALIGN_KP_ANG = 1.3                 # angular P-gain (using normalized error [-1,1])
ALIGN_MAX_ANG = 0.5                # rad/s
ALIGN_FWD_SPEED = 0.10             # m/s while moving closer
ALIGN_CENTER_TOL = 0.06            # |e| < tol means the robot is aligned
ALIGN_FWD_GATE = 0.20              # only move forward when |e| < gate (avoid drifting sideways)
ALIGN_STOP_WIDTH = 0.34            # marker width >= 34% of the frame means close enough
ALIGN_TIMEOUT = 30.0
ALIGN_LOST_TIMEOUT = 2.5           # stop aligning if the marker is lost for too long
TABLE_BACKUP_DIST = 0.28           # back up so the guest can interact at the table edge


class ArucoTracker(Node):
    """Track ArUco markers from the OAK-D camera and store the latest detection by ID."""

    def __init__(self):
        super().__init__('aruco_tracker')
        self.bridge = CvBridge()
        self._lock = threading.Lock()
        # id -> (cx, cy, bbox_w, bbox_h, img_w, img_h, stamp)
        self._markers = {}

        self.aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)
        self.aruco_params = cv2.aruco.DetectorParameters_create()

        self.create_subscription(
            Image, CAMERA_TOPIC, self._image_cb, qos_profile_sensor_data)
        self.get_logger().info(f'[ArUco] Subscribed: {CAMERA_TOPIC}')

    def _image_cb(self, msg: Image):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:  # noqa: BLE001
            self.get_logger().warn(f'[ArUco] cv_bridge error: {e}')
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.aruco_params)

        if ids is None or len(ids) == 0:
            return

        h, w = gray.shape[:2]
        now = time.time()
        with self._lock:
            for marker_corners, marker_id in zip(corners, ids.flatten()):
                pts = marker_corners.reshape(4, 2)
                xs, ys = pts[:, 0], pts[:, 1]
                cx, cy = float(xs.mean()), float(ys.mean())
                bbox_w = float(xs.max() - xs.min())
                bbox_h = float(ys.max() - ys.min())
                self._markers[int(marker_id)] = (
                    cx, cy, bbox_w, bbox_h, w, h, now)

    def get_marker(self, marker_id: int, max_age: float = DETECT_MAX_AGE):
        """Return marker info if the detection is still fresh; otherwise return None."""
        with self._lock:
            data = self._markers.get(marker_id)
        if data is None:
            return None
        cx, cy, bw, _bh, iw, _ih, stamp = data
        if time.time() - stamp > max_age:
            return None
        return {
            'err_x': (cx - iw / 2.0) / (iw / 2.0),   # [-1,1], >0 means shifted right
            'width_ratio': bw / iw,
            'cx': cx, 'cy': cy,
        }

    def visible_ids(self, max_age: float = DETECT_MAX_AGE):
        now = time.time()
        with self._lock:
            return [mid for mid, d in self._markers.items()
                    if now - d[6] <= max_age]


def _stop(cmd_pub):
    cmd_pub.publish(Twist())


def _run_nav_primitive(nav: TurtleBot4Navigator):
    """Wait for a Nav2 action (spin/backup/goToPose) to finish."""
    while not nav.isTaskComplete():
        time.sleep(0.1)


def search_marker_360(nav, tracker, cmd_pub, marker_id) -> bool:
    """Rotate in place up to one full turn while searching for marker_id."""
    nav.info(f'[Search] Marker {marker_id} not visible — rotating once to search...')
    twist = Twist()
    twist.angular.z = SEARCH_ANGULAR_SPEED
    t0 = time.time()
    while rclpy.ok() and (time.time() - t0) < SEARCH_TIMEOUT:
        cmd_pub.publish(twist)
        rclpy.spin_once(tracker, timeout_sec=0.02)
        if tracker.get_marker(marker_id) is not None:
            _stop(cmd_pub)
            nav.info(f'[Search] Found marker {marker_id}.')
            return True
        time.sleep(0.03)
    _stop(cmd_pub)
    nav.warn(f'[Search] Completed one turn but still did not find marker {marker_id}.')
    return False


def visual_align(nav, tracker, cmd_pub, marker_id,
                 approach: bool = True) -> bool:
    """
    P-controller on /cmd_vel: rotate to center the marker in the frame and,
    optionally, move closer until the marker is large enough. Return True if
    alignment succeeds.
    """
    nav.info(f'[Align] Aligning with marker {marker_id} '
             f'({"move closer" if approach else "rotate only"})...')
    t0 = time.time()
    last_seen = time.time()
    last_err = 0.0

    while rclpy.ok():
        if time.time() - t0 > ALIGN_TIMEOUT:
            _stop(cmd_pub)
            nav.warn('[Align] Timed out — stopping alignment.')
            return False

        rclpy.spin_once(tracker, timeout_sec=0.02)
        m = tracker.get_marker(marker_id)
        twist = Twist()

        if m is None:
            # Lost marker: slowly rotate toward the last seen direction to reacquire it.
            if time.time() - last_seen > ALIGN_LOST_TIMEOUT:
                _stop(cmd_pub)
                nav.warn(f'[Align] Marker {marker_id} was lost for too long.')
                return False
            twist.angular.z = math.copysign(0.25, -last_err) \
                if abs(last_err) > 1e-3 else 0.25
            cmd_pub.publish(twist)
            time.sleep(0.03)
            continue

        last_seen = time.time()
        err = m['err_x']
        last_err = err
        width = m['width_ratio']

        centered = abs(err) < ALIGN_CENTER_TOL
        close_enough = width >= ALIGN_STOP_WIDTH

        if centered and (not approach or close_enough):
            _stop(cmd_pub)
            nav.info(f'[Align] Done: err={err:+.3f}, '
                     f'width={width:.2f}.')
            return True

        # Rotate: marker shifted right (err>0) -> turn right (angular.z < 0).
        twist.angular.z = max(-ALIGN_MAX_ANG,
                              min(ALIGN_MAX_ANG, -ALIGN_KP_ANG * err))
        # Move forward only when roughly aligned and not close enough yet.
        if approach and abs(err) < ALIGN_FWD_GATE and not close_enough:
            twist.linear.x = ALIGN_FWD_SPEED

        cmd_pub.publish(twist)
        time.sleep(0.03)

    _stop(cmd_pub)
    return False


def goto_approach(nav, position, heading):
    """Send the robot to an approach pose using Nav2/AMCL."""
    nav.clearAllCostmaps()
    time.sleep(0.5)
    pose = nav.getPoseStamped(position, heading)
    nav.startToPose(pose)


# ============================================================
# Main phases
# ============================================================
def startup_sequence(nav, tracker, cmd_pub):
    nav.info('═══════════════════════════════════════════════')
    nav.info('[STARTUP] Set init to the fixed spawn pose.')
    nav.info(f'  spawn: x={SPAWN_POSE[0]}, y={SPAWN_POSE[1]}, '
             f'heading={SPAWN_HEADING.name}')
    nav.info('═══════════════════════════════════════════════')

    nav.setInitialPose(nav.getPoseStamped(SPAWN_POSE, SPAWN_HEADING))
    nav.waitUntilNav2Active()
    nav.info('Nav2 ACTIVE. Enabling camera scan for the dock ArUco marker (ID 0)...')

    # Scan the first few frames to check whether the dock marker is visible.
    seen = False
    t0 = time.time()
    while time.time() - t0 < 3.0:
        rclpy.spin_once(tracker, timeout_sec=0.05)
        if tracker.get_marker(DOCK_MARKER_ID) is not None:
            seen = True
            break

    if not seen:
        if search_marker_360(nav, tracker, cmd_pub, DOCK_MARKER_ID):
            seen = True

    if seen:
        visual_align(nav, tracker, cmd_pub, DOCK_MARKER_ID, approach=False)
        nav.info('[STARTUP] Dock confirmed — alignment complete.')
    else:
        nav.warn('[STARTUP] Could not confirm the dock with the camera. '
                 'Keeping init = spawn (the simulation is deterministic).')

    # The robot only rotates in place, so its position does not change; keep init = spawn.
    nav.setInitialPose(nav.getPoseStamped(SPAWN_POSE, SPAWN_HEADING))
    nav.info('[STARTUP] Complete. Ready to receive delivery commands.')


def deliver_to(nav, name):
    dest = DESTINATIONS[name]
    marker_id = dest['id']
    position, heading = dest['approach']

    nav.info(f'── Delivering to {name} (ArUco ID {marker_id}) ──')
    goto_approach(nav, position, heading)
    _run_nav_primitive(nav)
    nav.info(f'[{name}] Arrived at approach point. Delivery complete.')


def return_to_dock(nav):
    position, heading = DOCK_APPROACH
    nav.info('── Returning to Dock ──')
    goto_approach(nav, position, heading)
    _run_nav_primitive(nav)
    nav.setInitialPose(nav.getPoseStamped(SPAWN_POSE, SPAWN_HEADING))
    nav.info('[Dock] Returned to the spawn pose. Complete.')


def main(args=None):
    rclpy.init(args=args)

    nav = TurtleBot4Navigator()
    tracker = ArucoTracker()
    cmd_pub = nav.create_publisher(Twist, CMD_VEL_TOPIC, 10)

    try:
        startup_sequence(nav, tracker, cmd_pub)

        names = list(DESTINATIONS.keys())
        menu = names + ['Return to Dock', 'Exit']

        nav.info('Welcome to the restaurant delivery service.')
        while rclpy.ok():
            opts = 'Choose a destination (enter a number):\n'
            for i, label in enumerate(menu):
                opts += f'    {i}. {label}\n'
            raw = input(f'{opts}Selection: ')

            try:
                idx = int(raw)
            except ValueError:
                nav.error(f'Invalid selection: {raw}')
                continue

            if idx < 0 or idx >= len(menu):
                nav.error(f'Out of range: {idx}')
                continue

            choice = menu[idx]
            if choice == 'Exit':
                break
            elif choice == 'Return to Dock':
                return_to_dock(nav)
            else:
                deliver_to(nav, choice)

    except KeyboardInterrupt:
        nav.info('Interrupted by user.')
    finally:
        _stop(cmd_pub)
        tracker.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
