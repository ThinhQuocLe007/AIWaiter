"""Action commands the agent emits alongside its spoken reply (mục 12, system-design.md §5).

Until now the agent only produced *text* for TTS. A real waiter also *acts*: when the guest
starts ordering it opens the menu on the table's tablet; when they ask to pay it brings up the
bill + QR. Those are "UI action commands":

    {"type": "ui", "action": "open_menu"}      # tablet -> /menu
    {"type": "ui", "action": "open_payment"}   # tablet -> /payment (bill + QR)

This module is the DECISION half — it maps what the agent just did into a command. The DELIVERY
half (getting the command from this process to the tablet) is the "bridge", deliberately left as
a single seam, `emit_action()`, to be wired later. Keeping the two apart means the command logic
is unit-testable today without a robot, a websocket, or the web backend running.
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)

# Which successful tool implies which screen the guest's tablet should be on.
# Tool execution is the strongest, least-ambiguous signal that an action happened (vs. guessing
# from free-text intent): a cart synced / a dish searched -> they're ordering -> show the menu;
# a payment requested -> show the bill + QR. confirm_order is intentionally left out (neutral —
# the confirmation reply is spoken, no screen change needed).
_TOOL_TO_UI_ACTION = {
    "sync_cart": "open_menu",
    "search": "open_menu",
    "request_payment": "open_payment",
}


def ui_action_for_tool(tool_name: str) -> Optional[str]:
    """Return the UI action a successful tool call should trigger on the tablet, or None."""
    return _TOOL_TO_UI_ACTION.get(tool_name)


def build_action(ui_action: Optional[str]) -> Optional[dict]:
    """Wrap a bare UI action ("open_menu") into the wire command, or None if there is nothing."""
    return {"type": "ui", "action": ui_action} if ui_action else None


def emit_action(table_id: str, action: dict) -> None:
    """In-process decision log for the action this turn produced.

    The *delivery* bridge is now wired in the agent HTTP service (``ai_waiter_core/server.py``):
    after each turn it POSTs the reply **and** this action to the backend (``POST /voice/event``),
    which fans it to ``customer_ui`` over the ``role=customer`` WebSocket. Delivery lives there —
    not here — because that's the layer with the full turn (transcript + reply + action) and the
    orchestrator seam. This function stays as the observable record of *what* was decided, useful
    when running the graph standalone (tests / the old in-process loop) without a tablet attached.
    """
    log.info("[action] table=%s %s (delivered by the agent service via /voice/event)", table_id, action)
