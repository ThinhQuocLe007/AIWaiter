"""Shared helpers for Chapter 5 evaluate scripts: run dirs, pose snapshots, stats."""

from __future__ import annotations

import json
import math
import os
import statistics
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.time import Time
import tf2_ros
from tf2_ros import TransformException

from tarkbot_robot.visual_delivery import (
    ArucoTracker,
    BASE_FRAME,
    CMD_VEL_TOPIC,
    MAP_FRAME,
    NavigatorReal,
    deliver_to,
    load_floorplan,
    return_to_dock,
    startup_sequence,
)

DEFAULT_N_TRIALS = 5
DEFAULT_STANDOFF_M = 0.8
ODOM_TOPIC = '/odometry/filtered'

# RTAB-Map Link.type (rtabmap/core/Link.h)
LINK_GLOBAL_CLOSURE = 1
LINK_LOCAL_CLOSURE = 2
LINK_USER_CLOSURE = 3
LINK_LANDMARK = 7


def evaluate_root() -> Path:
    return Path(__file__).resolve().parent


def logs_root() -> Path:
    env = os.environ.get('TARKBOT_EVAL_LOG_DIR', '').strip()
    root = Path(env) if env else (evaluate_root() / 'logs')
    root.mkdir(parents=True, exist_ok=True)
    return root


def make_run_dir(test_name: str) -> Path:
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe = test_name.replace(' ', '_').replace('/', '_')
    path = logs_root() / f'{stamp}_{safe}'
    path.mkdir(parents=True, exist_ok=False)
    return path


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def wrap_angle_rad(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def wrap_angle_deg(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


def yaw_from_quat(z: float, w: float) -> float:
    return math.atan2(2.0 * w * z, 1.0 - 2.0 * z * z)


def mean_std(values: list[float]) -> tuple[float | None, float | None]:
    vals = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if not vals:
        return None, None
    if len(vals) == 1:
        return vals[0], 0.0
    return statistics.mean(vals), statistics.stdev(vals)


def fmt_mean_std(values: list[float], digits: int = 2) -> str:
    m, s = mean_std(values)
    if m is None:
        return 'n/a'
    return f'{m:.{digits}f} ± {s:.{digits}f}'


def load_gt_approaches(floorplan_path: str | None = None) -> dict[str, dict]:
    """Return surveyed approach poses: keys 'dock' and 'Table N'."""
    path = load_floorplan(floorplan_path) if floorplan_path else load_floorplan()
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    out: dict[str, dict] = {}
    dock = data['dock']['approach']
    out['dock'] = {
        'x': float(dock['x']),
        'y': float(dock['y']),
        'yaw_deg': float(dock.get('yaw_deg', 0.0)),
    }
    for t in data['tables']:
        a = t['approach']
        out[f"Table {int(t['id'])}"] = {
            'x': float(a['x']),
            'y': float(a['y']),
            'yaw_deg': float(a.get('yaw_deg', 0.0)),
        }
    return out


def pose_error_vs_gt(pose: dict, gt: dict) -> dict[str, float]:
    dx = pose['x'] - gt['x']
    dy = pose['y'] - gt['y']
    dpsi = wrap_angle_deg(math.degrees(pose['yaw']) - gt['yaw_deg'])
    return {
        'abs_dx_cm': abs(dx) * 100.0,
        'abs_dy_cm': abs(dy) * 100.0,
        'abs_dpsi_deg': abs(dpsi),
        'pos_err_cm': math.hypot(dx, dy) * 100.0,
    }


class TeeLogger:
    """Mirror stdout/stderr into a console.log under the run directory."""

    def __init__(self, log_path: Path):
        self.log_path = log_path
        self._file = log_path.open('a', encoding='utf-8')
        self._stdout = sys.stdout
        self._stderr = sys.stderr

    def write(self, data: str) -> int:
        self._stdout.write(data)
        self._file.write(data)
        self._file.flush()
        return len(data)

    def flush(self) -> None:
        self._stdout.flush()
        self._file.flush()

    def isatty(self) -> bool:
        return False

    def install(self) -> None:
        sys.stdout = self  # type: ignore[assignment]
        sys.stderr = self  # type: ignore[assignment]

    def uninstall(self) -> None:
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        self._file.close()


class EvalHelperNode(Node):
    """Parameter holder + /odometry/filtered cache + map-TF trajectory recorder."""

    def __init__(self, node_name: str = 'eval_helper'):
        super().__init__(node_name)
        self.declare_parameter('n_trials', DEFAULT_N_TRIALS)
        self.declare_parameter('table_id', 1)
        self.declare_parameter('floorplan_path', '')
        self.declare_parameter('enable_visual_align', True)
        self.declare_parameter('return_dock', True)
        self.declare_parameter('standoff_m', DEFAULT_STANDOFF_M)

        self._odom_lock = threading.Lock()
        self._last_odom: Odometry | None = None
        self._recording = False
        self._traj: list[dict[str, float]] = []
        self.create_subscription(Odometry, ODOM_TOPIC, self._on_odom, 50)

        self._map_lock = threading.Lock()
        self._map_recording = False
        self._map_traj: list[dict[str, float]] = []
        # ~20 Hz poll of map→base (downsampled in callback)
        self.create_timer(0.05, self._on_map_timer)

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

    def _on_odom(self, msg: Odometry) -> None:
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = yaw_from_quat(q.z, q.w)
        stamp = float(msg.header.stamp.sec) + float(msg.header.stamp.nanosec) * 1e-9
        sample = {
            't': stamp,
            'x': float(p.x),
            'y': float(p.y),
            'yaw': float(yaw),
        }
        with self._odom_lock:
            self._last_odom = msg
            if self._recording:
                # Downsample: keep if first, or moved ≥1 cm, or ≥0.1 s since last
                if not self._traj:
                    self._traj.append(sample)
                else:
                    last = self._traj[-1]
                    dist = math.hypot(sample['x'] - last['x'], sample['y'] - last['y'])
                    dt = sample['t'] - last['t']
                    if dist >= 0.01 or dt >= 0.1:
                        self._traj.append(sample)

    def start_traj_recording(self) -> None:
        with self._odom_lock:
            self._traj = []
            self._recording = True

    def stop_traj_recording(self) -> list[dict[str, float]]:
        with self._odom_lock:
            self._recording = False
            return list(self._traj)

    def _lookup_map_sample(self) -> dict[str, float] | None:
        try:
            tf = self.tf_buffer.lookup_transform(
                MAP_FRAME, BASE_FRAME, Time(),
                timeout=rclpy.duration.Duration(seconds=0.0))
            t = tf.transform.translation
            q = tf.transform.rotation
            stamp = float(tf.header.stamp.sec) + float(tf.header.stamp.nanosec) * 1e-9
            if stamp <= 0.0:
                # Some drivers leave stamp zero; wall time is fine for plotting.
                import time
                stamp = time.time()
            return {
                't': stamp,
                'x': float(t.x),
                'y': float(t.y),
                'yaw': float(yaw_from_quat(q.z, q.w)),
            }
        except TransformException:
            return None

    def _on_map_timer(self) -> None:
        with self._map_lock:
            if not self._map_recording:
                return
        sample = self._lookup_map_sample()
        if sample is None:
            return
        with self._map_lock:
            if not self._map_recording:
                return
            if not self._map_traj:
                self._map_traj.append(sample)
                return
            last = self._map_traj[-1]
            dist = math.hypot(sample['x'] - last['x'], sample['y'] - last['y'])
            dt = sample['t'] - last['t']
            if dist >= 0.01 or dt >= 0.1:
                self._map_traj.append(sample)

    def start_map_traj_recording(self) -> None:
        with self._map_lock:
            self._map_traj = []
            self._map_recording = True

    def stop_map_traj_recording(self) -> list[dict[str, float]]:
        with self._map_lock:
            self._map_recording = False
            return list(self._map_traj)

    def snapshot_odom(self, timeout_s: float = 5.0) -> dict[str, float] | None:
        import time
        deadline = time.time() + timeout_s
        while time.time() < deadline and rclpy.ok():
            with self._odom_lock:
                msg = self._last_odom
            if msg is not None:
                p = msg.pose.pose.position
                q = msg.pose.pose.orientation
                yaw = yaw_from_quat(q.z, q.w)
                return {
                    'x': float(p.x),
                    'y': float(p.y),
                    'yaw': float(yaw),
                    'frame_id': msg.header.frame_id or 'odom',
                }
            time.sleep(0.05)
        self.get_logger().error(f'No {ODOM_TOPIC} within {timeout_s:.1f}s')
        return None

    def snapshot_map_pose(self, timeout_s: float = 5.0) -> dict[str, float] | None:
        import time
        deadline = time.time() + timeout_s
        while time.time() < deadline and rclpy.ok():
            try:
                tf = self.tf_buffer.lookup_transform(
                    MAP_FRAME, BASE_FRAME, Time(),
                    timeout=rclpy.duration.Duration(seconds=0.2))
                t = tf.transform.translation
                q = tf.transform.rotation
                return {
                    'x': float(t.x),
                    'y': float(t.y),
                    'yaw': float(yaw_from_quat(q.z, q.w)),
                    'frame_id': MAP_FRAME,
                }
            except TransformException:
                time.sleep(0.05)
        self.get_logger().error(
            f'No TF {MAP_FRAME} → {BASE_FRAME} within {timeout_s:.1f}s')
        return None


def odom_return_error(start: dict, end: dict) -> dict[str, float]:
    dx = end['x'] - start['x']
    dy = end['y'] - start['y']
    dpsi = wrap_angle_deg(math.degrees(end['yaw']) - math.degrees(start['yaw']))
    return {
        'pos_err_cm': math.hypot(dx, dy) * 100.0,
        'yaw_err_deg': dpsi,
        'abs_yaw_err_deg': abs(dpsi),
        'dx_m': dx,
        'dy_m': dy,
    }


def docking_metrics_from_arrival(
    arrival: dict,
    standoff_m: float = DEFAULT_STANDOFF_M,
) -> dict[str, Any]:
    """Pick thesis docking fields from LAST_ARRIVAL (pre vs post align)."""
    source = arrival.get('metric_source') or 'pre_align'
    block = arrival.get(source) or arrival.get('pre_align') or {}
    err_x = block.get('err_x')
    marker_yaw = block.get('marker_yaw')
    range_m = block.get('range')
    lateral_cm = abs(err_x) * 100.0 if err_x is not None else None
    range_err_cm = abs(range_m - standoff_m) * 100.0 if range_m is not None else None
    abs_yaw = abs(marker_yaw) if marker_yaw is not None else None
    return {
        'metric_source': source,
        'visible': bool(block.get('visible')),
        'lateral_err_cm': lateral_cm,
        'range_m': range_m,
        'range_err_cm': range_err_cm,
        'abs_marker_yaw_deg': abs_yaw,
        'raw': block,
    }


class DeliverySession:
    """Bring-up pattern shared by odometry / localization / navigation evals."""

    def __init__(self, helper: EvalHelperNode):
        self.helper = helper
        self.nav = NavigatorReal()
        self.tracker = ArucoTracker()
        self.cmd_pub = helper.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        self.executor = MultiThreadedExecutor()
        self.executor.add_node(helper)
        self.executor.add_node(self.tracker)
        self._spin_thread = threading.Thread(target=self.executor.spin, daemon=True)
        self._spin_thread.start()
        self._started = False

    def configure_floorplan(self, floorplan_path: str = '') -> str:
        if floorplan_path:
            return load_floorplan(floorplan_path)
        return load_floorplan()

    def startup(self) -> None:
        if not self._started:
            startup_sequence(self.nav, self.tracker, self.cmd_pub)
            self._started = True

    def run_loop(self, table_name: str, return_dock: bool = True) -> dict[str, Any]:
        import time
        t0 = time.time()
        ok_table = deliver_to(self.nav, table_name, self.tracker, self.cmd_pub)
        t_table = time.time()
        ok_dock = True
        if return_dock and ok_table:
            ok_dock = return_to_dock(self.nav, self.tracker, self.cmd_pub)
        t1 = time.time()
        return {
            'nav_success_table': bool(ok_table),
            'nav_success_dock': bool(ok_dock),
            'nav_success': bool(ok_table and (ok_dock if return_dock else True)),
            't_table_s': t_table - t0,
            'trip_time_s': t1 - t0,
        }

    def shutdown(self) -> None:
        self.executor.shutdown()
        self.helper.destroy_node()
        self.tracker.destroy_node()
        self.nav.destroy_node()


def package_maps_dir() -> Path:
    here = evaluate_root().parent
    return here / 'maps'


def default_map_yaml() -> Path:
    return package_maps_dir() / 'restaurant.yaml'


def default_map_pgm() -> Path:
    return package_maps_dir() / 'restaurant.pgm'


def default_rtabmap_db() -> Path:
    return Path.home() / '.ros' / 'rtabmap.db'


def default_floorplan_json() -> Path:
    return evaluate_root().parent / 'config' / 'floorplan.json'


def save_trajectory_csv(path: Path, samples: list[dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        f.write('t,x,y,yaw\n')
        for s in samples:
            f.write(f"{s['t']:.6f},{s['x']:.6f},{s['y']:.6f},{s['yaw']:.6f}\n")


def load_trajectory_csv(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    lines = path.read_text(encoding='utf-8').splitlines()
    if not lines:
        return rows
    for line in lines[1:]:
        if not line.strip():
            continue
        t, x, y, yaw = line.split(',')
        rows.append({
            't': float(t), 'x': float(x), 'y': float(y), 'yaw': float(yaw)})
    return rows


def normalize_traj_to_start(
    samples: list[dict[str, float]],
) -> list[dict[str, float]]:
    """Translate/rotate so trial start is at origin facing +x (for overlay plots)."""
    if not samples:
        return []
    x0, y0, yaw0 = samples[0]['x'], samples[0]['y'], samples[0]['yaw']
    c, s = math.cos(-yaw0), math.sin(-yaw0)
    out: list[dict[str, float]] = []
    for p in samples:
        dx, dy = p['x'] - x0, p['y'] - y0
        out.append({
            't': p['t'] - samples[0]['t'],
            'x': c * dx - s * dy,
            'y': s * dx + c * dy,
            'yaw': wrap_angle_rad(p['yaw'] - yaw0),
        })
    return out


def read_map_yaml(path: Path) -> dict[str, Any]:
    """Minimal ROS map yaml parse (resolution, origin, image)."""
    data: dict[str, Any] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            continue
        key, val = line.split(':', 1)
        key, val = key.strip(), val.strip()
        if key == 'resolution':
            data[key] = float(val)
        elif key == 'origin':
            inner = val.strip('[]')
            parts = [p.strip() for p in inner.split(',')]
            data[key] = [float(parts[0]), float(parts[1]), float(parts[2])]
        elif key == 'image':
            data[key] = val
        elif key == 'negate':
            data[key] = int(val)
        elif key in ('occupied_thresh', 'free_thresh'):
            data[key] = float(val)
    return data


def load_pgm_gray(path: Path) -> tuple[Any, int, int]:
    """Return (numpy uint8 HxW, width, height) for a P5 PGM."""
    import numpy as np

    raw = path.read_bytes()
    pos = 0
    magic = width = height = maxval = None
    while pos < len(raw):
        if raw[pos:pos + 1] == b'#':
            while pos < len(raw) and raw[pos:pos + 1] != b'\n':
                pos += 1
            pos += 1
            continue
        if raw[pos:pos + 1] in (b' ', b'\t', b'\n', b'\r'):
            pos += 1
            continue
        start = pos
        while pos < len(raw) and raw[pos:pos + 1] not in (b' ', b'\t', b'\n', b'\r'):
            pos += 1
        tok = raw[start:pos].decode('ascii')
        if magic is None:
            magic = tok
        elif width is None:
            width = int(tok)
        elif height is None:
            height = int(tok)
        elif maxval is None:
            maxval = int(tok)
            break
    data = raw[pos:]
    if data[:1] in (b' ', b'\n', b'\r', b'\t'):
        data = data[1:]
    if magic != 'P5' or width is None or height is None:
        raise ValueError(f'Unsupported or invalid PGM: {path}')
    arr = np.frombuffer(data[: width * height], dtype=np.uint8).reshape((height, width))
    return arr, width, height


def figures_dir() -> Path:
    d = evaluate_root() / 'figures'
    d.mkdir(parents=True, exist_ok=True)
    return d
