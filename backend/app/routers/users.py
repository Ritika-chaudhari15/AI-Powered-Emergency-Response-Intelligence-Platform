from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import UserResponse, UserUpdate

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def read_profile(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserResponse)
def update_profile(payload: UserUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.full_name = payload.full_name.strip()
    db.commit()
    db.refresh(user)
    return user
