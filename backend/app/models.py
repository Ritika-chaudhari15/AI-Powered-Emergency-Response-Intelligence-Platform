from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TranslationKey(Base):
    """A stable UI/API key and its English source text."""
    __tablename__ = "translation_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    source_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TranslationValue(Base):
    """Persistent cache of a key translated into an Indic language by IndicTrans2."""
    __tablename__ = "translation_values"
    __table_args__ = (UniqueConstraint("translation_key_id", "locale", name="uq_translation_key_locale"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    translation_key_id: Mapped[int] = mapped_column(ForeignKey("translation_keys.id", ondelete="CASCADE"), nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    text: Mapped[str] = mapped_column(String(2000), nullable=False)
    generated_by: Mapped[str] = mapped_column(String(40), nullable=False, default="indictrans2")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DisasterReport(Base):
    """User and live-API data required to run one disaster prediction."""

    __tablename__ = "disaster_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    disaster_type: Mapped[str] = mapped_column(String(50), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    magnitude: Mapped[float] = mapped_column(Float, nullable=False)
    affected_population: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
    rainfall: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)
    weather_score: Mapped[float] = mapped_column(Float, nullable=False)
    population_density: Mapped[float] = mapped_column(Float, nullable=False)
    infrastructure_score: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_impact_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DisasterLifecycleEvent(Base):
    __tablename__ = "disaster_lifecycle_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("disaster_reports.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    estimated_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("disaster_reports.id", ondelete="CASCADE"), nullable=True)
    notification_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WarehouseStock(Base):
    """Operational stock imported once from the project's inventory CSV."""
    __tablename__ = "warehouse_stock"
    __table_args__ = (UniqueConstraint("warehouse_id", "resource", name="uq_warehouse_stock_resource"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    warehouse_name: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class ResourceReservation(Base):
    __tablename__ = "resource_reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("disaster_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="reserved")
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ResourceReservationItem(Base):
    __tablename__ = "resource_reservation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("resource_reservations.id", ondelete="CASCADE"), nullable=False, index=True)
    warehouse_stock_id: Mapped[int] = mapped_column(ForeignKey("warehouse_stock.id"), nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)


class ResponderTeam(Base):
    __tablename__ = "responder_teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    tags: Mapped[str | None] = mapped_column(String(300), nullable=True)
    skills: Mapped[str] = mapped_column(String(500), nullable=False)
    vehicles: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    estimated_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TeamMember(Base):
    """A volunteer's roster membership in a responder team."""
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "volunteer_id", name="uq_team_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("responder_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    volunteer_id: Mapped[int] = mapped_column(ForeignKey("volunteers.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class IncidentTeamAssignment(Base):
    __tablename__ = "incident_team_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("disaster_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("responder_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="assigned")
    estimated_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VehicleTracking(Base):
    """Latest simulated or GPS-supplied position for a deployed team vehicle."""
    __tablename__ = "vehicle_tracking"
    __table_args__ = (UniqueConstraint("report_id", "team_id", name="uq_vehicle_tracking_report_team"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("disaster_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("responder_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    route_status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned")
    reroute_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # The route is retained with the vehicle, so a re-route begins at the last
    # reported GPS point instead of sending the marker back to its warehouse.
    route_geometry: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    route_distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    speed_kmph: Mapped[float] = mapped_column(Float, nullable=False, default=45)
    estimated_arrival_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RoadRiskReport(Base):
    __tablename__ = "road_risk_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("disaster_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("responder_teams.id"), nullable=False)
    submitted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    risk_type: Mapped[str] = mapped_column(String(30), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    road_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Volunteer(Base):
    __tablename__ = "volunteers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    skill: Mapped[str] = mapped_column(String(100), nullable=False)
    availability: Mapped[str] = mapped_column(String(20), default="Available", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VolunteerAssignment(Base):
    __tablename__ = "volunteer_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    volunteer_id: Mapped[int] = mapped_column(ForeignKey("volunteers.id", ondelete="CASCADE"), nullable=False, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("disaster_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    available_before_assignment: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="Assigned", nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DisasterKnowledgeEntry(Base):
    __tablename__ = "disaster_knowledge_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(String(5000), nullable=False)
    disaster_type: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tags: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class KnowledgeRecommendationFeedback(Base):
    __tablename__ = "knowledge_recommendation_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    report_id: Mapped[int] = mapped_column(ForeignKey("disaster_reports.id", ondelete="CASCADE"), index=True, nullable=False)
    knowledge_entry_id: Mapped[int] = mapped_column(ForeignKey("disaster_knowledge_entries.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
