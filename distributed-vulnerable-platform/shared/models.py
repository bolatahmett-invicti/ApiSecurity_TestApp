"""Shared Pydantic schemas for cross-service communication."""

from pydantic import BaseModel
from typing import Any, Optional


class EventPayload(BaseModel):
    event_type: str
    source_service: str
    data: dict[str, Any]
    timestamp: Optional[str] = None


class PaymentCompletedEvent(BaseModel):
    invoice_id: int
    payment_id: int
    amount: float
    org_id: int


class InvoiceCreatedEvent(BaseModel):
    invoice_id: int
    org_id: int
    amount: float


class UserRegisteredEvent(BaseModel):
    user_id: int
    email: str
    org_id: Optional[int] = None


class NotificationSendEvent(BaseModel):
    user_id: Optional[int] = None
    org_id: Optional[int] = None
    target: str  # "user", "org", "all_users"
    title: str
    body: str
    channel: str = "in_app"  # email, webhook, in_app
