"""Payment Service — Payment processing, refunds, and card management."""

import sys
sys.path.insert(0, "/app")

import logging

import uvicorn
from fastapi import FastAPI

from database import create_tables
from routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Payment Service",
    description="Payment processing, refunds, and card management. Part of the Distributed Vulnerable Platform.",
    version="1.0.0",
    debug=True,  # VULN: Debug mode exposes stack traces
)

app.include_router(router)


@app.on_event("startup")
def on_startup():
    create_tables()
    logger.info("Payment service started")


@app.get("/health")
def health():
    return {"status": "ok", "service": "payment-service"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8005)
