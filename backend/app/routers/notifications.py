from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Notification, User
from app.schemas import NotificationResponse
from app.services.translation_service import translate


router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


def _localized_notification(notification: Notification, request: Request, db: Session) -> dict:
    """Translate generated notification text for the locale selected in the UI."""
    payload = NotificationResponse.model_validate(notification).model_dump()
    locale = request.state.locale
    if locale == "en":
        return payload
    try:
        # Stable IDs make each generated notification translation cacheable and avoid
        # re-running IndicTrans2 on every realtime poll.
        payload["title"] = translate(db, f"notification.{notification.id}.title", notification.title, locale)
        payload["message"] = translate(db, f"notification.{notification.id}.message", notification.message, locale)
    except Exception:
        # Alerts must remain available if the local translator has not been installed.
        pass
    return payload


@router.get("", response_model=list[NotificationResponse])
def list_notifications(request: Request, unread_only: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc())
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    return [_localized_notification(notification, request, db) for notification in db.scalars(query)]


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(notification_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return _localized_notification(notification, request, db)
