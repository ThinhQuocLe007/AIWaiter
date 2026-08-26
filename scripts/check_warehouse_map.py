#!/usr/bin/env python3
"""Prove the warehouse data still matches the Gazebo sa bàn, before the demo rather than during it.

The brain's `data/inventory.csv` and the sim's `config/semantic_tasks.yaml` describe the same nine
boxes from two sides, and nothing at runtime forces them to agree. If someone edits a colour on
either side, the failure appears as the AGV driving to the right rack and picking the wrong box in
front of an audience. This checks all of it in under a second:

  * the nine slots in the CSV are exactly the nine slots the sim defines;
  * each slot's colour matches the box actually placed there in the sim;
  * every section and colour translates to a `run_storage_pick.sh` argument;
  * every token the brain can emit resolves to a real command in `robot_link.bridge`;
  * the scripts that bridge shells out to exist and are executable;
  * stock levels leave both a shortage and a surplus, so "kệ nào thiếu đồ" has an answer.

Stdlib only, no venv needed:  python3 scripts/check_warehouse_map.py [--demo-dir ...]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.robot_link.bridge import _COLORS, _STORAGES, RobotBridge  # noqa: E402

failures: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(("  OK   " if ok else "  SAI  ") + msg)
    if not ok:
        failures.append(msg)


def sim_boxes(demo_dir: Path) -> dict[str, str]:
    """{slot: colour} as the sim actually places them. Parsed with a regex to avoid needing PyYAML
    on a machine that may only have ROS's interpreter."""
    raw = (demo_dir / "config" / "semantic_tasks.yaml").read_text(encoding="utf-8")
    return {
        slot: color
        for _obj, color, _zone, slot in re.findall(
            r"^\s{2}(\w+): \{color: (\w+), location: storage_([ABC]), slot: ([ABC]0[123])", raw, re.M
        )
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--demo-dir", default=str(ROOT.parent / "warehouse_agv_demo"))
    args = parser.parse_args()
    demo = Path(args.demo_dir).expanduser().resolve()
    if not (demo / "config" / "semantic_tasks.yaml").exists():
        print(f"Không thấy sa bàn ở {demo} — chỉ định --demo-dir")
        return 2

    inv = list(csv.DictReader((ROOT / "data" / "inventory.csv").open(encoding="utf-8")))
    wh = json.loads((ROOT / "data" / "warehouse.json").read_text(encoding="utf-8"))
    boxes = sim_boxes(demo)

    print("── data kho ↔ sa bàn Gazebo ──────────────────────────────────")
    check({r["slot"] for r in inv} == set(boxes),
          f"các ô trong inventory.csv khớp semantic_tasks.yaml ({len(boxes)} ô)")
    wrong = [(r["slot"], r["color"], boxes.get(r["slot"])) for r in inv
             if boxes.get(r["slot"]) != r["color"]]
    check(not wrong, f"màu mỗi ô khớp hộp thật trong sim {wrong or ''}")
    check({r["section"] for r in inv} <= set(wh["sections"]),
          "mọi khu trong CSV đều khai trong warehouse.json")
    check({r["section"] for r in inv} <= _STORAGES, "mọi khu dịch được sang --storage")
    check({r["color"] for r in inv} <= _COLORS, "mọi màu dịch được sang --color")

    print("── token brain phát ra ↔ lệnh bridge chạy ────────────────────")
    bridge = RobotBridge(demo, None, None)
    tokens = {r["section"] for r in inv} | {v.get("token", k).upper()
                                            for k, v in wh["named_places"].items()}
    for token in sorted(tokens):
        argv = bridge._argv_for(token, "blue" if token in _STORAGES else "")
        check(argv is not None, f"{token} → {' '.join(argv) if argv else 'KHÔNG DỊCH ĐƯỢC'}")

    print("── script sa bàn mà bridge gọi ───────────────────────────────")
    for name in ("run_storage_pick.sh", "run_task.sh"):
        path = demo / name
        check(path.exists() and bool(path.stat().st_mode & 0o111), f"{name} tồn tại, executable")

    print("── tồn kho cho câu hỏi 'kệ nào thiếu đồ' ─────────────────────")
    short = [f"{r['item']} (khu {r['section']})" for r in inv
             if float(r["quantity"]) < float(r["min_stock"])]
    check(0 < len(short) < len(inv), f"vừa có thiếu vừa có đủ: thiếu {short}")

    print()
    if failures:
        print(f"KẾT QUẢ: {len(failures)} LỖI — sửa trước khi demo")
        return 1
    print("KẾT QUẢ: TẤT CẢ KHỚP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
