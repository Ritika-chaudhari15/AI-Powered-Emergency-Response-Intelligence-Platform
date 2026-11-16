from types import SimpleNamespace

from app.services.volunteer_assignment_service import _severity


def test_assignment_severity_bands():
    assert _severity(30) == "Low"
    assert _severity(31) == "Moderate"
    assert _severity(71) == "High"
