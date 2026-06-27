"""AI Waiter — server orchestrator (FastAPI).

Central server's FastAPI app — the **only** writer to ``orchestrator.db``.
Owns the business ledger (tables / sessions / orders / payments / tasks /
robots), the live robot telemetry (RAM), the WebSocket hub, the task
dispatcher, the menu loader, and every REST endpoint the frontends
(customer_ui, kiosk, panel) and the agent service talk to.

Package layout:
  - main.py          — FastAPI app entry (lifespan, CORS, mount routers)
  - config.py        — settings (env prefix ORCH_)
  - data/            — persistence: db.py (schema + connection), seed.py (TODO)
  - realtime/        — WebSocket hub: connection_manager.py + ws.py
  - routers/         — REST endpoints (one file per resource)
  - schemas/         — pydantic REST contracts (re-exported from a single __init__.py)
  - services/        — business logic: dispatcher, fleet, menu_loader, sessions

The orchestrator stays ignorant of the agent (no import of ``src.agent_brain``);
the brain reaches it over HTTP via the ``OrchestratorClient``.
"""
