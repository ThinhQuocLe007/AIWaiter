"""HTTP client for the Orchestrator backend — the agent's seam to the single ledger.

The LLM tools (confirm_order / request_payment / verify_payment) used to write a private
restaurant.db directly. They now go through the backend REST API so orchestrator.db is the one
source of truth (kitchen panel, kiosk, robots and the agent all read/write the same rows).

The agent talks about tables as "T1"; the backend keys them by INT id. ``normalise_table_id``
(from ``src._shared.types``) handles that at the seam ("T1" → 1) so the rest of the system
stays INT.
"""

import httpx

from src._shared.types import normalise_table_id
from src.agent_brain.config import settings
from src.agent_brain.utils import logger

_TIMEOUT = httpx.Timeout(10.0)


class OrchestratorClient:
    """Thin sync wrapper over the backend REST API. One per tool module is fine (stateless)."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.ORCHESTRATOR_URL).rstrip("/")

    def _post(self, path: str, json: dict) -> dict:
        with httpx.Client(base_url=self.base_url, timeout=_TIMEOUT) as client:
            resp = client.post(path, json=json)
            resp.raise_for_status()
            return resp.json()

    def _get(self, path: str) -> httpx.Response:
        with httpx.Client(base_url=self.base_url, timeout=_TIMEOUT) as client:
            return client.get(path)

    # --- Orders ---------------------------------------------------------------
    def create_order(self, table_id, items: list[dict]) -> dict:
        """POST /orders — persist the cart under the table's active session. Returns the order."""
        payload = {"table_id": normalise_table_id(table_id), "items": items}
        order = self._post("/orders", payload)
        logger.info(f"Order #{order['id']} created for table {table_id} via orchestrator")
        return order

    # --- Sessions -------------------------------------------------------------
    def get_active_session(self, table_id) -> dict | None:
        """GET /tables/{id}/session — active session + gộp total, or None if none open."""
        resp = self._get(f"/tables/{normalise_table_id(table_id)}/session")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    # --- Payments -------------------------------------------------------------
    def create_payment(self, table_id) -> dict:
        """POST /payments — open/refresh the gộp payment for the table's session (amount + QR)."""
        pay = self._post("/payments", {"table_id": normalise_table_id(table_id)})
        logger.info(f"Payment #{pay['id']} opened for table {table_id}: {pay['amount']} VND")
        return pay

    def verify_payment(self, table_id) -> dict:
        """POST /payments/verify — settle the table's payment (PAID + close session). Idempotent."""
        pay = self._post("/payments/verify", {"table_id": normalise_table_id(table_id)})
        logger.info(f"Payment for table {table_id} verified: {pay['status']}")
        return pay

    # --- Voice bridge ---------------------------------------------------------
    def post_voice_event(self, event: dict) -> None:
        """POST /voice/event — mirror a voice turn / UI action onto the table's tablet.

        Best-effort: a tablet that isn't connected (or the bridge being down) must never break the
        spoken turn, so delivery failures are logged and swallowed, not raised.
        """
        try:
            self._post("/voice/event", event)
        except Exception as e:  # backend unreachable / no tablet — degrade silently
            logger.warning(f"voice event not delivered to tablet: {e}")
