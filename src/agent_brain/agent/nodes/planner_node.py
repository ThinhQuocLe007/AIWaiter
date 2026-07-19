"""planner_node — per-intent sub-query extraction for multi-intent turns.

A focused LLM call that splits the user's full utterance into per-intent
sub-queries. Only invoked when the router classifies 2+ intents.
Single-intent turns pass through with no LLM cost.

Usage (wired into the graph later)::

    workflow.add_node("planner", planner_node)
    # Router → planner → first worker
    workflow.add_edge("router", "planner")
    workflow.add_conditional_edges(
        "planner", _route_after_planner,
        {"order_worker": "order_worker", "search_worker": "search_worker", ...},
    )
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from src.agent_brain.agent.state import AgentState
from src.agent_brain.config import settings
from src.agent_brain.utils import trace_latency
from src.agent_brain.utils.state_helpers import last_user_text

logger = logging.getLogger(__name__)

# ── Lazy LLM (same model as router — no extra GPU memory) ──────────────────
_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        from langchain_ollama import ChatOllama
        _llm = ChatOllama(
            model=settings.ROUTER_MODEL,
            temperature=0.0,
            num_ctx=2048,  # small context — just the utterance + prompt
            keep_alive=settings.llm_keep_alive,
        )
    return _llm


# ── Output schema ──────────────────────────────────────────────────────────
class PlannerOutput(BaseModel):
    queries: dict[str, str] = Field(
        description="Per-intent sub-queries. Keys must match the intent list exactly."
    )


# ── Prompt ─────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are a query splitter for a Vietnamese restaurant voice AI.
Given a customer's full utterance and a list of intents, extract the relevant
portion of the utterance for each intent. Each sub-query must be a complete
Vietnamese sentence.

Rules:
- Return exactly one sub-query per intent, using the intent names as keys.
- Extract only the text relevant to each intent — remove text meant for other intents.
- Resolve pronouns ("nó", "món đó", "cái này") into concrete dish names.
- Every ORDER sub-query MUST include the dish name even if implied.
- For SEARCH intents, include the question being asked AND the subject it
  references (dish name, topic). NEVER emit a SEARCH sub-query that lacks
  a concrete subject. Cross-reference the ORDER half: if the user says
  "giá sao?" after listing dishes, resolve to "<dish names> giá bao nhiêu?".
  "có cay không?" → "<dish name> có cay không?".
  "có tươi không?" → "<dish name hoặc đồ ăn> có tươi không?".
- For PAYMENT intents, extract the payment/checkout request.
- If you cannot extract a clean sub-query, use the minimal relevant clause
  or fall back to the full utterance for that intent.

Output valid JSON only: {"queries": {"SEARCH": "...", "ORDER": "..."}}\
"""

_FEW_SHOT_EXAMPLES: list[dict[str, object]] = [
    {
        "intents": ["SEARCH", "ORDER"],
        "utterance": "Lẩu Thái có cay không? Nếu không cay thì lấy cho 2 phần nhé",
        "queries": {
            "SEARCH": "Lẩu Thái có cay không?",
            "ORDER": "lấy 2 phần Lẩu Thái",
        },
    },
    {
        "intents": ["ORDER", "PAYMENT"],
        "utterance": "Cho 1 Lẩu Thái và tính tiền luôn",
        "queries": {
            "ORDER": "cho 1 Lẩu Thái",
            "PAYMENT": "tính tiền",
        },
    },
    {
        "intents": ["SEARCH", "ORDER"],
        "utterance": "Mình muốn gọi 2 Tôm Càng Xanh Nướng Phô Mai, "
                     "nhưng trước đó cho hỏi phần này ăn mấy người?",
        "queries": {
            "SEARCH": "Tôm Càng Xanh Nướng Phô Mai phần ăn mấy người?",
            "ORDER": "gọi 2 Tôm Càng Xanh Nướng Phô Mai",
        },
    },
    {
        "intents": ["SEARCH", "ORDER"],
        "utterance": "Gỏi Xoài Ốc Giác có ngon không? Anh tính gọi thêm 1 phần mà sợ cay quá",
        "queries": {
            "SEARCH": "Gỏi Xoài Ốc Giác có ngon không, có cay không?",
            "ORDER": "gọi thêm 1 phần Gỏi Xoài Ốc Giác",
        },
    },
    {
        "intents": ["ORDER", "PAYMENT"],
        "utterance": "Lấy thêm 1 Mì Xào Sò và 1 Trà Tắc, xong tính tiền nhé",
        "queries": {
            "ORDER": "lấy thêm 1 Mì Xào Sò và 1 Trà Tắc",
            "PAYMENT": "tính tiền",
        },
    },
    {
        "intents": ["ORDER", "SEARCH"],
        "utterance": "Cho 1 Sò Điệp Nướng Phô Mai, 1 Ốc Hương Xốt Trứng Muối. Mà khoan, giá sao vậy?",
        "queries": {
            "ORDER": "cho 1 Sò Điệp Nướng Phô Mai và 1 Ốc Hương Xốt Trứng Muối",
            "SEARCH": "Sò Điệp Nướng Phô Mai, Ốc Hương Xốt Trứng Muối giá bao nhiêu?",
        },
    },
]


def _build_user_message(intents: list[str], utterance: str) -> str:
    """Build the user message with few-shots + the actual query."""
    parts: list[str] = []
    for ex in _FEW_SHOT_EXAMPLES:
        parts.append(
            f"Intents: {', '.join(ex['intents'])}\n"
            f"Utterance: {ex['utterance']}\n"
            f"Output: {json.dumps({'queries': ex['queries']}, ensure_ascii=False)}"
        )

    intents_str = ", ".join(intents)
    parts.append(f"Intents: {intents_str}\nUtterance: {utterance}\nOutput:")

    return "\n\n".join(parts)


# ── Public API ─────────────────────────────────────────────────────────────
@trace_latency("Planner Node", run_type="chain")
def planner_node(state: AgentState) -> dict[str, Any]:
    """Extract per-intent sub-queries for multi-intent turns.

    Single-intent turns: return ``intent_queries=None`` (no-op, zero LLM cost).

    Returns a dict suitable for a LangGraph node return value:
    ``{"intent_queries": {"SEARCH": "...", "ORDER": "..."}}``
    """
    intents: list[str] = state.get("current_intents") or []

    # No-op for single-intent turns.
    if len(intents) <= 1:
        logger.debug("Planner skipped — single-intent turn")
        return {"intent_queries": None}

    utterance = last_user_text(state)
    if not utterance:
        logger.warning("Planner: no user text found")
        return {"intent_queries": None}

    user_message = _build_user_message(intents, utterance)
    llm = _get_llm().with_structured_output(PlannerOutput)

    try:
        result: PlannerOutput = llm.invoke([
            ("system", _SYSTEM_PROMPT),
            ("human", user_message),
        ])
    except Exception:
        logger.exception("Planner LLM call failed")
        return {"intent_queries": None}

    logger.info("Planner extracted queries: %s", result.queries)
    return {"intent_queries": result.queries}


# ── Convenience: call outside the graph for testing ────────────────────────
def split_query(intents: list[str], utterance: str) -> dict[str, str]:
    """Standalone entry point for testing. Returns queries dict."""
    from langchain_core.messages import HumanMessage
    result = planner_node({
        "current_intents": intents,
        "messages": [HumanMessage(content=utterance)],
    })
    return result.get("intent_queries") or {}
