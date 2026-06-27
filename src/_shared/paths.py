"""Project paths — single source of truth for absolute locations.

Every cross-role constant (DB files, vector store, assets, .env) lives here
so the brain, voice, and orchestrator resolve the same paths no matter
where they're imported from. ``__file__``-anchored (``parents[2]``) so the
package relocates cleanly — no hard-coded ``/home/...`` or CWD-relative
magic.
"""
from pathlib import Path

from dotenv import load_dotenv

# Repo root — src/_shared/paths.py -> parents[0]=_shared, [1]=src, [2]=repo
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

# Storage (runtime artifacts — gitignored)
STORAGE_DIR: Path = PROJECT_ROOT / "storage"
DB_DIR: Path = STORAGE_DIR / "db"
VECTOR_DIR: Path = STORAGE_DIR / "vector"

# Specific DB files
ORCHESTRATOR_DB: Path = DB_DIR / "orchestrator.db"
CHECKPOINTS_DB: Path = DB_DIR / "checkpoints.db"

# Vector artifacts
FAISS_DIR: Path = VECTOR_DIR / "faiss_index"
BM25_PKL: Path = VECTOR_DIR / "bm25.pkl"

# Assets (shipped with the repo)
ASSETS_DIR: Path = PROJECT_ROOT / "assets"
MENU_JSON: Path = ASSETS_DIR / "data" / "menu.json"

# Env
ENV_FILE: Path = PROJECT_ROOT / ".env"


def load_dotenv_from_repo() -> bool:
    """Load the repo-root ``.env`` once. Returns True if a file was loaded.

    Centralises the ``load_dotenv(...)`` call so every entry point
    (orchestrator, agent HTTP service, voice device, scripts) reads the
    same env file regardless of cwd. Idempotent — ``load_dotenv`` is a
    no-op if already loaded.
    """
    return load_dotenv(ENV_FILE, override=False)
