"""Đường ack giữa script và bridge: trạng thái AGV bridge trả về, và thread đọc ack phía sender."""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # chạy được cả khi chưa có pytest

from src.robot_link import protocol
from src.robot_link.bridge import MissionRunner, RobotBridge
from src.robot_link.sender import CommandSender


class FakeHold:
    def __init__(self, moving=False, engaged=False):
        self.moving = moving
        self.engaged = engaged


def _bridge(hold, running=False):
    runner = MissionRunner(Path("/nonexistent"), dry_run=True)
    runner.running = lambda: running  # type: ignore[method-assign]
    return RobotBridge(Path("/nonexistent"), hold, runner)


def test_status():
    assert _bridge(None).status() == protocol.ST_UNKNOWN
    assert _bridge(FakeHold()).status() == protocol.ST_IDLE
    # Nav2/AMCL đang tìm đường: nhiệm vụ chạy rồi mà bánh chưa quay — đúng 6–8s mà kịch bản
    # cũ tưởng nhầm là xe đã đi.
    assert _bridge(FakeHold(), running=True).status() == protocol.ST_PLANNING
    assert _bridge(FakeHold(moving=True), running=True).status() == protocol.ST_MOVING
    assert _bridge(FakeHold(engaged=True), running=True).status() == protocol.ST_STOPPED
    # Đang gắp hàng thì hold chỉ outvote vqa_mission, xe có thể nhích: sự thật thắng ý định.
    assert _bridge(FakeHold(moving=True, engaged=True)).status() == protocol.ST_MOVING


def test_status_rides_in_ack():
    ack = protocol.decode(protocol.ack_for(protocol.Command(kind=protocol.KIND_PING, seq=7),
                                           protocol.ST_MOVING))
    assert ack.kind == protocol.KIND_ACK and ack.seq == 7 and ack.reply == protocol.ST_MOVING
    # Ack không kèm trạng thái vẫn hợp lệ (sender cũ, bridge cũ).
    assert protocol.decode(protocol.ack_for(protocol.Command(kind=protocol.KIND_PING))).reply == ""


def test_close_does_not_explode_the_ack_thread():
    """`close()` giữa lúc thread ack đang trong select: chỗ này từng ném traceback ra màn hình.

    Không phải lỗi vô hại về mặt demo — nó in stack trace ngay sau khi lệnh đã gửi xong, đúng lúc
    người xem đang nhìn terminal, và trông hệt như lệnh vừa hỏng.
    """
    seen: list[type] = []
    old_hook = threading.excepthook
    threading.excepthook = lambda args: seen.append(args.exc_type)
    try:
        for i in range(30):
            sender = CommandSender(host="127.0.0.1", port=45999, enabled=True)
            time.sleep(0.01 * (i % 5))  # rơi vào nhiều thời điểm khác nhau của select(0.5)
            sender.close()
        time.sleep(1.0)
    finally:
        threading.excepthook = old_hook
    assert not seen, seen


if __name__ == "__main__":
    test_status()
    test_status_rides_in_ack()
    test_close_does_not_explode_the_ack_thread()
    print("OK")
