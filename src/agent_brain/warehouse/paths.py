"""Resolve cross-role paths (data, models) from env / repo root."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# This file lives at <root>/src/agent_brain/warehouse/paths.py → repo root is parents[3].
ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # Anchor .env to the project root so it loads regardless of CWD (the agent can be
    # launched from a subdir by an eval/script). Same trick as src/agent_brain/config.
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    inventory_path: str = "data/inventory.csv"
    embed_model: str = "dangvantuan/vietnamese-embedding"
    embed_device: str = "cpu"
    # Minimum dense-cosine score for a retrieval candidate to count. 0.0 = only require lexical
    # (BM25) overlap. Raise (e.g. 0.3) once the real embedding model is used so descriptive/out-of-scope
    # queries resolve to nothing instead of a fuzzy neighbour.
    retrieval_min_score: float = 0.0
    llm_base_url: str = "http://localhost:11434/v1"
    # Khớp với .env.template. Để mặc định lệch với template thì máy nào quên tạo .env sẽ hỏi
    # Ollama một model chưa pull và nhận 404 — lỗi rất khó đoán ra nguyên nhân.
    llm_model: str = "qwen2.5:14b-instruct-q6_K"
    llm_api_key: str = "ollama"
    agent_host: str = "0.0.0.0"
    agent_port: int = 8000
    chat_url: str = "http://localhost:8000/chat"

    # Voice/edge device
    device: str = "cpu"  # "cuda" if the Jetson/box has a GPU for STT
    voice_robot_id: str = "robo-1"
    brain_enabled: bool = True  # set False to run the voice loop without the brain (voice-only test)

    # Runtime artifacts (checkpoints, TTS models, vector indexes) — gitignored.
    storage_dir: str = "storage"


def inventory_path() -> Path:
    p = Path(Settings().inventory_path)
    return p if p.is_absolute() else ROOT / p


def storage_path() -> Path:
    """Root directory for runtime artifacts (checkpoints, TTS models, indexes)."""
    p = Path(Settings().storage_dir)
    p = p if p.is_absolute() else ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p


settings = Settings()
