"""User service database setup."""

import os
import sys

sys.path.insert(0, "/app")

from shared.database import Base, get_engine, get_session_factory

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./user.db")

engine = get_engine(DATABASE_URL)
SessionLocal = get_session_factory(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from models import User, Organization, OrgMembership, APIToken, Invite  # noqa: F401
    Base.metadata.create_all(bind=engine)
