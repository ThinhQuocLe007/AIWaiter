from typing import Literal

from pydantic import BaseModel, Field

IntentType = Literal["ORDER", "ORDER_CONFIRM", "SEARCH", "PAYMENT", "CHAT"]

class IntentPrediction(BaseModel):
    """The result of the SLM multi-intent routing."""
    intents: list[IntentType] = Field(
        description="List of classified user intents in sequential execution order. E.g., ['SEARCH', 'ORDER']."
    )
    reasoning: str = Field(description="Brief step-by-step reasoning for the classification.")
    queries: dict[str, str] | None = Field(
        default=None,
        description="Per-intent sub-queries for multi-intent turns. "
        "e.g. {'SEARCH': 'Ốc Hương có cay không?', 'ORDER': 'lấy 1 phần Ốc Hương'}. "
        "Omit for single-intent turns."
    )
