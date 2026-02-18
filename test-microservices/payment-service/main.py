"""
Payment Service - FastAPI Microservice
Handles all payment processing, billing, and transaction management.

Enriched with comprehensive Pydantic validation for Logic-oriented Fuzzing (LoF) testing:
- Annotated field constraints (gt, lt, ge, le, min_length, max_length, pattern)
- Literal enum types for currency codes, billing intervals, refund reasons
- Ownership validation patterns (current_user checks → IDOR detection)
- Business rule validation (refund limits, subscription constraints)
"""
from fastapi import FastAPI, HTTPException, Depends, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
from typing import Annotated, Literal, Optional, List
from datetime import datetime
from enum import Enum
import uuid

app = FastAPI(
    title="Payment Service",
    description="Core payment processing microservice",
    version="2.1.0"
)

security = HTTPBearer()

# =============================================================================
# TYPE ALIASES — Literal enums for semantic validation
# =============================================================================

# Supported ISO 4217 currency codes
CurrencyCode = Literal["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF"]

# Subscription billing intervals
BillingInterval = Literal["weekly", "monthly", "quarterly", "yearly"]

# Refund reason codes (constrained to known values)
RefundReason = Literal[
    "duplicate",
    "fraudulent",
    "customer_request",
    "product_not_received",
    "product_unacceptable",
]

# Export file formats
ExportFormat = Literal["csv", "json", "xml", "pdf"]

# Transaction report grouping
ReportGroupBy = Literal["day", "week", "month", "currency", "payment_method"]


# =============================================================================
# ENUMS
# =============================================================================
class PaymentStatus(str, Enum):
    PENDING = "pending"
    AUTHORIZED = "authorized"
    COMPLETED = "completed"
    FAILED = "failed"
    VOIDED = "voided"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    CRYPTO = "crypto"
    WALLET = "wallet"


# =============================================================================
# MODELS — enriched with full Pydantic Field constraints
# =============================================================================

class CreatePaymentRequest(BaseModel):
    """
    Create a new payment transaction.

    :param amount: Payment amount in smallest currency unit (e.g. cents). Must be > 0 and < 1,000,000.
    :param currency: ISO 4217 currency code. One of: USD, EUR, GBP, JPY, CAD, AUD, CHF.
    :param customer_id: Customer identifier. Between 3 and 64 characters.
    :param order_id: Associated order identifier. Between 3 and 64 characters.
    :param payment_method: Payment method type.
    :param card_number: Card PAN (masked). Between 13 and 19 digits.
    :param card_expiry: Card expiry in MM/YY format.
    :param card_cvv: Card CVV. 3 or 4 digits.
    :param description: Optional transaction description. Max 255 characters.
    :param idempotency_key: Idempotency key to prevent duplicate charges. Between 10 and 128 characters.
    """
    amount: Annotated[float, Field(gt=0, lt=1_000_000, description="Amount in smallest currency unit")]
    currency: CurrencyCode = "USD"
    customer_id: Annotated[str, Field(min_length=3, max_length=64)]
    order_id: Annotated[str, Field(min_length=3, max_length=64)]
    payment_method: PaymentMethod
    card_number: Optional[Annotated[str, Field(min_length=13, max_length=19)]] = None
    card_expiry: Optional[Annotated[str, Field(pattern=r"^\d{2}/\d{2}$")]] = None
    card_cvv: Optional[Annotated[str, Field(min_length=3, max_length=4)]] = None
    description: Optional[Annotated[str, Field(max_length=255)]] = None
    idempotency_key: Optional[Annotated[str, Field(min_length=10, max_length=128)]] = None


class RefundRequest(BaseModel):
    """
    Process a refund for a completed transaction.

    :param transaction_id: UUID of the original transaction (36 chars).
    :param amount: Refund amount. Must be > 0 and < 1,000,000. Omit for full refund.
    :param reason: Refund reason code. Must be one of the allowed values.
    :param notes: Optional internal notes. Max 500 characters.
    """
    transaction_id: Annotated[str, Field(min_length=36, max_length=36)]
    amount: Optional[Annotated[float, Field(gt=0, lt=1_000_000)]] = None
    reason: RefundReason
    notes: Optional[Annotated[str, Field(max_length=500)]] = None


class CreateSubscriptionRequest(BaseModel):
    """
    Create a recurring subscription.

    :param customer_id: Customer identifier. Between 3 and 64 characters.
    :param plan_id: Subscription plan identifier. Between 3 and 64 characters.
    :param billing_interval: Billing cycle. One of: weekly, monthly, quarterly, yearly.
    :param amount: Recurring charge amount. Must be > 0 and < 100,000.
    :param trial_days: Free trial period. Between 0 and 365 days.
    :param max_retry_attempts: Payment retry attempts on failure. Between 1 and 5.
    :param discount_percent: Optional discount. Between 0 and 100 percent.
    """
    customer_id: Annotated[str, Field(min_length=3, max_length=64)]
    plan_id: Annotated[str, Field(min_length=3, max_length=64)]
    billing_interval: BillingInterval
    amount: Annotated[float, Field(gt=0, lt=100_000)]
    trial_days: Annotated[int, Field(ge=0, le=365)] = 0
    max_retry_attempts: Annotated[int, Field(ge=1, le=5)] = 3
    discount_percent: Annotated[float, Field(ge=0, le=100)] = 0.0


class BatchRefundRequest(BaseModel):
    """
    Process batch refunds for multiple transactions.

    :param transaction_ids: List of transaction UUIDs. Between 1 and 100 items.
    :param reason: Batch refund reason.
    :param notify_customers: Send email notifications to customers.
    """
    transaction_ids: Annotated[List[str], Field(min_length=1, max_length=100)]
    reason: RefundReason
    notify_customers: bool = True


class ExportTransactionsRequest(BaseModel):
    """
    Export transaction data.

    :param format: Output format. One of: csv, json, xml, pdf.
    :param customer_id: Filter by customer (optional).
    :param max_records: Maximum records to export. Between 1 and 10,000.
    :param group_by: Group results by period or dimension.
    """
    format: ExportFormat
    customer_id: Optional[Annotated[str, Field(min_length=3, max_length=64)]] = None
    max_records: Annotated[int, Field(ge=1, le=10_000)] = 1000
    group_by: Optional[ReportGroupBy] = None


class PaymentResponse(BaseModel):
    transaction_id: str
    status: PaymentStatus
    amount: float
    currency: str
    created_at: datetime


# =============================================================================
# AUTH HELPERS — ownership context for IDOR detection
# =============================================================================

class CurrentUser:
    def __init__(self, user_id: str, role: str = "user"):
        self.id = user_id
        self.role = role


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> CurrentUser:
    """
    Decode JWT and return current authenticated user.
    In production this validates the token; here it returns a mock user.
    """
    # In production: decode JWT, validate claims, fetch user
    return CurrentUser(user_id="user_mock_123", role="user")


# =============================================================================
# HEALTH ENDPOINTS
# =============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return {"status": "healthy", "service": "payment-service"}


@app.get("/health/live", tags=["Health"])
async def liveness_probe():
    """Kubernetes liveness probe."""
    return {"alive": True}


@app.get("/health/ready", tags=["Health"])
async def readiness_probe():
    """Kubernetes readiness probe."""
    return {"ready": True, "database": "connected", "redis": "connected"}


# =============================================================================
# PUBLIC ENDPOINTS
# =============================================================================

@app.get("/api/v1/payment-methods", tags=["Public"])
async def list_payment_methods():
    """List available payment methods (public endpoint)."""
    return {
        "methods": [
            {"id": "credit_card", "name": "Credit Card", "enabled": True},
            {"id": "debit_card", "name": "Debit Card", "enabled": True},
            {"id": "bank_transfer", "name": "Bank Transfer", "enabled": True},
            {"id": "crypto", "name": "Cryptocurrency", "enabled": False},
            {"id": "wallet", "name": "Digital Wallet", "enabled": True},
        ]
    }


@app.get("/api/v1/currencies", tags=["Public"])
async def list_currencies():
    """List supported currencies."""
    return {"currencies": ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF"]}


# =============================================================================
# AUTHENTICATED PAYMENT ENDPOINTS
# =============================================================================

@app.post("/api/v1/payments", tags=["Payments"], response_model=PaymentResponse)
async def create_payment(
    request: CreatePaymentRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Process a new payment transaction.

    Business rules:
    - amount must be greater than 0 and less than 1,000,000
    - currency must be a supported ISO 4217 code
    - card_number required when payment_method is credit_card or debit_card
    - card_expiry must match MM/YY format
    """
    # Business rule: card details required for card payments
    if request.payment_method in (PaymentMethod.CREDIT_CARD, PaymentMethod.DEBIT_CARD):
        if not request.card_number:
            raise HTTPException(status_code=422, detail="card_number required for card payments")
        if not request.card_expiry:
            raise HTTPException(status_code=422, detail="card_expiry required for card payments")

    transaction_id = str(uuid.uuid4())
    return PaymentResponse(
        transaction_id=transaction_id,
        status=PaymentStatus.COMPLETED,
        amount=request.amount,
        currency=request.currency,
        created_at=datetime.utcnow()
    )


@app.get("/api/v1/payments/{transaction_id}", tags=["Payments"])
async def get_payment(
    transaction_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Get payment details by transaction ID.

    IDOR protection: only the transaction owner can view their payment.
    The transaction's customer_id is compared to current_user.id.
    """
    # Simulate DB lookup
    transaction = {"transaction_id": transaction_id, "customer_id": "user_mock_123",
                   "status": "completed", "amount": 9999, "currency": "USD"}

    # IDOR check — ownership validation
    if transaction["customer_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this transaction")

    return transaction


@app.get("/api/v1/payments", tags=["Payments"])
async def list_payments(
    customer_id: Optional[str] = None,
    status: Optional[PaymentStatus] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 50,
    offset: Annotated[int, Field(ge=0)] = 0,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    List payments with optional filters.

    IDOR protection: if customer_id is provided, it must match the authenticated user
    (admins can query other users).

    :param limit: Page size. Between 1 and 100.
    :param offset: Page offset. Must be >= 0.
    """
    # IDOR: non-admin users can only list their own payments
    if customer_id and customer_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot list payments for another customer")

    return {"payments": [], "total": 0, "limit": limit, "offset": offset}


@app.post("/api/v1/payments/{transaction_id}/capture", tags=["Payments"])
async def capture_payment(
    transaction_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Capture an authorized payment.
    Only the transaction owner can capture their payment.
    """
    # Business rule: verify ownership before capture
    transaction = {"transaction_id": transaction_id, "customer_id": current_user.id,
                   "status": "authorized"}
    if transaction["customer_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if transaction["status"] != "authorized":
        raise HTTPException(status_code=409, detail="Only authorized payments can be captured")

    return {"transaction_id": transaction_id, "status": "captured"}


@app.post("/api/v1/payments/{transaction_id}/void", tags=["Payments"])
async def void_payment(
    transaction_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Void a pending or authorized payment.
    Only allowed for payments in pending or authorized state.
    """
    transaction = {"transaction_id": transaction_id, "customer_id": current_user.id,
                   "status": "authorized"}
    if transaction["status"] not in ("pending", "authorized"):
        raise HTTPException(status_code=409, detail="Only pending or authorized payments can be voided")
    if transaction["customer_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {"transaction_id": transaction_id, "status": "voided"}


# =============================================================================
# REFUND ENDPOINTS
# =============================================================================

@app.post("/api/v1/refunds", tags=["Refunds"])
async def create_refund(
    request: RefundRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Process a refund for a completed transaction.

    Business rules:
    - transaction must be in 'completed' status
    - refund amount must not exceed original transaction amount
    - cannot refund an already-fully-refunded transaction
    """
    # Simulate DB lookup
    transaction = {"transaction_id": request.transaction_id, "customer_id": current_user.id,
                   "status": "completed", "amount": 5000.0, "refunded_amount": 0.0}

    # IDOR: only the transaction owner can request a refund
    if transaction["customer_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Business rule: only completed transactions can be refunded
    if transaction["status"] != "completed":
        raise HTTPException(status_code=409, detail="Only completed transactions can be refunded")

    # Business rule: refund amount must not exceed original minus already refunded
    refund_amount = request.amount or transaction["amount"]
    remaining_refundable = transaction["amount"] - transaction["refunded_amount"]
    if refund_amount > remaining_refundable:
        raise HTTPException(
            status_code=422,
            detail=f"Refund amount {refund_amount} exceeds refundable balance {remaining_refundable}"
        )

    refund_id = str(uuid.uuid4())
    return {
        "refund_id": refund_id,
        "transaction_id": request.transaction_id,
        "amount": refund_amount,
        "reason": request.reason,
        "status": "processed"
    }


@app.get("/api/v1/refunds/{refund_id}", tags=["Refunds"])
async def get_refund(
    refund_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Get refund details.
    IDOR protection: only the refund owner can view it.
    """
    refund = {"refund_id": refund_id, "customer_id": current_user.id, "status": "completed"}
    if refund["customer_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return refund


# =============================================================================
# BILLING ENDPOINTS
# =============================================================================

@app.get("/api/v1/billing/invoices", tags=["Billing"])
async def list_invoices(
    customer_id: str,
    limit: Annotated[int, Field(ge=1, le=200)] = 20,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    List customer invoices.
    IDOR protection: customer_id must match authenticated user.

    :param limit: Page size. Between 1 and 200.
    """
    if customer_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot list invoices for another customer")
    return {"invoices": [], "customer_id": customer_id}


@app.get("/api/v1/billing/invoices/{invoice_id}", tags=["Billing"])
async def get_invoice(
    invoice_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get invoice details. Invoice must belong to the authenticated user."""
    invoice = {"invoice_id": invoice_id, "customer_id": current_user.id, "status": "paid"}
    if invoice["customer_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return invoice


@app.post("/api/v1/billing/invoices/{invoice_id}/pay", tags=["Billing"])
async def pay_invoice(
    invoice_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Pay an outstanding invoice.
    Business rule: invoice must be in 'pending' or 'overdue' status.
    """
    invoice = {"invoice_id": invoice_id, "customer_id": current_user.id,
               "status": "pending", "amount": 299.99}
    if invoice["customer_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if invoice["status"] not in ("pending", "overdue"):
        raise HTTPException(status_code=409, detail="Invoice is not payable in its current state")
    return {"invoice_id": invoice_id, "status": "paid", "amount_charged": invoice["amount"]}


# =============================================================================
# SUBSCRIPTION ENDPOINTS
# =============================================================================

@app.get("/api/v1/subscriptions", tags=["Subscriptions"])
async def list_subscriptions(
    customer_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    List customer subscriptions.
    IDOR protection: customer_id must match authenticated user.
    """
    if customer_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot list subscriptions for another customer")
    return {"subscriptions": []}


@app.post("/api/v1/subscriptions", tags=["Subscriptions"])
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Create a new subscription.

    Business rules:
    - customer_id must match authenticated user
    - discount_percent must be between 0 and 100
    - trial_days must be between 0 and 365
    - max_retry_attempts between 1 and 5
    """
    if request.customer_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Cannot create subscription for another customer")

    return {
        "subscription_id": str(uuid.uuid4()),
        "customer_id": request.customer_id,
        "plan_id": request.plan_id,
        "billing_interval": request.billing_interval,
        "amount": request.amount,
        "trial_days": request.trial_days,
        "status": "active"
    }


@app.delete("/api/v1/subscriptions/{subscription_id}", tags=["Subscriptions"])
async def cancel_subscription(
    subscription_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Cancel a subscription.
    Business rule: subscription must belong to authenticated user.
    """
    subscription = {"subscription_id": subscription_id, "customer_id": current_user.id,
                    "status": "active"}
    if subscription["customer_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    if subscription["status"] == "cancelled":
        raise HTTPException(status_code=409, detail="Subscription is already cancelled")

    return {"subscription_id": subscription_id, "status": "cancelled"}


# =============================================================================
# ADMIN ENDPOINTS (Internal)
# =============================================================================

@app.get("/internal/admin/transactions", tags=["Admin"])
async def admin_list_transactions(
    limit: Annotated[int, Field(ge=1, le=1000)] = 100,
    x_admin_key: str = Header(..., alias="X-Admin-Key")
):
    """[ADMIN] List all transactions across all customers."""
    return {"transactions": [], "total": 0}


@app.post("/internal/admin/refund-batch", tags=["Admin"])
async def admin_batch_refund(
    request: BatchRefundRequest,
    x_admin_key: str = Header(..., alias="X-Admin-Key")
):
    """
    [ADMIN] Process batch refunds.

    Business rule: transaction_ids list must have 1-100 items.
    """
    return {"processed": len(request.transaction_ids), "failed": 0}


@app.post("/internal/admin/export", tags=["Admin"])
async def admin_export_transactions(
    request: ExportTransactionsRequest,
    x_admin_key: str = Header(..., alias="X-Admin-Key")
):
    """
    [ADMIN] Export transaction data.
    Format must be one of: csv, json, xml, pdf.
    max_records must be between 1 and 10,000.
    """
    return {
        "export_id": str(uuid.uuid4()),
        "format": request.format,
        "max_records": request.max_records,
        "status": "queued"
    }


@app.delete("/internal/admin/transactions/{transaction_id}", tags=["Admin"])
async def admin_delete_transaction(
    transaction_id: str,
    x_admin_key: str = Header(..., alias="X-Admin-Key")
):
    """[ADMIN] Delete a transaction (audit log preserved)."""
    return {"deleted": True}


@app.post("/internal/admin/database/reset", tags=["Admin"])
async def admin_reset_database(
    x_admin_key: str = Header(..., alias="X-Admin-Key")
):
    """[ADMIN] Reset database to initial state (DANGEROUS)."""
    return {"reset": True, "warning": "All data has been cleared"}


# =============================================================================
# WEBHOOKS
# =============================================================================

@app.post("/webhooks/stripe", tags=["Webhooks"])
async def stripe_webhook():
    """Handle Stripe payment webhooks."""
    return {"received": True}


@app.post("/webhooks/paypal", tags=["Webhooks"])
async def paypal_webhook():
    """Handle PayPal payment webhooks."""
    return {"received": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
