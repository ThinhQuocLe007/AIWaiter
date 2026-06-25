"""Action commands the agent emits alongside its spoken reply (mục 12, system-architecture.md §5).

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
    """SEAM: deliver an action command to the table's tablet.

    Not yet wired to a transport — this is the "bridge" left open for a design decision. For now
    we only log it so the decision logic is observable end-to-end. When the bridge lands, this is
    the *single* place that pushes `action` to customer_ui (e.g. an HTTP POST to the backend, or a
    role=customer WS on the orchestrator hub).
    """
    log.info("[action] table=%s %s (bridge not wired — not delivered)", table_id, action)
