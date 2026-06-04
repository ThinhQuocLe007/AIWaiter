from pydantic import BaseModel, Field
from typing import List, Literal

IntentType = Literal["ORDER", "ORDER_CONFIRM", "SEARCH", "PAYMENT", "CHAT"]

class IntentPrediction(BaseModel):
    """The result of the SLM multi-intent routing."""
    intents: List[IntentType] = Field(
        description="List of classified user intents in sequential execution order. E.g., ['SEARCH', 'ORDER']."
    )
    reasoning: str = Field(description="Brief step-by-step reasoning for the classification.")
