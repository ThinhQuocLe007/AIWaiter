from typing import Literal

from pydantic import BaseModel, Field

IntentType = Literal["ORDER", "ORDER_CONFIRM", "SEARCH", "PAYMENT", "CHAT"]


class IntentPrediction(BaseModel):
    """Result of SLM multi-intent routing (legacy, kept for backward compatibility with eval)."""
    intents: list[IntentType] = Field(
        description="List of classified user intents in sequential execution order."
    )
    reasoning: str = Field(description="Brief step-by-step reasoning for the classification.")


class RewriterOutput(BaseModel):
    """Output of the rewriter node: utterance decomposed into single-intent fragments."""
    fragments: list[str] = Field(
        description="Single-intent fragment strings. Each is a complete, self-contained "
        "Vietnamese sentence that the semantic router can classify independently."
    )
