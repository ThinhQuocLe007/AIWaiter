#!/usr/bin/env python3
"""Kiểm ba máy có nói chuyện được với nhau không, trước khi đổ lỗi cho mic hay cho robot.

Chạy trên máy nào cũng được, không cần venv:

    python3 scripts/netcheck.py            # đọc .env
    python3 scripts/netcheck.py --pc 172.25.223.218 --robot 100.66.149.248

Buổi demo dùng HAI mạng overlay và mỗi chặng đi một mạng khác nhau: Jetson gọi LLM trên PC qua
ZeroTier (172.25.x), còn bắn lệnh sang laptop Gazebo qua Netbird (100.66.x). Gõ nhầm IP của mạng
này vào chỗ của mạng kia thì triệu chứng nhìn y hệt lỗi phần mềm — robot im lặng, agent không trả
lời — nên mỗi dòng kết quả bên dưới in luôn interface mà kernel chọn để đi.
Kiểm ở đây mất 5 giây, mò lúc demo mất 15 phút.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OK, FAIL, SKIP = "  OK  ", " HỎNG ", " BỎ QUA "


def read_env() -> dict[str, str]:
    """Đọc .env bằng tay — file này phải chạy được ở nơi không có pydantic."""
    env: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.split("#")[0].strip()
    env.update({k: v for k, v in os.environ.items() if k in
                ("ORCHESTRATOR_URL", "AGENT_URL", "ROBOT_UDP_HOST", "ROBOT_UDP_PORT")})
    return env


def route_via(host: str) -> str:
    """Interface + IP nguồn mà kernel sẽ dùng để tới `host`, kèm tên mạng overlay đoán được.

    Buổi demo có hai overlay chồng nhau và mỗi chặng đi một cái khác nhau. Biết chặng nào ra
    interface nào là cách nhanh nhất để thấy mình đang gõ nhầm IP của mạng kia.
    """
    try:
        out = subprocess.run(["ip", "route", "get", host], capture_output=True, text=True,
                             timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    dev = re.search(r"\bdev (\S+)", out)
    src = re.search(r"\bsrc (\S+)", out)
    if not dev:
        return ""
    name = dev.group(1)
    overlay = ("ZeroTier" if name.startswith("zt") else
               "Netbird/WireGuard" if name.startswith(("wt", "wg")) else
               "LAN/Wi-Fi" if name.startswith(("en", "wl", "eth")) else "")
    label = f"qua {name}"
    if overlay:
        label += f" ({overlay})"
    if src:
        label += f", IP nguồn {src.group(1)}"
    return label


def tcp(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "mở"
    except socket.timeout:
        return False, "hết giờ chờ — không tới được máy đó, hoặc tường lửa chặn"
    except ConnectionRefusedError:
        return False, "tới được máy nhưng CHƯA CÓ DỊCH VỤ nghe ở cổng này"
    except OSError as e:
        return False, f"{e}"


def udp_ack(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    """Bắn một gói ping thật của giao thức và chờ ack — dùng đúng code lúc demo."""
    from src.robot_link import protocol
    from src.robot_link.protocol import Command

    session = protocol.new_session()
    payload = Command(kind=protocol.KIND_PING, session=session, seq=1).encode()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        for _ in range(protocol.REPEATS):
            sock.sendto(payload, (host, port))
            time.sleep(protocol.REPEAT_GAP_S)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                raw, _ = sock.recvfrom(512)
            except socket.timeout:
                break
            ack = protocol.decode(raw)
            if ack and ack.kind == protocol.KIND_ACK and ack.session == session:
                return True, "cầu UDP trả lời"
        return False, "không ai trả lời — cầu chưa chạy, sai IP, hoặc UDP bị chặn"
    except OSError as e:
        return False, f"{e}"
    finally:
        sock.close()


def hostport(url: str, default_port: int) -> tuple[str, int]:
    p = urlparse(url if "//" in url else f"http://{url}")
    return p.hostname or "127.0.0.1", p.port or default_port


def main() -> int:
    env = read_env()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pc", help="IP PC server (ghi đè ORCHESTRATOR_URL/AGENT_URL)")
    ap.add_argument("--robot", default=env.get("ROBOT_UDP_HOST", ""),
                    help="IP laptop chạy Gazebo (mặc định: ROBOT_UDP_HOST)")
    ap.add_argument("--udp-port", type=int, default=int(env.get("ROBOT_UDP_PORT") or 45455))
    args = ap.parse_args()

    if args.pc:
        orch_host, orch_port = args.pc, 8000
        agent_host, agent_port = args.pc, 8100
    else:
        orch_host, orch_port = hostport(env.get("ORCHESTRATOR_URL", "http://127.0.0.1:8000"), 8000)
        agent_host, agent_port = hostport(env.get("AGENT_URL", "http://127.0.0.1:8100"), 8100)

    print("Máy này:", socket.gethostname())
    print()

    bad = 0
    checks = [
        (f"PC server  · backend  {orch_host}:{orch_port}",
         lambda: tcp(orch_host, orch_port), orch_host),
        (f"PC server  · agent    {agent_host}:{agent_port}",
         lambda: tcp(agent_host, agent_port), agent_host),
    ]
    if args.robot:
        checks.append((f"Laptop     · cầu UDP  {args.robot}:{args.udp_port}",
                       lambda: udp_ack(args.robot, args.udp_port), args.robot))

    for label, fn, target in checks:
        ok, detail = fn()
        bad += not ok
        via = route_via(target)
        print(f"[{OK if ok else FAIL}] {label}")
        if via:
            print(f"         {via}")
        print(f"         {detail}")

    if not args.robot:
        print(f"[{SKIP}] Laptop     · cầu UDP")
        print("         ROBOT_UDP_HOST chưa đặt — bình thường trên PC, nhưng trên Jetson là thiếu")

    print()
    if bad:
        print("Chưa thông. Kiểm theo thứ tự:")
        print("  1. Máy kia đã bật dịch vụ chưa (make backend / make agent / cầu UDP)?")
        print("  2. Đúng mạng chưa? PC server ở ZeroTier (172.25.x), laptop Gazebo ở Netbird")
        print("     (100.66.x). Dòng 'qua ...' ở trên cho biết kernel chọn interface nào —")
        print("     đi ra nhầm interface là dấu hiệu gõ nhầm IP của mạng kia.")
        print("     Netbird:  netbird status -d      ZeroTier:  sudo zerotier-cli listnetworks")
        print("  3. Tường lửa:  sudo ufw allow 8000,8100/tcp  ·  sudo ufw allow 45455/udp")
        return 1
    print("Cả ba chặng đều thông.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
