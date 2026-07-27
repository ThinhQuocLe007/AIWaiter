#!/usr/bin/env python3
"""§5.2.2 Odometry accuracy: return-to-start error on /odometry/filtered (Table 5.1).

Also records per-trial ``/odometry/filtered`` trajectories under ``trajectories/`` for
Figure 5.2 (overlaid paths).
"""

from __future__ import annotations

import rclpy

from evaluate.common import (
    DeliverySession,
    EvalHelperNode,
    TeeLogger,
    append_jsonl,
    as_bool,
    fmt_mean_std,
    make_run_dir,
    odom_return_error,
    save_trajectory_csv,
    write_summary,
)
from tarkbot_robot.visual_delivery import DESTINATIONS


def main(args=None) -> None:
    rclpy.init(args=args)
    helper = EvalHelperNode('eval_odometry')
    n_trials = int(helper.get_parameter('n_trials').value)
    table_id = int(helper.get_parameter('table_id').value)
    floorplan_path = str(helper.get_parameter('floorplan_path').value).strip()
    # Odometry scoring ignores map pose; align still runs for a realistic service loop.
    enable_align = as_bool(helper.get_parameter('enable_visual_align').value)

    run_dir = make_run_dir('odometry')
    traj_dir = run_dir / 'trajectories'
    traj_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = run_dir / 'metrics.jsonl'
    tee = TeeLogger(run_dir / 'console.log')
    tee.install()

    session = DeliverySession(helper)
    pos_errs: list[float] = []
    yaw_errs: list[float] = []
    traj_files: list[str] = []

    try:
        from tarkbot_robot.visual_delivery import set_enable_visual_align
        set_enable_visual_align(enable_align)
        path = session.configure_floorplan(floorplan_path)
        table_name = f'Table {table_id}'
        if table_name not in DESTINATIONS:
            helper.get_logger().error(
                f'Unknown {table_name}. Known: {sorted(DESTINATIONS)}')
            return

        helper.get_logger().info(
            f'Odometry eval N={n_trials}, floorplan={path}, table={table_name}, '
            f'logs={run_dir}')
        session.startup()

        for i in range(1, n_trials + 1):
            helper.get_logger().info(f'── Trial {i}/{n_trials} ──')
            start = helper.snapshot_odom()
            if start is None:
                append_jsonl(metrics_path, {
                    'trial': i, 'ok': False, 'error': 'no_odom_start'})
                continue

            helper.start_traj_recording()
            loop = session.run_loop(table_name, return_dock=True)
            samples = helper.stop_traj_recording()
            traj_path = traj_dir / f'trial_{i:02d}.csv'
            save_trajectory_csv(traj_path, samples)
            traj_files.append(str(traj_path))
            helper.get_logger().info(
                f'Trial {i}: recorded {len(samples)} odom samples → {traj_path.name}')

            end = helper.snapshot_odom()
            if end is None:
                append_jsonl(metrics_path, {
                    'trial': i, 'ok': False, 'error': 'no_odom_end', **loop,
                    'start': start, 'trajectory_csv': str(traj_path),
                    'n_traj_samples': len(samples)})
                continue

            err = odom_return_error(start, end)
            record = {
                'trial': i,
                'ok': bool(loop['nav_success']),
                'start': start,
                'end': end,
                'trajectory_csv': str(traj_path),
                'n_traj_samples': len(samples),
                **err,
                **loop,
            }
            append_jsonl(metrics_path, record)
            if record['ok']:
                pos_errs.append(err['pos_err_cm'])
                yaw_errs.append(err['abs_yaw_err_deg'])
            helper.get_logger().info(
                f'Trial {i}: pos_err={err["pos_err_cm"]:.2f} cm, '
                f'yaw_err={err["yaw_err_deg"]:+.2f} deg, ok={record["ok"]}')

        summary = {
            'test': 'odometry',
            'n_trials': n_trials,
            'n_ok': len(pos_errs),
            'table_id': table_id,
            'run_dir': str(run_dir),
            'trajectories_dir': str(traj_dir),
            'trajectory_files': traj_files,
            'position_cm_mean_std': fmt_mean_std(pos_errs),
            'heading_deg_mean_std': fmt_mean_std(yaw_errs),
            'position_cm_values': pos_errs,
            'heading_deg_values': yaw_errs,
            'thesis_table': '5.1',
            'thesis_figure': '5.2',
        }
        write_summary(run_dir / 'summary.json', summary)
        helper.get_logger().info(
            f'Done. Table 5.1 → position {summary["position_cm_mean_std"]} cm, '
            f'heading {summary["heading_deg_mean_std"]} deg')
        helper.get_logger().info(
            'Figure 5.2: ros2 run tarkbot_robot eval_plot_figures -- --odom-run '
            f'{run_dir}')
    finally:
        session.shutdown()
        tee.uninstall()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
