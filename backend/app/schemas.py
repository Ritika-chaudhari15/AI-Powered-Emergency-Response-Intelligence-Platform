from datetime import datetime

import math

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


# These are stable API/database codes.  Frontends translate their labels; they
# must not send translated labels as values used in allocation calculations.
SUPPORTED_DISASTER_TYPES = ("earthquake", "flood", "cyclone", "drought", "wildfire")


class UserRegister(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    message: str


class ImpactPredictionRequest(BaseModel):
    magnitude: float = Field(alias="Magnitude", description="Disaster magnitude used during model training")
    weather_score: float = Field(alias="WeatherScore", description="Engineered weather severity score")
    wind_speed: float = Field(alias="WindSpeed", description="Wind speed")
    population_density: float = Field(alias="PopulationDensity", ge=0, description="Population density")
    infrastructure_score: float = Field(alias="InfrastructureScore", ge=0, description="Infrastructure score")

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def numbers_must_be_finite(self):
        if not all(math.isfinite(value) for value in self.model_dump().values()):
            raise ValueError("All prediction inputs must be finite numbers")
        return self


class ImpactPredictionResponse(BaseModel):
    predicted_impact_score: float


class ResourceAllocationRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90, description="Disaster location latitude")
    longitude: float = Field(ge=-180, le=180, description="Disaster location longitude")
    required_resources: dict[str, int] = Field(min_length=1, description="Resource quantities required for the response")

    @model_validator(mode="after")
    def resources_must_be_valid(self):
        if any(quantity < 0 for quantity in self.required_resources.values()):
            raise ValueError("Required resource quantities cannot be negative")
        if not any(quantity > 0 for quantity in self.required_resources.values()):
            raise ValueError("At least one required resource quantity must be greater than zero")
        return self


class WarehouseSupply(BaseModel):
    warehouse_id: str
    warehouse_name: str
    state: str
    distance_km: float
    quantity: int


class ResourceAllocationItem(BaseModel):
    required: int
    allocated: int
    shortage: int
    supplies: list[WarehouseSupply]


class ResourceAllocationResponse(BaseModel):
    nearest_warehouse_id: str
    nearest_warehouse_name: str
    nearest_warehouse_distance_km: float
    allocation_status: str
    allocations: dict[str, ResourceAllocationItem]
    # Manual allocation requests are not tied to a disaster report, so they
    # cannot have a volunteer assignment. Report-based allocation populates it.
    volunteer_assignment: "VolunteerAssignmentResponse | None" = None


class WarehouseInventoryItem(BaseModel):
    resource: str
    available_quantity: int


class WarehouseResponse(BaseModel):
    warehouse_id: str
    warehouse_name: str
    state: str
    latitude: float
    longitude: float
    inventory: list[WarehouseInventoryItem]


class DisasterReportCreate(BaseModel):
    disaster_type: str = Field(min_length=2, max_length=50, examples=["flood"])
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    magnitude: float = Field(gt=0, le=15, description="Magnitude or intensity reported for the disaster")
    affected_population: int = Field(gt=0, description="People affected, reported by the user or field team")

    @field_validator("disaster_type")
    @classmethod
    def normalize_disaster_type(cls, value: str) -> str:
        """Store a canonical code even when legacy clients send `Flood`."""
        code = value.strip().lower().replace(" ", "_").replace("-", "_")
        if code not in SUPPORTED_DISASTER_TYPES:
            supported = ", ".join(SUPPORTED_DISASTER_TYPES)
            raise ValueError(f"Unsupported disaster_type. Use one of: {supported}")
        return code


class DisasterReportResponse(BaseModel):
    id: int
    disaster_type: str
    latitude: float
    longitude: float
    magnitude: float
    affected_population: int
    temperature: float
    humidity: float
    rainfall: float
    wind_speed: float
    weather_score: float
    population_density: float
    infrastructure_score: float
    predicted_impact_score: float | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DisasterPredictionResponse(BaseModel):
    report: DisasterReportResponse
    predicted_impact_score: float
    estimated_requirements: dict[str, int]
    volunteer_assignment: "VolunteerAssignmentResponse"


class DisasterReportHistoryItem(DisasterReportResponse):
    current_status: str


class DisasterStatusUpdate(BaseModel):
    status: str = Field(pattern="^(reported|assessed|partially_allocated|allocated|dispatched|completed)$")
    note: str | None = Field(default=None, max_length=500)
    estimated_arrival_at: datetime | None = None


class LifecycleEventResponse(BaseModel):
    id: int
    report_id: int
    status: str
    note: str | None
    estimated_arrival_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoutePlanResponse(BaseModel):
    warehouse_id: str
    warehouse_name: str
    warehouse_state: str
    distance_km: float
    duration_minutes: float
    estimated_arrival_at: datetime
    route_source: str
    geometry: dict | None
    excluded_road_risk_ids: list[int] = []
    route_safety_status: str = "no_active_risks"


class ShelterRecommendationItem(BaseModel):
    shelter_id: str
    name: str
    distance_km: float
    available_capacity: int
    allocated_people: int


class ShelterRecommendationResponse(BaseModel):
    affected_population: int
    allocated_people: int
    waiting_people: int
    allocation_status: str
    shelters: list[ShelterRecommendationItem]


class NotificationResponse(BaseModel):
    id: int
    report_id: int | None
    notification_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReservationItemResponse(BaseModel):
    resource: str
    quantity: int
    warehouse_id: str
    warehouse_name: str


class ResourceReservationResponse(BaseModel):
    id: int
    report_id: int
    status: str
    note: str | None
    created_at: datetime
    items: list[ReservationItemResponse]


class ReservationStatusUpdate(BaseModel):
    status: str = Field(pattern="^(approved|dispatched|delivered|cancelled|returned)$")
    note: str | None = Field(default=None, max_length=500)


class ResponderTeamCreate(BaseModel):
    team_number: str = Field(min_length=2, max_length=50)
    tags: str | None = Field(default=None, max_length=300)
    skills: str = Field(min_length=2, max_length=500)
    vehicles: str | None = Field(default=None, max_length=500)


class ResponderTeamResponse(BaseModel):
    id: int
    team_number: str
    tags: str | None
    skills: str
    vehicles: str | None
    status: str
    member_count: int = 0
    estimated_arrival_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TeamAssignmentCreate(BaseModel):
    team_id: int
    estimated_arrival_at: datetime | None = None
    note: str | None = Field(default=None, max_length=500)


class TeamAssignmentStatusUpdate(BaseModel):
    status: str = Field(pattern="^(assigned|en_route|on_site|returning|completed)$")
    estimated_arrival_at: datetime | None = None
    note: str | None = Field(default=None, max_length=500)


class TeamAssignmentResponse(BaseModel):
    id: int
    report_id: int
    team_id: int
    team_number: str
    status: str
    estimated_arrival_at: datetime | None
    note: str | None
    created_at: datetime


class VehicleTrackingResponse(BaseModel):
    id: int
    report_id: int
    team_id: int
    team_number: str
    latitude: float
    longitude: float
    progress_percent: int
    route_status: str
    reroute_count: int
    speed_kmph: float
    estimated_arrival_at: datetime | None
    route_geometry: dict | None = None
    updated_at: datetime


class VehicleTelemetryUpdate(BaseModel):
    """GPS/speed sample supplied by a vehicle tracker (or a simulator)."""
    speed_kmph: float = Field(ge=0, le=240)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class RoadRiskCreate(BaseModel):
    team_id: int
    risk_type: str = Field(pattern="^(blocked_road|flood_zone|damaged_bridge|unsafe_area)$")
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    road_name: str | None = Field(default=None, max_length=160)
    description: str = Field(min_length=3, max_length=1000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class RoadRiskStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|cleared)$")


class RoadRiskResponse(BaseModel):
    id: int
    report_id: int
    team_id: int
    risk_type: str
    severity: str
    road_name: str | None
    description: str
    latitude: float
    longitude: float
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VolunteerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(min_length=3, max_length=20)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    skill: str = Field(min_length=2, max_length=100)


class VolunteerResponse(VolunteerCreate):
    id: int
    availability: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class VolunteerStatusUpdate(BaseModel):
    availability: str = Field(pattern="^(Available|Busy|Unavailable)$")


class AssignedVolunteer(BaseModel):
    volunteer_id: int
    name: str
    skill: str
    status: str


class VolunteerAssignmentResponse(BaseModel):
    impact_score: float
    severity: str
    available_before_assignment: int
    assigned_count: int
    assigned_volunteers: list[AssignedVolunteer]


class DisasterTypeTrend(BaseModel):
    disaster_type: str
    report_count: int
    average_impact_score: float | None
    total_affected_population: int


class TrendTimelinePoint(BaseModel):
    period: str
    report_count: int
    average_impact_score: float | None
    total_affected_population: int


class DisasterTrendAnalyticsResponse(BaseModel):
    period_days: int
    start_date: datetime
    end_date: datetime
    total_reports: int
    predicted_reports: int
    average_impact_score: float | None
    total_affected_population: int
    most_frequent_disaster_type: str | None
    disaster_type_breakdown: list[DisasterTypeTrend]
    daily_trend: list[TrendTimelinePoint]


class DisasterPriorityQueueItem(BaseModel):
    rank: int
    report_id: int
    disaster_type: str
    magnitude: float
    affected_population: int
    impact_score: float
    impact_score_source: str
    severity_score: float
    severity: str
    priority_score: float
    current_status: str
    created_at: datetime


class DisasterPriorityQueueResponse(BaseModel):
    total_reports: int
    items: list[DisasterPriorityQueueItem]


class KnowledgeEntryCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    entry_type: str = Field(pattern="^(best_practice|past_response|lesson_learned)$")
    content: str = Field(min_length=10, max_length=5000)
    disaster_type: str | None = Field(default=None, max_length=50)
    severity: str | None = Field(default=None, pattern="^(Low|Moderate|High)$")
    tags: list[str] = Field(default_factory=list, max_length=20)


class KnowledgeEntryResponse(KnowledgeEntryCreate):
    id: int
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class SimilarDisasterItem(BaseModel):
    report_id: int
    disaster_type: str
    magnitude: float
    affected_population: int
    impact_score: float
    similarity_score: float
    created_at: datetime


class DisasterKnowledgeRecommendation(BaseModel):
    knowledge_entry: KnowledgeEntryResponse
    match_reasons: list[str]


class DisasterRecommendationsResponse(BaseModel):
    report_id: int
    disaster_type: str
    severity: str
    impact_score: float
    recommended_strategy: str
    recommendation_source: str
    recommended_strategies: list[DisasterKnowledgeRecommendation]
    similar_disasters: list[SimilarDisasterItem]


class RecommendationFeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class RecommendationFeedbackResponse(RecommendationFeedbackCreate):
    id: int
    report_id: int
    knowledge_entry_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
