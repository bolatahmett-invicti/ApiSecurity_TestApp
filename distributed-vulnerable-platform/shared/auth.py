"""Shared JWT authentication utilities.

INTENTIONAL VULNERABILITIES:
- HS256 with shared secret (no asymmetric keys)
- No audience/issuer validation
- No token blacklist
- Algorithm not enforced on decode (accepts whatever is in token)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, Header, HTTPException, status


# Read from env at import time
import os

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-jwt-key-do-not-use-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")


def create_access_token(data: dict, expires_minutes: int = 60) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload["iat"] = datetime.now(timezone.utc)
    payload["type"] = "access"
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict, expires_days: int = 30) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(days=expires_days)
    payload["iat"] = datetime.now(timezone.utc)
    payload["type"] = "refresh"
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode JWT token.

    VULN: No audience/issuer validation. Algorithm from token header is trusted.
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def get_current_user(authorization: str = Header(...)) -> dict:
    """FastAPI dependency — extracts user from Bearer token.

    Returns dict with: user_id, email, role, org_id
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth header")
    token = authorization[7:]
    try:
        payload = decode_token(token)
        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "role": payload.get("role", "user"),
            "org_id": payload.get("org_id"),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Same as get_current_user but returns None if no token provided."""
    if not authorization:
        return None
    return get_current_user(authorization)
