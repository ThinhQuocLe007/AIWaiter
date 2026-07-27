#!/usr/bin/env python3
"""§5.2.4 Navigation + docking with/without visual align (Tables 5.4 / 5.5)."""

from __future__ import annotations

import time

import rclpy

from evaluate.common import (
    DeliverySession,
    EvalHelperNode,
    TeeLogger,
    append_jsonl,
    as_bool,
    docking_metrics_from_arrival,
    fmt_mean_std,
    make_run_dir,
    write_summary,
)
from tarkbot_robot.visual_delivery import (
    DESTINATIONS,
    deliver_to,
    get_last_arrival,
    return_to_dock,
    set_enable_visual_align,
)


def main(args=None) -> None:
    rclpy.init(args=args)
    helper = EvalHelperNode('eval_navigation')
    n_trials = int(helper.get_parameter('n_trials').value)
    table_id = int(helper.get_parameter('table_id').value)
    floorplan_path = str(helper.get_parameter('floorplan_path').value).strip()
    enable_align = as_bool(helper.get_parameter('enable_visual_align').value)
    return_dock = as_bool(helper.get_parameter('return_dock').value)
    standoff_m = float(helper.get_parameter('standoff_m').value)

    tag = 'nav_align_on' if enable_align else 'nav_align_off'
    run_dir = make_run_dir(tag)
    metrics_path = run_dir / 'metrics.jsonl'
    tee = TeeLogger(run_dir / 'console.log')
    tee.install()

    session = DeliverySession(helper)
    trip_times: list[float] = []
    lateral: list[float] = []
    range_err: list[float] = []
    yaw_err: list[float] = []
    n_success = 0

    try:
        set_enable_visual_align(enable_align)
        path = session.configure_floorplan(floorplan_path)
        table_name = f'Table {table_id}'
        if table_name not in DESTINATIONS:
            helper.get_logger().error(
                f'Unknown {table_name}. Known: {sorted(DESTINATIONS)}')
            return

        helper.get_logger().info(
            f'Navigation eval N={n_trials}, enable_visual_align={enable_align}, '
            f'standoff={standoff_m} m, floorplan={path}, logs={run_dir}')
        session.startup()

        for i in range(1, n_trials + 1):
            helper.get_logger().info(f'── Trial {i}/{n_trials} ──')
            t0 = time.time()
            ok_table = deliver_to(
                session.nav, table_name, session.tracker, session.cmd_pub)
            table_arrival = get_last_arrival()
            table_metrics = docking_metrics_from_arrival(table_arrival, standoff_m)

            ok_dock = True
            if return_dock and ok_table:
                ok_dock = return_to_dock(
                    session.nav, session.tracker, session.cmd_pub)
            trip_s = time.time() - t0
            success = bool(ok_table and (ok_dock if return_dock else True))

            record = {
                'trial': i,
                'enable_visual_align': enable_align,
                'standoff_m': standoff_m,
                'nav_success_table': bool(ok_table),
                'nav_success_dock': bool(ok_dock),
                'nav_success': success,
                'trip_time_s': trip_s,
                'table_arrival': table_arrival,
                'table_docking': table_metrics,
            }
            append_jsonl(metrics_path, record)

            if success:
                n_success += 1
                trip_times.append(trip_s)
                if table_metrics['lateral_err_cm'] is not None:
                    lateral.append(table_metrics['lateral_err_cm'])
                if table_metrics['range_err_cm'] is not None:
                    range_err.append(table_metrics['range_err_cm'])
                if table_metrics['abs_marker_yaw_deg'] is not None:
                    yaw_err.append(table_metrics['abs_marker_yaw_deg'])

            helper.get_logger().info(
                f'Trial {i}: success={success}, trip={trip_s:.1f}s, '
                f'lateral={table_metrics["lateral_err_cm"]}, '
                f'range_err={table_metrics["range_err_cm"]}, '
                f'yaw={table_metrics["abs_marker_yaw_deg"]}')

        rate = (100.0 * n_success / n_trials) if n_trials else None
        summary = {
            'test': 'navigation',
            'enable_visual_align': enable_align,
            'n_trials': n_trials,
            'n_success': n_success,
            'nav_success_rate_pct': rate,
            'trip_time_s_mean_std': fmt_mean_std(trip_times),
            'lateral_err_cm_mean_std': fmt_mean_std(lateral),
            'range_err_cm_mean_std': fmt_mean_std(range_err),
            'abs_dpsi_deg_mean_std': fmt_mean_std(yaw_err),
            'run_dir': str(run_dir),
            'thesis_table': '5.4' if enable_align else '5.5',
        }
        write_summary(run_dir / 'summary.json', summary)
        helper.get_logger().info(
            f'Done. success={n_success}/{n_trials} ({rate}%), '
            f'trip={summary["trip_time_s_mean_std"]} s, '
            f'lateral={summary["lateral_err_cm_mean_std"]} cm')
    finally:
        session.shutdown()
        tee.uninstall()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
