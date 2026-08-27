#!/usr/bin/env python3
"""Type a Vietnamese sentence, send it to the robot. No microphone, no LLM, no venv.

The demo has four things that can be wrong at once — audio, VPN, the brain, the robot — and the
usual way to find out which is to open all of them and guess. This isolates the last two: it takes
the sentence you would have spoken and puts it on the wire exactly as the Jetson's voice loop
would, so a failure here is definitely not the microphone and definitely not Whisper.

    python3 -m src.robot_link.say "dẫn tôi đi lấy thùng bia"        # gửi thật
    python3 -m src.robot_link.say "dừng lại" --host 192.168.1.20
    python3 -m src.robot_link.say "qua khu C thôi" --dry            # chỉ xem sẽ ra lệnh gì

`--dry` resolves the sentence with the same parser the laptop uses and prints the command without
sending anything, which is also the fastest way to check a new phrasing before the demo.

Stdlib only, so it runs on the Jetson with nothing installed.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.robot_link import capabilities, parse_text  # noqa: E402
from src.robot_link.sender import CommandSender  # noqa: E402


def load_robot_env() -> None:
    """Đọc `ROBOT_UDP_*` trong .env bằng stdlib, để `make say` khỏi phải tự truyền `--host`.

    Không dùng python-dotenv: cả file này cố ý chạy được bằng `python3` trần trên Jetson, nơi
    không có venv — mà đó cũng là lúc cần nó nhất, khi đang đi tìm xem cái gì hỏng.
    """
    env = Path(__file__).resolve().parents[2] / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        key = key.strip()
        # Dòng comment `# ROBOT_UDP_HOST=...` tự rụng ở đây: key của nó bắt đầu bằng dấu #.
        if sep and key.startswith("ROBOT_UDP_") and key not in os.environ:
            os.environ[key] = value.split("#")[0].strip().strip("\"'")


def explain(sentence: str, task: str = "") -> dict | None:
    """Print how the sentence reads and what it would run. Returns the action, or None.

    `task` ép việc phải làm ở đích. Nhánh dự phòng đoán `fetch` cho mọi câu có tên khu — đúng cho
    một đơn hàng, nhưng không có cách nói nào ra được "chạy tới thôi, đừng gắp", nên khi cần đúng
    một việc cụ thể thì chỉ định thẳng thay vì đi tìm câu tiếng Việt hợp ý bộ đọc.
    """
    action = parse_text.parse(sentence)
    if action is None:
        if parse_text.needs_memory(sentence):
            print(f"  Đây LÀ lệnh, nhưng cần brain nhớ hộp nào đang trên khay "
                  f"(nhánh dự phòng không nhớ được).")
        else:
            print(f"  Không phải lệnh cho robot — câu này để brain trả lời.")
        return None

    kind = action.get("type")
    if task and kind == "navigate":
        action["task"] = task
    if kind == "control":
        print(f"  Lệnh điều khiển: {action['verb']} — {capabilities.CONTROL_VI[action['verb']]}")
        print("  (bridge tự xử lý, không gọi script)")
        return action
    try:
        argv = capabilities.resolve(action)
    except capabilities.Unsupported as e:
        print(f"  KHÔNG LÀM ĐƯỢC: {e}")
        return None
    if kind == "navigate":
        pos = action.get("position", {})
        print(f"  Việc: {action.get('task')}   Đích: {pos.get('token')}"
              f"{'  ô ' + pos['slot'] if pos.get('slot') else ''}"
              f"{'  màu ' + pos['color'] if pos.get('color') else ''}")
    print(f"  Robot sẽ chạy: {' '.join(argv)}")
    return action


def main(argv: list[str] | None = None) -> int:
    load_robot_env()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("sentence", nargs="+", help="câu tiếng Việt, như khi nói vào mic")
    parser.add_argument("--host", default=os.environ.get("ROBOT_UDP_HOST", ""),
                        help="IP LAN của laptop chạy Gazebo (mặc định: ROBOT_UDP_HOST)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("ROBOT_UDP_PORT", "45455")))
    parser.add_argument("--task", default="", choices=("", *capabilities.TASKS),
                        help="ép việc ở đích (goto = chạy tới, không gắp). Mặc định: đọc từ câu")
    parser.add_argument("--dry", action="store_true", help="chỉ in ra, không gửi")
    parser.add_argument("--robot-id", default=os.environ.get("VOICE_ROBOT_ID", "robo-1"))
    args = parser.parse_args(argv)

    sentence = " ".join(args.sentence)
    print(f'Câu: "{sentence}"')
    action = explain(sentence, args.task)

    if args.dry:
        return 0
    if not args.host:
        print("\nChưa có --host (hoặc ROBOT_UDP_HOST) — không biết gửi đi đâu.", file=sys.stderr)
        return 2

    # Send the sentence even when the local parse found nothing: the laptop may be running a
    # newer capability table than this machine, and the point of the test is what IT does.
    sender = CommandSender(host=args.host, port=args.port, robot_id=args.robot_id)
    sender.navigate(action or {}, sentence=sentence, source="say")
    print(f"\nĐã gửi tới {args.host}:{args.port}, đang chờ robot xác nhận...")
    for _ in range(30):  # 3 s
        if sender.link_ok:
            print("  ✓ Robot đã nhận. Xem log của `make robotlink` bên laptop.")
            sender.close()
            return 0
        time.sleep(0.1)
    print("  ✗ KHÔNG có phản hồi trong 3 giây. Kiểm tra theo thứ tự:", file=sys.stderr)
    print(f"      1. `make robotlink` đã chạy bên laptop chưa?", file=sys.stderr)
    print(f"      2. {args.host} có đúng IP LAN của laptop không? (`ip a` bên đó)", file=sys.stderr)
    print(f"      3. Tường lửa laptop có chặn UDP {args.port} không?", file=sys.stderr)
    print(f"         sudo ufw allow {args.port}/udp", file=sys.stderr)
    sender.close()
    return 1


if __name__ == "__main__":
    sys.exit(main())
