"""Payment service Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Payment schemas ---

class PaymentCreate(BaseModel):
    invoice_id: int
    amount: float
    method: str  # card, bank, wallet
    card_number: Optional[str] = None
    card_expiry: Optional[str] = None
    org_id: Optional[int] = None


class PaymentResponse(BaseModel):
    """VULN: Includes card_number and card_expiry in API response — sensitive data exposure.
    Should mask or omit card details in responses.
    """
    id: int
    invoice_id: int
    org_id: int
    amount: float
    method: str
    # VULN: Full card number returned in response — should be masked (e.g. ****1234)
    card_number: Optional[str] = None
    # VULN: Card expiry returned in response — sensitive data exposure
    card_expiry: Optional[str] = None
    status: str
    transaction_ref: Optional[str] = None
    created_at: Optional[datetime] = None


# --- Refund schemas ---

class RefundRequest(BaseModel):
    amount: float
    reason: Optional[str] = None


class RefundResponse(BaseModel):
    id: int
    payment_id: int
    amount: float
    reason: Optional[str] = None
    status: str
    requested_by: int
    approved_by: Optional[int] = None
    created_at: Optional[datetime] = None


class RefundApproval(BaseModel):
    approved: bool
