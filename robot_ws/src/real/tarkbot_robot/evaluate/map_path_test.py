#!/usr/bin/env python3
"""Localized path eval: dock → Table N → dock with map-frame ground truth.

Records ``map → base_footprint`` trajectories (not ``/odometry/filtered``) so
paths overlay cleanly on ``restaurant.pgm`` even when Nav2 takes alternate
routes. Arrival / return scored against surveyed approaches in ``floorplan.json``.
"""

from __future__ import annotations

import json
import time

import rclpy

from evaluate.common import (
    DeliverySession,
    EvalHelperNode,
    TeeLogger,
    append_jsonl,
    as_bool,
    default_floorplan_json,
    default_map_pgm,
    default_map_yaml,
    fmt_mean_std,
    load_gt_approaches,
    make_run_dir,
    pose_error_vs_gt,
    save_trajectory_csv,
    write_summary,
)
from tarkbot_robot.visual_delivery import (
    DESTINATIONS,
    deliver_to,
    return_to_dock,
    set_enable_visual_align,
)


def main(args=None) -> None:
    rclpy.init(args=args)
    helper = EvalHelperNode('eval_map_path')
    n_trials = int(helper.get_parameter('n_trials').value)
    table_id = int(helper.get_parameter('table_id').value)
    floorplan_path = str(helper.get_parameter('floorplan_path').value).strip()
    enable_align = as_bool(helper.get_parameter('enable_visual_align').value)

    run_dir = make_run_dir('map_path')
    traj_dir = run_dir / 'trajectories'
    traj_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / 'metrics.jsonl'
    tee = TeeLogger(run_dir / 'console.log')
    tee.install()

    session = DeliverySession(helper)
    table_pos: list[float] = []
    table_yaw: list[float] = []
    dock_pos: list[float] = []
    dock_yaw: list[float] = []
    trip_times: list[float] = []
    traj_files: list[str] = []
    n_ok = 0

    try:
        set_enable_visual_align(enable_align)
        path = session.configure_floorplan(floorplan_path)
        gt = load_gt_approaches(path)
        table_name = f'Table {table_id}'
        if table_name not in DESTINATIONS or table_name not in gt:
            helper.get_logger().error(
                f'Missing GT/destination for {table_name}. '
                f'Known DEST: {sorted(DESTINATIONS)}; GT: {sorted(gt)}')
            return

        map_yaml = default_map_yaml()
        map_pgm = default_map_pgm()
        floorplan_resolved = path or str(default_floorplan_json())
        meta = {
            'test': 'map_path',
            'frame_id': 'map',
            'pose_source': 'TF map → base_footprint',
            'ground_truth': 'floorplan.json approach poses',
            'table_id': table_id,
            'n_trials': n_trials,
            'enable_visual_align': enable_align,
            'floorplan': floorplan_resolved,
            'map_yaml': str(map_yaml),
            'map_pgm': str(map_pgm),
            'gt_approaches': gt,
            'run_dir': str(run_dir),
            'trajectories_dir': str(traj_dir),
            'csv_columns': 't,x,y,yaw (map frame, metres / rad)',
        }
        (run_dir / 'run_meta.json').write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

        helper.get_logger().info(
            f'Map-path eval N={n_trials}, floorplan={path}, table={table_name}, '
            f'logs={run_dir} (scoring TF map→base vs floorplan GT)')
        session.startup()

        for i in range(1, n_trials + 1):
            helper.get_logger().info(f'── Trial {i}/{n_trials} ──')
            t0 = time.time()
            helper.start_map_traj_recording()

            ok_table = deliver_to(
                session.nav, table_name, session.tracker, session.cmd_pub)
            t_table = time.time()
            pose_table = helper.snapshot_map_pose()
            table_err = (
                pose_error_vs_gt(pose_table, gt[table_name])
                if pose_table is not None else None)

            ok_dock = False
            pose_dock = None
            dock_err = None
            if ok_table:
                ok_dock = return_to_dock(
                    session.nav, session.tracker, session.cmd_pub)
                pose_dock = helper.snapshot_map_pose()
                if pose_dock is not None:
                    dock_err = pose_error_vs_gt(pose_dock, gt['dock'])

            samples = helper.stop_map_traj_recording()
            t1 = time.time()
            traj_path = traj_dir / f'trial_{i:02d}.csv'
            save_trajectory_csv(traj_path, samples)
            traj_files.append(str(traj_path))

            ok = bool(ok_table and ok_dock)
            trip_time_s = t1 - t0
            if ok and table_err is not None:
                table_pos.append(table_err['pos_err_cm'])
                table_yaw.append(table_err['abs_dpsi_deg'])
            if ok and dock_err is not None:
                dock_pos.append(dock_err['pos_err_cm'])
                dock_yaw.append(dock_err['abs_dpsi_deg'])
                n_ok += 1
            if ok:
                trip_times.append(trip_time_s)

            record = {
                'trial': i,
                'ok': ok,
                'ok_table': ok_table,
                'ok_dock': ok_dock,
                'frame_id': 'map',
                'trajectory_csv': str(traj_path),
                'n_traj_samples': len(samples),
                't_table_s': t_table - t0,
                'trip_time_s': trip_time_s,
                'table_pose': pose_table,
                'table_err': table_err,
                'dock_pose': pose_dock,
                'dock_err': dock_err,
            }
            append_jsonl(metrics_path, record)

            table_s = (
                f'{table_err["pos_err_cm"]:.1f}cm' if table_err else 'n/a')
            dock_s = (
                f'{dock_err["pos_err_cm"]:.1f}cm' if dock_err else 'n/a')
            helper.get_logger().info(
                f'Trial {i}: samples={len(samples)}, '
                f'table_pos_err={table_s}, dock_pos_err={dock_s}, ok={ok}')

        summary = {
            'test': 'map_path',
            'n_trials': n_trials,
            'n_ok': n_ok,
            'table_id': table_id,
            'frame_id': 'map',
            'run_dir': str(run_dir),
            'trajectories_dir': str(traj_dir),
            'trajectory_files': traj_files,
            'map_yaml': str(map_yaml),
            'map_pgm': str(map_pgm),
            'floorplan': floorplan_resolved,
            'nav_success_rate_pct': (100.0 * n_ok / n_trials) if n_trials else 0.0,
            'trip_time_s_mean_std': fmt_mean_std(trip_times),
            'table_pos_err_cm_mean_std': fmt_mean_std(table_pos),
            'table_yaw_err_deg_mean_std': fmt_mean_std(table_yaw),
            'dock_pos_err_cm_mean_std': fmt_mean_std(dock_pos),
            'dock_yaw_err_deg_mean_std': fmt_mean_std(dock_yaw),
            'table_pos_err_cm_values': table_pos,
            'dock_pos_err_cm_values': dock_pos,
            'thesis_figure': 'map_path_overlay',
        }
        write_summary(run_dir / 'summary.json', summary)
        helper.get_logger().info(
            f'Done. table {summary["table_pos_err_cm_mean_std"]} cm, '
            f'dock {summary["dock_pos_err_cm_mean_std"]} cm → {run_dir}')
        helper.get_logger().info(
            'Plot: ros2 run tarkbot_robot eval_plot_figures -- --only map_path '
            f'--map-path-run {run_dir}')
    finally:
        session.shutdown()
        tee.uninstall()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
