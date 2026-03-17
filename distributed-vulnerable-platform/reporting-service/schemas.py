from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ReportCreate(BaseModel):
    report_type: str  # usage, billing, security, activity
    parameters: dict  # Accepts arbitrary params like date_from, date_to, include_all_orgs


class ReportResponse(BaseModel):
    id: int
    org_id: int
    requested_by: int
    report_type: str
    status: str
    parameters_json: Optional[str] = None
    file_path: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReportDownload(BaseModel):
    report_id: int
    file_path: str
    content_type: str = "application/json"
