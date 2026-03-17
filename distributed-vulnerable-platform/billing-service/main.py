"""Billing Service — Subscription, invoice, and coupon management."""

import sys
sys.path.insert(0, "/app")

import logging
import threading
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI

from database import create_tables, SessionLocal
from models import Invoice
from routes import router
from shared.messaging import consume_events, EVENT_PAYMENT_COMPLETED

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Billing Service",
    description="Billing, subscriptions, invoices, and coupons. Part of the Distributed Vulnerable Platform.",
    version="1.0.0",
    debug=True,  # VULN: Debug mode exposes stack traces
)

app.include_router(router)


def handle_payment_event(routing_key: str, payload: dict):
    """Handle payment completed events from RabbitMQ.

    VULN: No source validation — trusts any event on the queue. An attacker
    who can publish to RabbitMQ can mark any invoice as paid by sending a
    crafted event with an arbitrary invoice_id. There is no signature
    verification, no shared secret, and no sender identity check.
    """
    logger.info(f"Received event: {routing_key} — payload: {payload}")

    if routing_key == EVENT_PAYMENT_COMPLETED:
        invoice_id = payload.get("invoice_id")
        if not invoice_id:
            logger.warning("Payment event missing invoice_id")
            return

        # VULN: Blindly trusts the event — no verification that payment actually occurred
        db = SessionLocal()
        try:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if invoice:
                invoice.status = "paid"
                invoice.paid_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"Invoice {invoice_id} marked as paid via event")
            else:
                logger.warning(f"Invoice {invoice_id} not found for payment event")
        finally:
            db.close()


def start_consumer():
    """Start RabbitMQ consumer in a background thread."""
    try:
        consume_events(
            queue_name="billing_payment_queue",
            routing_keys=[EVENT_PAYMENT_COMPLETED],
            handler=handle_payment_event,
        )
    except Exception as e:
        logger.error(f"RabbitMQ consumer failed: {e}")


@app.on_event("startup")
def on_startup():
    create_tables()
    consumer_thread = threading.Thread(target=start_consumer, daemon=True)
    consumer_thread.start()
    logger.info("Billing service started — RabbitMQ consumer running in background")


@app.get("/health")
def health():
    return {"status": "ok", "service": "billing-service"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004)
