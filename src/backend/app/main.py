"""AI Waiter — central Orchestrator API (FastAPI).

Run (from repo root):
    uv run uvicorn src.backend.app.main:app --reload --port 8000

This is the single backend that serves all web clients (customer UI, kiosk, panel) and the
robot WS hub. Bước 0 ships the skeleton + GET /menu; orders/payments/tasks come next.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .menu import seed_dishes
from .routers import menu


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_dishes()
    yield


app = FastAPI(title="AI Waiter Orchestrator", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(menu.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
