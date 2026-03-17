"""Payment service routes.

INTENTIONAL VULNERABILITIES:
- Race condition on payment creation (no locking, no duplicate invoice check)
- BOLA on payment retrieval (no org ownership check)
- Sensitive data exposure (full card number and expiry in responses)
- Cross-org data leak on list endpoint (no org filter)
- Broken function-level auth on refund approval (no admin role check)
- Cross-service trust exploitation on internal confirm endpoint (trusts header without crypto)
"""

import sys
sys.path.insert(0, "/app")

import logging
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models import Payment, Refund
from schemas import (
    PaymentCreate,
    PaymentResponse,
    RefundApproval,
    RefundRequest,
    RefundResponse,
)
from shared.auth import get_current_user
from shared.messaging import publish_event, EVENT_PAYMENT_COMPLETED

logger = logging.getLogger(__name__)

router = APIRouter(tags=["payments"])


# --- Payments ---


@router.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(
    req: PaymentCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a payment for an invoice.

    VULN: Race condition — no database-level locking or unique constraint on
    invoice_id + status. Concurrent requests for the same invoice can all pass
    the (missing) duplicate check and create multiple payments. The deliberate
    time.sleep(0.1) widens the race window.

    VULN: No check if invoice is already paid — allows double-charging.
    """
    # VULN: No check if a payment already exists for this invoice
    # VULN: No SELECT ... FOR UPDATE or advisory lock — race condition

    payment = Payment(
        invoice_id=req.invoice_id,
        org_id=req.org_id or current_user["org_id"],
        amount=req.amount,
        method=req.method,
        # VULN: Stores full card number in plaintext
        card_number=req.card_number,
        card_expiry=req.card_expiry,
        status="pending",
        transaction_ref=str(uuid.uuid4()),
    )
    db.add(payment)

    # VULN: Artificial delay makes race condition more exploitable
    time.sleep(0.1)

    db.commit()
    db.refresh(payment)

    # Simulate payment processing — mark as completed immediately
    payment.status = "completed"
    db.commit()
    db.refresh(payment)

    # Publish payment completed event for billing service
    try:
        publish_event(EVENT_PAYMENT_COMPLETED, {
            "payment_id": payment.id,
            "invoice_id": payment.invoice_id,
            "amount": payment.amount,
            "org_id": payment.org_id,
        })
        logger.info(f"Published payment completed event for payment {payment.id}")
    except Exception as e:
        logger.error(f"Failed to publish payment event: {e}")

    return payment


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single payment by ID.

    VULN: BOLA — retrieves any payment by ID without checking that the payment
    belongs to the current user's organization. An authenticated user can access
    payments from any organization by iterating IDs.

    VULN: Returns full card_number and card_expiry — sensitive data exposure.
    """
    # VULN: No org_id filter — any authenticated user can read any payment
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    # VULN: Full card details returned in response
    return payment


@router.get("/payments", response_model=list[PaymentResponse])
def list_payments(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all payments.

    VULN: Cross-org data leak — returns ALL payments across all organizations
    instead of filtering by the current user's org_id. Any authenticated user
    can see every payment in the system including card numbers.
    """
    # VULN: No org_id filter — returns payments from all organizations
    return db.query(Payment).all()


# --- Refunds ---


@router.post("/payments/{payment_id}/refund", response_model=RefundResponse, status_code=201)
def request_refund(
    payment_id: int,
    req: RefundRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Request a refund for a payment. Any authenticated user can request."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != "completed":
        raise HTTPException(status_code=400, detail="Can only refund completed payments")

    if req.amount > payment.amount:
        raise HTTPException(status_code=400, detail="Refund amount exceeds payment amount")

    refund = Refund(
        payment_id=payment_id,
        amount=req.amount,
        reason=req.reason,
        status="pending",
        requested_by=current_user["user_id"],
    )
    db.add(refund)
    db.commit()
    db.refresh(refund)
    return refund


@router.put("/payments/{payment_id}/refund/approve", response_model=RefundResponse)
def approve_refund(
    payment_id: int,
    req: RefundApproval,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve or reject a pending refund.

    VULN: Broken function-level authorization — the endpoint requires a valid
    JWT (get_current_user) but does NOT check if the user has an admin role.
    Any authenticated user can approve their own or anyone else's refund.
    """
    # VULN: Missing role check — should verify current_user["role"] == "admin"
    refund = (
        db.query(Refund)
        .filter(Refund.payment_id == payment_id, Refund.status == "pending")
        .first()
    )
    if not refund:
        raise HTTPException(status_code=404, detail="No pending refund found for this payment")

    if req.approved:
        refund.status = "approved"
        refund.approved_by = current_user["user_id"]

        # Mark payment as refunded
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if payment:
            payment.status = "refunded"
    else:
        refund.status = "rejected"

    db.commit()
    db.refresh(refund)
    return refund


# --- Internal endpoint ---


@router.post("/internal/payments/confirm", response_model=PaymentResponse)
def internal_confirm_payment(
    request: Request,
    db: Session = Depends(get_db),
):
    """Internal endpoint to confirm a payment from another service.

    VULN: Cross-service trust exploitation — trusts the X-Service-Name header
    without any cryptographic verification (no HMAC, no mTLS, no shared secret).
    Any caller that sets the header can confirm any payment. No JWT required.
    An attacker can forge the header to mark arbitrary payments as completed.
    """
    # VULN: Only checks that X-Service-Name header exists — no crypto verification
    service_name = request.headers.get("X-Service-Name")
    if not service_name:
        raise HTTPException(
            status_code=403,
            detail="Internal endpoint — requires X-Service-Name header",
        )

    payment_id = request.query_params.get("payment_id")
    if not payment_id:
        raise HTTPException(status_code=400, detail="payment_id query parameter required")

    payment = db.query(Payment).filter(Payment.id == int(payment_id)).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # VULN: Blindly trusts the header — marks payment as completed without verification
    logger.info(f"Internal confirm from service '{service_name}' for payment {payment.id}")
    payment.status = "completed"
    db.commit()
    db.refresh(payment)
    return payment
