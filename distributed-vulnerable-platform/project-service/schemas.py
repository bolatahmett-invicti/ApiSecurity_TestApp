"""Project service Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    org_id: int


class ProjectResponse(BaseModel):
    id: int
    org_id: int
    name: str
    description: str
    status: str
    created_by: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    assignee_id: Optional[int] = None
    priority: Optional[str] = "medium"


class TaskResponse(BaseModel):
    id: int
    project_id: int
    title: str
    description: str
    assignee_id: Optional[int]
    status: str
    priority: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None


class CommentCreate(BaseModel):
    body: str


class CommentResponse(BaseModel):
    id: int
    task_id: int
    author_id: int
    body: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
