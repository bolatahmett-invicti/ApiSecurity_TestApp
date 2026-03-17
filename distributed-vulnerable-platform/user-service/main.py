"""User Service — user profiles, organizations, memberships, API tokens."""

import sys
sys.path.insert(0, "/app")

import uvicorn
from fastapi import FastAPI

from database import create_tables
from routes import router

app = FastAPI(
    title="User Service",
    description="User management, organizations, and API tokens. Part of the Distributed Vulnerable Platform.",
    version="1.0.0",
    debug=True,  # VULN: Debug mode exposes stack traces
)

app.include_router(router)


@app.on_event("startup")
def on_startup():
    create_tables()


@app.get("/health")
def health():
    return {"status": "ok", "service": "user-service"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
