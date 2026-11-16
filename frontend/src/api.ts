export const API_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

export type ApiError = Error & { status?: number };

function headers(token?: string, language = "en", json = true): HeadersInit {
  return {
    ...(json ? { "Content-Type": "application/json" } : {}),
    "Accept-Language": language.includes("-") ? language : `${language}-IN`,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

export async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
  language?: string,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...headers(token, language), ...options.headers },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error: ApiError = new Error(body?.detail || body?.message || "The request could not be completed.");
    error.status = response.status;
    if (response.status === 401) window.dispatchEvent(new Event("responda:session-expired"));
    throw error;
  }
  return body as T;
}

export const api = {
  languages: () => request<{ default: string; supported: Language[] }>("/i18n/languages"),
  bundle: (language: string) => request<{ locale: string; translations: Record<string, string> }>("/i18n/bundle", {}, undefined, language),
  login: (payload: { email: string; password: string }, language: string) => request<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) }, undefined, language),
  register: (payload: { email: string; full_name: string; password: string }, language: string) => request<User>("/auth/register", { method: "POST", body: JSON.stringify(payload) }, undefined, language),
  logout: (token: string, language: string) => request<{ message: string }>("/auth/logout", { method: "POST" }, token, language),
  me: (token: string, language: string) => request<User>("/users/me", {}, token, language),
  updateMe: (payload: { full_name: string }, token: string, language: string) => request<User>("/users/me", { method: "PATCH", body: JSON.stringify(payload) }, token, language),
  reports: (token: string, language: string) => request<Report[]>("/disaster-reports", {}, token, language),
  report: (id: number, token: string, language: string) => request<Report>(`/disaster-reports/${id}`, {}, token, language),
  createReport: (payload: Record<string, unknown>, token: string, language: string) => request<Report>("/disaster-reports", { method: "POST", body: JSON.stringify(payload) }, token, language),
  predict: (id: number, token: string, language: string) => request<Prediction>(`/disaster-reports/${id}/predict`, { method: "POST" }, token, language),
  allocate: (id: number, token: string, language: string) => request<Allocation>(`/disaster-reports/${id}/allocate`, { method: "POST" }, token, language),
  timeline: (id: number, token: string, language: string) => request<TimelineItem[]>(`/disaster-reports/${id}/timeline`, {}, token, language),
  route: (id: number, token: string, language: string) => request<RoutePlan>(`/disaster-reports/${id}/route`, {}, token, language),
  shelters: (id: number, token: string, language: string) => request<ShelterData>(`/disaster-reports/${id}/shelters`, {}, token, language),
  vehicleTracking: (id: number, token: string, language: string) => request<VehicleTracking[]>(`/disaster-reports/${id}/vehicle-tracking`, {}, token, language),
  startVehicleSimulation: (id: number, token: string, language: string) => request<VehicleTracking>(`/disaster-reports/${id}/vehicle-tracking/simulate`, { method: "POST" }, token, language),
  advanceVehicleSimulation: (id: number, token: string, language: string) => request<VehicleTracking[]>(`/disaster-reports/${id}/vehicle-tracking/tick`, { method: "POST" }, token, language),
  simulateRoadblock: (id: number, token: string, language: string) => request<unknown>(`/disaster-reports/${id}/vehicle-tracking/simulate-roadblock`, { method: "POST" }, token, language),
  updateVehicleTelemetry: (reportId: number, trackingId: number, payload: { speed_kmph: number; latitude?: number; longitude?: number }, token: string, language: string) => request<VehicleTracking>(`/disaster-reports/${reportId}/vehicle-tracking/${trackingId}/telemetry`, { method: "PATCH", body: JSON.stringify(payload) }, token, language),
  roadRisks: (id: number, token: string, language: string) => request<RoadRisk[]>(`/disaster-reports/${id}/road-risks?active_only=true`, {}, token, language),
  reservations: (id: number, token: string, language: string) => request<Reservation[]>(`/disaster-reports/${id}/reservations`, {}, token, language),
  updateReservation: (reportId: number, reservationId: number, status: string, token: string, language: string) => request<Reservation>(`/disaster-reports/${reportId}/reservations/${reservationId}`, { method: "PATCH", body: JSON.stringify({ status }) }, token, language),
  teams: (token: string, language: string) => request<Team[]>("/responder-teams", {}, token, language),
  createTeam: (payload: Record<string, unknown>, token: string, language: string) => request<Team>("/responder-teams", { method: "POST", body: JSON.stringify(payload) }, token, language),
  warehouses: (token: string, language: string) => request<Warehouse[]>("/warehouses", {}, token, language),
  stock: (token: string, language: string) => request<StockItem[]>("/operational-stock", {}, token, language),
  volunteers: (token: string, language: string) => request<Volunteer[]>("/volunteers", {}, token, language),
  createVolunteer: (payload: Record<string, unknown>, token: string, language: string) => request<Volunteer>("/volunteers", { method: "POST", body: JSON.stringify(payload) }, token, language),
  notifications: (token: string, language: string) => request<Notification[]>("/notifications", {}, token, language),
  markRead: (id: number, token: string, language: string) => request<Notification>(`/notifications/${id}/read`, { method: "PATCH" }, token, language),
  trends: (token: string, language: string) => request<Trends>("/analytics/trends", {}, token, language),
  priority: (token: string, language: string) => request<PriorityQueue>("/analytics/priority-queue", {}, token, language),
  knowledge: (token: string, language: string) => request<Knowledge[]>("/knowledge-base", {}, token, language),
  createKnowledge: (payload: { title: string; entry_type: string; content: string; disaster_type?: string; severity?: string; tags: string[] }, token: string, language: string) => request<Knowledge>("/knowledge-base", { method: "POST", body: JSON.stringify(payload) }, token, language),
};

export type Language = { code: string; name: string };
export type User = { id: number; email: string; full_name: string; created_at: string };
export type AuthResponse = { access_token: string; token_type: string; user: User };
export type Report = { id: number; disaster_type: string; latitude: number; longitude: number; magnitude: number; affected_population: number; predicted_impact_score?: number; current_status?: string; created_at: string; temperature?: number; humidity?: number; wind_speed?: number };
export type Prediction = { predicted_impact_score: number; estimated_requirements: Record<string, number> };
export type Allocation = { nearest_warehouse_name: string; nearest_warehouse_distance_km: number; allocation_status: string; allocations: Record<string, { required: number; allocated: number; shortage: number }> };
export type TimelineItem = { id: number; status: string; note?: string; created_at: string };
export type RoutePlan = { warehouse_name: string; warehouse_state: string; distance_km: number; duration_minutes: number; estimated_arrival_at: string; route_safety_status: string; geometry?: { coordinates: [number, number][] } | null };
export type ShelterData = { affected_population: number; allocated_people: number; waiting_people: number; shelters: { shelter_id: string; name: string; distance_km: number; available_capacity: number; allocated_people: number }[] };
export type Reservation = { id: number; status: string; note?: string; created_at: string; allocation_status?: string; allocations?: Allocation["allocations"]; items: { resource: string; quantity: number; warehouse_name: string }[] };
export type Team = { id: number; team_number: string; skills: string; vehicles?: string; tags?: string; status: string; member_count: number; created_at: string };
export type VehicleTracking = { id: number; report_id: number; team_id: number; team_number: string; latitude: number; longitude: number; progress_percent: number; route_status: string; reroute_count: number; speed_kmph: number; estimated_arrival_at?: string; route_geometry?: { coordinates: [number, number][] } | null; updated_at: string };
export type RoadRisk = { id: number; report_id: number; team_id: number; risk_type: string; severity: string; road_name?: string; description: string; latitude: number; longitude: number; status: string; created_at: string };
export type Warehouse = { warehouse_id: string; warehouse_name: string; state: string; latitude: number; longitude: number; inventory: { resource: string; available_quantity: number }[] };
export type StockItem = { resource?: string; available_quantity?: number; warehouse_name?: string; [key: string]: unknown };
export type Volunteer = { id: number; name: string; email: string; phone: string; skill: string; availability: string };
export type Notification = { id: number; report_id?: number; notification_type: string; title: string; message: string; is_read: boolean; created_at: string };
export type Trends = { total_reports: number; predicted_reports: number; average_impact_score?: number; total_affected_population: number; disaster_type_breakdown: { disaster_type: string; report_count: number; average_impact_score?: number }[] };
export type PriorityQueue = { total_reports: number; items: { report_id: number; disaster_type: string; priority_score: number; severity: string; current_status: string; affected_population: number }[] };
export type Knowledge = { id: number; title: string; entry_type: string; content: string; disaster_type?: string; severity?: string; tags: string[]; created_at?: string };
