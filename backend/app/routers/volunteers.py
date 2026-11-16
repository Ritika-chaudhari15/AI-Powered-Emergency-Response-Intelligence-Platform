from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import VolunteerCreate, VolunteerResponse, VolunteerStatusUpdate
from app.services import volunteer_service
from app.services.operations_service import ensure_demo_response_roster

router = APIRouter(prefix="/api/v1/volunteers", tags=["Volunteer management"])


@router.post("", response_model=VolunteerResponse, status_code=status.HTTP_201_CREATED)
def register_volunteer(payload: VolunteerCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return volunteer_service.create_volunteer(db, user.id, payload)


@router.get("", response_model=list[VolunteerResponse])
def list_volunteers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ensure_demo_response_roster(db, user.id)
    return volunteer_service.list_volunteers(db, user.id)


@router.get("/{volunteer_id}", response_model=VolunteerResponse)
def get_volunteer(volunteer_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    volunteer = volunteer_service.get_volunteer(db, user.id, volunteer_id)
    if volunteer is None:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    return volunteer


@router.patch("/{volunteer_id}/status", response_model=VolunteerResponse)
def update_status(volunteer_id: int, payload: VolunteerStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    volunteer = volunteer_service.update_availability(db, user.id, volunteer_id, payload.availability)
    if volunteer is None:
        raise HTTPException(status_code=404, detail="Volunteer not found")
    return volunteer
