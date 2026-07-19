"""Long-conversation test: realistic 15-turn couple visit at Ốc Quậy.

A husband and wife visit the seafood restaurant. They browse the menu,
ask questions about dishes, order multiple items across several turns,
substitute items, review the cart, confirm, and pay.

Exercises: SEARCH (menu browse, questions, cart review), ORDER (single,
multi-item, substitution, off-menu, special_request), ORDER_CONFIRM,
PAYMENT (request + verify).

Backend dependency
------------------
The orchestrator backend (``make backend``, port 8000) is required for
turns 13-15 — confirm_order / request_payment / verify_payment POST to it.

Run
---
    uv run python -m tests.scripts.run_long_conversation --scenario A
    uv run python -m tests.scripts.run_long_conversation --all

Logs are saved to evals/results/long_conv_<timestamp>.log
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
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

from tests.scripts.conversations import SCENARIOS

_RESULTS_DIR = _REPO_ROOT / "evals" / "results"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
_LOG_PATH = _RESULTS_DIR / f"long_conv_{_TIMESTAMP}.log"
_REPORT_PATH = _RESULTS_DIR / f"long_conv_{_TIMESTAMP}.json"
_log_file: object = None


def _open_log():
    global _log_file
    _log_file = open(str(_LOG_PATH), "w", encoding="utf-8")


def _close_log():
    global _log_file
    if _log_file:
        _log_file.close()
        _log_file = None


def _log(msg: str):
    """Write to both stdout and the log file."""
    print(msg)
    if _log_file:
        _log_file.write(msg + "\n")
        _log_file.flush()


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





def backend_alive(base_url: str, timeout: float = 1.5) -> bool:
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def seat_test_table(base_url: str, table_id: str, party_size: int = 2) -> int | None:
    base = base_url.rstrip("/")
    from src._shared.types import normalise_table_id
    numeric_id = normalise_table_id(table_id)
    try:
        resp = httpx.post(
            f"{base}/seatings",
            json={"table_id": numeric_id, "party_size": party_size},
            timeout=5.0,
        )
        if resp.status_code == 201:
            return numeric_id
        if resp.status_code == 409:
            _log(_dim(f"  table {numeric_id} already seated, reusing"))
            return numeric_id
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return numeric_id
    except Exception as e:
        _log(_yellow(f"  seating failed: {e}"))
        return None


def reset_backend(base_url: str) -> None:
    try:
        httpx.post(f"{base_url.rstrip('/')}/admin/reset", timeout=5.0)
    except Exception:
        pass


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
        items.append(f"{i.name} ×{i.quantity}{extra}")
    total = getattr(cart, "total_price", 0)
    return "\n           ".join(items) + f"\n           {_bold(_format_price(total))}"


def _fmt_validator(state_values: dict) -> str:
    parts = []
    unavailable = state_values.get("unavailable_items")
    ambiguous = state_values.get("ambiguous_items")
    is_valid = state_values.get("is_valid", True)
    feedback = state_values.get("feedback")
    loop = state_values.get("loop_count", 0)

    parts.append(f"valid={_green('yes') if is_valid else _red('no')}")
    parts.append(f"loop={loop}")

    if ambiguous:
        for item in ambiguous:
            if isinstance(item, dict):
                name = item.get("name", "?")
                candidates = item.get("candidates", [])
                parts.append(_yellow(f"ambiguous: {name} → {candidates[:3]}..."))
    if unavailable:
        for item in unavailable:
            if isinstance(item, dict):
                name = item.get("name", "?")
                suggestion = item.get("suggestion", "none")
                parts.append(_red(f"off-menu: {name} → suggest={suggestion}"))
    if feedback:
        parts.append(_magenta(f"feedback: {feedback[:120]}"))
    return " | ".join(parts)


def run_turn(agent: AIWaiterGraph, text: str, table_id: str,
             session_id: str | None) -> tuple[dict, float, str | None]:
    t0 = time.time()
    result = agent.chat(query=text, table_id=table_id, session_id=session_id)
    latency = time.time() - t0
    return result, latency, result.get("session_id")


def inspect_state(agent: AIWaiterGraph, session_id: str) -> dict:
    try:
        snap = agent.app.get_state({"configurable": {"thread_id": session_id}})
        values = snap.values if snap else {}
    except Exception as e:
        return {"_inspect_error": str(e)}
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--backend-url", default=settings.ORCHESTRATOR_URL)
    parser.add_argument("--stop-on-fail", action="store_true",
                        help="Stop the conversation at the first failed turn")
    parser.add_argument("--scenario", default=None,
                        help="Run a single scenario by letter (A/B/C/D)")
    parser.add_argument("--all", action="store_true",
                        help="Run all scenarios sequentially")
    args = parser.parse_args()

    if args.all:
        scenarios_to_run: list[str] = list(SCENARIOS.keys())
    elif args.scenario:
        key = args.scenario.upper()
        if key not in SCENARIOS:
            print(_red(f"Unknown scenario '{args.scenario}'. Valid: {list(SCENARIOS.keys())}"))
            return 1
        scenarios_to_run = [key]
    else:
        # Default: run all
        scenarios_to_run = list(SCENARIOS.keys())

    _open_log()
    _log(f"Log file: {_LOG_PATH}")
    _log(f"Report file: {_REPORT_PATH}")

    _log("")
    _log(_bold("=" * 78))
    _log(_bold("  AI Waiter — Long Conversation Stress Test"))
    _log(_bold("=" * 78))
    count = len(scenarios_to_run)
    _log(_dim(f"  scenarios     : {count} ({', '.join(scenarios_to_run)})"))
    _log(_dim(f"  embed model   : {os.environ.get('EMBEDDING_MODEL') or 'AITeamVN/Vietnamese_Embedding (default)'}"))
    _log(_dim(f"  LLM models    : router={settings.ROUTER_MODEL} | worker={settings.WORKER_MODEL} | response={settings.RESPONSE_MODEL}"))
    _log(_dim(f"  backend URL   : {args.backend_url}"))

    backend_up = backend_alive(args.backend_url)
    if backend_up:
        _log(_green(f"  backend       : up"))
    else:
        _log(_yellow(f"  backend       : DOWN — confirm/payment turns will be skipped"))

    _log("")
    _log(_bold("Building agent graph..."))
    t0 = time.time()
    try:
        agent = AIWaiterGraph()
    except Exception as e:
        _log(_red(f"  FATAL: {e}"))
        traceback.print_exc()
        _close_log()
        return 1
    _log(_dim(f"  built in {time.time() - t0:.2f}s"))

    _log("")
    _log(_bold("Warmup turn (throwaway table — won't pollute test state)..."))
    try:
        warm = agent.chat(query="xin chào", table_id="T_warmup", session_id=None)
        _log(_dim(f"  ok (session={warm.get('session_id')})"))
    except Exception as e:
        _log(_yellow(f"  skipped: {e}"))

    all_reports: list[dict] = []
    global_status = 0

    for key in scenarios_to_run:
        conv = SCENARIOS[key]

        if backend_up:
            numeric_id = seat_test_table(args.backend_url, conv.table_id, conv.party_size)
            if numeric_id is None:
                _log(_yellow(f"  seating: FAILED for table {conv.table_id}"))
            else:
                _log(_green(f"  seating: table {numeric_id} ready"))

        _log("")
        _log(_bold("=" * 78))
        _log(_bold(f"  {conv.name} ({conv.table_id}, {len(conv)} turns)"))
        _log(_bold("=" * 78))

        report = {
            "scenario": key,
            "name": conv.name,
            "table_id": conv.table_id,
            "turns": [],
        }
        session_id: str | None = None
        scenario_latency = 0.0
        turn_failures = 0
        prev_msg_count = 0

        for idx, turn in enumerate(conv.turns, start=1):
            text, note, expected_intent = turn.text, turn.note, turn.expected_intent
            needs_backend = expected_intent in ("ORDER_CONFIRM", "PAYMENT")
            if needs_backend and not backend_up:
                _log("")
                _log(_bold(f"[Turn {idx}/{len(conv)}] ") + _cyan("USER: ") + text)
                _log(_yellow(f"  ⚠ backend down — skipping"))
                report["turns"].append({
                    "turn": idx, "skipped": True, "reason": "backend down",
                    "text": text, "note": note, "expected_intent": expected_intent,
                })
                continue

            _log("")
            _log(_bold(f"[Turn {idx}/{len(conv)}] ") + _cyan("USER: ") + text)
            _log(_dim(f"  purpose: {note}  |  expected: {expected_intent}"))

            try:
                result, latency, new_sid = run_turn(agent, text, conv.table_id, session_id)
            except Exception as e:
                _log(_red(f"  ✗ CRASH: {type(e).__name__}: {e}"))
                traceback.print_exc()
                turn_failures += 1
                report["turns"].append({
                    "turn": idx, "failed": True,
                    "error": f"{type(e).__name__}: {e}",
                    "text": text, "note": note, "expected_intent": expected_intent,
                })
                if args.stop_on_fail:
                    break
                continue

            session_id = new_sid
            state = inspect_state(agent, session_id)
            routing = state.get("routing_meta") or {}

            intent = routing.get("semantic_intent") or "?"
            decided = routing.get("decided_by") or "?"
            conf = routing.get("semantic_confidence")
            conf_str = f", conf={conf:.3f}" if isinstance(conf, (int, float)) else ""

            scenario_latency += latency

            _log(f"  ├─ router:     {intent} ({_bold(decided)}{conf_str})")
            if routing.get("slm_intents"):
                _log(f"  │  slm_out:   {routing['slm_intents']}")
            _log(f"  │  sem_all:    {routing.get('semantic_all_sims', {})}")

            all_msgs = state.get("messages", [])
            new_msgs = all_msgs[prev_msg_count:]
            tool_calls_done = []
            for msg in new_msgs:
                for tc in (getattr(msg, "tool_calls", None) or []):
                    if isinstance(tc, dict):
                        tool_calls_done.append({"name": tc.get("name"), "args": tc.get("args", {})})

            if tool_calls_done:
                for tc in tool_calls_done:
                    name = tc["name"]
                    tc_args = tc["args"]
                    if name == "add_cart":
                        items = tc_args.get("items", [])
                        pretty = ", ".join(f"{i.get('name','?')}×{i.get('quantity','?')}" for i in items)
                        _log(f"  ├─ tool:       {_green(name)}([{pretty}])")
                    elif name == "remove_cart":
                        _log(f"  ├─ tool:       {_yellow(name)}({tc_args.get('name','?')})")
                    elif name == "clear_cart":
                        _log(f"  ├─ tool:       {_red(name)}()")
                    elif name == "confirm_order":
                        items = tc_args.get("items", [])
                        _log(f"  ├─ tool:       {_green(name)}(table={tc_args.get('table_id')}, {len(items)} items)")
                    elif name == "search":
                        _log(f"  ├─ tool:       {_cyan(name)}({tc_args.get('query','?')!r})")
                    elif name == "request_payment":
                        _log(f"  ├─ tool:       {_magenta(name)}(table={tc_args.get('table_id')})")
                    elif name == "verify_payment":
                        _log(f"  ├─ tool:       {_magenta(name)}(table={tc_args.get('table_id')})")
                    else:
                        _log(f"  ├─ tool:       {name}({tc_args})")
            else:
                _log(f"  ├─ tool:       {_red('none')}")

            _log(f"  ├─ validator:  {_fmt_validator(state)}")

            cart = state.get("active_cart")
            _log(f"  ├─ cart:       {_fmt_cart(cart)}")

            stage = state.get("order_stage") or result.get("final_stage", "?")
            action = result.get("action")
            action_str = action.get("action") if isinstance(action, dict) else str(action) if action else "(none)"
            _log(f"  ├─ stage:      {_bold(stage)}  |  ui_action: {action_str}")
            _log(f"  ├─ latency:    {latency:.2f}s")
            _log(f"  └─ AGENT:      {result.get('response', '')[:300]}")

            intent_ok = (intent == expected_intent
                         or (expected_intent == "SEARCH" and intent == "CHAT")
                         or (expected_intent == "ORDER" and intent == "ORDER_CONFIRM"))

            report["turns"].append({
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
                "semantic_all_sims": routing.get("semantic_all_sims", {}),
                "unavailable_items": [
                    {"name": i.get("name"), "suggestion": i.get("suggestion")}
                    for i in (state.get("unavailable_items") or [])
                ] if state.get("unavailable_items") else None,
                "ambiguous_items": [
                    {"name": i.get("name"), "candidates": i.get("candidates")}
                    for i in (state.get("ambiguous_items") or [])
                ] if state.get("ambiguous_items") else None,
                "loop_count": state.get("loop_count", 0),
                "response": result.get("response", "")[:500],
            })

            prev_msg_count = len(all_msgs)

        # ── Per-scenario summary ──
        summary = report["turns"]
        passed = sum(1 for r in summary if not r.get("skipped") and not r.get("failed") and r.get("tools_called"))
        total = sum(1 for r in summary if not r.get("skipped") and not r.get("failed"))
        skipped = sum(1 for r in summary if r.get("skipped"))
        crashed = sum(1 for r in summary if r.get("failed"))
        no_tool = sum(1 for r in summary if not r.get("skipped") and not r.get("failed") and not r.get("tools_called"))

        _log("")
        _log(_bold("-" * 78))
        _log(_bold(f"  {conv.name} — SUMMARY"))
        _log(_bold("-" * 78))
        _log(f"{'#':>2} {'lat':>6} {'expected':<12} {'actual':<12} {'router':<10} {'tools':<20} {'stage':<22} text")
        _log(_dim("-" * 90))
        for row in summary:
            if row.get("skipped"):
                _log(_yellow(f"{row['turn']:>2} {'—':>6} {'SKIPPED':<12} {'—':<12} {'—':<10} {'—':<20} {'—':<22} {row['text'][:50]}"))
            elif row.get("failed"):
                err = row.get("error", "?")[:25]
                _log(_red(f"{row['turn']:>2} {'—':>6} {'CRASH':<12} {err:<12} {'—':<10} {'—':<20} {'—':<22} {row['text'][:50]}"))
            else:
                tools = ",".join(row.get("tools", ["none"]))[:18]
                intent_icon = "✓" if row.get("intent_match") else "?"
                actual = row.get("actual_intent", "?")
                tool_icon = "✓" if row.get("tools_called") else "✗"
                _log(f"{row['turn']:>2} {row.get('latency', 0):>5.2f}s "
                     f"{row.get('expected_intent', '?'):<12} "
                     f"{actual}{intent_icon:<11} "
                     f"{row.get('decided_by', '?'):<10} "
                     f"{tools}{tool_icon:<2} "
                     f"{row.get('stage', '?'):<22} "
                     f"{row['text'][:50]}")

        _log("")
        _log(f"  Turns executed   : {total}")
        _log(f"  Tools called     : {_green(str(passed))}")
        _log(f"  Tools NOT called : {_red(str(no_tool))}")
        _log(f"  Crashes          : {_red(str(crashed))}")
        _log(f"  Total latency    : {scenario_latency:.1f}s")
        _log(f"  Avg latency/turn : {scenario_latency / max(total, 1):.2f}s")

        report["summary"] = {
            "total_turns": total, "turns_with_tools": passed,
            "turns_without_tools": no_tool, "skipped": skipped, "crashes": crashed,
            "total_latency_s": round(scenario_latency, 1),
            "avg_latency_s": round(scenario_latency / max(total, 1), 2),
        }
        all_reports.append(report)

        if crashed:
            global_status = 1
        elif no_tool:
            global_status = 2

        if backend_up:
            reset_backend(args.backend_url)

    # ── Save combined JSON report ──
    combined = {
        "timestamp": _TIMESTAMP,
        "backend_up": backend_up,
        "models": {
            "router": settings.ROUTER_MODEL,
            "worker": settings.WORKER_MODEL,
            "response": settings.RESPONSE_MODEL,
        },
        "embedding_model": os.environ.get("EMBEDDING_MODEL") or "AITeamVN/Vietnamese_Embedding (default)",
        "scenarios": all_reports,
    }
    with open(str(_REPORT_PATH), "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2, default=str)
    _log(_dim(f"\n  JSON report saved to {_REPORT_PATH}"))

    if backend_up:
        reset_backend(args.backend_url)

    _close_log()

    if global_status == 1:
        print(_red("\n✗ One or more scenarios had crashes"))
        return 1
    if global_status == 2:
        print(_yellow(f"\n⚠ Some turns had no tool calls"))
    print(_green("\n✓ All scenarios completed"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
