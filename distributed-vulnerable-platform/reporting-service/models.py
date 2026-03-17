from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, nullable=False)
    requested_by = Column(Integer, nullable=False)
    report_type = Column(String(50), nullable=False)  # usage, billing, security, activity
    status = Column(String(50), nullable=False, default="queued")  # queued, generating, ready, failed
    parameters_json = Column(Text, nullable=True)  # Stores JSON params
    file_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
