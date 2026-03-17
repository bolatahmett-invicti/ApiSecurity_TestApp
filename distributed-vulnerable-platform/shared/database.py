"""Shared SQLAlchemy database setup."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def get_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def get_session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
