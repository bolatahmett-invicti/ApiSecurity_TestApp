"""Billing service routes.

INTENTIONAL VULNERABILITIES:
- BOLA on invoice retrieval (no org ownership check)
- State bypass on subscription upgrade (no payment verification)
- No idempotency on coupon application (same coupon applied multiple times)
- Workflow bypass on refund (refund without prior payment)
- Broken function-level auth on coupon creation (no admin role check)
- RabbitMQ consumer trusts events without source validation
"""

import sys
sys.path.insert(0, "/app")

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Subscription, Invoice, Coupon, AppliedCoupon
from schemas import (
    AppliedCouponResponse,
    ApplyCouponRequest,
    CouponCreate,
    CouponResponse,
    InvoiceCreate,
    InvoiceResponse,
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from shared.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# ─── Subscriptions ──────────────────────────────────────────────────────────


@router.get("/subscriptions", response_model=list[SubscriptionResponse])
def list_subscriptions(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List subscriptions for the current user's organization."""
    return (
        db.query(Subscription)
        .filter(Subscription.org_id == current_user["org_id"])
        .all()
    )


@router.post("/subscriptions", response_model=SubscriptionResponse, status_code=201)
def create_subscription(
    req: SubscriptionCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new subscription for the current user's organization."""
    sub = Subscription(
        org_id=current_user["org_id"],
        plan=req.plan,
        status="active",
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.put("/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
def update_subscription(
    subscription_id: int,
    req: SubscriptionUpdate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update a subscription.

    VULN: State bypass — allows upgrading the plan (e.g. free -> enterprise)
    without any payment verification. The plan field is directly overwritten
    from the request body. An attacker can upgrade to any plan for free.
    """
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.id == subscription_id,
            Subscription.org_id == current_user["org_id"],
        )
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # VULN: No payment verification — plan upgrade is accepted as-is
    if req.plan is not None:
        sub.plan = req.plan
    if req.status is not None:
        sub.status = req.status

    db.commit()
    db.refresh(sub)
    return sub


# ─── Invoices ────────────────────────────────────────────────────────────────


@router.get("/invoices", response_model=list[InvoiceResponse])
def list_invoices(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List invoices for the current user's organization."""
    return (
        db.query(Invoice)
        .filter(Invoice.org_id == current_user["org_id"])
        .all()
    )


@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
def create_invoice(
    req: InvoiceCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new invoice."""
    # Verify subscription belongs to org
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.id == req.subscription_id,
            Subscription.org_id == current_user["org_id"],
        )
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    invoice = Invoice(
        org_id=current_user["org_id"],
        subscription_id=req.subscription_id,
        amount=req.amount,
        tax=req.tax,
        discount=req.discount,
        status="draft",
        due_date=req.due_date,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(
    invoice_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single invoice by ID.

    VULN: BOLA — retrieves any invoice by ID without checking that the
    invoice belongs to the current user's organization. An authenticated
    user can access invoices from any organization by iterating IDs.
    """
    # VULN: No org_id filter — any authenticated user can read any invoice
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.post("/invoices/{invoice_id}/apply-coupon", response_model=AppliedCouponResponse)
def apply_coupon(
    invoice_id: int,
    req: ApplyCouponRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Apply a coupon to an invoice.

    VULN: No idempotency — the same coupon can be applied multiple times to
    the same invoice in rapid succession. There is no check for whether the
    coupon has already been applied to this invoice. An attacker can send
    concurrent requests to stack discounts and reduce the invoice to zero.
    """
    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_id,
            Invoice.org_id == current_user["org_id"],
        )
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    coupon = (
        db.query(Coupon)
        .filter(Coupon.code == req.coupon_code, Coupon.is_active == True)
        .first()
    )
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found or inactive")

    if coupon.current_uses >= coupon.max_uses:
        raise HTTPException(status_code=400, detail="Coupon usage limit reached")

    if coupon.expires_at and coupon.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Coupon expired")

    # VULN: No check for already-applied coupon on this invoice.
    # Race condition: concurrent requests can all pass the max_uses check
    # before any of them increment current_uses.
    discount_amount = invoice.amount * (coupon.discount_percent / 100)
    invoice.discount += discount_amount
    coupon.current_uses += 1

    applied = AppliedCoupon(
        invoice_id=invoice.id,
        coupon_id=coupon.id,
        discount_amount=discount_amount,
    )
    db.add(applied)
    db.commit()
    db.refresh(applied)
    return applied


@router.post("/invoices/{invoice_id}/refund", response_model=InvoiceResponse)
def refund_invoice(
    invoice_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Refund an invoice.

    VULN: Workflow bypass — allows refund on invoices with status "pending"
    or "draft" that were never actually paid. The endpoint sets status to
    "refunded" without verifying that the invoice was in "paid" status first.
    An attacker can create a draft invoice and immediately refund it.
    """
    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_id,
            Invoice.org_id == current_user["org_id"],
        )
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # VULN: No check that invoice.status == "paid" before refunding
    if invoice.status == "refunded":
        raise HTTPException(status_code=400, detail="Invoice already refunded")
    if invoice.status == "cancelled":
        raise HTTPException(status_code=400, detail="Cannot refund cancelled invoice")

    invoice.status = "refunded"
    db.commit()
    db.refresh(invoice)
    return invoice


# ─── Coupons ─────────────────────────────────────────────────────────────────


@router.post("/coupons", response_model=CouponResponse, status_code=201)
def create_coupon(
    req: CouponCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new coupon.

    VULN: Broken function-level authorization — the endpoint requires a valid
    JWT (get_current_user) but does NOT check if the user has an admin role.
    Any authenticated user can create arbitrary discount coupons.
    """
    # VULN: Missing role check — should verify current_user["role"] == "admin"
    coupon = Coupon(
        code=req.code,
        discount_percent=req.discount_percent,
        max_uses=req.max_uses,
        expires_at=req.expires_at,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.get("/coupons/{code}", response_model=CouponResponse)
def validate_coupon(
    code: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validate a coupon by code."""
    coupon = db.query(Coupon).filter(Coupon.code == code).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return coupon
