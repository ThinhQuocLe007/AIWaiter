"""AI Waiter — central Orchestrator API (FastAPI).

Run (from repo root):
    uv run uvicorn src.server_orchestrator.main:app --reload --port 8000
    # or: make backend

This is the single backend that serves all web clients (customer UI, kiosk, panel) and the
robot WS hub. Bước 0 ships the skeleton + GET /menu; orders/payments/tasks come next.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .services import dispatcher
from .config import settings
from .data.db import init_db
from .services.menu_loader import seed_dishes, seed_robots, seed_tables
from .routers import admin, layout, menu, orders, payments, robots, tables, tasks, voice
from .realtime.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_tables()
    seed_dishes()
    seed_robots()
    # Fresh start: no robot WS is connected yet, so every robot shows "Chưa kích hoạt" until its
    # bridge connects (stale idle/battery rows from a previous run would lie on the panel).
    dispatcher.reset_fleet_offline()
    # Background watchdog: detects robots that went silent (hung) and requeues their tasks.
    watchdog = asyncio.create_task(dispatcher.watchdog_loop())
    yield
    watchdog.cancel()


app = FastAPI(title="AI Waiter Orchestrator", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(menu.router)
app.include_router(tables.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(robots.router)
app.include_router(layout.router)
app.include_router(tasks.router)
app.include_router(admin.router)
app.include_router(voice.router)
app.include_router(ws_router)

# The browsers call every endpoint under /api — in dev the Vite proxy strips that prefix before
# forwarding here, so the bare paths above are all a dev server ever needs. In production the SPAs
# are served by THIS app (below) with no proxy in front, so the same routers must also answer at
# /api or every fetch from the built bundles 404s. Bare paths stay for the non-browser callers
# (agent_brain's voice bridge, the robot clients) which address the backend directly.
# include_in_schema=False: the alias would otherwise duplicate every operation in /docs.
for _api_router in (menu, tables, orders, payments, robots, layout, tasks, admin, voice):
    app.include_router(_api_router.router, prefix="/api", include_in_schema=False)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ── Production web serving ───────────────────────────────────────────────────────────────────
# One origin for everything: the server builds all three SPAs (`make build`) and serves them here,
# so every client (Jetson kiosk browser, entrance tablet, kitchen panel) only opens a URL — no
# Node, no build, no CORS, no dev server. Mounted only when a dist/ exists, so a machine that
# never built the web still boots the API fine.
#
# customer_ui uses hash routing and kiosk/panel are single-page, so no SPA history fallback is
# needed — the server never sees a client-side route.
FRONTENDS_DIR = Path(__file__).resolve().parents[2] / "src" / "frontends"


def _mount_spa(url_path: str, app_name: str) -> None:
    dist = FRONTENDS_DIR / app_name / "dist"
    if not dist.is_dir():
        return
    if url_path != "/":
        # Send /panel to /panel/ ourselves. Starlette does this redirect natively, but only when
        # NOTHING else matches — and the "/" mount below matches everything, so it swallows the
        # bare path and StaticFiles answers 404 for a file named "panel". Without this the sub-path
        # apps only load with a trailing slash, which is not what anyone types or bookmarks.
        # Registered before the "/" mount, so it wins on order.
        app.get(url_path, include_in_schema=False)(
            lambda: RedirectResponse(f"{url_path}/", status_code=308)
        )
    app.mount(url_path, StaticFiles(directory=dist, html=True), name=app_name)


# Sub-path apps first: mounting "/" is a catch-all and would shadow anything mounted after it.
_mount_spa("/kiosk", "kiosk")
_mount_spa("/panel", "panel")
_mount_spa("/", "customer_ui")
