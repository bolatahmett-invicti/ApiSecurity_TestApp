"""API Gateway — routes all incoming requests to internal microservices.

INTENTIONAL VULNERABILITIES:
- Adds X-Gateway-Auth header that downstream services might trust
- No rate limiting on any route
- Forwards all headers including attacker-injected ones (X-Service-Name, X-Admin-Role)
- Debug mode exposes stack traces
"""

import sys
sys.path.insert(0, "/app")

import os
import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

app = FastAPI(
    title="API Gateway",
    description="Central entry point for the Distributed Vulnerable Platform. Routes requests to microservices.",
    version="1.0.0",
    debug=True,  # VULN: Stack traces exposed
)

# Service routing map
SERVICE_MAP = {
    "/api/auth": os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001"),
    "/api/users": os.getenv("USER_SERVICE_URL", "http://user-service:8002"),
    "/api/orgs": os.getenv("USER_SERVICE_URL", "http://user-service:8002"),
    "/api/projects": os.getenv("PROJECT_SERVICE_URL", "http://project-service:8003"),
    "/api/tasks": os.getenv("PROJECT_SERVICE_URL", "http://project-service:8003"),
    "/api/billing": os.getenv("BILLING_SERVICE_URL", "http://billing-service:8004"),
    "/api/payments": os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8005"),
    "/api/notifications": os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8006"),
    "/api/reports": os.getenv("REPORTING_SERVICE_URL", "http://reporting-service:8007"),
}


def _resolve_backend(path: str) -> tuple[str, str] | None:
    """Find the backend service URL for a given request path."""
    for prefix, service_url in SERVICE_MAP.items():
        if path.startswith(prefix):
            # Strip /api prefix, forward the rest
            backend_path = path[len("/api"):]
            return service_url, backend_path
    return None


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    """Reverse proxy to backend services.

    VULN: Forwards ALL headers to backend, including attacker-controlled ones
    like X-Service-Name and X-Admin-Role.
    VULN: Adds X-Gateway-Auth header that backends might blindly trust.
    VULN: No rate limiting.
    """
    full_path = f"/api/{path}"
    resolved = _resolve_backend(full_path)

    if not resolved:
        return JSONResponse(status_code=404, content={"detail": "Service not found"})

    service_url, backend_path = resolved

    # Build target URL with query string
    target_url = f"{service_url}{backend_path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Forward headers (VULN: includes attacker-injected headers)
    headers = dict(request.headers)
    headers.pop("host", None)
    # VULN: Gateway adds trusted header that backends might trust without verification
    headers["X-Gateway-Auth"] = "gateway-internal-trusted"
    headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"

    # Read request body
    body = await request.body()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )
            # Forward response headers (except hop-by-hop)
            response_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in ("transfer-encoding", "content-encoding", "content-length")
            }
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=response_headers,
                media_type=resp.headers.get("content-type", "application/json"),
            )
        except httpx.ConnectError:
            return JSONResponse(status_code=502, content={"detail": "Backend service unavailable"})
        except httpx.TimeoutException:
            return JSONResponse(status_code=504, content={"detail": "Backend service timeout"})


@app.get("/health")
def health():
    return {"status": "ok", "service": "gateway"}


from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
def root():
    try:
        with open("/app/ui.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>UI not found</h1>", status_code=500)


if __name__ == "__main__":
    import ssl
    cert_file = "/etc/tls/tls.crt"
    key_file = "/etc/tls/tls.key"
    if os.path.exists(cert_file) and os.path.exists(key_file):
        uvicorn.run(app, host="0.0.0.0", port=8443, ssl_keyfile=key_file, ssl_certfile=cert_file)
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
