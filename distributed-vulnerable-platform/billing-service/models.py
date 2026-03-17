"""Billing service SQLAlchemy models."""

import sys
sys.path.insert(0, "/app")

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, ForeignKey
from shared.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, nullable=False, index=True)
    plan = Column(String(50), nullable=False, default="free")  # free, starter, pro, enterprise
    status = Column(String(50), nullable=False, default="active")  # active, cancelled, past_due
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False)
    amount = Column(Float, nullable=False)
    tax = Column(Float, default=0)
    discount = Column(Float, default=0)
    status = Column(String(50), nullable=False, default="draft")  # draft, pending, paid, refunded, cancelled
    due_date = Column(DateTime, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    discount_percent = Column(Integer, nullable=False)
    max_uses = Column(Integer, nullable=False)
    current_uses = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)


class AppliedCoupon(Base):
    __tablename__ = "applied_coupons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    coupon_id = Column(Integer, ForeignKey("coupons.id"), nullable=False)
    discount_amount = Column(Float, nullable=False)
