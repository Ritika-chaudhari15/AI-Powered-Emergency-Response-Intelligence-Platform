import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "postgresql://postgres:Aashrith@localhost:5432/disaster_response"
os.environ["JWT_SECRET_KEY"] = "d47e3ab6e0e8a17d61f7dbb5002a6fe9a7c8a97aff3d91b9da25d0afd12d38dd"

# Put backend/ before site-packages. This prevents a third-party package named
# "app" from being imported instead of this project's backend/app package.
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

test_engine = create_engine("sqlite:///./test_user_api.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_module(module):
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)


def test_complete_user_lifecycle():
    register = client.post("/api/v1/auth/register", json={"email": "responder@example.com", "full_name": "Asha Responder", "password": "safe-password-123"})
    assert register.status_code == 201
    assert register.json()["email"] == "responder@example.com"

    duplicate = client.post("/api/v1/auth/register", json={"email": "responder@example.com", "full_name": "Duplicate User", "password": "safe-password-123"})
    assert duplicate.status_code == 409

    bad_login = client.post("/api/v1/auth/login", json={"email": "responder@example.com", "password": "wrong-password"})
    assert bad_login.status_code == 401

    login = client.post("/api/v1/auth/login", json={"email": "responder@example.com", "password": "safe-password-123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/users/me", headers=headers).status_code == 200
    updated = client.patch("/api/v1/users/me", headers=headers, json={"full_name": "Asha Relief Coordinator"})
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Asha Relief Coordinator"

    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401


def test_api_localizes_known_messages_and_advertises_locales():
    from app import main
    from app.services import translation_service

    class FakeIndicTrans:
        def __init__(self):
            self.calls = 0

        def translate_batch(self, texts, locale):
            self.calls += 1
            return [f"[{locale}] {text}" for text in texts]

    engine = FakeIndicTrans()
    original_session_factory = main.SessionLocal
    main.SessionLocal = TestingSessionLocal
    original_engine_factory = translation_service.get_local_indictrans_engine
    translation_service.get_local_indictrans_engine = lambda: engine
    try:
        bad_login = client.post(
            "/api/v1/auth/login",
            headers={"Accept-Language": "ta-IN, en;q=0.8"},
            json={"email": "missing@example.com", "password": "safe-password-123"},
        )
        assert bad_login.status_code == 401
        assert bad_login.headers["content-language"] == "ta"
        assert bad_login.json()["detail"] == "[ta] Incorrect email or password"
        assert engine.calls == 1

        repeated = client.post(
            "/api/v1/auth/login",
            headers={"Accept-Language": "ta-IN"},
            json={"email": "missing@example.com", "password": "safe-password-123"},
        )
        assert repeated.json()["detail"] == "[ta] Incorrect email or password"
        assert engine.calls == 1  # The RAM/DB cache prevents another model call.

        languages = client.get("/api/v1/i18n/languages?lang=te")
        assert languages.status_code == 200
        assert languages.headers["content-language"] == "te"
        assert len(languages.json()["supported"]) == 23  # English plus all 22 scheduled Indian languages.
        assert {"en", "ta", "hi", "te", "ml"}.issubset({item["code"] for item in languages.json()["supported"]})
    finally:
        main.SessionLocal = original_session_factory
        translation_service.get_local_indictrans_engine = original_engine_factory


def test_translation_bundle_returns_503_when_local_model_is_unavailable():
    from app import main
    from app.services import translation_service
    from app.services.indictrans_local_service import LocalIndicTransUnavailable

    class UnavailableLocalIndicTrans:
        def translate_batch(self, *_):
            raise LocalIndicTransUnavailable("Local IndicTrans2 model is missing.")

    original_session_factory = main.SessionLocal
    original_engine_factory = translation_service.get_local_indictrans_engine
    main.SessionLocal = TestingSessionLocal
    translation_service.get_local_indictrans_engine = lambda: UnavailableLocalIndicTrans()
    try:
        response = client.get("/api/v1/i18n/bundle", headers={"Accept-Language": "kn-IN"})
        assert response.status_code == 503
        assert "Local IndicTrans2 model is missing" in response.json()["detail"]
    finally:
        main.SessionLocal = original_session_factory
        translation_service.get_local_indictrans_engine = original_engine_factory


def test_indictrans_splits_cold_bundles_and_retries_cuda_oom_on_cpu():
    from app.services.indictrans_local_service import LocalIndicTransEngine

    engine = LocalIndicTransEngine.__new__(LocalIndicTransEngine)
    engine.batch_size = 2
    engine._load = lambda: None
    calls, retries = [], []

    def translate_chunk(texts, _target_language):
        calls.append(list(texts))
        if len(calls) == 1:
            raise RuntimeError("CUDA error: out of memory")
        return [f"translated:{text}" for text in texts]

    engine._translate_chunk = translate_chunk
    engine._retry_on_cpu_after_cuda_oom = lambda error: retries.append(str(error)) or True

    result = engine.translate_batch(["one", "two", "three"], "ta")

    assert result == ["translated:one", "translated:two", "translated:three"]
    assert calls == [["one", "two"], ["one", "two"], ["three"]]
    assert retries == ["CUDA error: out of memory"]


def test_impact_prediction_endpoint(monkeypatch):
    from app.services import model_service

    monkeypatch.setattr(model_service, "predict_impact", lambda _: 42.5)
    register = client.post("/api/v1/auth/register", json={"email": "analyst@example.com", "full_name": "Impact Analyst", "password": "safe-password-123"})
    assert register.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": "analyst@example.com", "password": "safe-password-123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post("/api/v1/predictions/impact", headers=headers, json={
        "Magnitude": 6.4,
        "WeatherScore": 3.1,
        "WindSpeed": 18.0,
        "PopulationDensity": 1200.0,
        "InfrastructureScore": 75.0
    })
    assert response.status_code == 200
    assert response.json() == {"predicted_impact_score": 42.5}


def test_disaster_type_is_normalized_to_a_canonical_code():
    from pydantic import ValidationError

    from app.schemas import DisasterReportCreate

    report = DisasterReportCreate(
        disaster_type=" Flood ", latitude=13.0, longitude=80.0, magnitude=6.0, affected_population=100,
    )
    assert report.disaster_type == "flood"

    try:
        DisasterReportCreate(
            disaster_type="வெள்ளம்", latitude=13.0, longitude=80.0, magnitude=6.0, affected_population=100,
        )
    except ValidationError:
        pass
    else:
        raise AssertionError("Translated labels must not be stored as disaster_type codes")


def test_resource_allocation_uses_next_nearest_warehouse(monkeypatch):
    import pandas as pd

    from app.services import allocation_service

    monkeypatch.setattr(allocation_service, "load_inventory", lambda: pd.DataFrame([
        {
            "WarehouseID": "WH001", "WarehouseName": "Nearest Warehouse", "State": "State A",
            "Latitude": 12.0, "Longitude": 77.0, "Resource": "Food Packets", "AvailableQuantity": 2_000_000,
        },
        {
            "WarehouseID": "WH002", "WarehouseName": "Next Nearest Warehouse", "State": "State B",
            "Latitude": 13.0, "Longitude": 77.0, "Resource": "Food Packets", "AvailableQuantity": 1_000_000,
        },
    ]))
    client.post("/api/v1/auth/register", json={
        "email": "allocator@example.com", "full_name": "Resource Allocator", "password": "safe-password-123",
    })
    login = client.post("/api/v1/auth/login", json={"email": "allocator@example.com", "password": "safe-password-123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.post("/api/v1/resource-allocation", headers=headers, json={
        "latitude": 12.01,
        "longitude": 77.0,
        "required_resources": {"Food Packets": 2_500_000},
    })

    assert response.status_code == 200
    allocation = response.json()["allocations"]["Food Packets"]
    assert response.json()["allocation_status"] == "Complete"
    assert allocation["shortage"] == 0
    assert allocation["supplies"] == [
        {"warehouse_id": "WH001", "warehouse_name": "Nearest Warehouse", "state": "State A", "distance_km": 1.11, "quantity": 2_000_000},
        {"warehouse_id": "WH002", "warehouse_name": "Next Nearest Warehouse", "state": "State B", "distance_km": 110.08, "quantity": 500_000},
    ]


def test_warehouse_directory_lists_locations_and_inventory(monkeypatch):
    import pandas as pd

    from app.services import allocation_service

    monkeypatch.setattr(allocation_service, "load_inventory", lambda: pd.DataFrame([
        {
            "WarehouseID": "WH001", "WarehouseName": "North Warehouse", "State": "State A",
            "Latitude": 12.0, "Longitude": 77.0, "Resource": "Food Packets", "AvailableQuantity": 500,
        },
        {
            "WarehouseID": "WH001", "WarehouseName": "North Warehouse", "State": "State A",
            "Latitude": 12.0, "Longitude": 77.0, "Resource": "Water Bottles", "AvailableQuantity": 800,
        },
        {
            "WarehouseID": "WH002", "WarehouseName": "South Warehouse", "State": "State B",
            "Latitude": 13.0, "Longitude": 78.0, "Resource": "Food Packets", "AvailableQuantity": 300,
        },
    ]))
    client.post("/api/v1/auth/register", json={
        "email": "warehouse@example.com", "full_name": "Warehouse Coordinator", "password": "safe-password-123",
    })
    login = client.post("/api/v1/auth/login", json={"email": "warehouse@example.com", "password": "safe-password-123"})

    response = client.get("/api/v1/warehouses", headers={"Authorization": f"Bearer {login.json()['access_token']}"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "warehouse_id": "WH001", "warehouse_name": "North Warehouse", "state": "State A",
            "latitude": 12.0, "longitude": 77.0,
            "inventory": [
                {"resource": "Food Packets", "available_quantity": 500},
                {"resource": "Water Bottles", "available_quantity": 800},
            ],
        },
        {
            "warehouse_id": "WH002", "warehouse_name": "South Warehouse", "state": "State B",
            "latitude": 13.0, "longitude": 78.0,
            "inventory": [{"resource": "Food Packets", "available_quantity": 300}],
        },
    ]


def test_disaster_report_uses_live_data_then_predicts_requirements(monkeypatch):
    from app.services import model_service, realtime_data_service

    monkeypatch.setattr(realtime_data_service, "get_current_weather", lambda *_: {
        "temperature": 28.0, "humidity": 80.0, "rainfall": 12.0, "wind_speed": 22.0,
    })
    monkeypatch.setattr(realtime_data_service, "get_infrastructure_score", lambda *_: 0.42)
    monkeypatch.setattr(model_service, "predict_impact", lambda _: 75.0)
    client.post("/api/v1/auth/register", json={
        "email": "field-team@example.com", "full_name": "Field Team", "password": "safe-password-123",
    })
    login = client.post("/api/v1/auth/login", json={"email": "field-team@example.com", "password": "safe-password-123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created = client.post("/api/v1/disaster-reports", headers=headers, json={
        "disaster_type": "Flood", "latitude": 13.0827, "longitude": 80.2707,
        "magnitude": 6.2, "affected_population": 1_000,
    })
    assert created.status_code == 201
    assert created.json()["wind_speed"] == 22.0
    assert created.json()["infrastructure_score"] == 0.42

    prediction = client.post(f"/api/v1/disaster-reports/{created.json()['id']}/predict", headers=headers)
    assert prediction.status_code == 200
    assert prediction.json()["predicted_impact_score"] == 75.0
    assert set(prediction.json()["estimated_requirements"]) == {
        "Food Packets", "Water Bottles", "Medical Kits", "Blankets", "Temporary Tents",
        "Rescue Teams", "Ambulances", "Trucks", "Boats", "Helicopters",
    }


def test_partial_allocation_is_visible_in_response_and_lifecycle(monkeypatch):
    from app.services import allocation_service, model_service, realtime_data_service

    monkeypatch.setattr(realtime_data_service, "get_current_weather", lambda *_: {
        "temperature": 28.0, "humidity": 80.0, "rainfall": 12.0, "wind_speed": 22.0,
    })
    monkeypatch.setattr(realtime_data_service, "get_infrastructure_score", lambda *_: 0.42)
    monkeypatch.setattr(model_service, "predict_impact", lambda _: 50.0)
    monkeypatch.setattr(allocation_service, "allocate_resources", lambda *_: {
        "nearest_warehouse_id": "WH001", "nearest_warehouse_name": "Chennai Warehouse",
        "nearest_warehouse_distance_km": 1.0, "allocation_status": "Partial",
        "allocations": {"Food Packets": {"required": 100, "allocated": 60, "shortage": 40, "supplies": []}},
    })
    client.post("/api/v1/auth/register", json={
        "email": "partial-allocation@example.com", "full_name": "Partial Allocation", "password": "safe-password-123",
    })
    login = client.post("/api/v1/auth/login", json={"email": "partial-allocation@example.com", "password": "safe-password-123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    report = client.post("/api/v1/disaster-reports", headers=headers, json={
        "disaster_type": "Flood", "latitude": 13.5, "longitude": 80.5, "magnitude": 6.0, "affected_population": 100,
    }).json()

    assert client.post(f"/api/v1/disaster-reports/{report['id']}/predict", headers=headers).status_code == 200
    allocation = client.post(f"/api/v1/disaster-reports/{report['id']}/allocate", headers=headers)
    assert allocation.status_code == 200
    assert allocation.json()["allocation_status"] == "Partial"
    assert allocation.json()["allocations"]["Food Packets"]["shortage"] == 40
    history = client.get(f"/api/v1/disaster-reports/{report['id']}", headers=headers)
    assert history.json()["current_status"] == "partially_allocated"


def test_duplicate_disaster_report_is_rejected_before_live_data_lookup(monkeypatch):
    from app.services import realtime_data_service

    weather_calls = 0

    def get_current_weather(*_):
        nonlocal weather_calls
        weather_calls += 1
        return {"temperature": 28.0, "humidity": 80.0, "rainfall": 12.0, "wind_speed": 22.0}

    monkeypatch.setattr(realtime_data_service, "get_current_weather", get_current_weather)
    monkeypatch.setattr(realtime_data_service, "get_infrastructure_score", lambda *_: 0.42)
    client.post("/api/v1/auth/register", json={
        "email": "duplicate-check@example.com", "full_name": "Duplicate Checker", "password": "safe-password-123",
    })
    login = client.post("/api/v1/auth/login", json={"email": "duplicate-check@example.com", "password": "safe-password-123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    payload = {
        "disaster_type": "Cyclone", "latitude": 19.0760, "longitude": 72.8777,
        "magnitude": 7.0, "affected_population": 1_000,
    }

    created = client.post("/api/v1/disaster-reports", headers=headers, json=payload)
    assert created.status_code == 201

    duplicate = client.post("/api/v1/disaster-reports", headers=headers, json={**payload, "magnitude": 7.4})
    assert duplicate.status_code == 409
    assert weather_calls == 1
    assert duplicate.json()["detail"] == {
        "message": "Duplicate disaster report detected.",
        "existing_report_id": created.json()["id"],
    }


def test_report_history_lifecycle_notifications_and_route(monkeypatch):
    from app.services import model_service, realtime_data_service, route_service

    monkeypatch.setattr(realtime_data_service, "get_current_weather", lambda *_: {
        "temperature": 30.0, "humidity": 70.0, "rainfall": 2.0, "wind_speed": 12.0,
    })
    monkeypatch.setattr(realtime_data_service, "get_infrastructure_score", lambda *_: 0.3)
    monkeypatch.setattr(model_service, "predict_impact", lambda _: 80.0)
    monkeypatch.setattr(route_service, "plan_route", lambda *_: {
        "warehouse_id": "WH001", "warehouse_name": "Nearest Warehouse", "warehouse_state": "State A",
        "distance_km": 12.5, "duration_minutes": 20.0, "estimated_arrival_at": "2026-07-22T12:00:00Z",
        "route_source": "osrm", "geometry": {"type": "LineString", "coordinates": []},
    })
    client.post("/api/v1/auth/register", json={
        "email": "coordinator@example.com", "full_name": "Response Coordinator", "password": "safe-password-123",
    })
    login = client.post("/api/v1/auth/login", json={"email": "coordinator@example.com", "password": "safe-password-123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    report = client.post("/api/v1/disaster-reports", headers=headers, json={
        "disaster_type": "Flood", "latitude": 13.0, "longitude": 80.0, "magnitude": 6.0, "affected_population": 100,
    }).json()
    report_id = report["id"]

    history = client.get("/api/v1/disaster-reports", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["current_status"] == "reported"
    assert client.post(f"/api/v1/disaster-reports/{report_id}/predict", headers=headers).status_code == 200
    assert client.get(f"/api/v1/disaster-reports/{report_id}/route", headers=headers).json()["duration_minutes"] == 20.0
    dispatched = client.patch(f"/api/v1/disaster-reports/{report_id}/status", headers=headers, json={
        "status": "dispatched", "estimated_arrival_at": "2026-07-22T12:00:00Z",
    })
    assert dispatched.status_code == 409  # Allocation must happen before dispatch.
    notifications = client.get("/api/v1/notifications?unread_only=true", headers=headers)
    assert notifications.status_code == 200
    assert len(notifications.json()) >= 2


def test_persistent_reservations_teams_and_road_risks(monkeypatch):
    from app.models import WarehouseStock
    from app.services import model_service, realtime_data_service, route_service

    monkeypatch.setattr(realtime_data_service, "get_current_weather", lambda *_: {
        "temperature": 30.0, "humidity": 70.0, "rainfall": 2.0, "wind_speed": 12.0,
    })
    monkeypatch.setattr(realtime_data_service, "get_infrastructure_score", lambda *_: 0.3)
    monkeypatch.setattr(model_service, "predict_impact", lambda _: 50.0)
    monkeypatch.setattr(route_service, "plan_route", lambda latitude, longitude, road_risks=None: {
        "warehouse_id": "OPS-1", "warehouse_name": "Operational Warehouse", "warehouse_state": "State A",
        "distance_km": 5.0, "duration_minutes": 10.0, "estimated_arrival_at": "2026-07-27T12:00:00Z",
        "route_source": "osrm", "geometry": None,
        "excluded_road_risk_ids": [risk["id"] for risk in (road_risks or [])],
        "route_safety_status": "risk_aware_detour" if road_risks else "no_active_risks",
    })
    db = TestingSessionLocal()
    db.add_all([
        WarehouseStock(warehouse_id="OPS-1", warehouse_name="Operational Warehouse", state="State A", latitude=14.0,
                       longitude=81.0, resource=resource, available_quantity=100_000_000)
        for resource in ["Food Packets", "Water Bottles", "Medical Kits", "Blankets", "Temporary Tents", "Rescue Teams", "Ambulances", "Boats", "Helicopters", "Trucks"]
    ])
    db.commit(); db.close()

    client.post("/api/v1/auth/register", json={
        "email": "operations@example.com", "full_name": "Operations Lead", "password": "safe-password-123",
    })
    login = client.post("/api/v1/auth/login", json={"email": "operations@example.com", "password": "safe-password-123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    report = client.post("/api/v1/disaster-reports", headers=headers, json={
        "disaster_type": "Flood", "latitude": 14.0, "longitude": 81.0, "magnitude": 6.0, "affected_population": 100,
    }).json()
    report_id = report["id"]
    assert client.post(f"/api/v1/disaster-reports/{report_id}/predict", headers=headers).status_code == 200

    reservation = client.post(f"/api/v1/disaster-reports/{report_id}/reservations", headers=headers)
    assert reservation.status_code == 201
    reservation_id = reservation.json()["id"]
    assert reservation.json()["status"] == "reserved"
    stock_after_reserve = client.get("/api/v1/operational-stock", headers=headers).json()
    assert next(item for item in stock_after_reserve if item["resource"] == "Food Packets")["available_quantity"] < 100_000_000
    assert client.patch(f"/api/v1/disaster-reports/{report_id}/reservations/{reservation_id}", headers=headers, json={"status": "approved"}).status_code == 200
    assert client.patch(f"/api/v1/disaster-reports/{report_id}/reservations/{reservation_id}", headers=headers, json={"status": "dispatched"}).status_code == 200
    assert client.patch(f"/api/v1/disaster-reports/{report_id}/reservations/{reservation_id}", headers=headers, json={"status": "delivered"}).status_code == 200

    team = client.post("/api/v1/responder-teams", headers=headers, json={
        "team_number": "TEAM-CHN-01", "tags": "water-rescue,medical", "skills": "Swift-water rescue, first aid", "vehicles": "2 boats, 1 ambulance",
    })
    assert team.status_code == 201
    assignment = client.post(f"/api/v1/disaster-reports/{report_id}/teams", headers=headers, json={"team_id": team.json()["id"]})
    assert assignment.status_code == 201
    assignment_id = assignment.json()["id"]
    assert client.patch(f"/api/v1/disaster-reports/{report_id}/teams/{assignment_id}", headers=headers, json={"status": "on_site"}).status_code == 200

    risk = client.post(f"/api/v1/disaster-reports/{report_id}/road-risks", headers=headers, json={
        "team_id": team.json()["id"], "risk_type": "blocked_road", "severity": "high", "road_name": "ECR",
        "description": "Flood water has blocked the road.", "latitude": 14.05, "longitude": 81.1,
    })
    assert risk.status_code == 201
    route = client.get(f"/api/v1/disaster-reports/{report_id}/route", headers=headers)
    assert route.status_code == 200
    assert risk.json()["id"] in route.json()["excluded_road_risk_ids"]
    assert client.patch(f"/api/v1/disaster-reports/{report_id}/road-risks/{risk.json()['id']}", headers=headers, json={"status": "cleared"}).status_code == 200
