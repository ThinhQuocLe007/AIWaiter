from typing import Literal, Optional
from pydantic import BaseModel


class PaymentResponse(BaseModel):
    status: Literal["success", "error"]
    qr_url: Optional[str] = None
    amount: Optional[int] = None
    message: str
