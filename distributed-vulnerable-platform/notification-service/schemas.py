from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    org_id: Optional[int] = None
    type: str
    title: str
    body: str
    channel: str
    status: str
    metadata_json: Optional[str] = None
    webhook_response: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SendNotificationRequest(BaseModel):
    user_id: Optional[int] = None
    org_id: Optional[int] = None
    target: str  # "user" | "org" | "all_users"
    title: str
    body: str
    channel: str = "in_app"


class BroadcastRequest(BaseModel):
    title: str
    body: str
    channel: str = "in_app"


class PreferenceUpdate(BaseModel):
    channel: str
    enabled: bool
    webhook_url: Optional[str] = None


class PreferenceResponse(BaseModel):
    id: int
    user_id: int
    channel: str
    enabled: bool
    webhook_url: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InternalEventRequest(BaseModel):
    event_type: str
    source_service: str
    data: dict
