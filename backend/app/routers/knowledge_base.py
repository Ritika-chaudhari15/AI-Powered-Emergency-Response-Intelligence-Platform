from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import DisasterKnowledgeEntry, DisasterReport, KnowledgeRecommendationFeedback, User
from app.schemas import DisasterRecommendationsResponse, KnowledgeEntryCreate, KnowledgeEntryResponse, RecommendationFeedbackCreate, RecommendationFeedbackResponse
from app.services import knowledge_base_service
from app.services.analytics_service import impact_for, severity_for_score

router = APIRouter(prefix="/api/v1", tags=["Disaster knowledge base"])

def _report(db, report_id, user_id):
    report = db.get(DisasterReport, report_id)
    if not report or report.user_id != user_id: raise HTTPException(404, "Disaster report not found")
    return report

@router.post("/knowledge-base", response_model=KnowledgeEntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(payload: KnowledgeEntryCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = DisasterKnowledgeEntry(user_id=user.id, title=payload.title.strip(), entry_type=payload.entry_type, content=payload.content.strip(), disaster_type=payload.disaster_type.strip().lower() if payload.disaster_type else None, severity=payload.severity, tags=','.join(sorted({tag.strip() for tag in payload.tags if tag.strip()})) or None)
    db.add(entry); db.commit(); db.refresh(entry)
    return knowledge_base_service.entry_response(entry)

@router.get("/knowledge-base", response_model=list[KnowledgeEntryResponse])
def list_entries(disaster_type: str | None = None, entry_type: str | None = Query(None, pattern="^(best_practice|past_response|lesson_learned)$"), severity: str | None = Query(None, pattern="^(Low|Moderate|High)$"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(DisasterKnowledgeEntry).where(DisasterKnowledgeEntry.user_id == user.id).order_by(DisasterKnowledgeEntry.id.desc())
    if disaster_type: query = query.where(DisasterKnowledgeEntry.disaster_type.ilike(disaster_type.strip()))
    if entry_type: query = query.where(DisasterKnowledgeEntry.entry_type == entry_type)
    if severity: query = query.where(DisasterKnowledgeEntry.severity == severity)
    return [knowledge_base_service.entry_response(entry) for entry in db.scalars(query)]

@router.get("/disaster-reports/{report_id}/recommendations", response_model=DisasterRecommendationsResponse)
def recommendations(report_id: int, limit: int = Query(5, ge=1, le=20), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = _report(db, report_id, user.id); entries = list(db.scalars(select(DisasterKnowledgeEntry).where(DisasterKnowledgeEntry.user_id == user.id))); score = impact_for(report)[0]; strategies = knowledge_base_service.matching_entries(report, entries, limit)
    return {"report_id": report.id, "disaster_type": report.disaster_type, "severity": severity_for_score(score), "impact_score": score, "recommended_strategy": strategies[0]["knowledge_entry"]["content"] if strategies else knowledge_base_service.default_strategy(report), "recommendation_source": "knowledge_base" if strategies else "default_playbook", "recommended_strategies": strategies, "similar_disasters": knowledge_base_service.similar_reports(report, list(db.scalars(select(DisasterReport).where(DisasterReport.user_id == user.id))), limit)}

@router.post("/disaster-reports/{report_id}/recommendations/{knowledge_entry_id}/feedback", response_model=RecommendationFeedbackResponse, status_code=status.HTTP_201_CREATED)
def feedback(report_id: int, knowledge_entry_id: int, payload: RecommendationFeedbackCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _report(db, report_id, user.id); entry = db.get(DisasterKnowledgeEntry, knowledge_entry_id)
    if not entry or entry.user_id != user.id: raise HTTPException(404, "Knowledge entry not found")
    result = KnowledgeRecommendationFeedback(user_id=user.id, report_id=report_id, knowledge_entry_id=knowledge_entry_id, rating=payload.rating, comment=payload.comment.strip() if payload.comment else None)
    db.add(result); db.commit(); db.refresh(result); return result
