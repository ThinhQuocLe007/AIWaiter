"""Central Orchestrator server settings.

This server is the restaurant "coordination brain" (mục 8 of docs/SYSTEM_ARCHITECTURE.md):
it owns table/order/payment state and dispatches tasks to robots. It is intentionally
standalone — it does NOT import ai_waiter_core (the per-robot Brain), so it can later run
on its own machine.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .../AI_Waiver/src/backend/app/config.py -> repo root is 4 levels up.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORCH_", env_file=".env", extra="ignore")

    # Canonical menu source, shared with the customer UI and the RAG pipeline.
    menu_path: Path = REPO_ROOT / "assets" / "data" / "menu.json"

    # Orchestrator SQLite file (tables/orders/payments/robots/tasks). Separate from the
    # per-robot Brain DB under storage/db.
    db_path: Path = REPO_ROOT / "storage" / "db" / "orchestrator.db"

    # Allowed CORS origins for the browser frontends. Dev servers normally hit the backend
    # through each app's same-origin Vite proxy (/api -> :8000) so CORS does not bite, but we
    # list every dev port (customer_ui 5173 · kiosk 5174 · panel 5175) so a direct
    # VITE_API_URL=http://127.0.0.1:8000 setup still works.
    cors_origins: list[str] = [
        "http://localhost:5173",  # customer_ui
        "http://127.0.0.1:5173",
        "http://localhost:5174",  # kiosk
        "http://127.0.0.1:5174",
        "http://localhost:5175",  # panel
        "http://127.0.0.1:5175",
        "http://localhost:4173",  # vite preview
        "http://127.0.0.1:4173",
    ]


settings = Settings()
