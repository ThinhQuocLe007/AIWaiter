#!/usr/bin/env python3
"""§5.2.3 Offline map summary from restaurant.yaml + rtabmap.db (Table 5.2)."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from evaluate.common import (
    LINK_GLOBAL_CLOSURE,
    LINK_LANDMARK,
    LINK_LOCAL_CLOSURE,
    LINK_USER_CLOSURE,
    default_map_pgm,
    default_map_yaml,
    default_rtabmap_db,
    make_run_dir,
    write_summary,
)


def _read_yaml_resolution(path: Path) -> float | None:
    # Minimal parse — avoid requiring PyYAML on the robot image.
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line.startswith('resolution:'):
            return float(line.split(':', 1)[1].strip())
    return None


def _pgm_occupancy_stats(path: Path) -> dict:
    """Count free / occupied / unknown in a binary PGM occupancy grid."""
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
        return {'error': 'failed to parse PGM header', 'magic': magic}

    # Common ROS export: 0=occupied, 254=free, ~205=unknown
    free = occ = unk = 0
    for b in data[: width * height]:
        if b >= 250:
            free += 1
        elif b <= 50:
            occ += 1
        else:
            unk += 1
    total = max(free + occ + unk, 1)
    return {
        'width': width,
        'height': height,
        'maxval': maxval,
        'free_pct': 100.0 * free / total,
        'occupied_pct': 100.0 * occ / total,
        'unknown_pct': 100.0 * unk / total,
    }


def _count_loop_closures(db_path: Path) -> dict:
    if not db_path.is_file():
        return {
            'error': f'database not found: {db_path}',
            'geom': None,
            'aruco': None,
        }
    geom_types = (LINK_GLOBAL_CLOSURE, LINK_LOCAL_CLOSURE, LINK_USER_CLOSURE)
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        # Link table: type column
        cur.execute('SELECT type, COUNT(*) FROM Link GROUP BY type')
        by_type = {int(t): int(c) for t, c in cur.fetchall()}
        geom = sum(by_type.get(t, 0) for t in geom_types)
        aruco = by_type.get(LINK_LANDMARK, 0)
        return {
            'geom': geom,
            'aruco': aruco,
            'by_type': by_type,
            'db': str(db_path),
        }
    except sqlite3.Error as exc:
        return {'error': str(exc), 'geom': None, 'aruco': None}
    finally:
        con.close()


def main(args=None) -> None:
    parser = argparse.ArgumentParser(
        description='Offline RTAB-Map / occupancy summary for thesis Table 5.2')
    parser.add_argument(
        '--db', type=Path, default=default_rtabmap_db(),
        help='Path to rtabmap.db (default: ~/.ros/rtabmap.db)')
    parser.add_argument(
        '--map-yaml', type=Path, default=default_map_yaml(),
        help='Path to restaurant.yaml')
    parser.add_argument(
        '--map-pgm', type=Path, default=default_map_pgm(),
        help='Path to restaurant.pgm')
    parser.add_argument(
        '--duration-min', type=float, default=None,
        help='Mapping duration in minutes (manual; recorded into summary)')
    parser.add_argument(
        '--consistency', type=str, default='',
        help='Short qualitative consistency note for Table 5.2')
    ns = parser.parse_args(args=args)

    run_dir = make_run_dir('map_summary')
    resolution = _read_yaml_resolution(ns.map_yaml) if ns.map_yaml.is_file() else None
    links = _count_loop_closures(ns.db)
    pgm_stats = _pgm_occupancy_stats(ns.map_pgm) if ns.map_pgm.is_file() else {
        'error': f'missing {ns.map_pgm}'}

    consistency = ns.consistency.strip()
    if not consistency and isinstance(pgm_stats, dict) and 'free_pct' in pgm_stats:
        consistency = (
            f"grid {pgm_stats.get('width')}x{pgm_stats.get('height')}, "
            f"free={pgm_stats['free_pct']:.1f}%, occ={pgm_stats['occupied_pct']:.1f}%, "
            f"unk={pgm_stats['unknown_pct']:.1f}%"
        )

    summary = {
        'test': 'map_summary',
        'thesis_table': '5.2',
        'run_dir': str(run_dir),
        'duration_min': ns.duration_min,
        'resolution_m': resolution,
        'loop_closures_geom': links.get('geom'),
        'loop_closures_aruco': links.get('aruco'),
        'loop_closures_detail': links,
        'consistency': consistency or None,
        'map_yaml': str(ns.map_yaml),
        'map_pgm': str(ns.map_pgm),
        'pgm_stats': pgm_stats,
    }
    write_summary(run_dir / 'summary.json', summary)
    # Also print a one-line thesis hint
    print('Table 5.2 fields:')
    print(f'  Duration: {ns.duration_min if ns.duration_min is not None else "[TBD]"} min')
    print(f'  Loop closures (geom / ArUco): '
          f'{links.get("geom")} / {links.get("aruco")}')
    print(f'  Resolution: {resolution} m')
    print(f'  Consistency: {consistency or "[TBD]"}')
    print(f'Saved: {run_dir / "summary.json"}')


if __name__ == '__main__':
    main()
