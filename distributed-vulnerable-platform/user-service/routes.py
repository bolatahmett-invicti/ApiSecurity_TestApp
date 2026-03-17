"""User service routes.

INTENTIONAL VULNERABILITIES:
- BOLA: No org_id check on user/org access
- Broken function-level auth: DELETE /users/{id} has no admin check
- Bulk data harvesting: GET /users has no org filter, accepts page_size=10000
- Sensitive data exposure: Returns PII, password_hash, plaintext API tokens
- Mass assignment: PUT /users/{id} accepts role field
"""

import sys
sys.path.insert(0, "/app")

import hashlib
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import APIToken, Invite, OrgMembership, Organization, User
from schemas import (
    APITokenCreate,
    APITokenResponse,
    InviteRequest,
    MembershipResponse,
    OrgCreate,
    OrgResponse,
    UserResponse,
    UserUpdate,
)
from shared.auth import get_current_user

router = APIRouter(tags=["users"])


# ── Users ──────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserResponse])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20),  # VULN: No max page_size — allows page_size=10000
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all users.

    VULN: No org_id filter — returns ALL users across all orgs.
    VULN: No max page_size — allows bulk data harvesting.
    VULN: Sequential integer IDs enable enumeration.
    """
    offset = (page - 1) * page_size
    users = db.query(User).offset(offset).limit(page_size).all()
    return users


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get user by ID.

    VULN: BOLA — any authenticated user can access any user's profile.
    VULN: Returns ssn_last4, internal_notes, password_hash.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update user profile.

    VULN: BOLA — no ownership check, any user can update any user.
    VULN: Mass assignment — accepts 'role' field from client.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # VULN: Applies all fields from request including 'role'
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete user.

    VULN: Broken function-level authorization — no admin role check.
    Any authenticated user can delete any user.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": f"User {user_id} deleted"}


# ── Organizations ──────────────────────────────────────────────

@router.get("/orgs", response_model=list[OrgResponse])
def list_orgs(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all organizations."""
    return db.query(Organization).all()


@router.post("/orgs", response_model=OrgResponse)
def create_org(
    org: OrgCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new organization."""
    new_org = Organization(
        name=org.name,
        slug=org.slug,
        owner_id=current_user["user_id"],
    )
    db.add(new_org)
    db.commit()
    db.refresh(new_org)

    # Auto-add creator as owner
    membership = OrgMembership(
        user_id=current_user["user_id"],
        org_id=new_org.id,
        role="owner",
    )
    db.add(membership)
    db.commit()
    return new_org


@router.get("/orgs/{org_id}", response_model=OrgResponse)
def get_org(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get organization details.

    VULN: BOLA — no membership check.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.get("/orgs/{org_id}/members", response_model=list[MembershipResponse])
def list_members(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List organization members.

    VULN: BOLA — any user can list any org's members.
    """
    members = db.query(OrgMembership).filter(OrgMembership.org_id == org_id).all()
    return members


@router.post("/orgs/{org_id}/invite")
def invite_member(
    org_id: int,
    invite_req: InviteRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Invite a user to an organization."""
    token = secrets.token_urlsafe(32)
    invite = Invite(
        org_id=org_id,
        email=invite_req.email,
        role=invite_req.role,
        token=token,
    )
    db.add(invite)
    db.commit()
    return {"invite_token": token, "email": invite_req.email}


# ── API Tokens ─────────────────────────────────────────────────

@router.post("/orgs/{org_id}/api-tokens", response_model=APITokenResponse)
def create_api_token(
    org_id: int,
    token_req: APITokenCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create an API token.

    VULN: Returns plaintext token in response AND stores it in DB.
    """
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    api_token = APIToken(
        user_id=current_user["user_id"],
        org_id=org_id,
        token_hash=token_hash,
        token_plain=raw_token,  # VULN: Stored in plaintext
        name=token_req.name,
        scopes=token_req.scopes,
    )
    db.add(api_token)
    db.commit()
    db.refresh(api_token)
    return api_token


@router.get("/orgs/{org_id}/api-tokens", response_model=list[APITokenResponse])
def list_api_tokens(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List API tokens for an organization.

    VULN: Returns plaintext token values.
    VULN: BOLA — no org membership check.
    """
    tokens = db.query(APIToken).filter(APIToken.org_id == org_id).all()
    return tokens
