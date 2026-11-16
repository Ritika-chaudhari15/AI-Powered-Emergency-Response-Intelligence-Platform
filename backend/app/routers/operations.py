from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    DisasterReport, IncidentTeamAssignment, ResponderTeam, RoadRiskReport,
    ResourceReservation, ResourceReservationItem, TeamMember, User, VehicleTracking, WarehouseStock,
)
from app.schemas import (
    ReservationStatusUpdate, ResponderTeamCreate, ResponderTeamResponse, RoadRiskCreate,
    RoadRiskResponse, RoadRiskStatusUpdate, TeamAssignmentCreate, TeamAssignmentResponse,
    TeamAssignmentStatusUpdate, VehicleTelemetryUpdate, VehicleTrackingResponse,
)
from app.services import lifecycle_service, live_update_service, operations_service, resource_planning_service, route_service


team_router = APIRouter(prefix="/api/v1/responder-teams", tags=["Responder teams"])
report_router = APIRouter(prefix="/api/v1/disaster-reports", tags=["Operations"])
stock_router = APIRouter(prefix="/api/v1/operational-stock", tags=["Operational inventory"])


def owned_report(db: Session, report_id: int, user_id: int) -> DisasterReport:
    report = db.get(DisasterReport, report_id)
    if not report or report.user_id != user_id:
        raise HTTPException(status_code=404, detail="Disaster report not found")
    return report


def reservation_response(db: Session, reservation: ResourceReservation) -> dict:
    items = db.scalars(select(ResourceReservationItem).where(ResourceReservationItem.reservation_id == reservation.id))
    response_items = []
    allocated_by_resource: dict[str, int] = {}
    for item in items:
        stock = db.get(WarehouseStock, item.warehouse_stock_id)
        response_items.append({"resource": item.resource, "quantity": item.quantity,
                               "warehouse_id": stock.warehouse_id, "warehouse_name": stock.warehouse_name})
        allocated_by_resource[item.resource] = allocated_by_resource.get(item.resource, 0) + item.quantity
    report = db.get(DisasterReport, reservation.report_id)
    requirements = resource_planning_service.calculate_requirements(
        report.affected_population, report.disaster_type, report.predicted_impact_score
    )
    allocations = {
        resource: {
            "required": required,
            "allocated": allocated_by_resource.get(resource, 0),
            "shortage": max(required - allocated_by_resource.get(resource, 0), 0),
        }
        for resource, required in requirements.items()
    }
    allocation_status = "Complete" if all(item["shortage"] == 0 for item in allocations.values()) else "Partial"
    return {"id": reservation.id, "report_id": reservation.report_id, "status": reservation.status,
            "note": reservation.note, "created_at": reservation.created_at, "items": response_items,
            "allocation_status": allocation_status, "allocations": allocations}


@team_router.post("", response_model=ResponderTeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(payload: ResponderTeamCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    team = ResponderTeam(created_by_user_id=user.id, team_number=payload.team_number.strip(), tags=payload.tags,
                         skills=payload.skills.strip(), vehicles=payload.vehicles)
    db.add(team)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A responder team with this team number already exists")
    db.refresh(team)
    return team


@team_router.get("", response_model=list[ResponderTeamResponse])
def list_teams(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    operations_service.ensure_demo_response_roster(db, user.id)
    member_counts = dict(db.execute(
        select(TeamMember.team_id, func.count(TeamMember.id)).group_by(TeamMember.team_id)
    ).tuples().all())
    teams = db.scalars(select(ResponderTeam).order_by(ResponderTeam.team_number))
    return [{
        "id": team.id, "team_number": team.team_number, "tags": team.tags, "skills": team.skills,
        "vehicles": team.vehicles, "status": team.status, "member_count": member_counts.get(team.id, 0),
        "estimated_arrival_at": team.estimated_arrival_at, "created_at": team.created_at,
    } for team in teams]


@stock_router.get("")
def list_operational_stock(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Current database stock after reservations, cancellations, and returns."""
    return [{"warehouse_id": stock.warehouse_id, "warehouse_name": stock.warehouse_name,
             "state": stock.state, "resource": stock.resource, "available_quantity": stock.available_quantity}
            for stock in db.scalars(select(WarehouseStock).order_by(WarehouseStock.warehouse_id, WarehouseStock.resource))]


@report_router.post("/{report_id}/reservations", status_code=status.HTTP_201_CREATED)
def reserve_report_resources(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = owned_report(db, report_id, user.id)
    if report.predicted_impact_score is None:
        raise HTTPException(status_code=409, detail="Predict this disaster report before reserving resources")
    requirements = resource_planning_service.calculate_requirements(report.affected_population, report.disaster_type, report.predicted_impact_score)
    try:
        reservation = operations_service.create_reservation(db, report.id, user.id, report.latitude, report.longitude, requirements)
        reservation_payload = reservation_response(db, reservation)
        current_status = lifecycle_service.current_status(db, report.id)
        if current_status in {"assessed", "partially_allocated"}:
            allocation_complete = reservation_payload["allocation_status"] == "Complete"
            lifecycle_service.add_event(
                db,
                report.id,
                user.id,
                "allocated" if allocation_complete else "partially_allocated",
                "Operational reservation completed." if allocation_complete else "Operational reservation is partial because one or more supplies are unavailable.",
            )
        db.commit()
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    db.refresh(reservation)
    return reservation_response(db, reservation)


@report_router.get("/{report_id}/reservations")
def list_reservations(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_report(db, report_id, user.id)
    reservations = db.scalars(select(ResourceReservation).where(ResourceReservation.report_id == report_id).order_by(ResourceReservation.id.desc()))
    return [reservation_response(db, reservation) for reservation in reservations]


@report_router.patch("/{report_id}/reservations/{reservation_id}")
def update_reservation(report_id: int, reservation_id: int, payload: ReservationStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_report(db, report_id, user.id)
    reservation = db.get(ResourceReservation, reservation_id)
    if not reservation or reservation.report_id != report_id:
        raise HTTPException(status_code=404, detail="Resource reservation not found")
    try:
        operations_service.update_reservation_status(db, reservation, payload.status, payload.note)
        db.commit()
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error))
    db.refresh(reservation)
    return reservation_response(db, reservation)


@report_router.post("/{report_id}/teams", response_model=TeamAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_team(report_id: int, payload: TeamAssignmentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = owned_report(db, report_id, user.id)
    team = db.get(ResponderTeam, payload.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Responder team not found")
    if team.status != "available":
        raise HTTPException(status_code=409, detail="Responder team is not available")
    assignment = IncidentTeamAssignment(report_id=report_id, team_id=team.id, assigned_by_user_id=user.id,
                                        estimated_arrival_at=payload.estimated_arrival_at, note=payload.note)
    team.status, team.estimated_arrival_at = "en_route", payload.estimated_arrival_at
    origin_latitude, origin_longitude = simulation_origin(db, report)
    route = route_service.route_between(origin_latitude, origin_longitude, report.latitude, report.longitude)
    eta = datetime.now(timezone.utc) + timedelta(hours=route["distance_km"] / 45) if route["distance_km"] else datetime.now(timezone.utc)
    assignment.estimated_arrival_at = team.estimated_arrival_at = eta
    tracking = VehicleTracking(report_id=report.id, team_id=team.id, latitude=origin_latitude, longitude=origin_longitude,
                               route_geometry=route["geometry"], route_distance_km=route["distance_km"], speed_kmph=45,
                               estimated_arrival_at=eta, progress_percent=0, route_status="planned")
    db.add_all([assignment, tracking]); db.commit(); db.refresh(assignment)
    lifecycle_service.add_event(db, report.id, user.id, "dispatched", f"Team {team.team_number} assigned and dispatched.", eta, validate_transition=False)
    db.commit()
    live_update_service.publish(user.id, "team_assigned", {"report_id": report.id, "team_id": team.id, "team_number": team.team_number})
    return operations_service.team_assignment_response(db, assignment)


@report_router.get("/{report_id}/teams", response_model=list[TeamAssignmentResponse])
def list_assigned_teams(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_report(db, report_id, user.id)
    assignments = db.scalars(select(IncidentTeamAssignment).where(IncidentTeamAssignment.report_id == report_id))
    return [operations_service.team_assignment_response(db, assignment) for assignment in assignments]


@report_router.patch("/{report_id}/teams/{assignment_id}", response_model=TeamAssignmentResponse)
def update_team_assignment(report_id: int, assignment_id: int, payload: TeamAssignmentStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_report(db, report_id, user.id)
    assignment = db.get(IncidentTeamAssignment, assignment_id)
    if not assignment or assignment.report_id != report_id:
        raise HTTPException(status_code=404, detail="Team assignment not found")
    team = db.get(ResponderTeam, assignment.team_id)
    assignment.status, assignment.note, assignment.estimated_arrival_at = payload.status, payload.note, payload.estimated_arrival_at
    team.status, team.estimated_arrival_at = ("available", None) if payload.status == "completed" else (payload.status, payload.estimated_arrival_at)
    if payload.status == "on_site":
        lifecycle_service.add_event(db, report_id, user.id, "completed", payload.note or f"Team {team.team_number} arrived at the disaster site.", validate_transition=False)
    db.commit(); db.refresh(assignment)
    live_update_service.publish(user.id, "team_status", {"report_id": report_id, "team_id": team.id, "status": payload.status})
    return operations_service.team_assignment_response(db, assignment)


def tracking_response(db: Session, tracking: VehicleTracking) -> dict:
    team = db.get(ResponderTeam, tracking.team_id)
    return {
        "id": tracking.id, "report_id": tracking.report_id, "team_id": tracking.team_id,
        "team_number": team.team_number, "latitude": tracking.latitude, "longitude": tracking.longitude,
        "progress_percent": tracking.progress_percent, "route_status": tracking.route_status,
        "reroute_count": tracking.reroute_count, "speed_kmph": tracking.speed_kmph,
        "estimated_arrival_at": tracking.estimated_arrival_at, "route_geometry": tracking.route_geometry,
        "updated_at": tracking.updated_at,
    }


def simulation_origin(db: Session, report: DisasterReport) -> tuple[float, float]:
    """Use the nearest operational warehouse as the simulated vehicle origin."""
    stocks = list(db.scalars(select(WarehouseStock)))
    if not stocks:
        return report.latitude - 0.18, report.longitude - 0.18
    warehouse = min(stocks, key=lambda stock: (stock.latitude - report.latitude) ** 2 + (stock.longitude - report.longitude) ** 2)
    return warehouse.latitude, warehouse.longitude


def update_vehicle_eta(db: Session, report: DisasterReport, vehicle: VehicleTracking) -> None:
    remaining_km = max(vehicle.route_distance_km * (100 - vehicle.progress_percent) / 100, 0)
    vehicle.estimated_arrival_at = datetime.now(timezone.utc) + timedelta(hours=remaining_km / vehicle.speed_kmph) if vehicle.speed_kmph > 0 else None
    assignment = db.scalar(select(IncidentTeamAssignment).where(IncidentTeamAssignment.report_id == report.id, IncidentTeamAssignment.team_id == vehicle.team_id).order_by(IncidentTeamAssignment.id.desc()))
    if assignment:
        assignment.estimated_arrival_at = vehicle.estimated_arrival_at
    team = db.get(ResponderTeam, vehicle.team_id)
    if team:
        team.estimated_arrival_at = vehicle.estimated_arrival_at


def point_on_route(geometry: dict | None, fraction: float, start: tuple[float, float], destination: tuple[float, float]) -> tuple[float, float]:
    coordinates = (geometry or {}).get("coordinates") or [[start[1], start[0]], [destination[1], destination[0]]]
    if len(coordinates) == 1:
        return coordinates[0][1], coordinates[0][0]
    # A route's sampled OSRM coordinates are ordered along the road. Selecting a
    # point by index keeps the marker on the displayed path rather than a chord.
    index = min(round(fraction * (len(coordinates) - 1)), len(coordinates) - 1)
    longitude, latitude = coordinates[index]
    return latitude, longitude


def move_vehicles(db: Session, report: DisasterReport, user_id: int, progress_increment: int) -> list[VehicleTracking]:
    vehicles = list(db.scalars(select(VehicleTracking).where(
        VehicleTracking.report_id == report.id, VehicleTracking.progress_percent < 100
    )))
    for vehicle in vehicles:
        vehicle.progress_percent = min(vehicle.progress_percent + progress_increment, 100)
        fraction = vehicle.progress_percent / 100
        vehicle.latitude, vehicle.longitude = point_on_route(vehicle.route_geometry, fraction, (vehicle.latitude, vehicle.longitude), (report.latitude, report.longitude))
        update_vehicle_eta(db, report, vehicle)
        if vehicle.progress_percent == 100:
            vehicle.route_status = "arrived"
            team = db.get(ResponderTeam, vehicle.team_id)
            team.status = "on_site"
            assignment = db.scalar(select(IncidentTeamAssignment).where(
                IncidentTeamAssignment.report_id == report.id, IncidentTeamAssignment.team_id == vehicle.team_id
            ).order_by(IncidentTeamAssignment.id.desc()))
            if assignment:
                assignment.status = "on_site"
                assignment.estimated_arrival_at = datetime.now(timezone.utc)
            lifecycle_service.add_event(
                db, report.id, user_id, "completed", "Responder vehicle arrived at the disaster site.", validate_transition=False
            )
    return vehicles


def reroute_active_vehicles(db: Session, report_id: int) -> list[VehicleTracking]:
    report = db.get(DisasterReport, report_id)
    risks = [{"id": risk.id, "latitude": risk.latitude, "longitude": risk.longitude} for risk in db.scalars(select(RoadRiskReport).where(RoadRiskReport.report_id == report_id, RoadRiskReport.status == "active"))]
    vehicles = list(db.scalars(select(VehicleTracking).where(
        VehicleTracking.report_id == report_id, VehicleTracking.progress_percent < 100
    )))
    for vehicle in vehicles:
        vehicle.route_status = "rerouted"
        vehicle.reroute_count += 1
        route = route_service.route_between(vehicle.latitude, vehicle.longitude, report.latitude, report.longitude, risks)
        vehicle.route_geometry, vehicle.route_distance_km = route["geometry"], route["distance_km"]
        vehicle.progress_percent = 0
        update_vehicle_eta(db, report, vehicle)
    return vehicles


@report_router.get("/{report_id}/vehicle-tracking", response_model=list[VehicleTrackingResponse])
def list_vehicle_tracking(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = owned_report(db, report_id, user.id)
    # Each polling request advances the demo a little, which behaves like GPS
    # telemetry while the map is open without requiring a manual button press.
    moving = move_vehicles(db, report, user.id, 2)
    if moving:
        db.commit()
    vehicles = db.scalars(select(VehicleTracking).where(VehicleTracking.report_id == report_id).order_by(VehicleTracking.id))
    return [tracking_response(db, vehicle) for vehicle in vehicles]


@report_router.patch("/{report_id}/vehicle-tracking/{tracking_id}/telemetry", response_model=VehicleTrackingResponse)
def update_vehicle_telemetry(report_id: int, tracking_id: int, payload: VehicleTelemetryUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = owned_report(db, report_id, user.id)
    vehicle = db.get(VehicleTracking, tracking_id)
    if not vehicle or vehicle.report_id != report_id:
        raise HTTPException(status_code=404, detail="Vehicle tracking record not found")
    vehicle.speed_kmph = payload.speed_kmph
    if payload.latitude is not None and payload.longitude is not None:
        vehicle.latitude, vehicle.longitude = payload.latitude, payload.longitude
        # A GPS sample replaces the remaining route from that exact point.
        route = route_service.route_between(vehicle.latitude, vehicle.longitude, report.latitude, report.longitude)
        vehicle.route_geometry, vehicle.route_distance_km, vehicle.progress_percent = route["geometry"], route["distance_km"], 0
    update_vehicle_eta(db, report, vehicle)
    db.commit(); db.refresh(vehicle)
    live_update_service.publish(user.id, "vehicle_telemetry", tracking_response(db, vehicle))
    return tracking_response(db, vehicle)


@report_router.post("/{report_id}/vehicle-tracking/simulate", response_model=VehicleTrackingResponse, status_code=status.HTTP_201_CREATED)
def start_vehicle_simulation(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = owned_report(db, report_id, user.id)
    existing = db.scalar(select(VehicleTracking).where(VehicleTracking.report_id == report.id).order_by(VehicleTracking.id))
    if existing:
        return tracking_response(db, existing)
    team = db.scalar(select(ResponderTeam).where(ResponderTeam.status == "available").order_by(ResponderTeam.team_number))
    if not team:
        raise HTTPException(status_code=409, detail="No available responder team can be simulated")
    assignment = IncidentTeamAssignment(report_id=report.id, team_id=team.id, assigned_by_user_id=user.id, status="en_route", note="Vehicle tracking simulation")
    team.status = "en_route"
    origin_latitude, origin_longitude = simulation_origin(db, report)
    route = route_service.route_between(origin_latitude, origin_longitude, report.latitude, report.longitude)
    eta = datetime.now(timezone.utc) + timedelta(hours=route["distance_km"] / 45) if route["distance_km"] else datetime.now(timezone.utc)
    assignment.estimated_arrival_at = team.estimated_arrival_at = eta
    tracking = VehicleTracking(
        report_id=report.id, team_id=team.id, latitude=origin_latitude, longitude=origin_longitude,
        progress_percent=0, route_status="planned", route_geometry=route["geometry"], route_distance_km=route["distance_km"], speed_kmph=45, estimated_arrival_at=eta,
    )
    db.add_all([assignment, tracking]); db.commit(); db.refresh(tracking)
    lifecycle_service.add_event(db, report.id, user.id, "dispatched", "Responder vehicle dispatched from the nearest warehouse.", validate_transition=False)
    db.commit()
    live_update_service.publish(user.id, "vehicle_started", tracking_response(db, tracking))
    return tracking_response(db, tracking)


@report_router.post("/{report_id}/vehicle-tracking/tick", response_model=list[VehicleTrackingResponse])
def advance_vehicle_simulation(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = owned_report(db, report_id, user.id)
    vehicles = move_vehicles(db, report, user.id, 15)
    db.commit()
    for vehicle in vehicles:
        db.refresh(vehicle)
        live_update_service.publish(user.id, "vehicle_position", tracking_response(db, vehicle))
    return [tracking_response(db, vehicle) for vehicle in vehicles]


@report_router.post("/{report_id}/vehicle-tracking/simulate-roadblock", response_model=RoadRiskResponse, status_code=status.HTTP_201_CREATED)
def simulate_roadblock(report_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    report = owned_report(db, report_id, user.id)
    vehicle = db.scalar(select(VehicleTracking).where(VehicleTracking.report_id == report.id, VehicleTracking.progress_percent < 100))
    if not vehicle:
        raise HTTPException(status_code=409, detail="Start a vehicle simulation before reporting a roadblock")
    risk = RoadRiskReport(report_id=report.id, team_id=vehicle.team_id, submitted_by_user_id=user.id,
                          risk_type="blocked_road", severity="high", road_name="Simulated route obstruction",
                          description="Simulated team roadblock report. Vehicles have been rerouted.",
                          latitude=vehicle.latitude, longitude=vehicle.longitude)
    db.add(risk)
    reroute_active_vehicles(db, report.id)
    db.commit(); db.refresh(risk)
    live_update_service.publish(user.id, "road_risk_reroute", {"report_id": report.id, "risk_id": risk.id})
    return risk


@report_router.post("/{report_id}/road-risks", response_model=RoadRiskResponse, status_code=status.HTTP_201_CREATED)
def create_road_risk(report_id: int, payload: RoadRiskCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_report(db, report_id, user.id)
    assignment = db.scalar(select(IncidentTeamAssignment).where(
        IncidentTeamAssignment.report_id == report_id, IncidentTeamAssignment.team_id == payload.team_id,
        IncidentTeamAssignment.status.in_(["en_route", "on_site"]),
    ))
    if not assignment:
        raise HTTPException(status_code=409, detail="Only a team deployed to this disaster can report a road risk")
    risk = RoadRiskReport(report_id=report_id, team_id=payload.team_id, submitted_by_user_id=user.id,
                          risk_type=payload.risk_type, severity=payload.severity, road_name=payload.road_name,
                          description=payload.description, latitude=payload.latitude, longitude=payload.longitude)
    db.add(risk)
    reroute_active_vehicles(db, report_id)
    db.commit(); db.refresh(risk)
    live_update_service.publish(user.id, "road_risk_reroute", {"report_id": report_id, "risk_id": risk.id})
    return risk


@report_router.get("/{report_id}/road-risks", response_model=list[RoadRiskResponse])
def list_road_risks(report_id: int, active_only: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_report(db, report_id, user.id)
    query = select(RoadRiskReport).where(RoadRiskReport.report_id == report_id).order_by(RoadRiskReport.id.desc())
    if active_only:
        query = query.where(RoadRiskReport.status == "active")
    return list(db.scalars(query))


@report_router.patch("/{report_id}/road-risks/{risk_id}", response_model=RoadRiskResponse)
def update_road_risk(report_id: int, risk_id: int, payload: RoadRiskStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_report(db, report_id, user.id)
    risk = db.get(RoadRiskReport, risk_id)
    if not risk or risk.report_id != report_id:
        raise HTTPException(status_code=404, detail="Road risk report not found")
    risk.status = payload.status; db.commit(); db.refresh(risk)
    return risk
