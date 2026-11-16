"""Duplicate detection for recently submitted disaster reports."""

from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DisasterReport


MAX_DISTANCE_KM = 2.0
REPORT_WINDOW = timedelta(minutes=30)
MAX_MAGNITUDE_DIFFERENCE = 0.5


def distance_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    """Return the great-circle distance between two geographic coordinates."""
    latitude_delta = radians(latitude_b - latitude_a)
    longitude_delta = radians(longitude_b - longitude_a)
    haversine = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(latitude_a)) * cos(radians(latitude_b)) * sin(longitude_delta / 2) ** 2
    )
    return 2 * 6371.0 * asin(sqrt(haversine))


def find_duplicate_report(
    db: Session,
    *,
    disaster_type: str,
    latitude: float,
    longitude: float,
    magnitude: float,
) -> DisasterReport | None:
    """Find a matching report submitted within the duplicate-detection window."""
    cutoff = datetime.now(timezone.utc) - REPORT_WINDOW
    reports = db.scalars(
        select(DisasterReport).where(
            func.lower(DisasterReport.disaster_type) == disaster_type.strip().lower(),
            DisasterReport.created_at >= cutoff,
        )
    )
    for report in reports:
        if abs(report.magnitude - magnitude) > MAX_MAGNITUDE_DIFFERENCE:
            continue
        if distance_km(latitude, longitude, report.latitude, report.longitude) <= MAX_DISTANCE_KM:
            return report
    return None
