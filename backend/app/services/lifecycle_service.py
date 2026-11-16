from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DisasterLifecycleEvent
from app.services import live_update_service, notification_service


VALID_TRANSITIONS = {
    "reported": {"assessed"},
    "assessed": {"allocated", "partially_allocated"},
    # A later allocation attempt may fill the outstanding shortage.
    "partially_allocated": {"allocated", "dispatched"},
    "allocated": {"dispatched"},
    "dispatched": {"completed"},
    "completed": set(),
}


def current_status(db: Session, report_id: int) -> str:
    event = db.scalar(
        select(DisasterLifecycleEvent)
        .where(DisasterLifecycleEvent.report_id == report_id)
        .order_by(DisasterLifecycleEvent.id.desc())
    )
    return event.status if event else "reported"


def add_event(
    db: Session, report_id: int, user_id: int, status: str, note: str | None = None,
    estimated_arrival_at: datetime | None = None, validate_transition: bool = True,
) -> DisasterLifecycleEvent:
    previous = current_status(db, report_id)
    if validate_transition and status not in VALID_TRANSITIONS.get(previous, set()):
        raise ValueError(f"Cannot change disaster status from {previous} to {status}")
    event = DisasterLifecycleEvent(
        report_id=report_id, user_id=user_id, status=status, note=note, estimated_arrival_at=estimated_arrival_at,
    )
    db.add(event)
    db.flush()
    payload = {"report_id": report_id, "status": status, "note": note, "estimated_arrival_at": estimated_arrival_at}
    live_update_service.publish(user_id, "lifecycle", payload)
    notification_service.create_notification(
        db, user_id, "lifecycle", f"Disaster {status.title()}",
        note or f"Disaster report #{report_id} is now {status}.", report_id,
    )
    return event
