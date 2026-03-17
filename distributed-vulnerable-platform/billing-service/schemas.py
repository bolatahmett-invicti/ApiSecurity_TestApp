"""Billing service Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# --- Subscription schemas ---

class SubscriptionCreate(BaseModel):
    plan: str = "free"

class SubscriptionUpdate(BaseModel):
    plan: Optional[str] = None
    status: Optional[str] = None

class SubscriptionResponse(BaseModel):
    id: int
    org_id: int
    plan: str
    status: str
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


# --- Invoice schemas ---

class InvoiceCreate(BaseModel):
    subscription_id: int
    amount: float
    tax: float = 0
    discount: float = 0
    due_date: datetime

class InvoiceResponse(BaseModel):
    id: int
    org_id: int
    subscription_id: int
    amount: float
    tax: float
    discount: float
    status: str
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# --- Coupon schemas ---

class CouponCreate(BaseModel):
    code: str
    discount_percent: int
    max_uses: int
    expires_at: Optional[datetime] = None

class CouponResponse(BaseModel):
    id: int
    code: str
    discount_percent: int
    max_uses: int
    current_uses: int
    expires_at: Optional[datetime] = None
    is_active: bool


# --- AppliedCoupon schemas ---

class ApplyCouponRequest(BaseModel):
    coupon_code: str

class AppliedCouponResponse(BaseModel):
    id: int
    invoice_id: int
    coupon_id: int
    discount_amount: float
