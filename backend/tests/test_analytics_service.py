from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.analytics_service import build_trend_analytics, priority_item


def report(**overrides):
    data = {"id": 1, "disaster_type": "flood", "magnitude": 6.0, "affected_population": 1000, "weather_score": 0.5, "predicted_impact_score": None, "created_at": datetime.now(timezone.utc)}
    data.update(overrides)
    return SimpleNamespace(**data)


def test_trends_and_priority_queue_are_explainable():
    result = build_trend_analytics([report(predicted_impact_score=80.0), report(id=2, disaster_type="earthquake", predicted_impact_score=40.0)], 30)
    assert result["total_reports"] == 2
    assert result["average_impact_score"] == 60.0
    assert priority_item(report(predicted_impact_score=None), "reported")["impact_score_source"] == "estimated"
