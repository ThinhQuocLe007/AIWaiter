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
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src._shared.paths import load_dotenv_from_repo  # noqa: E402
from src.robot_link import protocol  # noqa: E402
from src.robot_link.sender import CommandSender  # noqa: E402

load_dotenv_from_repo()  # ROBOT_UDP_HOST trong .env, như HUONG_DAN_DEMO_KHO.md hứa


# Kịch bản: (nhãn, loại, action, câu nói, giây XEM xe chạy | None, trạng thái phải đạt trước).
#
# `wait=None` nghĩa là "chờ tới khi nhiệm vụ chạy xong" (xe về `idle`) thay vì đếm một số giây —
# dùng cho bước cuối, vì gắp hàng rồi mang về lâu bao nhiêu là do sa bàn quyết, không phải mình.
#
# `await_state` là thứ làm kịch bản bám theo robot thật thay vì đoán bằng sleep: bridge trả trạng
# thái AGV (đọc /odom) trong mỗi ack, nên script đứng chờ tới khi bánh THẬT SỰ quay rồi mới tính
# giờ. Nav2/AMCL trên xe này mất 6–8s mới ra path — sleep cứng hoặc là hụt (bắn lệnh kế khi xe
# chưa nhúc nhích) hoặc là thừa (đứng ngó cái xe đã tới nơi từ lâu).
#
# `wait` do đó là thời gian xe CHẠY THẬT trước bước sau, không còn gánh phần chờ tìm đường: 4s ở
# bước 1 nghĩa là "dừng lại" rơi đúng lúc xe đang giữa đường, y như kịch bản muốn.
SCENARIOS = [
    ("đi tới khu A", "navigate",
     {"type": "navigate", "task": "goto", "position": {"token": "A"}},
     "đi tới khu A", 4.0, protocol.ST_MOVING),
    ("dừng lại giữa đường", "control",
     {"type": "control", "verb": "stop"},
     "dừng lại", 5.0, protocol.ST_STOPPED),
    # `fetch` = tới kệ, gắp, RỒI mang về trạm đóng gói (pick_box.sh --deliver). "Đi về" đã nằm
    # trong lệnh này — thêm một bước "về trạm sạc" nữa là chạy lại đúng chỗ vừa đứng, vì sa bàn
    # neo trạm sạc chung với trạm đóng gói (xem `make caps`).
    ("qua khu B lấy hàng rồi mang về", "navigate",
     {"type": "navigate", "task": "fetch", "position": {"token": "B"}},
     "qua khu B lấy hàng rồi mang về trạm đóng gói", None, protocol.ST_MOVING),
]

# Trần chờ một lệnh biến thành chuyển động. Nav2/AMCL ~6–8s; quá ngần này thì có gì đó hỏng và
# nói ra hữu ích hơn là treo kịch bản.
STATE_TIMEOUT_S = 25.0
# Trần cho cả một chuyến gắp-và-mang-về. Rộng tay, vì đây chỉ là cái phanh khi có gì đó treo.
MISSION_TIMEOUT_S = 300.0
POLL_S = 0.5


def _send(sender: CommandSender, kind: str, action: dict, sentence: str) -> None:
    if kind == "navigate":
        sender.navigate(action, sentence=sentence, source="agent")
    else:
        sender.control(action["verb"], sentence=sentence, source="fastpath")


def _await_state(sender: CommandSender, want: str, timeout: float) -> tuple[bool, float, str]:
    """Ping cho tới khi bridge báo AGV đạt `want`. Trả (đạt?, số giây, trạng thái cuối)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        sender.ping()
        time.sleep(POLL_S)
        state = sender.last_status
        if state == want:
            return True, time.time() - t0, state
        # Hai loại bridge không nói được xe đang làm gì, và cả hai đều KHÔNG phải lý do để treo
        # kịch bản 25s mỗi bước: bridge chạy --no-ros (không đọc được odom), và bridge cũ / bản
        # built-in trong warehouse_agv_demo, vốn ack rỗng vì không biết khái niệm trạng thái.
        if state in (protocol.ST_UNKNOWN, ""):
            return True, time.time() - t0, state
    return False, time.time() - t0, sender.last_status


def drive_real(host: str | None, port: int, wait_scale: float = 1.0) -> int:
    # host None -> CommandSender tự đọc env ROBOT_UDP_HOST, rồi 127.0.0.1
    resolved = host or os.environ.get("ROBOT_UDP_HOST") or "127.0.0.1"
    print(f"[setup] gửi kịch bản UDP tới bridge tại {resolved}:{port}")
    sender = CommandSender(host=host, port=port, enabled=True)
    results: list[tuple[str, bool]] = []
    try:
        for label, kind, action, sentence, wait, want in SCENARIOS:
            print(f"\n>>> gửi: '{sentence}'  ({label})")
            _send(sender, kind, action, sentence)
            time.sleep(0.4)  # đợi ACK về
            ok = sender.link_ok
            print(f"    [{'OK' if ok else 'NO ACK'}] robot {'nhận lệnh' if ok else 'KHÔNG phản hồi'}")
            if not ok:
                results.append((label, False))
                continue
            reached, took, state = _await_state(sender, want, STATE_TIMEOUT_S)
            if state == protocol.ST_UNKNOWN:
                print("    [?] bridge chạy --no-ros: không đọc được odom, không kiểm được xe chạy")
            elif not state:
                print("    [?] bridge không báo trạng thái xe — laptop đang chạy bản built-in của "
                      "sa bàn (hoặc bridge AIWaiter cũ). Đổi sang `src.robot_link.bridge` mới thì "
                      "script mới chờ được xe lăn bánh; giờ chỉ đếm giờ như trước.")
            elif reached:
                print(f"    [{want.upper()}] sau {took:.1f}s")
            else:
                print(f"    [TIMEOUT] {took:.0f}s vẫn chưa '{want}' (đang '{state or 'không rõ'}')")
            results.append((label, reached))
            if not reached:
                continue
            if wait is None:
                print("    ... chờ xe làm xong nhiệm vụ (gắp hàng + mang về trạm đóng gói)")
                done, took, state = _await_state(sender, protocol.ST_IDLE,
                                                 MISSION_TIMEOUT_S * wait_scale)
                if state == protocol.ST_UNKNOWN or not state:
                    # Bridge không báo được "xong" — đếm giờ thay, còn hơn cắt ngang chuyến.
                    time.sleep(30.0 * wait_scale)
                elif done:
                    print(f"    [XONG] nhiệm vụ kết thúc sau {took:.0f}s, xe đã về trạm")
                else:
                    print(f"    [TIMEOUT] {took:.0f}s chưa xong (đang '{state or 'không rõ'}')")
                    results[-1] = (label, False)
            else:
                wait *= wait_scale
                print(f"    ... xem xe chạy {wait:.1f}s rồi sang bước sau")
                time.sleep(wait)
    finally:
        sender.close()

    passed = sum(1 for _, ok in results if ok)
    print("\n" + "=" * 70)
    print(f"KẾT QUẢ: {passed}/{len(results)} bước robot vào đúng trạng thái mong đợi")
    if passed != len(results):
        print("Bước hỏng: [NO ACK] = không tới được bridge (kiểm --robot-host / bridge);")
        print("            [TIMEOUT] = bridge nhận rồi nhưng xe không vào trạng thái đó — xem log")
        print("            terminal bridge và output pick_box.sh trên máy sim.")
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
            "qua khu B lấy hàng rồi mang về": ["pick_box.sh --storage B", "--deliver"],
        }
        for label, kind, action, sentence, _wait, _want in SCENARIOS:
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
    ap.add_argument("--robot-host", default=None,
                    help="IP máy bridge (laptop Gazebo). Nếu không truyền, lấy từ env "
                         "ROBOT_UDP_HOST, rồi mặc định 127.0.0.1. Chạy trên server PC thì truyền "
                         "IP ZeroTier của laptop, hoặc set ROBOT_UDP_HOST trong .env của server.")
    ap.add_argument("--robot-port", type=int, default=45455)
    ap.add_argument("--wait-scale", type=float, default=1.0,
                    help="nhân mọi khoảng chờ (máy sim chậm thì --wait-scale 1.5)")
    ap.add_argument("--local", action="store_true",
                    help="headless: tự bật bridge dry-run, chỉ kiểm logic dịch lệnh (không cần Gazebo)")
    args = ap.parse_args()

    if args.local:
        return drive_local()
    return drive_real(args.robot_host, args.robot_port, args.wait_scale)


if __name__ == "__main__":
    raise SystemExit(main())
