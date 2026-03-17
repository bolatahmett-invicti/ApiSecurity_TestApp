import json
import time
import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional

import jwt

from database import get_db
from models import Report
from schemas import ReportCreate, ReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key")


def get_current_user(authorization: Optional[str] = Header(None)):
    """Extract user from JWT token."""
    if not authorization:
        return {"user_id": 1, "org_id": 1}  # Default for testing
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.exceptions.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/generate", response_model=ReportResponse)
def generate_report(
    report: ReportCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a new report.

    VULN: Resource Amplification — No rate limiting on report generation.
    Any user can trigger unlimited expensive report generation requests.
    The time.sleep(2) simulates an expensive database/file operation.

    VULN: Cross-Org Data Access — If parameters contain "include_all_orgs": true,
    the report will include data from ALL organizations, not just the user's org.
    No server-side validation prevents this parameter from being set.
    """
    # VULN: No rate limiting — attacker can queue thousands of expensive reports
    # VULN: No validation on date ranges — attacker can request years of data

    # Simulate expensive report generation
    time.sleep(2)

    # VULN: include_all_orgs parameter is accepted without authorization check
    # A regular user can set include_all_orgs=true to access cross-org data
    parameters_json = json.dumps(report.parameters)

    # VULN: If include_all_orgs is set, the report silently includes all orgs' data
    include_all = report.parameters.get("include_all_orgs", False)

    # Simulate file path generation
    # VULN: file_path is derived from user-controllable report_type without sanitization
    file_path = f"/reports/{current_user.get('org_id', 1)}/{report.report_type}_report.json"

    new_report = Report(
        org_id=current_user.get("org_id", 1),
        requested_by=current_user.get("user_id", 1),
        report_type=report.report_type,
        status="ready",
        parameters_json=parameters_json,
        file_path=file_path,
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return new_report


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get report status by ID.

    VULN: BOLA (Broken Object Level Authorization) — No org ownership check.
    Any authenticated user can access any report by ID, regardless of which
    organization the report belongs to. Should verify report.org_id == current_user.org_id.
    """
    # VULN: No org_id check — any user can view any report from any org
    report = db.query(Report).filter(Report.id == report_id).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # VULN: Missing authorization check — should be:
    # if report.org_id != current_user.get("org_id"):
    #     raise HTTPException(status_code=403, detail="Not authorized")

    return report


@router.get("/", response_model=list[ReportResponse])
def list_reports(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    List all reports.

    VULN: Cross-Org Data Leak — Returns ALL reports from ALL organizations.
    No org_id filter is applied to the query. Should filter by current user's org_id.
    """
    # VULN: No org_id filter — returns reports from ALL organizations
    # Should be: db.query(Report).filter(Report.org_id == current_user.get("org_id")).all()
    reports = db.query(Report).all()

    return reports


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Download a report file.

    VULN: Path Traversal — The file_path stored in the report record is used
    without sanitization. If an attacker can control the file_path (e.g., via
    report_type injection like "../../etc/passwd"), they could read arbitrary
    files from the filesystem.

    VULN: BOLA — No org ownership check on download either.
    """
    # VULN: No org_id check — any user can download any report
    report = db.query(Report).filter(Report.id == report_id).first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # VULN: Missing authorization check
    # if report.org_id != current_user.get("org_id"):
    #     raise HTTPException(status_code=403, detail="Not authorized")

    # VULN: Path traversal — file_path is used directly without sanitization
    # If file_path contains "../" sequences, it could read arbitrary files
    # e.g., file_path = "/reports/1/../../etc/passwd"
    file_path = report.file_path

    # VULN: No path sanitization — should use os.path.realpath() and verify
    # the resolved path is within the allowed reports directory
    # safe_base = "/reports"
    # resolved = os.path.realpath(file_path)
    # if not resolved.startswith(safe_base):
    #     raise HTTPException(status_code=403, detail="Invalid path")

    # Simulate report content (in production, this would read from file_path)
    simulated_content = {
        "report_id": report.id,
        "report_type": report.report_type,
        "org_id": report.org_id,
        "requested_by": report.requested_by,
        "status": report.status,
        "parameters": json.loads(report.parameters_json) if report.parameters_json else {},
        "file_path": file_path,  # VULN: Exposes internal file path to user
        "data": {
            "summary": f"Simulated {report.report_type} report data",
            "generated_at": str(report.created_at),
            "records_count": 150,
        },
    }

    return simulated_content
