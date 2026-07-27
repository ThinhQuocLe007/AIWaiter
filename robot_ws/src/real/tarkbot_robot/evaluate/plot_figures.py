#!/usr/bin/env python3
"""Plot thesis figures from evaluate assets (offline, no robot).

Figure 5.2 — overlaid odometry paths (from ``eval_odometry`` trajectory CSVs).
Figure 5.3 — occupancy grid with dock + Table 1 (from ``restaurant.pgm`` + floorplan).

Requires: ``pip install matplotlib`` (and numpy, usually already present).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluate.common import (
    default_floorplan_json,
    default_map_pgm,
    default_map_yaml,
    figures_dir,
    load_pgm_gray,
    load_trajectory_csv,
    logs_root,
    normalize_traj_to_start,
    read_map_yaml,
)


def _require_matplotlib():
    try:
        import matplotlib.pyplot as plt
        return plt
    except ImportError as exc:
        raise SystemExit(
            'matplotlib is required for plotting. Install with:\n'
            '  pip install matplotlib\n'
            f'({exc})'
        ) from exc


def _latest_odometry_run(logs: Path) -> Path | None:
    if not logs.is_dir():
        return None
    runs = sorted(
        [p for p in logs.iterdir() if p.is_dir() and p.name.endswith('_odometry')],
        reverse=True,
    )
    for run in runs:
        traj = run / 'trajectories'
        if traj.is_dir() and any(traj.glob('trial_*.csv')):
            return run
    return runs[0] if runs else None


def plot_figure_52(odom_run: Path, out: Path, plt) -> Path:
    traj_dir = odom_run / 'trajectories'
    files = sorted(traj_dir.glob('trial_*.csv')) if traj_dir.is_dir() else []
    if not files:
        raise SystemExit(f'No trial_*.csv under {traj_dir}')

    fig, ax = plt.subplots(figsize=(6.5, 5.5), dpi=150)
    cmap = plt.get_cmap('tab10')
    for i, f in enumerate(files):
        raw = load_trajectory_csv(f)
        norm = normalize_traj_to_start(raw)
        if len(norm) < 2:
            continue
        xs = [p['x'] for p in norm]
        ys = [p['y'] for p in norm]
        color = cmap(i % 10)
        ax.plot(xs, ys, color=color, linewidth=1.4, alpha=0.85, label=f'Trial {i + 1}')
        ax.plot(xs[0], ys[0], 'o', color=color, markersize=5)
        ax.plot(xs[-1], ys[-1], 'x', color=color, markersize=7)

    ax.axhline(0.0, color='0.7', linewidth=0.6)
    ax.axvline(0.0, color='0.7', linewidth=0.6)
    ax.set_aspect('equal', adjustable='datalim')
    ax.set_xlabel('x (m), start-aligned')
    ax.set_ylabel('y (m), start-aligned')
    ax.set_title('Figure 5.2 — Overlaid odometry paths\n'
                 '(each trial translated/rotated to start at origin)')
    ax.legend(loc='best', fontsize=8, frameon=False)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    return out


def plot_figure_53(
    map_yaml: Path,
    map_pgm: Path,
    floorplan: Path,
    out: Path,
    plt,
) -> Path:
    import numpy as np

    meta = read_map_yaml(map_yaml)
    resolution = float(meta['resolution'])
    origin = meta['origin']  # [ox, oy, yaw]
    ox, oy = float(origin[0]), float(origin[1])

    # Prefer yaml-relative image name next to yaml
    pgm = map_pgm
    if 'image' in meta:
        candidate = map_yaml.parent / meta['image']
        if candidate.is_file():
            pgm = candidate

    gray, width, height = load_pgm_gray(pgm)
    # World extents: cell (0,0) is bottom-left of image in ROS map_server convention
    # (row 0 in file is top of image; imshow origin='upper' matches file rows)
    xmin, xmax = ox, ox + width * resolution
    ymin, ymax = oy, oy + height * resolution

    fp = json.loads(floorplan.read_text(encoding='utf-8'))
    dock = fp['dock']
    table = next(t for t in fp['tables'] if int(t['id']) == 1)

    fig, ax = plt.subplots(figsize=(7.0, 6.0), dpi=150)
    ax.imshow(
        gray,
        cmap='gray',
        origin='upper',
        extent=[xmin, xmax, ymin, ymax],
        interpolation='nearest',
    )

    def _mark(node: dict, label: str, color: str) -> None:
        a = node['approach']
        m = node['marker']
        ax.plot(a['x'], a['y'], 'o', color=color, markersize=8, label=f'{label} approach')
        ax.plot(m['x'], m['y'], 's', color=color, markersize=7, label=f'{label} marker')
        # yaw arrow at approach
        yaw = np.deg2rad(float(a.get('yaw_deg', 0.0)))
        ax.arrow(
            a['x'], a['y'],
            0.35 * np.cos(yaw), 0.35 * np.sin(yaw),
            head_width=0.12, head_length=0.1, fc=color, ec=color, length_includes_head=True,
        )
        ax.annotate(
            label, (m['x'], m['y']),
            textcoords='offset points', xytext=(6, 6), fontsize=9, color=color,
        )

    _mark(dock, 'Dock (ArUco 6)', '#c0392b')
    _mark(table, 'Table 1 (ArUco 1)', '#2980b9')

    ax.set_xlabel('x (m, map)')
    ax.set_ylabel('y (m, map)')
    ax.set_title('Figure 5.3 — Occupancy grid with dock and Table 1')
    ax.set_aspect('equal', adjustable='box')
    ax.legend(loc='upper right', fontsize=8, framealpha=0.9)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    plt.close(fig)
    return out


def main(args=None) -> None:
    parser = argparse.ArgumentParser(
        description='Generate Chapter 5 figures 5.2 and 5.3')
    parser.add_argument(
        '--odom-run', type=Path, default=None,
        help='Odometry eval run dir containing trajectories/ '
             '(default: latest *_odometry under evaluate/logs)')
    parser.add_argument(
        '--logs', type=Path, default=None, help='evaluate/logs root')
    parser.add_argument(
        '--map-yaml', type=Path, default=None)
    parser.add_argument(
        '--map-pgm', type=Path, default=None)
    parser.add_argument(
        '--floorplan', type=Path, default=None)
    parser.add_argument(
        '--out-dir', type=Path, default=None,
        help='Output directory (default: evaluate/figures)')
    parser.add_argument(
        '--only', choices=('5.2', '5.3', 'all'), default='all')
    ns = parser.parse_args(args=args)

    plt = _require_matplotlib()
    out_dir = ns.out_dir or figures_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []

    if ns.only in ('5.2', 'all'):
        logs = ns.logs or logs_root()
        run = ns.odom_run or _latest_odometry_run(logs)
        if run is None:
            raise SystemExit(
                f'No odometry run found under {logs}. '
                'Run eval_odometry first, or pass --odom-run.')
        path = plot_figure_52(run, out_dir / 'figure_5_2_odometry_paths.png', plt)
        written.append(path)
        print(f'Figure 5.2 → {path}  (from {run})')

    if ns.only in ('5.3', 'all'):
        map_yaml = ns.map_yaml or default_map_yaml()
        map_pgm = ns.map_pgm or default_map_pgm()
        floorplan = ns.floorplan or default_floorplan_json()
        if not map_yaml.is_file():
            raise SystemExit(f'Missing map yaml: {map_yaml}')
        if not floorplan.is_file():
            raise SystemExit(f'Missing floorplan: {floorplan}')
        path = plot_figure_53(
            map_yaml, map_pgm, floorplan,
            out_dir / 'figure_5_3_occupancy_grid.png', plt)
        written.append(path)
        print(f'Figure 5.3 → {path}')

    print(f'Done ({len(written)} figure(s)). Paste into chapter5-robot-navigation.md.')


if __name__ == '__main__':
    main()
