from pydantic import BaseModel, Field
from typing import List, Optional

class ItemCorrection(BaseModel):
    original_name: str = Field(..., description="The name used by the Actor")
    suggested_name: str = Field(..., description="The correct name from MenuItemLiteral")
    reason: str = Field(..., description="Why the correction is needed")

class CriticVerdict(BaseModel):
    is_valid: bool = Field(..., description="True if the order matches the menu exactly")
    feedback: Optional[str] = Field(None, description="Natural language feedback for the Actor")
    corrections: List[ItemCorrection] = Field(default_factory=list, description="Structured corrections")
