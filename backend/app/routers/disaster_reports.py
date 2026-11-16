from fastapi import APIRouter, Depends, HTTPException, status
from requests import RequestException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import DisasterLifecycleEvent, DisasterReport, ResourceReservation, ResourceReservationItem, RoadRiskReport, User, VehicleTracking, WarehouseStock
from app.schemas import (
    DisasterPredictionResponse,
    DisasterReportCreate,
    DisasterReportHistoryItem,
    DisasterReportResponse,
    DisasterStatusUpdate,
    LifecycleEventResponse,
    ResourceAllocationResponse,
    RoutePlanResponse,
    ShelterRecommendationResponse,
)
from app.services import (
    allocation_service, duplicate_report_service, lifecycle_service, model_service, notification_service, realtime_data_service,
    operations_service, resource_planning_service, route_service, shelter_service,
)
from app.services import volunteer_assignment_service


router = APIRouter(prefix="/api/v1/disaster-reports", tags=["Disaster reports"])


def get_owned_report(db: Session, report_id: int, user_id: int) -> DisasterReport:
    report = db.get(DisasterReport, report_id)
    if not report or report.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Disaster report not found")
    return report


def history_item(db: Session, report: DisasterReport) -> DisasterReportHistoryItem:
    return DisasterReportHistoryItem(
        **DisasterReportResponse.model_validate(report).model_dump(),
        current_status=lifecycle_service.current_status(db, report.id),
    )


def reservation_allocation_response(db: Session, report: DisasterReport, reservation: ResourceReservation, requirements: dict[str, int]) -> dict:
    """Turn a persisted operational reservation into the allocation response shape."""
    items = list(db.scalars(select(ResourceReservationItem).where(ResourceReservationItem.reservation_id == reservation.id)))
    allocations = {resource: {"required": required, "allocated": 0, "shortage": required, "supplies": []}
                   for resource, required in requirements.items()}
    nearest = None
    for item in items:
        stock = db.get(WarehouseStock, item.warehouse_stock_id)
        distance = allocation_service.haversine_distance_km(report.latitude, report.longitude, stock.latitude, stock.longitude)
        supply = {"warehouse_id": stock.warehouse_id, "warehouse_name": stock.warehouse_name, "state": stock.state,
                  "distance_km": round(distance, 2), "quantity": item.quantity}
        allocations[item.resource]["allocated"] += item.quantity
        allocations[item.resource]["shortage"] -= item.quantity
        allocations[item.resource]["supplies"].append(supply)
        if nearest is None or distance < nearest["distance_km"]:
            nearest = supply
    if nearest is None:
        nearest = {"warehouse_id": "—", "warehouse_name": "No available warehouse", "distance_km": 0}
    return {"nearest_warehouse_id": nearest["warehouse_id"], "nearest_warehouse_name": nearest["warehouse_name"],
            "nearest_warehouse_distance_km": nearest["distance_km"],
            "allocation_status": "Complete" if all(item["shortage"] == 0 for item in allocations.values()) else "Partial",
            "allocations": allocations}


@router.post("", response_model=DisasterReportResponse, status_code=status.HTTP_201_CREATED)
def create_disaster_report(
    payload: DisasterReportCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Store user-reported disaster details and fetch current weather automatically."""
    duplicate = duplicate_report_service.find_duplicate_report(
        db,
        disaster_type=payload.disaster_type,
        latitude=payload.latitude,
        longitude=payload.longitude,
        magnitude=payload.magnitude,
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Duplicate disaster report detected.",
                "existing_report_id": duplicate.id,
            },
        )
    try:
        weather = realtime_data_service.get_current_weather(payload.latitude, payload.longitude)
    except (RequestException, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Current weather data is unavailable. Please retry shortly.",
        )
    infrastructure_score = realtime_data_service.get_infrastructure_score(payload.latitude, payload.longitude)
    report = DisasterReport(
        user_id=user.id,
        disaster_type=payload.disaster_type.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        magnitude=payload.magnitude,
        affected_population=payload.affected_population,
        temperature=weather["temperature"],
        humidity=weather["humidity"],
        rainfall=weather["rainfall"],
        wind_speed=weather["wind_speed"],
        weather_score=realtime_data_service.calculate_weather_score(weather),
        population_density=realtime_data_service.estimate_population_density(payload.affected_population),
        infrastructure_score=infrastructure_score,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    lifecycle_service.add_event(db, report.id, user.id, "reported", "Disaster report received.", validate_transition=False)
    db.commit()
    return report


@router.get("", response_model=list[DisasterReportHistoryItem])
def list_disaster_reports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the authenticated user's saved disaster reports, newest first."""
    reports = list(db.scalars(select(DisasterReport).where(DisasterReport.user_id == user.id).order_by(DisasterReport.id.desc())))
    return [history_item(db, report) for report in reports]


@router.get("/{report_id}", response_model=DisasterReportHistoryItem)
def get_disaster_report(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return history_item(db, get_owned_report(db, report_id, user.id))


@router.get("/{report_id}/timeline", response_model=list[LifecycleEventResponse])
def get_timeline(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_report(db, report_id, user.id)
    return list(db.scalars(select(DisasterLifecycleEvent).where(DisasterLifecycleEvent.report_id == report_id).order_by(DisasterLifecycleEvent.id)))


@router.patch("/{report_id}/status", response_model=LifecycleEventResponse)
def update_status(report_id: int, payload: DisasterStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_owned_report(db, report_id, user.id)
    try:
        event = lifecycle_service.add_event(
            db, report_id, user.id, payload.status, payload.note, payload.estimated_arrival_at
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    db.commit()
    db.refresh(event)
    return event


@router.post("/{report_id}/predict", response_model=DisasterPredictionResponse)
def predict_report(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Predict impact and calculate the full warehouse resource requirement from a stored report."""
    report = get_owned_report(db, report_id, user.id)
    try:
        impact_score = model_service.predict_impact({
            "Magnitude": report.magnitude,
            "WeatherScore": report.weather_score,
            "WindSpeed": report.wind_speed,
            "PopulationDensity": report.population_density,
            "InfrastructureScore": report.infrastructure_score,
        })
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="The trained model could not make a prediction")

    report.predicted_impact_score = impact_score
    db.commit()
    db.refresh(report)
    volunteer_assignment = volunteer_assignment_service.assign_volunteers(db, report)
    if lifecycle_service.current_status(db, report.id) == "reported":
        lifecycle_service.add_event(db, report.id, user.id, "assessed", f"Impact prediction completed: {impact_score:.2f}.")
    if impact_score >= 70:
        notification_service.create_notification(
            db, user.id, "severe_impact", "High-impact disaster", f"Report #{report.id} has impact score {impact_score:.2f}.", report.id
        )
    db.commit()
    requirements = resource_planning_service.calculate_requirements(
        report.affected_population, report.disaster_type, impact_score
    )
    return DisasterPredictionResponse(
        report=report,
        predicted_impact_score=impact_score,
        estimated_requirements=requirements,
        volunteer_assignment=volunteer_assignment,
    )


@router.post("/{report_id}/allocate", response_model=ResourceAllocationResponse)
def allocate_report_resources(
    report_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allocate every calculated resource from nearest warehouses for a predicted report."""
    report = get_owned_report(db, report_id, user.id)
    if report.predicted_impact_score is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Predict this disaster report before allocating resources",
        )
    requirements = resource_planning_service.calculate_requirements(
        report.affected_population, report.disaster_type, report.predicted_impact_score
    )
    # Do not simulate against inventory.csv: reservations are the single source
    # of truth and preserve allocations after a refresh/restart.
    reservation = db.scalar(select(ResourceReservation).where(
        ResourceReservation.report_id == report.id,
        ResourceReservation.status.in_(["reserved", "approved", "dispatched"]),
    ).order_by(ResourceReservation.id.desc()))
    try:
        if reservation is None:
            reservation = operations_service.create_reservation(
                db, report.id, user.id, report.latitude, report.longitude, requirements
            )
        allocation = reservation_allocation_response(db, report, reservation, requirements)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))
    allocation["volunteer_assignment"] = volunteer_assignment_service.assignment_response(db, report)
    allocation_complete = allocation["allocation_status"] == "Complete"
    if lifecycle_service.current_status(db, report.id) in {"assessed", "partially_allocated"}:
        lifecycle_service.add_event(
            db,
            report.id,
            user.id,
            "allocated" if allocation_complete else "partially_allocated",
            "Resource allocation completed." if allocation_complete else "Resource allocation is partial because one or more supplies are unavailable.",
        )
    if not allocation_complete:
        notification_service.create_notification(
            db, user.id, "shortage", "Resource shortage", "One or more resources could not be fully allocated.", report.id
        )
    db.commit()
    return allocation


@router.get("/{report_id}/route", response_model=RoutePlanResponse)
def get_route(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = get_owned_report(db, report_id, user.id)
    try:
        road_risks = [
            {"id": risk.id, "latitude": risk.latitude, "longitude": risk.longitude}
            for risk in db.scalars(select(RoadRiskReport).where(
                RoadRiskReport.report_id == report_id, RoadRiskReport.status == "active"
            ))
        ]
        route = route_service.plan_route(report.latitude, report.longitude, road_risks)
        # Once a team is moving, expose its current re-routed geometry and ETA
        # to the report page as well as to the live map.
        vehicle = db.scalar(select(VehicleTracking).where(VehicleTracking.report_id == report_id).order_by(VehicleTracking.id.desc()))
        if vehicle and vehicle.route_geometry:
            route.update({
                "distance_km": round(vehicle.route_distance_km * (100 - vehicle.progress_percent) / 100, 2),
                "duration_minutes": round((vehicle.route_distance_km * (100 - vehicle.progress_percent) / 100) / vehicle.speed_kmph * 60, 1) if vehicle.speed_kmph else 0,
                "estimated_arrival_at": vehicle.estimated_arrival_at or route["estimated_arrival_at"],
                "geometry": vehicle.route_geometry,
                "route_safety_status": "risk_aware_detour" if vehicle.route_status == "rerouted" else route["route_safety_status"],
            })
        return route
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))


@router.get("/{report_id}/shelters", response_model=ShelterRecommendationResponse)
def get_shelter_recommendations(report_id: int, limit: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = get_owned_report(db, report_id, user.id)
    try:
        return shelter_service.recommend_shelters(report.latitude, report.longitude, report.affected_population, min(max(limit, 1), 100))
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error))
    except (ImportError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error))
