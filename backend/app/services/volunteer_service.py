from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Volunteer
from app.schemas import VolunteerCreate


def create_volunteer(db: Session, user_id: int, payload: VolunteerCreate) -> Volunteer:
    volunteer = Volunteer(user_id=user_id, **payload.model_dump(), availability="Available")
    db.add(volunteer)
    db.commit()
    db.refresh(volunteer)
    return volunteer


def list_volunteers(db: Session, user_id: int) -> list[Volunteer]:
    return list(db.scalars(select(Volunteer).where(Volunteer.user_id == user_id).order_by(Volunteer.id.desc())))


def get_volunteer(db: Session, user_id: int, volunteer_id: int) -> Volunteer | None:
    return db.scalar(select(Volunteer).where(Volunteer.id == volunteer_id, Volunteer.user_id == user_id))


def update_availability(db: Session, user_id: int, volunteer_id: int, availability: str) -> Volunteer | None:
    volunteer = get_volunteer(db, user_id, volunteer_id)
    if volunteer is None:
        return None
    volunteer.availability = availability
    db.commit()
    db.refresh(volunteer)
    return volunteer
