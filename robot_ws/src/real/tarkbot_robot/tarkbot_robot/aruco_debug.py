#!/usr/bin/env python3

"""
ArUco debug-image node for the real TarkBot.

Purpose: VISUALIZATION ONLY. It detects ArUco markers in the RealSense color
stream, draws the detected markers/IDs, and republishes the annotated frame on
``/aruco_debug_image`` so it can be inspected in RViz2 (Image display).

Pose correction itself is handled by RTAB-Map's native marker detection
(RGBD/MarkerDetection), configured in rtabmap_localization_params.yaml — this
node does NOT publish any pose / initialpose and does not touch localization.

Detection is throttled (see PUBLISH_RATE_HZ) to keep CPU usage low.
"""

import numpy as np

import cv2
from cv_bridge import CvBridge

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import Image, CameraInfo

# Must match the mapping / localization config (Marker/Dictionary '0').
ARUCO_DICT_TYPE = cv2.aruco.DICT_4X4_50
# Marker side length in meters — keep in sync with Marker/Length in the RTAB-Map
# config. Only used here to scale the drawn pose axes.
MARKER_LENGTH = 0.15
CAMERA_TOPIC = '/camera/camera/color/image_raw'
CAMERA_INFO_TOPIC = '/camera/camera/color/camera_info'
DEBUG_IMAGE_TOPIC = '/aruco_debug_image'

# Throttle detection/publish rate (Hz). Camera streams at 15 Hz; 10 Hz keeps
# the debug view smooth without wasting CPU.
PUBLISH_RATE_HZ = 10.0


def _make_detector(aruco_dict):
    """Build an ArUco detector compatible with both old and new OpenCV APIs."""
    if hasattr(cv2.aruco, 'ArucoDetector'):
        # OpenCV >= 4.7
        params = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(aruco_dict, params)
        return lambda gray: detector.detectMarkers(gray)
    # OpenCV < 4.7
    params = cv2.aruco.DetectorParameters_create()
    return lambda gray: cv2.aruco.detectMarkers(gray, aruco_dict, parameters=params)


class ArucoDebugNode(Node):
    def __init__(self):
        super().__init__('aruco_debug')

        self.bridge = CvBridge()
        self.camera_matrix = None
        self.dist_coeffs = None
        self._have_info = False

        if hasattr(cv2.aruco, 'getPredefinedDictionary'):
            self.aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)
        else:
            self.aruco_dict = cv2.aruco.Dictionary_get(ARUCO_DICT_TYPE)
        self._detect = _make_detector(self.aruco_dict)

        # 3D corner model (marker frame) for solvePnP, used to draw pose axes.
        half = MARKER_LENGTH / 2.0
        self.obj_pts = np.array([
            [-half,  half, 0.0],
            [ half,  half, 0.0],
            [ half, -half, 0.0],
            [-half, -half, 0.0],
        ], dtype=np.float32)

        self._min_period = 1.0 / PUBLISH_RATE_HZ if PUBLISH_RATE_HZ > 0 else 0.0
        self._last_proc = self.get_clock().now()
        self._last_ids: list[int] | None = None  # log only when the visible set changes

        self.create_subscription(
            CameraInfo, CAMERA_INFO_TOPIC, self._camera_info_cb, qos_profile_sensor_data)
        self.create_subscription(
            Image, CAMERA_TOPIC, self._image_cb, qos_profile_sensor_data)

        self.debug_pub = self.create_publisher(Image, DEBUG_IMAGE_TOPIC, 10)

        self.get_logger().info(
            f'ArUco debug node up. Sub: {CAMERA_TOPIC} | Pub: {DEBUG_IMAGE_TOPIC} '
            f'@ {PUBLISH_RATE_HZ:.0f} Hz (visualization only).')

    def _camera_info_cb(self, msg: CameraInfo):
        if not self._have_info:
            self.camera_matrix = np.array(msg.k).reshape((3, 3))
            self.dist_coeffs = np.array(msg.d)
            self._have_info = True
            self.get_logger().info('Received CameraInfo.')

    def _image_cb(self, msg: Image):
        # Throttle to PUBLISH_RATE_HZ.
        now = self.get_clock().now()
        if self._min_period > 0.0:
            dt = (now - self._last_proc).nanoseconds * 1e-9
            if dt < self._min_period:
                return
        self._last_proc = now

        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().warn(f'cv_bridge error: {e}')
            return

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self._detect(gray)

        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(frame, corners, ids)
            for i in range(len(ids)):
                marker_id = int(ids[i][0])
                c = corners[i][0]
                xs, ys = c[:, 0], c[:, 1]
                cv2.putText(frame, f'id={marker_id}',
                            (int(xs.min()), max(20, int(ys.min()) - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

                # Draw 3D pose axes (needs camera intrinsics).
                if self._have_info:
                    ok, rvec, tvec = cv2.solvePnP(
                        self.obj_pts, c, self.camera_matrix, self.dist_coeffs)
                    if ok:
                        axis_len = MARKER_LENGTH * 0.5
                        if hasattr(cv2, 'drawFrameAxes'):
                            cv2.drawFrameAxes(
                                frame, self.camera_matrix, self.dist_coeffs,
                                rvec, tvec, axis_len)
                        else:
                            cv2.aruco.drawAxis(
                                frame, self.camera_matrix, self.dist_coeffs,
                                rvec, tvec, axis_len)
            # Only on CHANGE — logging every frame at camera rate drowns the console
            # (the annotated image on /aruco_debug_image is the real per-frame view).
            id_list = sorted({int(x[0]) for x in ids})
            if id_list != self._last_ids:
                self.get_logger().info(f'Detected ArUco IDs: {id_list}')
                self._last_ids = id_list
        elif self._last_ids is not None:
            self.get_logger().info('ArUco IDs: none in view')
            self._last_ids = None

        try:
            debug_msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            debug_msg.header = msg.header
            self.debug_pub.publish(debug_msg)
        except Exception as e:
            self.get_logger().warn(f'Publish debug image error: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = ArucoDebugNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
