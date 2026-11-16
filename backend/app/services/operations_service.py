"""Database-backed operational inventory and responder-team workflows."""

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    IncidentTeamAssignment,
    ResponderTeam,
    ResourceReservation,
    ResourceReservationItem,
    TeamMember,
    Volunteer,
    WarehouseStock,
)
from app.services.allocation_service import haversine_distance_km


INVENTORY_PATH = Path(__file__).resolve().parents[3] / "datasets" / "inventory.csv"
RESERVATION_TRANSITIONS = {
    "reserved": {"approved", "cancelled"},
    "approved": {"dispatched", "cancelled"},
    "dispatched": {"delivered", "cancelled"},
    "delivered": {"returned"},
    "cancelled": set(),
    "returned": set(),
}

DEMO_TEAM_PREFIX = "DEMO-RESCUE-"
DEMO_TEAM_COUNT = 50
DEMO_VOLUNTEER_COUNT = 200
DEMO_EMAIL_DOMAIN = "responda-demo.com"


def ensure_demo_response_roster(db: Session, user_id: int) -> None:
    """Create an idempotent, usable demo roster for API and UI testing.

    The stock and user-entered records are never changed.  Demo volunteers are
    added only until the signed-in user has 200 volunteers, and the 50 shared
    demo teams receive four of those generated volunteers each.
    """
    teams = list(db.scalars(
        select(ResponderTeam).where(ResponderTeam.team_number.like(f"{DEMO_TEAM_PREFIX}%"))
        .order_by(ResponderTeam.team_number)
    ))
    team_skills = ("Search and rescue", "Medical response", "Water rescue", "Logistics and relief")
    existing_team_numbers = {team.team_number for team in teams}
    missing_teams = [ResponderTeam(
        created_by_user_id=user_id,
        team_number=f"{DEMO_TEAM_PREFIX}{index:02d}",
        skills=team_skills[(index - 1) % len(team_skills)],
        vehicles="1 rescue vehicle, 1 support vehicle",
        tags="demo, field-response",
        status="available",
    ) for index in range(1, DEMO_TEAM_COUNT + 1) if f"{DEMO_TEAM_PREFIX}{index:02d}" not in existing_team_numbers]
    if missing_teams:
        db.add_all(missing_teams)
        db.flush()
        teams.extend(missing_teams)
        teams.sort(key=lambda team: team.team_number)

    volunteers = list(db.scalars(
        select(Volunteer).where(Volunteer.user_id == user_id).order_by(Volunteer.id)
    ))
    # Earlier demo data used the reserved `.test` domain, which EmailStr rejects
    # when FastAPI validates the response. Repair those rows before returning.
    for volunteer in volunteers:
        if volunteer.email.endswith("@responda.test"):
            volunteer.email = f"demo.volunteer.{volunteer.id}@{DEMO_EMAIL_DOMAIN}"
    required_new = max(DEMO_VOLUNTEER_COUNT - len(volunteers), 0)
    if required_new:
        skills = ("First aid", "Search and rescue", "Logistics", "Radio operations", "Medical support")
        first_index = len(volunteers) + 1
        generated = [Volunteer(
            user_id=user_id,
            name=f"Demo Volunteer {index:03d}",
            email=f"demo.volunteer.{user_id}.{index:03d}@{DEMO_EMAIL_DOMAIN}",
            phone=f"+910000{index:06d}",
            latitude=13.0827 + ((index % 10) - 5) * 0.01,
            longitude=80.2707 + ((index % 10) - 5) * 0.01,
            skill=skills[(index - 1) % len(skills)],
            availability="Available",
        ) for index in range(first_index, first_index + required_new)]
        db.add_all(generated)
        db.flush()
        volunteers.extend(generated)

    generated_volunteers = [
        volunteer for volunteer in volunteers
        if volunteer.email.startswith("demo.volunteer.") and volunteer.email.endswith(f"@{DEMO_EMAIL_DOMAIN}")
    ]
    existing_memberships = {
        (team_id, volunteer_id) for team_id, volunteer_id in db.execute(
            select(TeamMember.team_id, TeamMember.volunteer_id).where(TeamMember.team_id.in_([team.id for team in teams]))
        )
    }
    for index, volunteer in enumerate(generated_volunteers[:DEMO_VOLUNTEER_COUNT]):
        team = teams[index // 4]
        if (team.id, volunteer.id) not in existing_memberships:
            db.add(TeamMember(team_id=team.id, volunteer_id=volunteer.id))
    db.commit()


def seed_warehouse_stock(db: Session) -> None:
    """Import the checked-in initial stock only when the operational table is empty."""
    if db.scalar(select(WarehouseStock.id).limit(1)) is not None:
        return
    if not INVENTORY_PATH.is_file():
        return
    inventory = pd.read_csv(INVENTORY_PATH)
    records = []
    for row in inventory.to_dict("records"):
        records.append(WarehouseStock(
            warehouse_id=str(row["WarehouseID"]), warehouse_name=str(row["WarehouseName"]),
            state=str(row["State"]), latitude=float(row["Latitude"]), longitude=float(row["Longitude"]),
            resource=str(row["Resource"]), available_quantity=int(row["AvailableQuantity"]),
        ))
    db.add_all(records)
    db.commit()


def create_reservation(db: Session, report_id: int, user_id: int, latitude: float, longitude: float, requirements: dict[str, int]) -> ResourceReservation:
    """Reserve available stock atomically in the current transaction, nearest warehouse first."""
    stocks = list(db.scalars(select(WarehouseStock).with_for_update()))
    available = {stock.resource for stock in stocks}
    unknown = set(requirements).difference(available)
    if unknown:
        raise ValueError(f"Operational inventory does not contain: {', '.join(sorted(unknown))}")

    reservation = ResourceReservation(report_id=report_id, user_id=user_id, status="reserved")
    db.add(reservation)
    db.flush()
    for resource, required in requirements.items():
        remaining = required
        candidates = sorted(
            (stock for stock in stocks if stock.resource == resource and stock.available_quantity > 0),
            key=lambda stock: haversine_distance_km(latitude, longitude, stock.latitude, stock.longitude),
        )
        for stock in candidates:
            if remaining <= 0:
                break
            quantity = min(remaining, stock.available_quantity)
            stock.available_quantity -= quantity
            remaining -= quantity
            db.add(ResourceReservationItem(
                reservation_id=reservation.id, warehouse_stock_id=stock.id, resource=resource, quantity=quantity,
            ))
    db.flush()
    return reservation


def update_reservation_status(db: Session, reservation: ResourceReservation, new_status: str, note: str | None) -> ResourceReservation:
    if new_status not in RESERVATION_TRANSITIONS.get(reservation.status, set()):
        raise ValueError(f"Cannot change reservation from {reservation.status} to {new_status}")
    if new_status in {"cancelled", "returned"}:
        items = db.scalars(select(ResourceReservationItem).where(ResourceReservationItem.reservation_id == reservation.id))
        for item in items:
            stock = db.get(WarehouseStock, item.warehouse_stock_id)
            stock.available_quantity += item.quantity
    reservation.status, reservation.note = new_status, note
    db.flush()
    return reservation


def team_assignment_response(db: Session, assignment: IncidentTeamAssignment) -> dict:
    team = db.get(ResponderTeam, assignment.team_id)
    return {
        "id": assignment.id, "report_id": assignment.report_id, "team_id": assignment.team_id,
        "team_number": team.team_number, "status": assignment.status,
        "estimated_arrival_at": assignment.estimated_arrival_at, "note": assignment.note,
        "created_at": assignment.created_at,
    }
