"""Read and set this device's speaker / microphone levels through ``pactl``.

The voice monitor has two sliders; this is what they actually move. PulseAudio — or PipeWire's
pulse shim, which is what a stock Jetson desktop runs — owns the levels, so the honest way to
change them is the same command the runbook tells a human to type. Applying a software gain to
our own stream instead would leave ``pactl`` and the sliders disagreeing about the truth, and the
next person to run ``pactl set-sink-volume`` by hand would silently undo the slider.

Version-proofing, and the reason this reads ``pactl list`` instead of the obvious one-liner:
``pactl get-sink-volume`` only exists from pactl 15 (Ubuntu 22.04 / JetPack 6). A Jetson still on
JetPack 5 ships pactl 13, where that subcommand does not exist at all — but ``pactl list sinks``
and ``pactl set-sink-volume`` are present on both. So reads go through the older, uglier path on
purpose.

Everything here is best-effort and returns ``None`` rather than raising: a machine with no pactl
(the device code run on a bare-ALSA dev box) must leave the sliders disabled, not send an
exception up into the WS receive loop and drop the mic's connection to the hub.
"""

import re
import shutil
import subprocess

# What the wire calls each target, and the pactl object behind it.
_TARGETS = {
    "speaker": ("Sink", "sinks", "set-sink-volume"),
    "mic": ("Source", "sources", "set-source-volume"),
}

# The speaker stops at 100%: past that PulseAudio applies digital gain and a demo hall hears
# clipping, not loudness. The mic is allowed past it because a quiet USB capsule in a noisy hall
# genuinely needs the headroom, and an over-driven mic costs a word, not the whole reply.
_MAX = {"speaker": 100, "mic": 150}

_CMD_TIMEOUT = 3.0


def available() -> bool:
    """Is pactl even installed? False disables the sliders instead of failing every call."""
    return shutil.which("pactl") is not None


def _run(args: list[str]) -> str | None:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=_CMD_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _default_name(kind: str) -> str | None:
    """The name of the current default sink/source, per `pactl info`."""
    info = _run(["pactl", "info"])
    if not info:
        return None
    for line in info.splitlines():
        if line.startswith(f"Default {kind}:"):
            return line.split(":", 1)[1].strip()
    return None


def get_level(target: str) -> int | None:
    """Current volume of the default sink/source, in percent. None if it can't be read."""
    spec = _TARGETS.get(target)
    if spec is None:
        return None
    kind, listing, _ = spec
    name = _default_name(kind)
    if not name:
        return None
    out = _run(["pactl", "list", listing])
    if not out:
        return None
    for block in out.split("\n\n"):
        if not re.search(rf"^\s*Name:\s*{re.escape(name)}\s*$", block, re.M):
            continue
        # `^\s*Volume:` and not just `Volume:` — the same block also carries a "Base Volume:"
        # line, which is the hardware reference level and not what the slider is showing.
        m = re.search(r"^\s*Volume:.*?/\s*(\d+)%", block, re.M)
        return int(m.group(1)) if m else None
    return None


def set_level(target: str, percent: int) -> int | None:
    """Set the default sink/source volume, then read back what actually took effect.

    Reading back rather than echoing the requested number: pactl silently clamps, and a slider
    that keeps showing a value the hardware refused is worse than one that snaps back.
    """
    spec = _TARGETS.get(target)
    if spec is None:
        return None
    kind, _, setter = spec
    name = _default_name(kind)
    if not name:
        return None
    pct = max(0, min(int(percent), _MAX[target]))
    if _run(["pactl", setter, name, f"{pct}%"]) is None:
        return None
    return get_level(target)


def get_levels() -> dict[str, int | None]:
    """Both levels at once — what the device reports on connect so the sliders start honest."""
    return {"speaker": get_level("speaker"), "mic": get_level("mic")}
