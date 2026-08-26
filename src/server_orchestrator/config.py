"""Central Orchestrator server settings.

This server is the warehouse "coordination brain": it owns fleet state and
dispatches navigation tasks to the AGV(s) on command from the warehouse brain
(``src.agent_brain``). It is intentionally standalone — it does NOT import
``src.agent_brain`` (the LLM Brain that runs as a separate FastAPI service), so it
can later run on its own machine.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .../AI_Waiter/src/server_orchestrator/config.py -> repo root is 2 levels up
# (parents[0]=server_orchestrator, parents[1]=src, parents[2]=repo).
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORCH_", env_file=".env", extra="ignore")

    # Orchestrator SQLite file (robots/tasks). Separate from the per-robot Brain DB under storage/db.
    db_path: Path = REPO_ROOT / "storage" / "db" / "orchestrator.db"

    # Warehouse geometry: SLAM map + section/named-place waypoints (services/floorplan.py). The
    # default is the layout the AGV bridge navigates by, so the dispatcher's "nearest robot"
    # scoring and the panel minimap can never drift from the robot's own waypoints. Override with
    #   ORCH_FLOORPLAN_PATH=assets/data/warehouse_layout.json
    # Relative paths resolve from the repo root.
    floorplan_path: Path = REPO_ROOT / "assets" / "data" / "warehouse_layout.json"

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

    # The LLM agent service (src.agent_brain.server, port 8100). The orchestrator still never
    # IMPORTS the agent — this is only the HTTP address used to forward the tablet's
    # "cuộc trò chuyện mới" reset (POST {agent_url}/reset). Same-host default; override with
    # ORCH_AGENT_URL when the agent runs elsewhere.
    agent_url: str = "http://127.0.0.1:8100"

    # Robot liveness. A robot pings a heartbeat on a fixed interval (independent of how fast it
    # drives). If the server sees no heartbeat for `heartbeat_timeout_s`, it treats the robot as
    # hung — even though its TCP socket may still look open — and requeues its task. Generous by
    # default so a busy Jetson (Nav2 hogging CPU) that ships heartbeats late isn't killed early;
    # raise via ORCH_HEARTBEAT_TIMEOUT_S=... if needed. The watchdog scans every
    # `watchdog_interval_s`.
    heartbeat_timeout_s: float = 30.0
    watchdog_interval_s: float = 5.0


settings = Settings()
