from sqlalchemy.orm import Session

from app.models import Notification
from app.services import live_update_service


def create_notification(
    db: Session, user_id: int, notification_type: str, title: str, message: str, report_id: int | None = None
) -> Notification:
    notification = Notification(
        user_id=user_id,
        report_id=report_id,
        notification_type=notification_type,
        title=title,
        message=message,
    )
    db.add(notification)
    db.flush()
    live_update_service.publish(user_id, "notification", {
        "id": notification.id, "report_id": report_id, "type": notification_type,
        "title": title, "message": message, "is_read": False,
    })
    return notification
