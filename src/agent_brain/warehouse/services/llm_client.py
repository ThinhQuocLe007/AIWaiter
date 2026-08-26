"""Minimal OpenAI-compatible LLM client (tested against local Ollama).

Used by the planner and chat worker. Structured intents (locate/stock/navigate) are answered
deterministically and do NOT call the LLM, keeping latency low.
"""

from __future__ import annotations

import httpx

from src.agent_brain.warehouse.paths import settings

# JSON schema the decomposer requests: an array of {intent, text} steps. Ollama uses it to constrain
# the model to valid JSON, avoiding malformed arrays (e.g. swapped `]`/`}`) that small models emit.
STEP_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "text": {"type": "string"},
        },
        "required": ["intent", "text"],
    },
}


def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 512,
    json_schema: dict | None = None,
) -> str:
    """Call the chat endpoint. `messages` is a list of {"role","content"} dicts.

    `json_schema` (optional) is forwarded as Ollama's structured-output `format` so the model is
    constrained to valid JSON — used by the decomposer, which otherwise gets malformed arrays
    (e.g. swapped `]`/`}`) from small models.
    """
    payload = {
        "model": model or settings.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if json_schema is not None:
        payload["format"] = json_schema
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
