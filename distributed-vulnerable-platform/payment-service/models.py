"""Payment service SQLAlchemy models."""

import sys
sys.path.insert(0, "/app")

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, ForeignKey
from shared.database import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, nullable=False, index=True)
    org_id = Column(Integer, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    method = Column(String(50), nullable=False)  # card, bank, wallet
    # VULN: Stores full card number in plaintext — should be tokenized or encrypted
    card_number = Column(String(20), nullable=True)
    # VULN: Stores card expiry in plaintext — sensitive data at rest
    card_expiry = Column(String(10), nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, completed, failed, refunded
    transaction_ref = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, approved, completed
    requested_by = Column(Integer, nullable=False)
    approved_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
