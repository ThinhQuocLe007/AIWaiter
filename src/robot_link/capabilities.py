"""THE table: what the AGV can be told to do, and the exact command that does it.

This is the single place where a spoken intention becomes a `warehouse_agv_demo` invocation.
Everything upstream (STT, router, RAG, the fallback parser) exists to fill in an action dict;
everything downstream just runs `argv`. If the robot gains a skill, it gets a row here and
nothing else changes.

It lives in AIWaiter rather than in `warehouse_agv_demo` for three reasons: that project's logic
stays untouched by agreement; this mapping depends on AIWaiter's `inventory.csv`, `colors` and
`control_phrases`; and it imports nothing from ROS, so the Humble/Jazzy split that forced the UDP
link in the first place cannot reach it.

**`pick_box.sh`, not `run_storage_pick.sh`.** The mission script is the inner half. `pick_box.sh`
is the one that refuses to start when Gazebo is down, brings up the bridge / image relay / Nav2 /
V-JEPA if they are missing, waits for `bt_navigator` to go active — and, most importantly for this
demo, pulses `/warehouse/random_people/reset` so the five workers re-arm their crossings. Calling
the inner script directly still drives the AGV, but the second run of the day has the two workers
who cross the pick routes sitting wherever the last run left them, and the WAIT/PASS/REPLAN
scenario silently stops happening.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Storage areas and box colours the sa bàn physically has. Anything outside these is refused
# rather than passed through: `pick_box.sh` would reject it anyway, but failing here gives the
# operator a Vietnamese log line instead of an exit code.
STORAGES = ("A", "B", "C")
COLORS = ("blue", "red", "green")
PLACES = ("PACK", "DOCK")


@dataclass(frozen=True)
class Capability:
    """One thing the robot can be asked to do."""

    script: str
    flags: tuple[str, ...] = ()
    needs_storage: bool = False
    needs_color: bool = False
    # True when the mission script *errors out* without a colour, as opposed to resolving one at
    # the rack. Only `--resume-delivery` does: it needs to know which payload is on the tray, and
    # storage_pick_mission.py calls parser.error() if it isn't told.
    color_required: bool = False
    vi: str = ""
    example: str = ""


# ── Navigate tasks: a destination plus what to do on arrival ──────────────────
# The task verb is what separates "đi lấy thùng bia" from "đi tới khu B thôi, đừng lấy" — same
# destination, different mission. `fetch` is the default because it is what a warehouse order
# means when nobody says otherwise.
TASKS: dict[str, Capability] = {
    "fetch": Capability(
        script="pick_box.sh",
        flags=("--deliver",),
        needs_storage=True, needs_color=True,
        vi="đi lấy hàng rồi mang về trạm đóng gói",
        example="dẫn tôi đi lấy thùng bia",
    ),
    "fetch_hold": Capability(
        script="pick_box.sh",
        flags=("--pick-only",),
        needs_storage=True, needs_color=True,
        vi="đi lấy hàng, giữ trên khay, không mang về",
        example="lấy thùng bia rồi giữ trên xe",
    ),
    "goto": Capability(
        script="pick_box.sh",
        flags=("--route-only",),
        needs_storage=True, needs_color=False,
        vi="chỉ chạy tới kệ, không gắp gì cả (đây là bài demo né người)",
        example="qua khu C thôi, đừng lấy gì",
    ),
    "deliver": Capability(
        script="pick_box.sh",
        flags=("--resume-delivery",),
        needs_storage=True, needs_color=True, color_required=True,
        vi="hàng đã trên khay: chạy nốt chặng về và hạ xuống trạm đóng gói",
        example="mang về đi",
    ),
}

# ── Named places: a bare Nav2 goal, no picking involved ──────────────────────
# The sa bàn has exactly one anchor at this end of the warehouse — dropoff_PACK01. `dock_exit`
# sits 0.6 m from it in storage_routes.yaml and no script targets it, so "về trạm sạc" lands at
# the packing bay. Stated here rather than hidden, because on screen the two look identical and
# somebody will eventually ask.
PLACE_COMMANDS: dict[str, Capability] = {
    "PACK": Capability(
        script="run_task.sh", flags=("--destination", "packing"),
        vi="chạy tới trạm đóng gói", example="về trạm đóng gói",
    ),
    "DOCK": Capability(
        script="run_task.sh", flags=("--destination", "packing"),
        vi="chạy về trạm sạc (sa bàn dùng chung neo với trạm đóng gói, cách 0,6 m)",
        example="về trạm sạc",
    ),
}

# ── Manipulator: the five-stage scissor lift ─────────────────────────────────
LIFT_COMMANDS: dict[str, Capability] = {
    "up": Capability(script="run_lift_demo.sh", flags=("up",),
                     vi="nâng càng nâng lên", example="nâng càng lên"),
    "down": Capability(script="run_lift_demo.sh", flags=("down",),
                       vi="hạ càng nâng xuống", example="hạ càng xuống"),
}

# ── Run control: handled inside the bridge, not by a script ──────────────────
# Listed so this file stays the complete answer to "what can the robot be told to do", even
# though these three never shell out. See `bridge.RobotBridge._control` for how they work.
CONTROL_VI: dict[str, str] = {
    "stop": "đứng yên tại chỗ, giữ nguyên đích đến (nói “đi tiếp” để chạy lại)",
    "resume": "bỏ giữ, chạy tiếp đúng đích cũ, không tính lại đường",
    "cancel": "bỏ hẳn nhiệm vụ, hủy đích Nav2, đứng chờ lệnh mới",
}


class Unsupported(Exception):
    """The action names something the robot has no way to do."""


def resolve(action: dict) -> list[str]:
    """Turn one action dict into `[script, *flags]` for `warehouse_agv_demo`.

    Raises `Unsupported` with a Vietnamese reason rather than returning None, so the caller can
    log *why* nothing happened. Silence is the failure mode that wastes demo time.
    """
    kind = (action or {}).get("type")

    if kind == "lift":
        direction = str(action.get("direction") or "").lower()
        cap = LIFT_COMMANDS.get(direction)
        if cap is None:
            raise Unsupported(f"hướng nâng/hạ không hợp lệ: {direction!r}")
        return [cap.script, *cap.flags]

    if kind != "navigate":
        raise Unsupported(f"loại action không chạy được bằng script: {kind!r}")

    position = action.get("position") or {}
    token = str(position.get("token") or "").upper()

    if token in PLACE_COMMANDS:
        cap = PLACE_COMMANDS[token]
        return [cap.script, *cap.flags]

    if token not in STORAGES:
        raise Unsupported(f"sa bàn không có khu {token!r} (chỉ có {', '.join(STORAGES)}, "
                          f"{', '.join(PLACES)})")

    task = str(action.get("task") or "fetch").lower()
    cap = TASKS.get(task)
    if cap is None:
        raise Unsupported(f"không rõ việc cần làm: {task!r}")

    color = str(position.get("color") or "").lower()
    if color and color not in COLORS:
        raise Unsupported(f"sa bàn không có hộp màu {color!r}")
    if not color and cap.color_required:
        raise Unsupported(f"việc {task!r} phải biết hộp màu gì đang trên khay")

    argv = [cap.script, "--storage", token, *cap.flags]
    if color:
        argv += ["--color", color]
    # No colour and none required is fine: storage_pick_mission.py documents --color as optional
    # ("để trống để chọn sau khi tới tủ") — it drives to the rack and resolves the box on camera
    # there. "Qua khu B lấy hàng" without naming a colour gets exactly that.
    return argv


def describe() -> str:
    """The whole table as text — for the runbook, and for `make caps` before a demo."""
    lines = ["ROBOT LÀM ĐƯỢC NHỮNG GÌ (bảng mapping giọng nói → lệnh)", ""]
    lines.append("  ĐIỀU KHIỂN CHUYẾN ĐANG CHẠY (bridge xử lý, không gọi script)")
    for verb, vi in CONTROL_VI.items():
        lines.append(f"    {verb:<12} {vi}")
    lines.append("")
    lines.append("  ĐI + LÀM VIỆC Ở KỆ")
    for task, cap in TASKS.items():
        flags = " ".join(cap.flags)
        lines.append(f"    {task:<12} {cap.vi}")
        lines.append(f"    {'':<12} → {cap.script} --storage <A|B|C> {flags} [--color <màu>]")
        lines.append(f"    {'':<12} ví dụ: “{cap.example}”")
    lines.append("")
    lines.append("  ĐIỂM CÓ TÊN")
    for token, cap in PLACE_COMMANDS.items():
        lines.append(f"    {token:<12} {cap.vi}")
        lines.append(f"    {'':<12} → {cap.script} {' '.join(cap.flags)}   ví dụ: “{cap.example}”")
    lines.append("")
    lines.append("  CÀNG NÂNG")
    for direction, cap in LIFT_COMMANDS.items():
        lines.append(f"    {direction:<12} {cap.vi}")
        lines.append(f"    {'':<12} → {cap.script} {' '.join(cap.flags)}   ví dụ: “{cap.example}”")
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
