"""User service Pydantic schemas."""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserResponse(BaseModel):
    """VULN: Returns sensitive fields — ssn_last4, internal_notes, password_hash."""
    id: int
    auth_user_id: int
    email: str
    full_name: str
    phone: str
    ssn_last4: str          # VULN: PII exposed
    internal_notes: str     # VULN: Internal data exposed
    password_hash: str      # VULN: Hash exposed
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None  # VULN: mass assignment — role update from client


class OrgCreate(BaseModel):
    name: str
    slug: str


class OrgResponse(BaseModel):
    id: int
    name: str
    slug: str
    owner_id: int
    plan_type: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MembershipResponse(BaseModel):
    id: int
    user_id: int
    org_id: int
    role: str
    joined_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InviteRequest(BaseModel):
    email: str
    role: str = "member"


class APITokenCreate(BaseModel):
    name: str = "default"
    scopes: str = "read"


class APITokenResponse(BaseModel):
    """VULN: Returns plaintext token."""
    id: int
    name: str
    scopes: str
    token_plain: str    # VULN: Plaintext API token in response
    token_hash: str     # VULN: Hash also exposed
    last_used: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
