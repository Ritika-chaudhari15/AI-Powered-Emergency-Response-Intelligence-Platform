from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.knowledge_base_service import default_strategy, matching_entries


def test_matching_entry_beats_general_and_fallback_is_available():
    report = SimpleNamespace(id=1, disaster_type="flood", magnitude=7.0, affected_population=1000, weather_score=.5, predicted_impact_score=75.0, created_at=datetime.now(timezone.utc))
    entry = SimpleNamespace(id=1, title="Flood response", entry_type="best_practice", content="Deploy water and medical teams.", disaster_type="flood", severity="High", tags="water", created_at=report.created_at, updated_at=report.created_at)
    assert matching_entries(report, [entry], 5)[0]["knowledge_entry"]["id"] == 1
    assert "evacuation" in default_strategy(report).lower()
