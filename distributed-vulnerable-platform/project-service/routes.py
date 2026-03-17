"""Project service routes.

INTENTIONAL VULNERABILITIES:
- BOLA: No org_id ownership check on project/task/comment access
- Cross-org data leak: GET /projects returns ALL projects without org_id filter
- Direct object reference: GET /tasks/{id} bypasses project/org hierarchy
- No authorization on delete: Any authenticated user can delete any project
"""

import sys
sys.path.insert(0, "/app")

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Comment, Project, Task
from schemas import (
    CommentCreate,
    CommentResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from shared.auth import get_current_user

router = APIRouter(tags=["projects"])


# -- Projects ----------------------------------------------------------------

@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all projects.

    VULN: No org_id filter — returns ALL projects across all organizations.
    Any authenticated user can see every org's projects.
    """
    # VULN: Should filter by current_user["org_id"] but doesn't
    return db.query(Project).all()


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new project."""
    new_project = Project(
        org_id=project.org_id,
        name=project.name,
        description=project.description,
        created_by=current_user["user_id"],
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get project by ID.

    VULN: BOLA — no check that current_user belongs to the project's org.
    Any authenticated user can access any project by ID.
    """
    # VULN: Should verify current_user["org_id"] == project.org_id
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    update: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a project.

    VULN: BOLA — no org ownership check. Any user can update any project.
    """
    # VULN: Should verify current_user["org_id"] == project.org_id
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a project.

    VULN: BOLA — no org ownership check. Any authenticated user can delete
    any project regardless of organization.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
    return {"message": f"Project {project_id} deleted"}


# -- Tasks -------------------------------------------------------------------

@router.get("/projects/{project_id}/tasks", response_model=list[TaskResponse])
def list_tasks(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List tasks for a project.

    VULN: No org ownership check on the parent project.
    """
    return db.query(Task).filter(Task.project_id == project_id).all()


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=201)
def create_task(
    project_id: int,
    task: TaskCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a task in a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    new_task = Task(
        project_id=project_id,
        title=task.title,
        description=task.description,
        assignee_id=task.assignee_id,
        priority=task.priority,
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get task by ID.

    VULN: BOLA — direct object access without project or org hierarchy check.
    Any authenticated user can access any task by guessing/enumerating its ID.
    """
    # VULN: Should verify task -> project -> org_id matches current_user["org_id"]
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    update: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update a task.

    VULN: BOLA — no project/org ownership check. Any user can update any task.
    """
    # VULN: Should verify task -> project -> org_id matches current_user["org_id"]
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


# -- Comments ----------------------------------------------------------------

@router.post("/tasks/{task_id}/comments", response_model=CommentResponse, status_code=201)
def create_comment(
    task_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a comment on a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    new_comment = Comment(
        task_id=task_id,
        author_id=current_user["user_id"],
        body=comment.body,
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment


@router.get("/tasks/{task_id}/comments", response_model=list[CommentResponse])
def list_comments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List comments on a task.

    VULN: No project/org ownership check. Any user can read comments on any task.
    """
    return db.query(Comment).filter(Comment.task_id == task_id).all()
