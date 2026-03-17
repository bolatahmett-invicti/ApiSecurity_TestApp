import json
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional

from database import get_db
from models import Notification, NotificationPreference
from schemas import (
    NotificationResponse,
    SendNotificationRequest,
    BroadcastRequest,
    PreferenceUpdate,
    PreferenceResponse,
    InternalEventRequest,
)

router = APIRouter()


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    """Extract user_id from JWT token (simplified for demo)."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    import jwt
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("user_id", payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


# ---------------------------------------------------------------------------
# GET /notifications — list user's notifications (works correctly)
# ---------------------------------------------------------------------------
@router.get("/notifications", response_model=List[NotificationResponse])
def list_notifications(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user_id = get_current_user_id(authorization)
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return notifications


# ---------------------------------------------------------------------------
# POST /notifications/send — send notification
#
# VULN: Resource Amplification — accepts target="all_users" which fans out
#       to ALL users in the system. A single request can generate thousands
#       of notifications with no rate limiting or authorization check on the
#       target type.
# VULN: SSRF-like — when channel="webhook", the service makes an HTTP
#       callback to the user-supplied webhook_url without any URL validation
#       or allowlist, enabling Server-Side Request Forgery.
# ---------------------------------------------------------------------------
@router.post("/notifications/send")
def send_notification(
    request: SendNotificationRequest,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user_id = get_current_user_id(authorization)

    target_user_ids = []

    if request.target == "user":
        # Send to a specific user
        target_user_ids = [request.user_id or user_id]

    elif request.target == "org":
        # Send to all users in an org — simplified: fake a list
        if not request.org_id:
            raise HTTPException(status_code=400, detail="org_id required for org target")
        # VULN: No check that the sender belongs to the org
        rows = db.execute(
            text("SELECT DISTINCT user_id FROM notifications WHERE org_id = :org_id"),
            {"org_id": request.org_id},
        ).fetchall()
        target_user_ids = [row[0] for row in rows] if rows else [request.org_id]

    elif request.target == "all_users":
        # VULN: Resource Amplification — fans out to ALL known users
        # No authorization check on whether the caller can broadcast
        rows = db.execute(
            text("SELECT DISTINCT user_id FROM notifications")
        ).fetchall()
        target_user_ids = [row[0] for row in rows]
        if not target_user_ids:
            target_user_ids = list(range(1, 101))  # Fallback: generate for 100 users

    created = []
    for tid in target_user_ids:
        notif = Notification(
            user_id=tid,
            org_id=request.org_id,
            type="direct",
            title=request.title,
            body=request.body,
            channel=request.channel,
            status="pending",
        )
        db.add(notif)
        db.flush()

        # VULN: SSRF — if channel is webhook, call the user-controlled URL
        if request.channel == "webhook":
            pref = (
                db.query(NotificationPreference)
                .filter(
                    NotificationPreference.user_id == tid,
                    NotificationPreference.channel == "webhook",
                )
                .first()
            )
            if pref and pref.webhook_url:
                try:
                    # VULN: No URL validation — can hit internal services,
                    # cloud metadata endpoints, etc.
                    resp = httpx.post(
                        pref.webhook_url,
                        json={"title": request.title, "body": request.body},
                        timeout=5.0,
                    )
                    notif.webhook_response = resp.text[:2000]
                    notif.status = "sent"
                except Exception as e:
                    notif.webhook_response = str(e)
                    notif.status = "failed"
        else:
            notif.status = "sent"

        created.append(notif.id)

    db.commit()
    return {"sent": len(created), "notification_ids": created}


# ---------------------------------------------------------------------------
# POST /notifications/broadcast — broadcast to all users
#
# VULN: Broken Function-Level Authorization — checks the X-Admin-Role
#       header instead of the JWT role claim. Any user can set this header
#       to "true" and bypass the authorization check entirely.
# ---------------------------------------------------------------------------
@router.post("/notifications/broadcast")
def broadcast_notification(
    request: BroadcastRequest,
    authorization: Optional[str] = Header(None),
    x_admin_role: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    # VULN: Checks a client-controlled header instead of JWT role
    if x_admin_role != "true":
        raise HTTPException(status_code=403, detail="Admin role required")

    # Still decode token to get a user_id, but role is NOT checked from JWT
    sender_id = get_current_user_id(authorization)

    rows = db.execute(text("SELECT DISTINCT user_id FROM notifications")).fetchall()
    target_user_ids = [row[0] for row in rows] if rows else list(range(1, 51))

    created = []
    for tid in target_user_ids:
        notif = Notification(
            user_id=tid,
            org_id=None,
            type="broadcast",
            title=request.title,
            body=request.body,
            channel=request.channel,
            status="sent",
        )
        db.add(notif)
        db.flush()
        created.append(notif.id)

    db.commit()
    return {"broadcast_to": len(created), "notification_ids": created}


# ---------------------------------------------------------------------------
# PUT /notifications/preferences — update notification preferences
# ---------------------------------------------------------------------------
@router.put("/notifications/preferences", response_model=PreferenceResponse)
def update_preferences(
    request: PreferenceUpdate,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    user_id = get_current_user_id(authorization)

    pref = (
        db.query(NotificationPreference)
        .filter(
            NotificationPreference.user_id == user_id,
            NotificationPreference.channel == request.channel,
        )
        .first()
    )

    if pref:
        pref.enabled = request.enabled
        pref.webhook_url = request.webhook_url
    else:
        pref = NotificationPreference(
            user_id=user_id,
            channel=request.channel,
            enabled=request.enabled,
            webhook_url=request.webhook_url,
        )
        db.add(pref)

    db.commit()
    db.refresh(pref)
    return pref


# ---------------------------------------------------------------------------
# POST /internal/events — receive internal service events
#
# VULN: Event Injection — no authentication whatsoever. This endpoint does
#       NOT require a JWT token or any form of auth. Anyone who can reach
#       this endpoint can inject arbitrary events.
# VULN: Cross-Service Trust — the source_service field is trusted blindly.
#       An attacker can impersonate any internal service (e.g., "payment-service",
#       "identity-service") and inject fake events that generate notifications.
# ---------------------------------------------------------------------------
@router.post("/internal/events")
def receive_internal_event(
    request: InternalEventRequest,
    db: Session = Depends(get_db),
):
    # VULN: No authentication — no JWT, no API key, no mTLS check
    # VULN: Trusts source_service field from the request body blindly

    user_id = request.data.get("user_id", 0)
    org_id = request.data.get("org_id")

    notif = Notification(
        user_id=user_id,
        org_id=org_id,
        type=request.event_type,
        title=f"Event from {request.source_service}: {request.event_type}",
        body=json.dumps(request.data),
        channel="in_app",
        status="sent",
        metadata_json=json.dumps({
            "source_service": request.source_service,
            "event_type": request.event_type,
            "raw_data": request.data,
        }),
    )
    db.add(notif)
    db.commit()

    return {"status": "processed", "notification_id": notif.id}
