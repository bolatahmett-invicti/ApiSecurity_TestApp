"""Auth service routes.

INTENTIONAL VULNERABILITIES:
- Verbose error messages distinguish 'user not found' vs 'wrong password'
- Password reset without email verification
- No brute-force protection
- Role settable during registration (mass assignment)
"""

import sys
sys.path.insert(0, "/app")

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import AuthUser, RefreshToken
from schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from shared.auth import create_access_token, create_refresh_token, decode_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Simple user→org mapping (in a real system this would be a DB lookup)
# Users 1-3 belong to org 1 (Acme), users 4-5 to org 2 (Globex), user 6 to org 1 (system)
USER_ORG_MAP = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 1}


def _get_org_id(user_id: int) -> int:
    return USER_ORG_MAP.get(user_id, 1)


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user.

    VULN: Role is accepted from request body (mass assignment).
    """
    existing = db.query(AuthUser).filter(AuthUser.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = AuthUser(
        email=req.email,
        password_hash=pwd_context.hash(req.password),
        role=req.role or "user",  # VULN: accepts role from client
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token_data = {"user_id": user.id, "email": user.email, "role": user.role, "org_id": _get_org_id(user.id)}
    access = create_access_token(token_data)
    refresh = create_refresh_token(token_data)

    # Store refresh token
    db.add(RefreshToken(
        user_id=user.id,
        token=refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    db.commit()

    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login and get JWT tokens.

    VULN: Verbose error messages — distinguishes 'user not found' vs 'wrong password'.
    VULN: No brute-force protection / rate limiting.
    """
    user = db.query(AuthUser).filter(AuthUser.email == req.email).first()
    if not user:
        # VULN: Reveals that the user does not exist
        raise HTTPException(status_code=401, detail="User not found")

    if not pwd_context.verify(req.password, user.password_hash):
        # VULN: Reveals that password is wrong (user exists)
        raise HTTPException(status_code=401, detail="Incorrect password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    token_data = {"user_id": user.id, "email": user.email, "role": user.role, "org_id": _get_org_id(user.id)}
    access = create_access_token(token_data)
    refresh = create_refresh_token(token_data)

    db.add(RefreshToken(
        user_id=user.id,
        token=refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    db.commit()

    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)):
    """Refresh access token."""
    try:
        payload = decode_token(req.refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    stored = db.query(RefreshToken).filter(
        RefreshToken.token == req.refresh_token,
        RefreshToken.revoked == False,
    ).first()

    if not stored:
        raise HTTPException(status_code=401, detail="Token revoked or not found")

    user = db.query(AuthUser).filter(AuthUser.id == payload["user_id"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    token_data = {"user_id": user.id, "email": user.email, "role": user.role, "org_id": _get_org_id(user.id)}
    new_access = create_access_token(token_data)
    new_refresh = create_refresh_token(token_data)

    # Revoke old, issue new
    stored.revoked = True
    db.add(RefreshToken(
        user_id=user.id,
        token=new_refresh,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    db.commit()

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current authenticated user."""
    user = db.query(AuthUser).filter(AuthUser.id == current_user["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(id=user.id, email=user.email, role=user.role, is_active=user.is_active)


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password.

    VULN: No email verification — anyone can reset any user's password
    if they know the email address.
    """
    user = db.query(AuthUser).filter(AuthUser.email == req.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = pwd_context.hash(req.new_password)
    db.commit()
    return {"message": "Password reset successful"}
