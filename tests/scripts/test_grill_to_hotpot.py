"""End-to-end test: Grill-to-Hotpot scenario with auto backend + agent lifecycle.

What it does
------------
1. Starts orchestrator backend (port 8000) as a subprocess
2. Starts AI Waiter agent (port 8100) as a subprocess
3. Waits for both to become healthy
4. Seeds the test table
5. Runs the GRILL_TO_HOTPOT conversation scenario (5 turns):
   - ask about grilled → ORDER grilled → replace with hotpot → ORDER hotpot → CONFIRM
6. Prints per-turn details + summary table
7. Saves JSON report to evals/results/
8. Shuts down both services

Usage
-----
    uv run python tests/scripts/test_grill_to_hotpot.py
    uv run python tests/scripts/test_grill_to_hotpot.py --keep-alive  # don't stop backend+agent

Dependencies
------------
- Ollama must be running with qwen2.5:7b-instruct (or whatever .env points to)
- FAISS + BM25 indices must exist (run `make reindex` if missing)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import signal
import subprocess
import sys
import time
import traceback
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

import httpx

from src.agent_brain.agent import AIWaiterGraph
from src.agent_brain.config import settings
from tests.scripts.conversations.grill_to_hotpot import GRILL_TO_HOTPOT

_RESULTS_DIR = _REPO_ROOT / "evals" / "results"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
_JSON_REPORT = _RESULTS_DIR / f"grill_to_hotpot_{_TIMESTAMP}.json"
_LOG_PATH = _RESULTS_DIR / f"grill_to_hotpot_{_TIMESTAMP}.log"

_log_fh: object = None
_processes: list[subprocess.Popen] = []


# ── ANSI ────────────────────────────────────────────────────────────────────
def _supports_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


_USE_COLOR = _supports_color()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def _green(t: str) -> str: return _c("32", t)
def _yellow(t: str) -> str: return _c("33", t)
def _red(t: str) -> str: return _c("31", t)
def _cyan(t: str) -> str: return _c("36", t)
def _dim(t: str) -> str: return _c("2", t)
def _bold(t: str) -> str: return _c("1", t)
def _magenta(t: str) -> str: return _c("35", t)


def _log(msg: str):
    print(msg)
    if _log_fh:
        _log_fh.write(msg + "\n")
        _log_fh.flush()


# ── Service lifecycle ───────────────────────────────────────────────────────
def _start_service(name: str, cmd: list[str], env_extra: dict[str, str] | None = None) -> subprocess.Popen:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    _log(_dim(f"  Starting {name}: {' '.join(cmd)}"))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        cwd=str(_REPO_ROOT),
        text=True,
    )
    _processes.append(proc)
    return proc


def _wait_healthy(url: str, label: str, timeout: float = 120.0) -> bool:
    _log(_dim(f"  Waiting for {label} at {url} ..."))
    deadline = time.time() + timeout
    last_err = ""
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=3.0)
            if r.status_code == 200:
                _log(_green(f"  {label} is healthy (status={r.status_code})"))
                return True
            last_err = f"status={r.status_code}"
        except Exception as e:
            last_err = str(e)
        time.sleep(1.5)
    _log(_red(f"  {label} did NOT become healthy in {timeout}s: {last_err}"))
    return False


def _start_backend() -> subprocess.Popen | None:
    _log(_bold("\n[1/4] Starting orchestrator backend (port 8000)..."))
    proc = _start_service("backend", [
        "uv", "run", "uvicorn", "src.server_orchestrator.main:app",
        "--host", "0.0.0.0", "--port", "8000",
    ])
    if not _wait_healthy("http://localhost:8000/health", "Backend"):
        return None
    return proc


def _start_agent() -> subprocess.Popen | None:
    _log(_bold("\n[2/4] Starting AI Waiter agent (port 8100)..."))
    proc = _start_service("agent", [
        "uv", "run", "uvicorn", "src.agent_brain.server:app",
        "--host", "0.0.0.0", "--port", "8100",
    ])
    if not _wait_healthy("http://localhost:8100/health", "Agent", timeout=180.0):
        return None
    return proc


def _shutdown():
    _log(_bold("\n[Cleanup] Stopping services..."))
    for proc in _processes:
        try:
            proc.send_signal(signal.SIGINT)
        except Exception:
            pass
    for proc in _processes:
        try:
            proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            proc.kill()
    _processes.clear()
    _log(_dim("  All services stopped."))


def _seat_table(table_id: str, party_size: int = 2) -> bool:
    from src._shared.types import normalise_table_id
    numeric_id = normalise_table_id(table_id)
    try:
        resp = httpx.post(
            f"http://localhost:8000/seatings",
            json={"table_id": numeric_id, "party_size": party_size},
            timeout=5.0,
        )
        if resp.status_code in (201, 409):
            return True
        _log(_yellow(f"  Seating failed: status={resp.status_code} body={resp.text[:120]}"))
        return False
    except Exception as e:
        _log(_yellow(f"  Seating failed: {e}"))
        return False


# ── State inspection ────────────────────────────────────────────────────────
def inspect_state(agent: AIWaiterGraph, session_id: str) -> dict:
    try:
        snap = agent.app.get_state({"configurable": {"thread_id": session_id}})
        return snap.values if snap else {}
    except Exception as e:
        return {"_inspect_error": str(e)}


def _format_price(vnd: float) -> str:
    return f"{int(vnd):,}₫".replace(",", ".")


def _fmt_cart(cart) -> str:
    if not cart or not getattr(cart, "items", None):
        return _dim("(empty)")
    items = []
    for i in cart.items:
        extra = ""
        if getattr(i, "special_requests", None):
            extra = f" [{i.special_requests}]"
        items.append(f"{i.name} x{i.quantity}{extra}")
    total = getattr(cart, "total_price", 0)
    return "\n           ".join(items) + f"\n           {_bold(_format_price(total))}"


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--keep-alive", action="store_true",
                        help="Don't stop backend + agent after the test")
    parser.add_argument("--skip-services", action="store_true",
                        help="Assume backend + agent are already running (ports 8000, 8100)")
    args = parser.parse_args()

    global _log_fh
    _log_fh = open(str(_LOG_PATH), "w", encoding="utf-8")

    _log(_bold("=" * 78))
    _log(_bold("  AI Waiter — Grill to Hotpot E2E Test"))
    _log(_bold("=" * 78))
    _log(_dim(f"  timestamp     : {_TIMESTAMP}"))
    _log(_dim(f"  scenario      : {GRILL_TO_HOTPOT.name}"))
    _log(_dim(f"  table_id      : {GRILL_TO_HOTPOT.table_id}"))
    _log(_dim(f"  party_size    : {GRILL_TO_HOTPOT.party_size}"))
    _log(_dim(f"  turns         : {len(GRILL_TO_HOTPOT)}"))
    _log(_dim(f"  embed model   : {os.environ.get('EMBEDDING_MODEL') or 'default'}"))
    _log(_dim(f"  LLM models    : router={settings.ROUTER_MODEL} | worker={settings.WORKER_MODEL} | response={settings.RESPONSE_MODEL}"))
    _log(_dim(f"  log file      : {_LOG_PATH}"))
    _log(_dim(f"  json report   : {_JSON_REPORT}"))

    # ── Start services ───────────────────────────────────────────────────────
    if not args.skip_services:
        backend_proc = _start_backend()
        if backend_proc is None:
            _log(_red("\n✗ Backend failed to start. Exiting."))
            _shutdown()
            return 1

        # Kill existing agent on 8100 if any
        try:
            subprocess.run(["fuser", "-k", "8100/tcp"], capture_output=True, timeout=3)
        except Exception:
            pass

        agent_proc = _start_agent()
        if agent_proc is None:
            _log(_red("\n✗ Agent failed to start. Exiting."))
            _shutdown()
            return 1

        # Reset backend + wipe stale checkpoints BEFORE seating
        _log(_bold("\n[3/4] Resetting state..."))
        try:
            httpx.post("http://localhost:8000/admin/reset", timeout=5.0)
        except Exception:
            pass
        ckp = _REPO_ROOT / "storage" / "db" / "checkpoints.db"
        if ckp.exists():
            ckp.unlink()
        _log(_dim("  Backend reset + checkpoints wiped."))

        # Seat the test table
        if _seat_table(GRILL_TO_HOTPOT.table_id, GRILL_TO_HOTPOT.party_size):
            _log(_green(f"  Table {GRILL_TO_HOTPOT.table_id} seated."))
        else:
            _log(_yellow(f"  Seating may have failed — continuing anyway"))
    else:
        _log(_yellow("\n  --skip-services: assuming backend + agent are already up"))

    # ── Build agent graph ────────────────────────────────────────────────────
    _log(_bold("\n[4/4] Building agent graph..."))
    t0 = time.time()
    try:
        agent = AIWaiterGraph()
    except Exception as e:
        _log(_red(f"  FATAL: {e}"))
        traceback.print_exc()
        if not args.keep_alive:
            _shutdown()
        return 1
    _log(_dim(f"  built in {time.time() - t0:.2f}s"))

    # ── Warmup ───────────────────────────────────────────────────────────────
    _log(_bold("\nWarmup turn..."))
    warmup_tid = f"T_warmup_{uuid.uuid4().hex[:6]}"
    try:
        warm = agent.chat(query="xin chào", table_id=warmup_tid, session_id=None)
        _log(_dim(f"  ok (session={warm.get('session_id')})"))
    except Exception as e:
        _log(_yellow(f"  skipped: {e}"))

    # ── Run scenario ─────────────────────────────────────────────────────────
    _log(_bold("\n" + "=" * 78))
    _log(_bold(f"  RUNNING: {GRILL_TO_HOTPOT.name}"))
    _log(_bold("=" * 78))

    session_id: str | None = None
    report_turns: list[dict] = []
    total_latency = 0.0
    failed = False
    prev_msg_count = 0

    for idx, turn in enumerate(GRILL_TO_HOTPOT.turns, start=1):
        text, note, expected_intent = turn.text, turn.note, turn.expected_intent

        _log("")
        _log(_bold(f"[Turn {idx}/{len(GRILL_TO_HOTPOT)}] ") + _cyan("USER: ") + text)
        _log(_dim(f"  purpose   : {note}"))
        _log(_dim(f"  expected  : {expected_intent}"))

        t_start = time.time()
        try:
            result = agent.chat(query=text, table_id=GRILL_TO_HOTPOT.table_id, session_id=session_id)
        except Exception as e:
            _log(_red(f"  ✗ CRASH: {type(e).__name__}: {e}"))
            traceback.print_exc()
            failed = True
            report_turns.append({
                "turn": idx, "failed": True,
                "error": f"{type(e).__name__}: {e}",
                "text": text, "note": note, "expected_intent": expected_intent,
            })
            continue

        latency = time.time() - t_start
        total_latency += latency
        session_id = result.get("session_id")

        state = inspect_state(agent, session_id)
        routing = state.get("routing_meta") or {}

        # Extract tool calls from messages added this turn
        all_msgs = state.get("messages", [])
        new_msgs = all_msgs[prev_msg_count:]
        tool_calls_done = []
        for msg in new_msgs:
            for tc in (getattr(msg, "tool_calls", None) or []):
                if isinstance(tc, dict):
                    tool_calls_done.append({"name": tc.get("name"), "args": tc.get("args", {})})

        # Derive actual intent from tool calls as the most reliable indicator
        tool_names = [tc["name"] for tc in tool_calls_done]
        if "search" in tool_names:
            actual_intent = "SEARCH"
        elif "confirm_order" in tool_names:
            actual_intent = "ORDER_CONFIRM"
        elif "request_payment" in tool_names or "verify_payment" in tool_names:
            actual_intent = "PAYMENT"
        elif any(t in tool_names for t in ("add_cart", "remove_cart", "clear_cart")):
            actual_intent = "ORDER"
        else:
            actual_intent = (routing.get("semantic_intent") or routing.get("final_intent") or "CHAT")
        intent = actual_intent
        decided = routing.get("decided_by") or "?"
        conf = routing.get("semantic_confidence") or routing.get("confidence")
        conf_str = f", conf={conf:.3f}" if isinstance(conf, (int, float)) else ""

        # Print tool calls
        if tool_calls_done:
            for tc in tool_calls_done:
                name = tc["name"]
                tc_args = tc["args"]
                if name == "add_cart":
                    items = tc_args.get("items", [])
                    pretty = ", ".join(f"{i.get('name','?')}x{i.get('quantity','?')}" for i in items)
                    _log(f"  ├─ tool:     {_green(name)}([{pretty}])")
                elif name == "remove_cart":
                    _log(f"  ├─ tool:     {_yellow(name)}({tc_args.get('name','?')})")
                elif name == "clear_cart":
                    _log(f"  ├─ tool:     {_red(name)}()")
                elif name == "confirm_order":
                    items = tc_args.get("items", [])
                    _log(f"  ├─ tool:     {_green(name)}(table={tc_args.get('table_id')}, {len(items)} items)")
                elif name == "search":
                    _log(f"  ├─ tool:     {_cyan(name)}({tc_args.get('query','?')!r})")
                elif name == "request_payment":
                    _log(f"  ├─ tool:     {_magenta(name)}(table={tc_args.get('table_id')})")
                else:
                    _log(f"  ├─ tool:     {name}({tc_args})")
        else:
            _log(f"  ├─ tool:     {_red('none')}")

        # Router info
        _log(f"  ├─ router:   {intent} ({decided}{conf_str})")

        # Validator info
        is_valid = state.get("is_valid", True)
        feedback = state.get("feedback", "")
        loop = state.get("loop_count", 0)
        val_str = f"valid={_green('yes') if is_valid else _red('no')}, loop={loop}"
        if not is_valid and feedback:
            val_str += f", feedback={feedback[:120]}"
        _log(f"  ├─ validator:{val_str}")

        # Cart
        cart = state.get("active_cart")
        _log(f"  ├─ cart:     {_fmt_cart(cart)}")

        # Stage + UI action
        stage = state.get("order_stage") or result.get("final_stage", "?")
        action = result.get("action")
        action_str = action.get("action") if isinstance(action, dict) else str(action) if action else "(none)"
        _log(f"  ├─ stage:    {_bold(stage)}  |  ui_action: {action_str}")

        _log(f"  ├─ latency:  {latency:.2f}s")
        _log(f"  └─ AGENT:    {result.get('response', '')[:500]}")

        intent_ok = (actual_intent == expected_intent
                     or (expected_intent == "SEARCH" and actual_intent == "CHAT")
                     or (expected_intent == "ORDER" and actual_intent == "ORDER_CONFIRM"))

        report_turns.append({
            "turn": idx, "text": text, "note": note,
            "expected_intent": expected_intent,
            "actual_intent": intent,
            "decided_by": decided,
            "confidence": conf,
            "intent_match": intent_ok,
            "tools": [tc["name"] for tc in tool_calls_done],
            "tools_called": bool(tool_calls_done),
            "stage": stage,
            "action": action_str,
            "latency": round(latency, 2),
            "validator_valid": is_valid,
            "loop_count": loop,
            "response": result.get("response", "")[:500],
        })

        prev_msg_count = len(all_msgs)

    # ── Summary ──────────────────────────────────────────────────────────────
    _log("")
    _log(_bold("=" * 78))
    _log(_bold("  SCENARIO SUMMARY"))
    _log(_bold("=" * 78))
    header = f"{'#':>2}  {'lat':>6}  {'expected':<14}  {'actual':<16}  {'tool':<18}  {'stage':<24}  text"
    _log(_dim(header))
    _log(_dim("-" * 100))

    for row in report_turns:
        if row.get("failed"):
            err = row.get("error", "?")[:25]
            _log(_red(f"{row['turn']:>2}  {'—':>6}  {'CRASH':<14}  {err:<16}  {'—':<18}  {'—':<24}  {row['text'][:50]}"))
        else:
            tools = ",".join(row.get("tools", ["none"]))[:16]
            actual = row.get("actual_intent", "?")
            intent_icon = "✓" if row.get("intent_match") else "?"
            tool_icon = "✓" if row.get("tools_called") else "✗"
            _log(f"{row['turn']:>2}  {row.get('latency', 0):>5.2f}s  "
                 f"{row.get('expected_intent', '?'):<14}  "
                 f"{actual}{intent_icon:<15}  "
                 f"{tools}{tool_icon:<2}  "
                 f"{row.get('stage', '?'):<24}  "
                 f"{row['text'][:50]}")

    total = sum(1 for r in report_turns if not r.get("failed"))
    tool_count = sum(1 for r in report_turns if not r.get("failed") and r.get("tools_called"))
    no_tool = sum(1 for r in report_turns if not r.get("failed") and not r.get("tools_called"))
    crashed = sum(1 for r in report_turns if r.get("failed"))

    _log("")
    _log(f"  Total turns      : {len(report_turns)}")
    _log(f"  Executed (no crash): {total}")
    _log(f"  Tools called      : {_green(str(tool_count))}")
    _log(f"  Tools NOT called  : {_red(str(no_tool))}")
    _log(f"  Crashes           : {_red(str(crashed))}")
    _log(f"  Total latency     : {total_latency:.1f}s")
    _log(f"  Avg latency/turn  : {total_latency / max(total, 1):.2f}s")

    # ── Save JSON report ─────────────────────────────────────────────────────
    report = {
        "timestamp": _TIMESTAMP,
        "scenario_name": GRILL_TO_HOTPOT.name,
        "table_id": GRILL_TO_HOTPOT.table_id,
        "party_size": GRILL_TO_HOTPOT.party_size,
        "models": {
            "router": settings.ROUTER_MODEL,
            "worker": settings.WORKER_MODEL,
            "response": settings.RESPONSE_MODEL,
        },
        "embedding_model": os.environ.get("EMBEDDING_MODEL") or "default",
        "turns": report_turns,
    }
    with open(str(_JSON_REPORT), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    _log(_dim(f"\n  JSON report saved to {_JSON_REPORT}"))

    # ── Shutdown ─────────────────────────────────────────────────────────────
    if not args.keep_alive and not args.skip_services:
        _shutdown()

    _log_fh.close()

    if crashed:
        print(_red(f"\n✗ {crashed} turn(s) crashed"))
        return 1
    if no_tool:
        print(_yellow(f"\n⚠ {no_tool} turn(s) had no tool calls"))
    print(_green("\n✓ Test completed successfully"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
