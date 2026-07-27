#!/usr/bin/env bash
# Jetson - chạy CẢ BA thứ của một buổi demo trong MỘT terminal:
#   1) hwstack : RTAB-Map localization + Nav2 + ArUco + dispatcher bridge (ROS 2)
#   2) voice   : vòng lặp mic -> VAD/STT -> agent -> TTS (src/edge_voice/main.py)
#   3) web     : trình duyệt kiosk trên màn robot (customer_ui)
#
# Gọi qua Makefile:  make jetson          (SERVER_HOST + ID đã cố định sẵn trong Makefile)
# Tắt bớt phần nào:  make jetson VOICE=0    /    make jetson WEB=0
#
# Log mỗi tiến trình được gắn tiền tố [stack] / [voice] / [web] nên vẫn đọc được
# đúng trình tự khởi động trong runbook. Ctrl-C một lần là tắt sạch cả ba.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SERVER_HOST="${SERVER_HOST:-100.66.165.221:8000}"
ID="${ID:-robo-1}"
VOICE="${VOICE:-1}"
WEB="${WEB:-1}"
URL="${URL:-http://$SERVER_HOST/}"
ROS_SETUP="${ROS_SETUP:-/opt/ros/humble/setup.sh}"

if [ ! -x .venv/bin/python ]; then
	echo "Chưa có .venv/bin/python — chạy 'make install UV_EXTRAS=\"--extra voice\"' trước." >&2
	exit 1
fi

# Bật venv cho cả phiên chạy này (bạn không phải tự `source` nữa). `python` trần từ
# đây trở đi = .venv/bin/python. Riêng nhánh ROS ở dưới sẽ `deactivate` lại: venv này
# tạo với include-system-site-packages=false, để nó nằm trước trong PATH thì rclpy /
# python3-websocket của hệ thống biến mất khỏi tầm nhìn của ros2 launch.
# shellcheck disable=SC1091
. .venv/bin/activate
echo "[run] venv   : $VIRTUAL_ENV"
echo "[run] backend: $SERVER_HOST   robot_id: $ID"

tag() { sed -u "s/^/[$1] /"; }

# Ctrl-C (hoặc một tiến trình chết) -> giết cả process group.
cleanup() {
	trap - INT TERM EXIT
	echo
	echo "[run] đang tắt tất cả..."
	kill 0 2>/dev/null
	wait 2>/dev/null
}
trap cleanup INT TERM EXIT

# ── 1) Cả stack robot (ROS 2). Chạy trong subshell đã tắt venv, giống hệt `make hwstack`.
(
	deactivate 2>/dev/null || true
	cd robot_ws
	# Các file setup.sh do ament sinh ra đọc $AMENT_TRACE_SETUP_FILES khi biến chưa set ->
	# dưới `set -u` bash coi là lỗi và thoát NGAY subshell, hwstack không bao giờ khởi động.
	# Tắt -u quanh phần source (make hwstack chạy được chính vì shell của make không có -u).
	set +u
	# shellcheck disable=SC1090,SC1091
	. "$ROS_SETUP"
	# shellcheck disable=SC1091
	. install/setup.sh
	set -u
	exec ros2 launch ai_hw_bridge ai_waiter.launch.py \
		server_host:="$SERVER_HOST" robot_id:="$ID"
) 2>&1 | tag stack &
STACK_PID=$!

# ── 2) Voice. Dùng .venv/bin/python thẳng, KHÔNG qua `uv run` — trên Jetson uv sync sẽ
# gỡ mất ctranslate2/faster-whisper build tay (docs/guides/jetson-ctranslate2-build.md).
VOICE_PID=""
if [ "$VOICE" = "1" ]; then
	.venv/bin/python src/edge_voice/main.py 2>&1 | tag voice &
	VOICE_PID=$!
else
	echo "[run] VOICE=0 — bỏ qua vòng lặp voice."
fi

# ── 3) Trình duyệt kiosk trên màn robot. Chờ backend trả lời rồi mới mở, nếu không
# Firefox sẽ hiện trang lỗi và phải bấm reload tay.
if [ "$WEB" = "1" ]; then
	(
		export DISPLAY="${DISPLAY:-:0}"
		if [ -z "${XAUTHORITY:-}" ] && [ -f /run/user/1000/gdm/Xauthority ]; then
			export XAUTHORITY=/run/user/1000/gdm/Xauthority
		fi
		# Tên biến riêng, KHÔNG dùng $BROWSER: nhiều môi trường (VS Code, desktop) đã set
		# sẵn BROWSER trỏ vào script helper của chúng, make sẽ chuyển tiếp vào đây.
		BROWSER="${KIOSK_BROWSER:-}"
		if [ -z "$BROWSER" ]; then
			for b in firefox chromium-browser chromium google-chrome; do
				if command -v "$b" >/dev/null 2>&1; then BROWSER="$b"; break; fi
			done
		fi
		if [ -z "$BROWSER" ]; then
			echo "không thấy trình duyệt nào (firefox/chromium) — bỏ qua, mở tay: $URL"
			exit 0
		fi
		echo "chờ backend $URL ..."
		for _ in $(seq 1 90); do
			curl -fsS -o /dev/null --max-time 2 "$URL" && break
			sleep 2
		done
		echo "mở $BROWSER --kiosk $URL  (thoát kiosk: Ctrl+W / Alt+F4)"
		exec "$BROWSER" --kiosk "$URL" >/dev/null 2>&1
	) 2>&1 | tag web &
else
	echo "[run] WEB=0 — không mở trình duyệt."
fi

# Chờ: stack hoặc voice chết thì kéo theo phần còn lại (trap EXIT dọn). Trình duyệt
# đóng lại KHÔNG tính — tắt kiosk nhầm thì robot vẫn chạy tiếp.
while :; do
	kill -0 "$STACK_PID" 2>/dev/null || { echo "[run] hwstack đã thoát."; break; }
	if [ -n "$VOICE_PID" ] && ! kill -0 "$VOICE_PID" 2>/dev/null; then
		echo "[run] voice đã thoát."
		break
	fi
	sleep 2
done
