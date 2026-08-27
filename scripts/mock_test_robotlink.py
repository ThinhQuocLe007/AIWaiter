"""Mock test kịch bản: thay người nói, bắn lệnh cho simulation (Gazebo) chạy.

Mục đích: bạn của bạn bật máy simulation (laptop chạy `src.robot_link.bridge` + Gazebo), rồi
chạy script này. Script thay người nói, gửi từng câu trong kịch bản qua UDP tới bridge, và bạn
XEM XE CHẠY THẬT TRÊN MÁY SIMULATION.

Đường điều khiển (HUONG_DAN_DEMO_KHO.md):
    script này ──UDP──► RobotBridge (laptop, có Gazebo) ──► chạy run_storage_pick.sh ──► xe chạy

Cách chạy:
  * Trên MÁY SIMULATION (laptop, nơi bridge + Gazebo chạy), mở terminal đã `source ros`:
        python3 -m src.robot_link.bridge --demo-dir <warehouse_agv_demo> --bind 0.0.0.0:45455
    rồi (cùng máy hoặc máy có thể tới được cổng đó) chạy:
        uv run python scripts/mock_test_robotlink.py --robot-host 127.0.0.1
  * Hoặc chạy trên Jetson (nó ở cả Netbird nên tới được laptop):
        uv run python scripts/mock_test_robotlink.py --robot-host 100.66.149.248

Mỗi lệnh script gửi sẽ được bridge đáp lại (ACK). Script báo "robot nhận lệnh" hay "KHÔNG phản
hồi" — y hệt `make say`. Còn việc xe có thật sự chạy là do bạn nhìn Gazebo.

Chế độ --local: không cần Gazebo. Nó tự bật một bridge --no-ros --dry-run trên localhost, gửi
kịch bản, và KIỂM TRA bridge dịch ra đúng lệnh Gazebo (pick_box.sh --storage B ...). Dùng để check
logic脚本 trên server không có sim.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.robot_link.sender import CommandSender  # noqa: E402


# Kịch bản: (nhãn, loại, action dict, câu nói, số giây chờ SAU lệnh để xem xe chạy).
# Mỗi bước có khoảng chờ riêng — quan trọng: "đi khu A" chỉ chờ 3s (xe đang giữa đường)
# rồi mới "dừng lại", để kịch bản dừng/đổi ý xảy ra ĐÚNG LÚC xe đang chạy.
SCENARIOS = [
    ("đi tới khu A", "navigate",
     {"type": "navigate", "task": "goto", "position": {"token": "A"}}, "đi tới khu A", 3.0),
    ("dừng lại (giữa đường)", "control",
     {"type": "control", "verb": "stop"}, "dừng lại", 2.0),
    ("đổi sang khu B", "navigate",
     {"type": "navigate", "task": "goto", "position": {"token": "B"}}, "đổi sang khu B", 15.0),
    ("đi tiếp đúng đích cũ", "control",
     {"type": "control", "verb": "resume"}, "đi tiếp", 2.0),
    ("đổi sang khu C lấy hộp xanh", "navigate",
     {"type": "navigate", "task": "fetch", "position": {"token": "C", "color": "green"}},
     "thôi qua khu C lấy hộp xanh", 15.0),
]


def _send(sender: CommandSender, kind: str, action: dict, sentence: str) -> None:
    if kind == "navigate":
        sender.navigate(action, sentence=sentence, source="agent")
    else:
        sender.control(action["verb"], sentence=sentence, source="fastpath")


def drive_real(host: str, port: int) -> int:
    print(f"[setup] gửi kịch bản UDP tới bridge tại {host}:{port}")
    sender = CommandSender(host=host, port=port, enabled=True)
    results: list[tuple[str, bool]] = []
    try:
        for label, kind, action, sentence, wait in SCENARIOS:
            print(f"\n>>> gửi: '{sentence}'  ({label})")
            _send(sender, kind, action, sentence)
            time.sleep(0.4)  # đợi ACK về
            ok = sender.link_ok
            results.append((label, ok))
            print(f"    [{'OK' if ok else 'NO ACK'}] robot {'nhận lệnh' if ok else 'KHÔNG phản hồi'}")
            print(f"    ... chờ {wait}s để xem xe chạy trên simulation")
            time.sleep(wait)
    finally:
        sender.close()

    passed = sum(1 for _, ok in results if ok)
    print("\n" + "=" * 70)
    print(f"KẾT QUẢ: {passed}/{len(results)} lệnh được bridge nhận (ACK)")
    print("Xe có chạy thật trên Gazebo hay không là do bạn nhìn máy simulation.")
    if passed != len(results):
        print("Có lệnh KHÔNG tới được bridge — kiểm tra bridge có chạy và --robot-host đúng IP.")
    return 0 if passed == len(results) else 1


def drive_local() -> int:
    """Headless: tự bật bridge dry-run, gửi kịch bản, kiểm bridge dịch ra đúng lệnh Gazebo."""
    import tempfile
    demo = Path(tempfile.mkdtemp(prefix="mock_wh_demo_"))
    (demo / "run_storage_pick.sh").write_text("#!/bin/bash\necho mock\n")
    (demo / "run_storage_pick.sh").chmod(0o755)

    bridge_log: list[str] = []
    ready = threading.Event()

    def _drain():
        for line in iter(proc.stdout.readline, ""):
            if not line:
                break
            bridge_log.append(line.rstrip("\n"))
            if "udp://" in line:
                ready.set()

    proc = subprocess.Popen(
        [sys.executable, "-m", "src.robot_link.bridge", "--no-ros", "--dry-run",
         "--demo-dir", str(demo), "--bind", "127.0.0.1:45455"],
        cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    threading.Thread(target=_drain, daemon=True).start()
    if not ready.wait(timeout=15):
        print("[FAIL] bridge dry-run không khởi động. Log:")
        print("\n".join(bridge_log[-20:]))
        proc.terminate()
        return 1
    print("[setup] bridge dry-run sẵn sàng trên 127.0.0.1:45455")

    sender = CommandSender(host="127.0.0.1", port=45455, enabled=True)
    results: list[tuple[str, bool, str]] = []
    try:
        # mỗi label -> danh sách chuỗi con phải có trong log bridge (không phụ thuộc thứ tự argv)
        expect = {
            "đi tới khu A": ["pick_box.sh --storage A", "--route-only"],
            "đổi sang khu B": ["pick_box.sh --storage B", "--route-only"],
            "đổi sang khu C lấy hộp xanh": ["pick_box.sh --storage C", "--color green", "--deliver"],
        }
        for label, kind, action, sentence, _wait in SCENARIOS:
            _send(sender, kind, action, sentence)
            time.sleep(0.6)
            if kind == "control":
                ok = any("stop" in ln.lower() or "resume" in ln.lower() for ln in bridge_log)
                results.append((label, ok, "bridge log có lệnh điều khiển" if ok else "thiếu"))
            else:
                subs = expect.get(label, [])
                ok = subs and all(any(s in ln for ln in bridge_log) for s in subs)
                results.append((label, ok, f"mong {subs}" if subs else "kiểm thủ công"))
    finally:
        sender.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            proc.kill()

    passed = sum(1 for _, ok, _ in results if ok)
    print("\n" + "=" * 70)
    for label, ok, detail in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    print(f"\n  {passed}/{len(results)} kịch bản PASS (bridge dịch đúng lệnh Gazebo)")
    return 0 if passed == len(results) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Mock test kịch bản: gửi UDP cho simulation chạy.")
    ap.add_argument("--robot-host", default="127.0.0.1",
                    help="IP máy bridge (laptop Gazebo). Mặc định 127.0.0.1 (chạy trên máy sim).")
    ap.add_argument("--robot-port", type=int, default=45455)
    ap.add_argument("--local", action="store_true",
                    help="headless: tự bật bridge dry-run, chỉ kiểm logic dịch lệnh (không cần Gazebo)")
    args = ap.parse_args()

    if args.local:
        return drive_local()
    return drive_real(args.robot_host, args.robot_port)


if __name__ == "__main__":
    raise SystemExit(main())
