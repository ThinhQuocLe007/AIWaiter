"""End-to-end smoke test: one realistic guest visit, all five intents.

What it does
------------
Spins up ``AIWaiterGraph`` (the same object ``make agent`` uses) and walks a
guest through 8 turns that exercise every node in the LangGraph:

    CHAT  ->  SEARCH  ->  SEARCH  ->  ORDER  ->  ORDER
            ->  ORDER_CONFIRM  ->  PAYMENT  ->  PAYMENT

Prints each turn's intent, tool call, UI action, stage, and the agent's reply,
plus a final summary table. Exits 0 if no turn throws, 1 if any turn explodes
(so this is also a regression smoke — the error in
``src/agent_brain/services/retriever/indices/embeddings.py`` will show up on
turn 2 the moment ``search`` tries to embed the query).

Backend dependency
------------------
The orchestrator backend (``make backend``, port 8000) is required for
turns 6-8 — the ``confirm_order`` / ``request_payment`` / ``verify_payment``
tools POST to it. If it's down, those turns are skipped with a clear warning
so the earlier turns (which DON'T hit the backend) can still surface the
embedding error. Exits 0 either way; this is a smoke, not a strict gate.

Run
---
    uv run python tests/scripts/run_conversation_demo.py
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
import uuid
from pathlib import Path

# Repo root on sys.path so `from src.agent_brain.agent import …` resolves.
# Done BEFORE any project imports; conftest.py is for pytest, this script
# is also usable as a plain `python tests/scripts/run_conversation_demo.py`.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

import httpx  # used only for the /health probe

from src.agent_brain.agent import AIWaiterGraph
from src.agent_brain.config import settings
from langchain_core.messages import AIMessage, ToolMessage


# ── ANSI helpers (no third-party dep) ─────────────────────────────────────────
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


# ── Config ───────────────────────────────────────────────────────────────────
DEFAULT_TABLE_ID = f"T_demo_{uuid.uuid4().hex[:6]}"  # unique per run → no bleed

# The conversation: (turn text, what this turn primarily exercises)
CONVERSATION: list[tuple[str, str]] = [
    ("Chào bạn",                                            "greeting / CHAT"),
    ("Bạn có những món gì?",                               "menu search / SEARCH"),
    ("Có món chay nào không?",                             "filtered search / SEARCH"),
    ("Cho mình 2 Ốc Hương xốt trứng muối với 1 cơm chiên", "place order / ORDER"),
    ("Thêm 1 nước cam",                                    "add to cart / ORDER"),
    ("OK xác nhận luôn",                                   "confirm / ORDER_CONFIRM"),
    ("Tính tiền giúp mình",                                "request payment / PAYMENT"),
    ("Mình chuyển khoản xong rồi",                         "verify payment / PAYMENT"),
]


# ── Backend reachability check ───────────────────────────────────────────────
def backend_alive(base_url: str, timeout: float = 1.5) -> bool:
    """Quick TCP/HTTP probe of the orchestrator. Fast-fail; we don't want a
    10s httpx default to slow down a smoke when the backend is down."""
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


# ── Per-turn runner ──────────────────────────────────────────────────────────
def _extract_routing_meta(state_values: dict) -> dict:
    """The router node stashes its decision in state['routing_meta']."""
    return state_values.get("routing_meta") or {}


def _extract_tool_calls(state_values: dict) -> list[dict]:
    """Walk the message history and pull out every tool call the workers made.
    Returned as ``[{"name": ..., "args": ...}, ...]`` for the summary."""
    calls: list[dict] = []
    for msg in state_values.get("messages", []):
        if isinstance(msg, AIMessage):
            for tc in (getattr(msg, "tool_calls", None) or []):
                # LangChain tool_calls can be dicts or objects depending on version.
                if isinstance(tc, dict):
                    calls.append({"name": tc.get("name"), "args": tc.get("args")})
                else:
                    calls.append({"name": getattr(tc, "name", None),
                                  "args": getattr(tc, "args", None)})
    return calls


def _extract_tool_outputs(state_values: dict) -> list[dict]:
    return [{"name": m.name, "content": str(m.content)[:160]}
            for m in state_values.get("messages", [])
            if isinstance(m, ToolMessage)]


def _format_tool_calls(calls: list[dict]) -> str:
    if not calls:
        return _dim("(none)")
    parts = []
    for tc in calls:
        name = tc.get("name") or "?"
        args = tc.get("args") or {}
        # Compact renderer: search("..."), sync_cart([2 items]), confirm_order(T1, 2 items), ...
        if name == "search":
            parts.append(f'search({args.get("query", "")!r})')
        elif name == "sync_cart":
            items = args.get("items") or []
            pretty = ", ".join(
                f'{i.get("name", "?")}x{i.get("quantity", "?")}'
                for i in items
            )
            parts.append(f"sync_cart([{pretty}])")
        elif name == "confirm_order":
            items = args.get("items") or []
            parts.append(f"confirm_order(table={args.get('table_id')}, {len(items)} items)")
        elif name == "request_payment":
            parts.append(f"request_payment(table={args.get('table_id')})")
        elif name == "verify_payment":
            parts.append(f"verify_payment(table={args.get('table_id')})")
        else:
            parts.append(f"{name}({args})")
    return "; ".join(parts)


def run_turn(agent: AIWaiterGraph, text: str, table_id: str,
             session_id: str | None) -> tuple[dict, float, str | None]:
    """Run one chat turn. Returns (result, latency_seconds, new_session_id).
    Raises if the agent itself explodes (that's what we want to surface)."""
    t0 = time.time()
    result = agent.chat(query=text, table_id=table_id, session_id=session_id)
    latency = time.time() - t0
    return result, latency, result.get("session_id")


# ── Re-extract routing/tool info from the agent's state ──────────────────────
# AIWaiterGraph.chat() doesn't return routing_meta, only the response/stage/action.
# To print the router decision and tool calls, we dig into the LangGraph state
# after each turn using the session_id it returned.
def inspect_state(agent: AIWaiterGraph, session_id: str) -> dict:
    try:
        snap = agent.app.get_state({"configurable": {"thread_id": session_id}})
        values = snap.values if snap else {}
    except Exception as e:
        return {"_inspect_error": str(e)}
    return {
        "routing": _extract_routing_meta(values),
        "tool_calls": _extract_tool_calls(values),
        "tool_outputs": _extract_tool_outputs(values),
        "stage": values.get("order_stage"),
    }


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--table-id", default=DEFAULT_TABLE_ID,
                        help=f"Table id to use (default: random — {DEFAULT_TABLE_ID})")
    parser.add_argument("--turns", type=int, default=len(CONVERSATION),
                        help="How many of the scripted turns to run (default: all)")
    parser.add_argument("--backend-url", default=settings.ORCHESTRATOR_URL,
                        help="Orchestrator URL to probe / talk to")
    args = parser.parse_args()

    table_id = args.table_id
    turns = CONVERSATION[: max(1, min(args.turns, len(CONVERSATION)))]

    print(_bold("AI Waiter — conversation smoke"))
    print(_dim(f"  table_id     : {table_id}"))
    print(_dim(f"  embed model  : {os.environ.get('EMBEDDING_MODEL') or 'AITeamVN/Vietnamese_Embedding (default)'}"))
    print(_dim(f"  LLM models   : router={settings.ROUTER_MODEL} | worker={settings.WORKER_MODEL} | response={settings.RESPONSE_MODEL}"))
    print(_dim(f"  backend URL  : {args.backend_url}"))

    backend_up = backend_alive(args.backend_url)
    if backend_up:
        print(_green(f"  backend      : up ({args.backend_url})"))
    else:
        print(_yellow(f"  backend      : DOWN — turns needing /orders, /payments will be skipped"))
    print()

    print(_bold(f"Building agent graph..."))
    t0 = time.time()
    try:
        agent = AIWaiterGraph()
    except Exception as e:
        print(_red(f"  FATAL: could not build the agent graph: {e}"))
        traceback.print_exc()
        return 1
    print(_dim(f"  built in {time.time() - t0:.2f}s"))

    # First turn primes the embedding model too (search is a no-op on greeting
    # but building the graph already loaded the retriever singletons).
    print()
    print(_bold("Warming up: a throwaway 'ok' turn so the first real turn isn't slow..."))
    try:
        warm = agent.chat(query="ok", table_id=table_id, session_id=None)
        print(_dim(f"  warmup ok (session={warm.get('session_id')})"))
    except Exception as e:
        # Warmup is best-effort; if it fails because the embedding model is
        # the thing that's broken, the first real turn will fail too and
        # we'll surface the traceback there. Don't double-print.
        print(_yellow(f"  warmup skipped: {type(e).__name__}: {e}"))

    session_id: str | None = None
    summary: list[dict] = []
    failed = False

    for idx, (text, note) in enumerate(turns, start=1):
        # Skip the last 3 turns if backend is down — they need the REST API.
        needs_backend = idx >= 6  # confirm / request_payment / verify_payment
        if needs_backend and not backend_up:
            print()
            print(_bold(f"[Turn {idx}] ") + _cyan("USER: ") + text)
            print(_yellow(f"  ⚠ backend down — skipping (this turn needs POST /orders or /payments)"))
            summary.append({
                "turn": idx, "skipped": True, "reason": "backend down",
                "text": text, "note": note,
            })
            continue

        print()
        print(_bold(f"[Turn {idx}] ") + _cyan("USER: ") + text)
        print(_dim(f"  intent note: {note}"))

        t0 = time.time()
        try:
            result, latency, new_sid = run_turn(agent, text, table_id, session_id)
        except Exception as e:
            print(_red(f"  ✗ TURN FAILED: {type(e).__name__}: {e}"))
            traceback.print_exc()
            failed = True
            summary.append({
                "turn": idx, "failed": True,
                "error": f"{type(e).__name__}: {e}",
                "text": text, "note": note,
            })
            # If turn 2 fails (the search/embed turn), stop here — every later
            # turn depends on the retriever too.
            if idx == 2:
                print(_red("  → search worker blew up on turn 2; the retriever is the culprit. Stopping."))
                break
            continue

        session_id = new_sid
        info = inspect_state(agent, session_id)
        routing = info.get("routing") or {}
        tool_calls = info.get("tool_calls") or []
        stage = info.get("stage") or result.get("final_stage", "?")

        intent = routing.get("semantic_intent") or routing.get("final_intent") or "?"
        decided = routing.get("decided_by") or "?"
        conf = routing.get("semantic_confidence")
        conf_str = f", conf={conf:.2f}" if isinstance(conf, (int, float)) else ""
        print(f"  ├─ intent:    {intent} ({decided}{conf_str})")
        print(f"  ├─ tools:     {_format_tool_calls(tool_calls)}")
        print(f"  ├─ action:    {result.get('action') or _dim('(none)')}")
        print(f"  ├─ stage:     {stage}")
        print(f"  ├─ latency:   {latency:.2f}s")
        print(f"  └─ AGENT:     {result.get('response', '')}")

        summary.append({
            "turn": idx, "skipped": False, "failed": False,
            "text": text, "note": note,
            "intent": intent, "decided_by": decided,
            "confidence": conf,
            "tools": [tc.get("name") for tc in tool_calls],
            "action": (result.get("action") or {}).get("action") if result.get("action") else None,
            "stage": stage, "latency": round(latency, 2),
        })

    # ── Summary table ────────────────────────────────────────────────────────
    print()
    print(_bold("=" * 70))
    print(_bold("SUMMARY"))
    print(_bold("=" * 70))
    header = f"{'#':>2}  {'lat':>6}  {'intent':<14}  {'tool':<18}  {'action':<13}  {'stage':<13}  text"
    print(_dim(header))
    print(_dim("-" * len(header)))
    for row in summary:
        if row.get("skipped"):
            print(_yellow(f"{row['turn']:>2}  {'—':>6}  {'SKIPPED':<14}  {'—':<18}  {'—':<13}  {'—':<13}  {row['text']}"))
        elif row.get("failed"):
            err = row.get("error", "?")[:40]
            print(_red(f"{row['turn']:>2}  {'—':>6}  {'FAILED':<14}  {err:<18}  {'—':<13}  {'—':<13}  {row['text']}"))
        else:
            tool = (row.get("tools") or ["(none)"])[0]
            print(f"{row['turn']:>2}  {row.get('latency', 0):>5.2f}s  "
                  f"{row.get('intent', '?'):<14}  {tool:<18}  "
                  f"{(row.get('action') or '(none)'):<13}  "
                  f"{(row.get('stage') or '?'):<13}  {row['text']}")
    print()
    if failed:
        print(_red("✗ one or more turns failed — see traceback(s) above"))
        return 1
    print(_green("✓ all runs completed (no exceptions thrown)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
