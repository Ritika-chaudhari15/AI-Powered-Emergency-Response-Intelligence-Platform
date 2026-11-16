from math import atan2, ceil, cos, radians, sin, sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Volunteer, VolunteerAssignment


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * atan2(sqrt(a), sqrt(1 - a))


def _severity(impact_score: float) -> str:
    return "Low" if impact_score <= 30 else "Moderate" if impact_score <= 70 else "High"


def assignment_response(db: Session, report) -> dict:
    assignments = list(db.scalars(select(VolunteerAssignment).where(VolunteerAssignment.report_id == report.id).order_by(VolunteerAssignment.id)))
    assigned = []
    for assignment in assignments:
        volunteer = db.get(Volunteer, assignment.volunteer_id)
        if volunteer:
            assigned.append({"volunteer_id": volunteer.id, "name": volunteer.name, "skill": volunteer.skill, "status": assignment.status})
    impact_score = float(report.predicted_impact_score or 0.0)
    return {"impact_score": impact_score, "severity": _severity(impact_score),
            "available_before_assignment": assignments[0].available_before_assignment if assignments else 0,
            "assigned_count": len(assigned), "assigned_volunteers": assigned}


def assign_volunteers(db: Session, report) -> dict:
    # Prediction may be retried; preserve the original assignment instead of consuming more volunteers.
    existing = db.scalar(select(VolunteerAssignment.id).where(VolunteerAssignment.report_id == report.id))
    if existing:
        return assignment_response(db, report)
    volunteers = list(db.scalars(select(Volunteer).where(Volunteer.user_id == report.user_id, Volunteer.availability == "Available")))
    impact_score = float(report.predicted_impact_score or 0.0)
    if not volunteers:
        return {"impact_score": impact_score, "severity": _severity(impact_score), "available_before_assignment": 0, "assigned_count": 0, "assigned_volunteers": []}
    ranked = sorted(((volunteer, _distance_km(report.latitude, report.longitude, volunteer.latitude, volunteer.longitude)) for volunteer in volunteers), key=lambda item: item[1])
    count = max(1, ceil(len(ranked) * (0.25 if impact_score <= 30 else 0.50))) if impact_score <= 70 else len(ranked)
    for volunteer, _ in ranked[:count]:
        db.add(VolunteerAssignment(volunteer_id=volunteer.id, report_id=report.id, available_before_assignment=len(ranked)))
        volunteer.availability = "Busy"
    db.commit()
    return assignment_response(db, report)
