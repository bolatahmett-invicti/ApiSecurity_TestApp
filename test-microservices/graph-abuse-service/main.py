"""
Graph Abuse Test Microservice
==============================
Demonstrates API graph abuse patterns for DAST security testing.

Port: 8007

Attack patterns implemented:
1. Batch Abuse - Bulk operations without per-item authorization
2. Race Condition - TOCTOU without atomic operations
3. Circular Dependency - Self-referencing service calls
4. Fan-out Amplification - Unbounded downstream call multiplication
5. Webhook Bridge - External webhook triggering internal actions
6. Chain Exploitation - Public -> Admin privilege escalation
"""

from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Annotated
import httpx
import requests
import uuid
import asyncio

app = FastAPI(
    title="Graph Abuse Service",
    description="Demonstrates API graph abuse patterns for security testing",
    version="1.0.0",
)

security = HTTPBearer(auto_error=False)

BASE_URL = "http://localhost:8007"
INVENTORY_SERVICE_URL = "http://localhost:8006"
PAYMENT_SERVICE_URL = "http://localhost:8001"


# ── Data Models ─────────────────────────────────────────────────────────────

class RefundItem(BaseModel):
    transaction_id: str
    amount: Annotated[float, Field(gt=0, lt=1_000_000)]
    reason: str

class UserBulkImport(BaseModel):
    email: str
    name: str
    department: str
    role: str = "viewer"

class TransferRequest(BaseModel):
    from_account: str
    to_account: str
    amount: Annotated[float, Field(gt=0)]
    currency: str = "USD"

class CheckoutRequest(BaseModel):
    cart_id: str
    payment_method_id: str
    shipping_address_id: str

class BroadcastMessage(BaseModel):
    title: str
    body: str
    priority: str = "normal"
    channel: str = "all"

class RegistrationRequest(BaseModel):
    username: str
    email: str
    password: str

class WebhookEvent(BaseModel):
    event_type: str
    data: dict
    timestamp: Optional[str] = None

class OrderEvent(BaseModel):
    order_id: str
    status: str
    customer_id: str

class NotificationTarget(BaseModel):
    user_id: str
    channel: str  # email, sms, push
    template_id: str


# ── In-memory stores ────────────────────────────────────────────────────────

accounts_db = {
    "acc_001": {"balance": 5000.00, "owner": "user_1", "currency": "USD"},
    "acc_002": {"balance": 3000.00, "owner": "user_2", "currency": "USD"},
    "acc_003": {"balance": 10000.00, "owner": "user_3", "currency": "USD"},
}

inventory_db = {
    "prod_001": {"name": "Widget A", "stock": 5, "price": 29.99},
    "prod_002": {"name": "Widget B", "stock": 100, "price": 49.99},
}

subscriptions_db = {}
tokens_db = {}


# ── Helper functions ────────────────────────────────────────────────────────

def generate_token(user_data: dict) -> str:
    token = f"tok_{uuid.uuid4().hex[:16]}"
    tokens_db[token] = {"user_id": user_data.get("id", "unknown"), "scope": "basic"}
    return token

def verify_token_validity(token: str) -> bool:
    """Verifies token exists but does NOT check scope/role."""
    return token.replace("Bearer ", "") in tokens_db

def process_single_refund(item: RefundItem) -> dict:
    return {"transaction_id": item.transaction_id, "status": "refunded", "amount": item.amount}

def send_notification_sync(user_id: str, message: str):
    """Simulates sending a notification (blocking call)."""
    pass

def activate_subscription_internal(customer_id: str, plan: str = "premium"):
    subscriptions_db[customer_id] = {"plan": plan, "active": True}

def grant_role(user_id: str, role: str):
    pass

def suspend_account(user_id: str):
    pass


# ── Health & Readiness ──────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "graph-abuse-service"}

@app.get("/health/ready")
async def readiness():
    return {"ready": True}

@app.get("/health/live")
async def liveness():
    return {"live": True}


# ═══════════════════════════════════════════════════════════════════════════
# 1. BATCH ABUSE — Bulk operations without per-item authorization
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/admin/refund-batch")
async def batch_refund(
    items: List[RefundItem],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    VULNERABLE: Accepts 1-500 refund items in a single request.
    No per-item ownership verification. No per-item rate limiting.
    Attacker can refund any transaction by knowing the ID.
    """
    if not credentials:
        raise HTTPException(401, "Authentication required")

    results = []
    for item in items:
        # No check: does this user own this transaction?
        result = process_single_refund(item)
        results.append(result)

    return {
        "batch_id": f"batch_{uuid.uuid4().hex[:8]}",
        "processed": len(results),
        "total_refunded": sum(r["amount"] for r in results),
        "results": results,
    }


@app.post("/api/v1/admin/import-users")
async def bulk_import_users(
    users: List[UserBulkImport],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    VULNERABLE: Bulk user import without per-user validation.
    Attacker can create users with elevated roles.
    """
    if not credentials:
        raise HTTPException(401, "Authentication required")

    created = []
    for user in users:
        # No per-item role validation — attacker can set role: "admin"
        created.append({
            "email": user.email,
            "role": user.role,
            "status": "created",
            "id": f"usr_{uuid.uuid4().hex[:8]}",
        })

    return {"imported": len(created), "users": created}


@app.post("/api/v1/admin/bulk-suspend")
async def bulk_suspend(
    user_ids: List[str],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    VULNERABLE: Mass account suspension without per-account verification.
    """
    if not credentials:
        raise HTTPException(401, "Authentication required")

    suspended = []
    for user_id in user_ids:
        suspend_account(user_id)
        suspended.append(user_id)

    return {"suspended": len(suspended), "user_ids": suspended}


# ═══════════════════════════════════════════════════════════════════════════
# 2. RACE CONDITION — TOCTOU without atomic operations
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/transfers")
async def money_transfer(
    transfer: TransferRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    VULNERABLE: Balance check then deduct without atomic operation.
    Two concurrent requests can both pass the balance check.
    """
    if not credentials:
        raise HTTPException(401, "Authentication required")

    from_acc = accounts_db.get(transfer.from_account)
    if not from_acc:
        raise HTTPException(404, "Source account not found")

    # CHECK: Read balance (not locked)
    balance = from_acc["balance"]

    if balance < transfer.amount:
        raise HTTPException(400, "Insufficient funds")

    # ACT: Deduct (race window between CHECK and ACT!)
    # Another concurrent request could pass the check above
    from_acc["balance"] -= transfer.amount

    to_acc = accounts_db.get(transfer.to_account)
    if to_acc:
        to_acc["balance"] += transfer.amount

    return {
        "transfer_id": f"txn_{uuid.uuid4().hex[:8]}",
        "amount": transfer.amount,
        "from_balance": from_acc["balance"],
    }


@app.post("/api/v1/checkout")
async def checkout(
    request: CheckoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    VULNERABLE: Stock check then reserve without lock.
    Concurrent checkouts can oversell inventory.
    """
    if not credentials:
        raise HTTPException(401, "Authentication required")

    product = inventory_db.get("prod_001")
    if not product:
        raise HTTPException(404, "Product not found")

    # CHECK: Read stock (not locked)
    stock = product["stock"]
    available = stock

    if available <= 0:
        raise HTTPException(400, "Out of stock")

    # ACT: Reserve (race window!)
    product["stock"] -= 1

    return {
        "checkout_id": f"chk_{uuid.uuid4().hex[:8]}",
        "product": product["name"],
        "remaining_stock": product["stock"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3. CIRCULAR DEPENDENCY — Self-referencing service calls
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/events/order-completed")
async def on_order_completed(event: OrderEvent):
    """
    VULNERABLE: Order completion handler calls back to own service.
    Creates potential infinite loop.
    """
    # Process the order
    order_status = event.status

    # Notify via own service — creates circular dependency!
    requests.post(
        f"{BASE_URL}/api/v1/events/send-notification",
        json={
            "order_id": event.order_id,
            "customer_id": event.customer_id,
            "type": "order_completed",
        },
    )

    return {"processed": True, "order_id": event.order_id}


@app.post("/api/v1/events/send-notification")
async def send_notification_event(request: Request):
    """
    VULNERABLE: Notification sender calls back to event processor.
    """
    data = await request.json()

    # Process notification — then call back to own service!
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{BASE_URL}/api/v1/events/audit-log",
            json={"event": "notification_sent", "data": data},
        )

    return {"sent": True}


@app.post("/api/v1/events/audit-log")
async def audit_log_event(request: Request):
    """Part of circular chain: audit -> events -> notification -> audit."""
    data = await request.json()
    return {"logged": True, "event": data.get("event")}


# ═══════════════════════════════════════════════════════════════════════════
# 4. FAN-OUT AMPLIFICATION — Unbounded downstream calls
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/notifications/broadcast")
async def broadcast_notification(
    message: BroadcastMessage,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    VULNERABLE: Sends notification to ALL subscribers without throttling.
    1 request = N downstream calls (N could be 100K+).
    """
    if not credentials:
        raise HTTPException(401, "Authentication required")

    # Get all subscribers (could be massive list)
    subscribers = [f"user_{i}" for i in range(10000)]

    sent_count = 0
    for subscriber in subscribers:
        send_notification_sync(subscriber, message.body)
        sent_count += 1

    return {"broadcast_id": f"bc_{uuid.uuid4().hex[:8]}", "sent_to": sent_count}


@app.post("/api/v1/notifications/targeted")
async def targeted_notification(
    targets: List[NotificationTarget],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    VULNERABLE: Fan-out via unbounded target list with external calls.
    """
    if not credentials:
        raise HTTPException(401, "Authentication required")

    for target in targets:
        # Each target triggers an external service call
        send_notification_sync(target.user_id, f"template:{target.template_id}")

    return {"sent": len(targets)}


# ═══════════════════════════════════════════════════════════════════════════
# 5. WEBHOOK-TO-INTERNAL BRIDGE — External triggers internal actions
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """
    VULNERABLE: No webhook signature verification.
    Attacker can forge Stripe events to activate subscriptions.
    """
    event = await request.json()

    # No signature verification! Anyone can POST here
    event_type = event.get("type", "")

    if event_type == "checkout.session.completed":
        customer_id = event.get("data", {}).get("customer_id")
        activate_subscription_internal(customer_id, "premium")

    elif event_type == "customer.subscription.deleted":
        customer_id = event.get("data", {}).get("customer_id")
        suspend_account(customer_id)

    return {"received": True}


@app.post("/webhooks/payment-gateway")
async def payment_gateway_webhook(request: Request):
    """
    VULNERABLE: Payment webhook triggers role grants without verification.
    """
    data = await request.json()

    if data.get("status") == "success":
        grant_role(data.get("user_id"), data.get("tier", "premium"))
        activate_subscription_internal(data.get("user_id"))

    return {"processed": True}


@app.post("/webhooks/partner-callback")
async def partner_callback(request: Request):
    """
    VULNERABLE: Partner callback triggers internal admin actions.
    """
    data = await request.json()

    # No source IP validation, no HMAC, no shared secret
    if data.get("action") == "provision":
        activate_subscription_internal(data["customer_id"], data.get("plan", "basic"))
    elif data.get("action") == "deprovision":
        suspend_account(data["customer_id"])

    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# 6. CHAIN EXPLOITATION — Public to Admin privilege escalation
# ═══════════════════════════════════════════════════════════════════════════

@app.post("/api/v1/auth/register")
async def register_user(user: RegistrationRequest):
    """
    PUBLIC endpoint: Creates user and returns temporary token.
    This is step 1 of the privilege escalation chain.
    """
    user_id = f"usr_{uuid.uuid4().hex[:8]}"
    token = generate_token({"id": user_id, "email": user.email})

    return {
        "user_id": user_id,
        "access_token": token,
        "token_type": "bearer",
    }


@app.get("/api/v1/auth/token-exchange")
async def exchange_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Exchanges temporary token for long-lived token.
    Step 2: No scope upgrade validation.
    """
    if not credentials:
        raise HTTPException(401, "Token required")

    token = credentials.credentials
    if not verify_token_validity(token):
        raise HTTPException(401, "Invalid token")

    # Issue new token without scope restriction
    new_token = f"tok_{uuid.uuid4().hex[:16]}"
    tokens_db[new_token] = tokens_db.get(token, {})
    return {"access_token": new_token, "token_type": "bearer"}


@app.get("/internal/admin/users/{user_id}")
async def admin_get_user(
    user_id: str,
    authorization: str = Header(default=""),
):
    """
    VULNERABLE: Admin endpoint that trusts any valid token.
    Step 3: No admin role check — any registered user can access.
    """
    token = authorization.replace("Bearer ", "")
    if not verify_token_validity(token):
        raise HTTPException(401, "Invalid token")

    # No role/scope check! Any token works
    return {
        "user_id": user_id,
        "email": "admin@company.com",
        "role": "admin",
        "internal_notes": "Sensitive admin data exposed",
    }


@app.delete("/internal/admin/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    authorization: str = Header(default=""),
):
    """
    VULNERABLE: Admin deletion endpoint accessible with any valid token.
    """
    token = authorization.replace("Bearer ", "")
    if not verify_token_validity(token):
        raise HTTPException(401, "Invalid token")

    return {"deleted": True, "user_id": user_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
