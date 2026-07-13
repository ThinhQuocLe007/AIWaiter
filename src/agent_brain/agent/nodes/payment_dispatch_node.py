"""payment_dispatch_node — deterministic PAYMENT dispatcher (no LLM call).

Replaces ``payment_worker_node``. When the hybrid router resolves the
intent as PAYMENT, this node always emits a ``request_payment`` tool
call. No LLM, no keyword dispatch — the router already decided the
intent, and ``request_payment`` is the only payment action the agent
needs to initiate.

``verify_payment`` is called later via the backend's mock verification
flow, not by the agent on a customer turn.
"""

import logging
from typing import Dict, Any

from langchain_core.messages import AIMessage

from src.agent_brain.agent.state import AgentState
from src.agent_brain.utils import trace_latency

logger = logging.getLogger(__name__)


@trace_latency("Payment Dispatch Node", run_type="chain")
def payment_dispatch_node(state: AgentState) -> Dict[str, Any]:
    """Always emit a ``request_payment`` tool call. The router decided
    PAYMENT intent — no further LLM decision needed.
    """
    table_id = state.get("table_id", "T1")

    tool_call = {
        "name": "request_payment",
        "args": {"table_id": table_id},
        "id": "payment_dispatch_request_payment",
        "type": "tool_call",
    }

    ai_msg = AIMessage(
        content="",
        tool_calls=[tool_call],
    )

    return {"messages": [ai_msg], "feedback": None}
