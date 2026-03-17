"""Project service SQLAlchemy models."""

import sys
sys.path.insert(0, "/app")

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from shared.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(String(50), default="active")  # active | archived
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    assignee_id = Column(Integer, nullable=True)
    status = Column(String(50), default="todo")  # todo | in_progress | review | done
    priority = Column(String(50), default="medium")  # low | medium | high | urgent
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    author_id = Column(Integer, nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
