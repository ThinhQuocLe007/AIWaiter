#!/usr/bin/env bash
# Jetson - cả một buổi demo trong MỘT terminal, MỘT lệnh:  make jetson
#
#   1) voice   : vòng lặp mic -> VAD/STT -> agent -> TTS (src/edge_voice/main.py)   [mặc định BẬT]
#   2) web     : trình duyệt kiosk trên màn rời, mở thẳng màn giám sát /monitor     [mặc định BẬT]
#   3) hwstack : RTAB-Map localization + Nav2 + ArUco + dispatcher bridge (ROS 2)   [mặc định TẮT]
#
# Mặc định là cấu hình buổi demo hội chợ, vì đó là thứ chạy hằng ngày: robot đứng yên nên
# không bật ROS (nặng, và stack chết là kéo cả voice chết theo), màn rời chiếu /monitor cho
# người xem. Không cần truyền tham số nào.
#
# Cần robot chạy thật (nhà hàng, có Nav2):   make jetson STACK=1     (màn rời tự đổi sang customer_ui)
# Mặc định server lấy từ ORCHESTRATOR_URL trong .env; ghi đè khi cần:
#                                            make jetson SERVER_HOST=192.168.1.9:8000 ID=robo-2
# Chiếu trang khác lên màn rời:              make jetson URL=http://<SERVER_IP>:8000/panel
# Bỏ bớt phần nào:                           make jetson VOICE=0   /   make jetson WEB=0
#
# Log mỗi tiến trình được gắn tiền tố [stack] / [voice] / [web] nên vẫn đọc được
# đúng trình tự khởi động trong runbook. Ctrl-C một lần là tắt sạch cả ba.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# IP server chỉ khai MỘT chỗ: ORCHESTRATOR_URL trong .env. Trước đây host mặc định được
# hardcode ở đây, nên khi .env đổi sang mạng khác thì màn rời vẫn mở vào IP cũ đã chết và
# vòng chờ backend ở dưới quay đủ 90 lần (~3 phút) rồi mở ra trang lỗi.
if [ -z "${SERVER_HOST:-}" ] && [ -f .env ]; then
	SERVER_HOST="$(sed -n 's#^[[:space:]]*ORCHESTRATOR_URL[[:space:]]*=[[:space:]]*https\?://##p' .env \
		| tail -n 1 | tr -d '"'"'"'\r' | sed 's#[/[:space:]].*##')"
fi
if [ -z "${SERVER_HOST:-}" ]; then
	echo "Không đọc được ORCHESTRATOR_URL trong .env — truyền tay: make jetson SERVER_HOST=<ip>:8000" >&2
	exit 1
fi
ID="${ID:-robo-1}"
VOICE="${VOICE:-1}"
WEB="${WEB:-1}"
STACK="${STACK:-0}"
# Trang mặc định trên màn rời đi theo STACK, vì màn đó đóng hai vai khác hẳn nhau:
#   STACK=0 (demo hội chợ) -> /monitor : màn CHIẾU CHO NGƯỜI XEM, robot đứng yên, không có bàn nào
#   STACK=1 (nhà hàng)     -> /        : customer_ui, màn của KHÁCH ngồi tại bàn robot phục vụ
# Truyền URL= để ghi đè cả hai.
if [ "$STACK" = "1" ]; then
	URL="${URL:-http://$SERVER_HOST/}"
else
	URL="${URL:-http://$SERVER_HOST/monitor/}"
fi
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
echo "[run] màn rời: $URL"

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
STACK_PID=""
if [ "$STACK" = "1" ]; then
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
else
	echo "[run] STACK=0 — không bật ROS (robot không di chuyển trong buổi này)."
fi

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
		# Chromium/Chrome đã mở sẵn một cửa sổ thường (rất hay, vì máy demo còn dùng để tra cứu)
		# thì tiến trình mới chỉ đẩy URL sang instance cũ qua singleton lock rồi thoát: --kiosk bị
		# bỏ qua và trang chỉ hiện ra như một tab bình thường lẫn giữa các tab khác. Ép instance
		# RIÊNG bằng --user-data-dir. Hồ sơ riêng đó cũng nuốt luôn bong bóng "Restore pages?",
		# vốn hiện mỗi lần mở vì cleanup() ở trên giết trình duyệt cứng chứ không đóng tử tế.
		case "$(basename "$BROWSER")" in
		chromium*|google-chrome*|chrome*)
			# Bản snap bị nhốt trong interface `home`, không đọc được thư mục ẩn (~/.cache),
			# nên hồ sơ phải nằm trong vùng riêng của snap.
			if [ -z "${KIOSK_PROFILE:-}" ]; then
				case "$(readlink -f "$(command -v "$BROWSER")")" in
				/snap/*|/usr/bin/snap) KIOSK_PROFILE="$HOME/snap/chromium/common/ai-waiter-kiosk" ;;
				*) KIOSK_PROFILE="${XDG_CACHE_HOME:-$HOME/.cache}/ai-waiter-kiosk" ;;
				esac
			fi
			mkdir -p "$KIOSK_PROFILE"
			set -- --kiosk --user-data-dir="$KIOSK_PROFILE" --no-first-run \
				--noerrdialogs --disable-session-crashed-bubble --disable-infobars "$URL"
			;;
		firefox*)
			set -- --kiosk --new-instance "$URL"
			;;
		*)
			set -- --kiosk "$URL"
			;;
		esac
		echo "mở $BROWSER --kiosk $URL  (thoát kiosk: Ctrl+W / Alt+F4)"
		exec "$BROWSER" "$@" >/dev/null 2>&1
	) 2>&1 | tag web &
else
	echo "[run] WEB=0 — không mở trình duyệt."
fi

# Chờ: stack hoặc voice chết thì kéo theo phần còn lại (trap EXIT dọn). Trình duyệt
# đóng lại KHÔNG tính — tắt kiosk nhầm thì robot vẫn chạy tiếp.
if [ -z "$STACK_PID" ] && [ -z "$VOICE_PID" ]; then
	# Không có tiến trình nền nào để trông (STACK=0 VOICE=0): chỉ còn trình duyệt, chờ nó đóng.
	wait
else
	while :; do
		if [ -n "$STACK_PID" ] && ! kill -0 "$STACK_PID" 2>/dev/null; then
			echo "[run] hwstack đã thoát."
			break
		fi
		if [ -n "$VOICE_PID" ] && ! kill -0 "$VOICE_PID" 2>/dev/null; then
			echo "[run] voice đã thoát."
			break
		fi
		sleep 2
	done
fi
