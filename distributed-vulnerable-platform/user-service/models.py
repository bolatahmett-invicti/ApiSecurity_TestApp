"""User service SQLAlchemy models."""

import sys
sys.path.insert(0, "/app")

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from shared.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    auth_user_id = Column(Integer, nullable=False, unique=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), default="")
    phone = Column(String(50), default="")
    ssn_last4 = Column(String(4), default="")  # VULN: Sensitive PII stored
    internal_notes = Column(Text, default="")  # VULN: Internal data
    password_hash = Column(String(255), default="")  # VULN: Duplicated from auth, exposed in responses
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    owner_id = Column(Integer, nullable=False)
    plan_type = Column(String(50), default="free")  # free, starter, pro, enterprise
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OrgMembership(Base):
    __tablename__ = "org_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    role = Column(String(50), default="member")  # owner, admin, member, viewer
    invited_by = Column(Integer, nullable=True)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class APIToken(Base):
    __tablename__ = "api_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    token_hash = Column(String(255), nullable=False)
    token_plain = Column(String(255), nullable=False)  # VULN: Plaintext token stored
    name = Column(String(255), default="default")
    scopes = Column(String(500), default="read")
    last_used = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Invite(Base):
    __tablename__ = "invites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(50), default="member")
    token = Column(String(255), nullable=False, unique=True)
    accepted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
