from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    org_id = Column(Integer, nullable=True)
    type = Column(String(100), nullable=False)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    channel = Column(String(50), nullable=False, default="in_app")  # email | webhook | in_app
    status = Column(String(50), nullable=False, default="pending")  # pending | sent | failed
    metadata_json = Column(Text, nullable=True)  # Stores arbitrary JSON
    webhook_response = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    channel = Column(String(50), nullable=False)
    enabled = Column(Boolean, default=True)
    webhook_url = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
