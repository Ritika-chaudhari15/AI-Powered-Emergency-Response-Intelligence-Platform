from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import DisasterReport, User
from app.schemas import DisasterPriorityQueueResponse, DisasterTrendAnalyticsResponse
from app.services import analytics_service, lifecycle_service

router = APIRouter(prefix="/api/v1/analytics", tags=["Decision analytics"])

@router.get("/trends", response_model=DisasterTrendAnalyticsResponse)
def get_disaster_trends(days: int = Query(365, ge=1, le=3650), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return analytics_service.build_trend_analytics(list(db.scalars(select(DisasterReport).where(DisasterReport.user_id == user.id))), days)

@router.get("/priority-queue", response_model=DisasterPriorityQueueResponse)
def get_priority_queue(include_completed: bool = False, limit: int = Query(50, ge=1, le=200), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = []
    for report in db.scalars(select(DisasterReport).where(DisasterReport.user_id == user.id)):
        state = lifecycle_service.current_status(db, report.id)
        if include_completed or state != "completed": items.append(analytics_service.priority_item(report, state))
    items.sort(key=lambda item: (-item["priority_score"], -item["impact_score"], item["created_at"]))
    total_reports = len(items)
    for rank, item in enumerate(items[:limit], 1): item["rank"] = rank
    return {"total_reports": total_reports, "items": items[:limit]}
