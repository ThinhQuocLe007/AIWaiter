"""Minimal OpenAI-compatible LLM client (tested against local Ollama).

Used by the planner and chat worker. Structured intents (locate/stock/navigate) are answered
deterministically and do NOT call the LLM, keeping latency low.
"""

from __future__ import annotations

import httpx

from src.agent_brain.warehouse.paths import settings


def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 512,
) -> str:
    """Call the chat endpoint. `messages` is a list of {"role","content"} dicts."""
    payload = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
