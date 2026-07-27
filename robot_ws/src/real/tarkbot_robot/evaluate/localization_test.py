#!/usr/bin/env python3
"""§5.2.3 Localization drift vs floorplan approaches (Table 5.3)."""

from __future__ import annotations

import rclpy

from evaluate.common import (
    DeliverySession,
    EvalHelperNode,
    TeeLogger,
    append_jsonl,
    as_bool,
    fmt_mean_std,
    load_gt_approaches,
    make_run_dir,
    pose_error_vs_gt,
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
    helper = EvalHelperNode('eval_localization')
    n_trials = int(helper.get_parameter('n_trials').value)
    table_id = int(helper.get_parameter('table_id').value)
    floorplan_path = str(helper.get_parameter('floorplan_path').value).strip()
    enable_align = as_bool(helper.get_parameter('enable_visual_align').value)

    run_dir = make_run_dir('localization')
    metrics_path = run_dir / 'metrics.jsonl'
    tee = TeeLogger(run_dir / 'console.log')
    tee.install()

    session = DeliverySession(helper)
    table_dx: list[float] = []
    table_dy: list[float] = []
    table_dpsi: list[float] = []
    dock_dx: list[float] = []
    dock_dy: list[float] = []
    dock_dpsi: list[float] = []

    try:
        set_enable_visual_align(enable_align)
        path = session.configure_floorplan(floorplan_path)
        gt = load_gt_approaches(path)
        table_name = f'Table {table_id}'
        if table_name not in DESTINATIONS or table_name not in gt:
            helper.get_logger().error(f'Missing GT/destination for {table_name}')
            return

        helper.get_logger().info(
            f'Localization eval N={n_trials}, floorplan={path}, logs={run_dir}')
        session.startup()

        for i in range(1, n_trials + 1):
            helper.get_logger().info(f'── Trial {i}/{n_trials} ──')
            ok_table = deliver_to(
                session.nav, table_name, session.tracker, session.cmd_pub)
            pose_table = helper.snapshot_map_pose()
            table_err = None
            if pose_table is not None:
                table_err = pose_error_vs_gt(pose_table, gt[table_name])
                if ok_table:
                    table_dx.append(table_err['abs_dx_cm'])
                    table_dy.append(table_err['abs_dy_cm'])
                    table_dpsi.append(table_err['abs_dpsi_deg'])

            ok_dock = False
            pose_dock = None
            dock_err = None
            if ok_table:
                ok_dock = return_to_dock(
                    session.nav, session.tracker, session.cmd_pub)
                pose_dock = helper.snapshot_map_pose()
                if pose_dock is not None:
                    dock_err = pose_error_vs_gt(pose_dock, gt['dock'])
                    if ok_dock:
                        dock_dx.append(dock_err['abs_dx_cm'])
                        dock_dy.append(dock_err['abs_dy_cm'])
                        dock_dpsi.append(dock_err['abs_dpsi_deg'])

            record = {
                'trial': i,
                'ok_table': ok_table,
                'ok_dock': ok_dock,
                'table_pose': pose_table,
                'table_err': table_err,
                'dock_pose': pose_dock,
                'dock_err': dock_err,
            }
            append_jsonl(metrics_path, record)
            helper.get_logger().info(
                f'Trial {i}: table_err={table_err}, dock_err={dock_err}')

        summary = {
            'test': 'localization',
            'n_trials': n_trials,
            'run_dir': str(run_dir),
            'table_1_arrival': {
                'abs_dx_cm': fmt_mean_std(table_dx),
                'abs_dy_cm': fmt_mean_std(table_dy),
                'abs_dpsi_deg': fmt_mean_std(table_dpsi),
                'n': len(table_dx),
            },
            'dock_return': {
                'abs_dx_cm': fmt_mean_std(dock_dx),
                'abs_dy_cm': fmt_mean_std(dock_dy),
                'abs_dpsi_deg': fmt_mean_std(dock_dpsi),
                'n': len(dock_dx),
            },
            'thesis_table': '5.3',
        }
        write_summary(run_dir / 'summary.json', summary)
        helper.get_logger().info(f'Done. Summary → {run_dir / "summary.json"}')
    finally:
        session.shutdown()
        tee.uninstall()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
