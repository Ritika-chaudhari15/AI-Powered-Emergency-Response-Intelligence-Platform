# System Architecture: AI-Based Disaster Response Management System

**Last Updated:** 2026-07-27

## Table of Contents

1. [System Overview](#system-overview)
2. [Module Inventory](#module-inventory)
3. [Entry Points](#entry-points)
4. [Architecture Diagram](#architecture-diagram)
5. [Critical Data Flows](#critical-data-flows)
6. [Module Deep Dives](#module-deep-dives)
7. [Cross-Cutting Concerns](#cross-cutting-concerns)
8. [Known Coupling & Fragility](#known-coupling--fragility)
9. [External Dependencies](#external-dependencies)
10. [Environment & Configuration](#environment--configuration)

---

## System Overview

The **AI-Based Disaster Response Management System** is a full-stack platform combining geospatial data aggregation, machine learning impact prediction, and warehouse-based resource allocation to support emergency response coordination. Field teams and disaster responders use the web interface to report events; the backend auto-enriches reports with real-time weather and infrastructure data, predicts disaster impact, and recommends resource allocation from distributed warehouses.

The architecture segregates concerns into: **authentication layer** (JWT + token revocation), **disaster event lifecycle** (state machine from reported → assessed → allocated → dispatched → completed), **real-time enrichment** (weather APIs, OSM queries, population estimation), **impact prediction** (pre-trained sklearn pipelines), and **resource orchestration** (nearest-warehouse allocation + shelter recommendations). Frontend state is managed via React Context; backend services layer decouples route handlers from data retrieval and ML logic.

Data persists in PostgreSQL. External integrations include Open-Meteo (weather), Overpass API (infrastructure), OSRM (routing), and WorldPop / USGS / GDACS (historical enrichment via offline datasets). ML models are static joblib pickles loaded once and reused; inventory and shelter data are CSV/Parquet files read on-demand.

---

## Module Inventory

| Module/Folder | Purpose | Load-Bearing Components |
|---|---|---|
| `backend/app/` | FastAPI service; entry point: `main.py` | Authentication, routing, ORM models, dependency injection |
| `backend/app/routers/` | 8 API endpoint groups (auth, users, predictions, allocations, disaster reports, warehouses, notifications, updates) | Each router depends on services & DB |
| `backend/app/routers/auth.py` | User registration, login, logout (JWT token issuance & revocation) | POST /register, /login, /logout |
| `backend/app/routers/users.py` | Profile get/update | GET/PATCH /me |
| `backend/app/routers/predictions.py` | Direct impact prediction without report (ML inference endpoint) | POST /impact |
| `backend/app/routers/allocations.py` | Direct resource allocation without report (warehouse allocation endpoint) | POST / |
| `backend/app/routers/disaster_reports.py` | Full disaster lifecycle: create, list, predict, allocate, status, timeline, routing, shelters (most complex router) | POST /, GET /, GET /{id}, POST /{id}/predict, POST /{id}/allocate, PATCH /{id}/status, GET /{id}/timeline, GET /{id}/route, GET /{id}/shelters |
| `backend/app/routers/warehouses.py` | List all warehouses with inventory | GET / |
| `backend/app/routers/notifications.py` | List notifications, mark as read | GET /, PATCH /{id}/read |
| `backend/app/routers/updates.py` | Server-Sent Events stream for real-time lifecycle & notification updates | GET /stream |
| `backend/app/services/` | Business logic & data access (10 specialized services) | `model_service` (ML), `allocation_service` (resource), `realtime_data_service` (enrichment), `route_service`, `shelter_service` |
| `backend/app/models.py` | SQLAlchemy ORM: User, RevokedToken, DisasterReport, DisasterLifecycleEvent, Notification (5 tables) | Defines DB schema; FK constraints enforce data integrity |
| `backend/app/database.py` | Session factory, engine, Base declarative class | Connection pooling, transaction context |
| `backend/app/config.py` | Settings singleton (JWT secret, DB URL, token expiry) | Loaded once; mutable config requires restart |
| `backend/app/security.py` | Password hashing (argon2), JWT issuance & validation | Signature key must match across all instances |
| `backend/app/dependencies.py` | FastAPI dependency injection for auth, current user, token extraction | Used in every protected route |
| `frontend/src/` | React + Vite SPA | 7 pages, 1 context provider, 12 reusable components |
| `frontend/src/context/AuthContext.jsx` | Global auth state, token persistence, session recovery, token validation on mount | localStorage-backed; clears on 401 |
| `frontend/src/modules/auth/authApi.js` | Auth API client (register, login, logout, profile get/update) | Wraps axios; returns promises |
| `frontend/src/modules/reports/reportsApi.js` | Disaster reports API client (create, list, get, predict, allocate, status, timeline) | Wraps axios |
| `frontend/src/modules/allocation/allocationApi.js` | Manual resource allocation API client | Wraps axios |
| `frontend/src/modules/warehouses/warehouseApi.js` | Warehouse list + client-side aggregation (findLowStock, aggregateStockByResource) | Wraps axios |
| `frontend/src/services/api.js` | Axios interceptor; sets Bearer token, catches 401 → logout | Singleton; global unauthorized handler |
| `frontend/src/pages/` | 7 main pages (Login, Register, Resources, ResourceAllocation, ResourceShortages, Predictions, Profile) | Each page imports modules + components |
| `frontend/src/components/` | 12 reusable UI components (Badge, Button, Card, Input, Table, ProtectedRoute, Sidebar, etc.) | Used across multiple pages |
| `models/` | Pre-trained impact models (joblib pickles); feature engineering scripts | Models are immutable; predictions require exact feature column order |
| `datasets/` | CSV/Parquet inventory, shelters, historical disaster events | Read-only from services; no in-app mutate |
| `notebooks/` | Jupyter ETL & EDA (data preprocessing, GDACS API, WorldPop, USGS, OpenMeteo) | Generate training data & pre-computed feature sets |
| `tests/` | User & auth lifecycle test suite | SQLite in-memory DB override |

---

## Entry Points

### Backend

**Primary Entry:** [`backend/app/main.py`](backend/app/main.py)

```python
app = FastAPI(title="Disaster Response API", version="1.0.0", lifespan=lifespan)
# Database tables created on startup (lifespan context manager)
# 8 routers registered: auth, users, predictions, allocations, warehouses, disaster_reports, notifications, updates
# CORS allows: http://localhost:3000, http://127.0.0.1:3000, http://localhost:5173, http://127.0.0.1:5173
```

**Launch command:**
```bash
cd backend
uvicorn app.main:app --reload
```

Environment dependencies: `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` (see [config.py](backend/app/config.py))

**Legacy entry (unused in production):** [`backend/app.py`](backend/app.py) — old monolithic FastAPI blueprint; superseded by modular backend/app/ structure.

### Frontend

**Entry Point:** [`frontend/src/main.jsx`](frontend/src/main.jsx) → renders `<App />` to `#root` in [`index.html`](frontend/index.html)

**App Root:** [`frontend/src/App.jsx`](frontend/src/App.jsx)
- Wraps all routes in `<AuthProvider>`
- Public routes: `/login`, `/register`
- Protected routes (require token): `/`, `/resources`, `/resource-allocation`, `/resource-shortages`, `/predictions`, `/profile`
- ProtectedRoute component enforces redirect to login if token missing

**Launch command:**
```bash
cd frontend
npm install
npm run dev  # Vite dev server on http://localhost:5173
```

---

## Architecture Diagram

```mermaid
graph TB
    subgraph Frontend["Frontend (React/Vite)"]
        Browser["Browser<br/>(http://localhost:5173)"]
        AuthCtx["AuthContext<br/>(user, token, login/logout)"]
        Pages["Pages<br/>(Resources, Allocation, Predictions, Profile)"]
        API["api.js (Axios)"]
    end

    subgraph Backend["Backend (FastAPI)"
        Main["main.py<br/>(CORS, lifespan, routers)"]
        
        subgraph Routers["Routers"]
            AuthR["auth.py<br/>(register, login, logout)"]
            UserR["users.py<br/>(get profile, update)"]
            PredR["predictions.py<br/>(POST /impact)"]
            AllocR["allocations.py<br/>(allocate resources)"]
            DisR["disaster_reports.py<br/>(CRUD, predict, allocate, status)"]
            WarR["warehouses.py<br/>(list warehouses)"]
            NotR["notifications.py<br/>(list, mark read)"]
            UpdatesR["updates.py<br/>(SSE stream)"]
        end

        subgraph Services["Services"]
            Auth["model_service<br/>(load sklearn pipeline)"]
            Alloc["allocation_service<br/>(haversine, warehouse sort)"]
            Real["realtime_data_service<br/>(weather, infrastructure)"]
            Lifecycle["lifecycle_service<br/>(FSM: reported → completed)"]
            DupReport["duplicate_report_service<br/>(spatial+temporal matching)"]
            Notif["notification_service<br/>(create, publish SSE)"]
            Live["live_update_service<br/>(in-memory event queue)"]
            Route["route_service<br/>(OSRM routing)"]
            Shelter["shelter_service<br/>(recommend shelters)"]
            ResPlan["resource_planning_service<br/>(calc requirements)"]
        end

        DB["PostgreSQL"]
        Models["joblib pickles<br/>(impact_prediction_model.pkl)"]
        Inventory["inventory.csv<br/>(warehouse stocks)"]
        Shelters["shelter_infrastructure.parquet"]
    end

    subgraph External["External Services"]
        OpenMeteo["Open-Meteo API<br/>(weather data)"]
        Overpass["Overpass API<br/>(OSM infrastructure)"]
        OSRM["OSRM Router<br/>(routing)"]
    end

    Browser -->|HTTP requests| Main
    Main --> AuthR & UserR & PredR & AllocR & DisR & WarR & NotR & UpdatesR
    AuthR --> Auth & Lifecycle & Notif & DB
    UserR --> DB
    PredR --> Auth
    AllocR --> Alloc & Inventory
    DisR --> Real & DupReport & Lifecycle & Notif & Auth & ResPlan & Alloc & Route & Shelter
    WarR --> Alloc & Inventory
    NotR --> DB
    UpdatesR --> Live
    
    AuthCtx --> API
    Pages --> API
    API -->|Bearer token| Routers

    Real -->|fetch| OpenMeteo & Overpass
    Alloc -->|calc distance| Inventory
    Route -->|query| OSRM
    Auth -->|load| Models

    Lifecycle --> Live
    Notif --> Live & DB
    DB -.->|ORM session| Services

    style Frontend fill:#e1f5ff
    style Backend fill:#fff3e0
    style External fill:#f3e5f5
```

---

## Critical Data Flows

### Flow 1: User Registration → Login → Authenticated API Call

**Chain of files & functions:**

1. **Frontend:** User fills register form → calls [`authApi.register()`](frontend/src/modules/auth/authApi.js) → POST `/api/v1/auth/register`
   - **Request schema:** `{ email: EmailStr, full_name: str (2-120 chars), password: str (8-128 chars) }`
   - **Response schema:** `UserResponse` with id, email, full_name, created_at
2. **Backend Route:** [`auth.py:register()`](backend/app/routers/auth.py#L16)
   - Normalizes email to lowercase
   - Validates email uniqueness via `db.scalar(select(User).where(User.email == email))`
   - Hashes password via [`security.hash_password()`](backend/app/security.py#L12) using argon2 (recommended params)
   - Creates User ORM record; returns 409 Conflict if duplicate email
3. **ORM:** `User` record inserted into `users` table via SQLAlchemy with UNIQUE constraint on email
4. **Frontend:** Stores user in AuthContext state → `setUser(data.user)`
5. **Frontend:** User enters credentials → calls [`authApi.login()`](frontend/src/modules/auth/authApi.js) → POST `/api/v1/auth/login`
   - **Request schema:** `{ email: EmailStr, password: str (1-128 chars) }`
   - **Response schema:** `TokenResponse` with access_token, token_type="bearer", user object
6. **Backend Route:** [`auth.py:login()`](backend/app/routers/auth.py#L35)
   - Queries `User` by email (case-insensitive)
   - Calls [`security.verify_password()`](backend/app/security.py#L16) for constant-time password comparison
   - Returns 401 if credentials invalid
   - Creates JWT via [`security.create_access_token()`](backend/app/security.py#L22):
     - Payload: `{ sub: str(user_id), jti: str(uuid4()), exp: now + 60min }`
     - Signed with `JWT_SECRET_KEY` (HS256 algorithm)
7. **Response:** `TokenResponse` returned to frontend
8. **Frontend:** Stores token in localStorage via `localStorage.setItem("access_token", data.access_token)`
   - [`AuthContext.jsx`](frontend/src/context/AuthContext.jsx) updates `setToken(data.access_token)` + `setUser(data.user)`
   - Validates token on app mount by calling `authApi.getProfile()` → GET `/api/v1/users/me` (recovers session)
9. **API Interceptor:** [`api.js`](frontend/src/services/api.js) injects Bearer token in all subsequent requests:
   ```javascript
   request.headers.Authorization = `Bearer ${localStorage.getItem("access_token")}`
   ```
10. **Backend Dependency Injection:** Every protected route calls [`dependencies.get_current_token()`](backend/app/dependencies.py#L16)
    - Extracts token from `Authorization: Bearer <token>` header via HTTPBearer scheme
    - Decodes JWT using same secret & algorithm (HS256)
    - Checks token not in `revoked_tokens` table by querying `db.scalar(select(RevokedToken).where(RevokedToken.jti == jti))`
    - Validates user still exists in DB: `db.get(User, user_id)`
    - Returns dict: `{ payload, token }` or raises 401
    - Chained dependency: [`dependencies.get_current_user()`](backend/app/dependencies.py#L29) resolves to `User` object
11. **Logout:** Frontend calls [`authApi.logout()`](frontend/src/modules/auth/authApi.js) → POST `/api/v1/auth/logout` (Bearer token required)
12. **Backend:** [`auth.py:logout()`](backend/app/routers/auth.py#L46)
    - Extracts JWT payload + jti from token
    - Inserts `RevokedToken(jti=payload["jti"], user_id=payload["sub"], expires_at=payload["exp"])` into DB
    - Returns `{ message: "Logged out successfully" }`
    - Even if API call fails, frontend clears session anyway (resilient to network errors)
13. **Frontend:** AuthContext calls `clearSession()` which:
    - Removes token from localStorage
    - Resets user, token, status → "signed-out"
    - Redirects to `/login` page

**Error Handling:**
- 409 Conflict: duplicate email on registration
- 401 Unauthorized: wrong password, expired/revoked token, user not found
- 422 Unprocessable Entity: Pydantic validation failure (e.g., email format, password length)

**Potential failure points:**
- If `JWT_SECRET_KEY` differs between instances, tokens decode as invalid → 401
- If DB connection drops, `get_current_token()` fails → 500 (not graceful)
- If clock skew > token expiry, valid tokens rejected (or expired tokens accepted if clock goes backwards)
- Race condition: logout token revocation is not atomic with DB transaction

---

### Flow 2: Disaster Report → Impact Prediction → Resource Allocation → Routing & Shelters

**Chain of files & functions:**

1. **Frontend:** Field team inputs disaster (type, lat/lon, magnitude, population) via [`ReportForm.jsx`](frontend/src/pages/resources/)
   - **Request schema:** `DisasterReportCreate` with disaster_type (2-50 chars), latitude (-90..90), longitude (-180..180), magnitude (>0, ≤15), affected_population (>0)
   - Calls [`reportsApi.createReport()`](frontend/src/modules/reports/reportsApi.js) → POST `/api/v1/disaster-reports`

2. **Backend Route:** [`disaster_reports.py:create_disaster_report()`](backend/app/routers/disaster_reports.py#L36)
   - Calls [`duplicate_report_service.find_duplicate_report()`](backend/app/services/duplicate_report_service.py#L29)
     - Queries DB for reports in last 30 minutes
     - Checks: case-insensitive disaster_type match + distance ≤ 2km + magnitude ± 0.5
     - Returns 409 Conflict if duplicate found with existing_report_id
   
3. **Enrichment Phase (3 parallel calls, but sequential in code):**
   - **Weather:** Calls [`realtime_data_service.get_current_weather(latitude, longitude)`](backend/app/services/realtime_data_service.py#L13)
     - HTTP GET `https://api.open-meteo.com/v1/forecast?latitude=...&longitude=...&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m`
     - Parses JSON response → `{ temperature, humidity, rainfall, wind_speed }`
     - Returns 503 if timeout/unavailable (blocking; no fallback)
   
   - **Weather Score:** Calls [`realtime_data_service.calculate_weather_score(weather)`](backend/app/services/realtime_data_service.py#L28)
     - Formula: `(temp/50 + humidity/100 + rainfall/50) / 3` (all clamped 0-1)
     - Result: 0-1 normalized score
   
   - **Population Density:** Calls [`realtime_data_service.estimate_population_density(affected_population)`](backend/app/services/realtime_data_service.py#L34)
     - Formula: `affected_population / (π × 25²)` (area of 25km radius response zone)
     - Result: float (people per km²)
   
   - **Infrastructure Score:** Calls [`realtime_data_service.get_infrastructure_score(latitude, longitude)`](backend/app/services/realtime_data_service.py#L38)
     - HTTP POST Overpass API query for amenities within 25km: hospitals, clinics, schools, fire_stations
     - URL: `https://overpass-api.de/api/interpreter`
     - Query: `[out:json][timeout:10]; (nwr["amenity"~"hospital|clinic|school|fire_station"](around:25000,lat,lon);); out center;`
     - Returns: `facility_count / 50` (capped 1.0)
     - **Graceful Fallback:** If Overpass fails (timeout, 429, parse error), logs warning + returns 0.5 (neutral score; doesn't block report)

4. **DB Insert:** Creates `DisasterReport` record with all enriched fields:
   ```python
   DisasterReport(
     user_id=user.id,
     disaster_type=payload.disaster_type.strip(),
     latitude=payload.latitude, longitude=payload.longitude,
     magnitude=payload.magnitude,
     affected_population=payload.affected_population,
     temperature=weather["temperature"],
     humidity=weather["humidity"],
     rainfall=weather["rainfall"],
     wind_speed=weather["wind_speed"],
     weather_score=realtime_data_service.calculate_weather_score(weather),
     population_density=estimate_population_density(payload.affected_population),
     infrastructure_score=infrastructure_score,
     predicted_impact_score=None  # Set later
   )
   ```
   - Commits to DB

5. **Initial Lifecycle Event:** Calls [`lifecycle_service.add_event(db, report.id, user.id, "reported", "Disaster report received.", validate_transition=False)`](backend/app/services/lifecycle_service.py#L28)
   - Creates `DisasterLifecycleEvent(report_id, user_id, status="reported", note, created_at=now())`
   - Publishes SSE event via [`live_update_service.publish(user_id, "lifecycle", payload)`](backend/app/services/live_update_service.py#L32)
   - Creates notification via [`notification_service.create_notification(..., "lifecycle", "Disaster Reported", ...)`](backend/app/services/notification_service.py#L7)
   - Returns `DisasterReportResponse` to frontend

6. **Response:** Frontend receives report with all enriched fields; displays in `ReportCard.jsx` with "Predict" button

---

**Impact Prediction Phase (User clicks "Predict Impact"):**

7. **Frontend:** Calls [`reportsApi.predictReport(reportId)`](frontend/src/modules/reports/reportsApi.js) → POST `/api/v1/disaster-reports/{id}/predict`

8. **Backend Route:** [`disaster_reports.py:predict_report()`](backend/app/routers/disaster_reports.py#L117)
   - Retrieves report from DB; checks ownership (report.user_id == current_user.id)
   - Calls [`model_service.predict_impact()`](backend/app/services/model_service.py#L18) with feature dict:
     ```python
     {
       "Magnitude": report.magnitude,
       "WeatherScore": report.weather_score,
       "WindSpeed": report.wind_speed,
       "PopulationDensity": report.population_density,
       "InfrastructureScore": report.infrastructure_score
     }
     ```

9. **ML Inference:** [`model_service.predict_impact(features)`](backend/app/services/model_service.py#L18)
   - Calls [`model_service.load_model()`](backend/app/services/model_service.py#L12) (**LRU-cached, loads once per process**)
   - Path: `notebooks/impact_prediction_model.pkl` (joblib pickle)
   - Builds pandas DataFrame: `pd.DataFrame([[features[col] for col in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)`
   - **Critical:** Exact feature order: `["Magnitude", "WeatherScore", "WindSpeed", "PopulationDensity", "InfrastructureScore"]`
   - Runs: `model.predict(input_frame)[0]` → float (0-100 scale expected)
   - Returns 503 if pickle not found; ValueError if inputs not finite

10. **Post-Prediction Logic:**
    - Updates report: `report.predicted_impact_score = impact_score`
    - Commits to DB
    - If current status == "reported" → auto-transition to "assessed" via `lifecycle_service.add_event(..., status="assessed", note=f"Impact prediction completed: {impact_score:.2f}.")`
    - If impact_score ≥ 70 → creates "severe_impact" notification with high-priority alert
    - Calculates resource requirements via [`resource_planning_service.calculate_requirements(affected_population, disaster_type, impact_score)`](backend/app/services/resource_planning_service.py#L6)

11. **Resource Requirement Calculation:**
    - **Demographics:** children=27%, adults=60%, elderly=13%, critical_patients=5% of affected_population
    - **Severity Multiplier:** 1.25× if impact_score ≥ 70, else 1.0×
    - **3-Day Supply Calculation:**
      ```python
      "Food Packets": ceil(affected_population × 3 meals × 3 days × multiplier)
      "Water Bottles": ceil(affected_population × 5L × 3 days × multiplier)
      "Medical Kits": ceil((children×0.10 + adults×0.05 + elderly×0.15) × multiplier)
      "Blankets": ceil(affected_population × multiplier)
      "Temporary Tents": ceil(affected_population / 5)
      "Rescue Teams": ceil(affected_population / 250)
      "Ambulances": ceil(critical_patients / 4)
      "Boats": ceil(affected_population / 5000) if disaster_type.lower() == "flood" else 0
      "Helicopters": ceil(critical_patients / 400) if impact_score ≥ 70 else 0
      "Trucks": ceil(total_weight_kg / 8000)  # Based on resource weights
      ```
    - Returns dict: `{ "Food Packets": int, "Water Bottles": int, ... }`

12. **Response:** Returns `DisasterPredictionResponse`:
    ```python
    {
      "report": {...full DisasterReportResponse...},
      "predicted_impact_score": float,
      "estimated_requirements": dict[str, int]
    }
    ```
    - Frontend displays in `RequirementsTable.jsx`

---

**Resource Allocation Phase (User clicks "Allocate Resources"):**

13. **Frontend:** Calls [`reportsApi.allocateReport(reportId)`](frontend/src/modules/reports/reportsApi.js) → POST `/api/v1/disaster-reports/{id}/allocate`

14. **Backend Route:** [`disaster_reports.py:allocate_report_resources()`](backend/app/routers/disaster_reports.py#L151)
    - Retrieves report; checks ownership
    - Validates `report.predicted_impact_score is not None` → 409 Conflict if not predicted yet
    - Re-calculates requirements for consistency (deterministic; should match prediction phase)
    - Calls [`allocation_service.allocate_resources(report.latitude, report.longitude, requirements)`](backend/app/services/allocation_service.py#L73)

15. **Warehouse Allocation Logic:**
    - Loads [`datasets/inventory.csv`](datasets/inventory.csv) → pandas DataFrame (columns: WarehouseID, WarehouseName, State, Latitude, Longitude, Resource, AvailableQuantity)
    - Validates all required resources exist in inventory; returns 422 if not
    - For each warehouse: calculates haversine distance from disaster location
    - Sorts warehouses by ascending distance
    - **Greedy Allocation:** For each required resource:
      - remaining = required_quantity
      - For each warehouse (in distance order):
        - available = stock[warehouse_id][resource] or 0
        - quantity_to_allocate = min(remaining, available)
        - If quantity > 0: append to supplies list, decrement remaining
      - Track shortage = remaining (unmet quantity)
    - Returns `ResourceAllocationResponse`:
      ```python
      {
        "nearest_warehouse_id": str,
        "nearest_warehouse_name": str,
        "nearest_warehouse_distance_km": float,
        "allocation_status": "Complete" | "Partial",
        "allocations": {
          "Resource": {
            "required": int,
            "allocated": int,
            "shortage": int,
            "supplies": [
              {"warehouse_id", "warehouse_name", "state", "distance_km", "quantity"}
            ]
          }
        }
      }
      ```

16. **Post-Allocation Logic:**
    - If current status == "assessed" → auto-transition to "allocated"
    - If any shortage detected → creates "shortage" notification
    - Commits DB changes
    - Returns allocation response to frontend
    - Frontend displays in `AllocationResult.jsx`

---

**Route Planning Phase (User clicks "View Route" or page mounts for allocated report):**

17. **Frontend:** Calls [`reportsApi.getRoute(reportId)`](frontend/src/modules/reports/reportsApi.js) (implied) → GET `/api/v1/disaster-reports/{id}/route`

18. **Backend Route:** Not explicitly documented in provided code; assumed to call [`route_service.plan_route(report.latitude, report.longitude)`](backend/app/services/route_service.py#L11)

19. **Route Planning Logic:**
    - Finds nearest warehouse (haversine distance calculation)
    - Attempts to call OSRM routing API: `https://router.project-osrm.org/route/v1/driving/{lon_warehouse},{lat_warehouse};{lon_disaster},{lat_disaster}?overview=full&geometries=geojson`
    - **If OSRM succeeds:**
      - Extracts: distance_km, duration_minutes, geometry (GeoJSON LineString)
      - Sets route_source="osrm"
    - **If OSRM fails (timeout, 429, parse error):**
      - Fallback: distance_km = haversine distance, duration_minutes = distance_km / 50 * 60 (naive 50 km/h estimate)
      - Sets route_source="estimated_fallback"
    - Calculates ETA: `now(UTC) + timedelta(minutes=duration_minutes)`
    - Returns `RoutePlanResponse`:
      ```python
      {
        "warehouse_id": str,
        "warehouse_name": str,
        "warehouse_state": str,
        "distance_km": float,
        "duration_minutes": float,
        "estimated_arrival_at": datetime,
        "route_source": "osrm" | "estimated_fallback",
        "geometry": dict | None  # GeoJSON
      }
      ```

---

**Shelter Recommendation Phase (User clicks "Find Shelters" or page auto-loads):**

20. **Frontend:** Calls implied endpoint (not documented in provided code) → GET `/api/v1/disaster-reports/{id}/shelters?limit=20`

21. **Backend Route:** Assumed to call [`shelter_service.recommend_shelters(report.latitude, report.longitude, report.affected_population, limit=20)`](backend/app/services/shelter_service.py#L11)

22. **Shelter Allocation Logic:**
    - Loads [`datasets/shelter_infrastructure.parquet`](datasets/shelter_infrastructure.parquet) (columns: Latitude, Longitude, EstimatedCapacity, id, name)
    - Calculates distance from disaster to each shelter (haversine)
    - Sorts by distance ascending
    - **Greedy Shelter Allocation:** (similar to warehouse logic)
      - remaining = affected_population
      - For each shelter (top `limit`, in distance order):
        - capacity = EstimatedCapacity or 0
        - allocated = min(remaining, capacity)
        - remaining -= allocated
        - Append to recommendations
      - allocation_status = "Fully Allocated" if remaining == 0 else "Partially Allocated"
    - Returns `ShelterRecommendationResponse`:
      ```python
      {
        "affected_population": int,
        "allocated_people": int,
        "waiting_people": int,
        "allocation_status": str,
        "shelters": [
          {
            "shelter_id": str,
            "name": str,
            "distance_km": float,
            "available_capacity": int,
            "allocated_people": int
          }
        ]
      }
      ```

---

**Dependency chain:** Disaster Report → Weather API + OSM API → Feature enrichment → Model load → ML prediction → Resource calc → Warehouse allocation → Route planning → Shelter recommendation

**Failure modes:**
- Weather API timeout → 503 (blocks report creation; user must retry)
- OSM Infrastructure fails → graceful 0.5 fallback (report creation succeeds)
- Model pickle missing → 503 at prediction time
- Inventory CSV missing → 503 at allocation time
- OSRM routing fails → fallback to haversine + naive duration
- Shelter parquet missing → likely 503 (not gracefully handled)
- Race condition: concurrent allocation requests may over-allocate from same warehouse (no locking; stateless design assumes fresh read each time)

---

### Flow 3: Real-Time Updates via Server-Sent Events (SSE)

**Chain of files & functions:**

1. **Frontend:** Component mounts → calls [`updatesApi.subscribeToUpdates()`](frontend/src/modules/updates/updatesApi.js) → GET `/api/v1/updates/stream` with Bearer token
2. **Backend Route:** [`updates.py:stream_updates()`](backend/app/routers/updates.py#L16)
   - Calls [`live_update_service.subscribe()`](backend/app/services/live_update_service.py#L11) → returns Queue object
   - Starts async event generator
   - Yields `event: connected` frame
   - Loops, calling `queue.get(timeout=15)` in thread pool to avoid blocking
   - On timeout (no messages), yields keep-alive comment
3. **Publish:** When lifecycle event added (e.g., status → "allocated"), code calls [`live_update_service.publish()`](backend/app/services/live_update_service.py#L32)
   - Serializes event + payload to JSON
   - Puts message in all queues subscribed by that user_id
4. **Frontend:** EventSource listener receives SSE frame `event: update`, parses data JSON
   - Updates local state (e.g., add notification card, update disaster status badge)
5. **Cleanup:** Frontend navigates away or browser closes → EventSource closes → finally block calls [`live_update_service.unsubscribe()`](backend/app/services/live_update_service.py#L16) → removes queue from subscribers dict

**Dependency chain:** Lifecycle state change → notification service → live update service → subscriber queues → HTTP SSE stream → frontend event listener

**Failure mode:** If frontend loses connection, SSE reconnect is browser automatic; duplicate event handling on client depends on idempotency (consumer responsibility).

---

## API Endpoint Reference (Complete)

### Authentication Endpoints

| Endpoint | Method | Auth | Request Schema | Response Schema | Status Codes |
|---|---|---|---|---|---|
| `/api/v1/auth/register` | POST | None | `UserRegister` (email, full_name, password) | `UserResponse` | 201 (success), 409 (duplicate email), 422 (validation) |
| `/api/v1/auth/login` | POST | None | `UserLogin` (email, password) | `TokenResponse` (access_token, token_type, user) | 200, 401 (bad credentials), 422 |
| `/api/v1/auth/logout` | POST | Bearer | None | `MessageResponse` | 200, 401 (invalid token), 422 |

### User Endpoints

| Endpoint | Method | Auth | Response Schema | Status Codes |
|---|---|---|---|---|
| `/api/v1/users/me` | GET | Bearer | `UserResponse` | 200, 401 |
| `/api/v1/users/me` | PATCH | Bearer | `UserResponse` (update full_name) | 200, 401, 422 |

### Impact Prediction Endpoints

| Endpoint | Method | Auth | Request Schema | Response Schema | Status Codes |
|---|---|---|---|---|---|
| `/api/v1/predictions/impact` | POST | Bearer | `ImpactPredictionRequest` (5 float features) | `ImpactPredictionResponse` (predicted_impact_score) | 200, 401, 422, 503 (model missing) |

### Resource Allocation Endpoints

| Endpoint | Method | Auth | Request Schema | Response Schema | Status Codes |
|---|---|---|---|---|---|
| `/api/v1/resource-allocation` | POST | Bearer | `ResourceAllocationRequest` (lat, lon, resources dict) | `ResourceAllocationResponse` | 200, 401, 422 (invalid resources), 503 (inventory missing) |
| `/api/v1/warehouses` | GET | Bearer | None | `list[WarehouseResponse]` | 200, 401, 503 (inventory missing) |

### Disaster Reports Endpoints (Complex)

| Endpoint | Method | Auth | Purpose | Request Schema | Response Schema | Status Codes |
|---|---|---|---|---|---|---|
| `/api/v1/disaster-reports` | POST | Bearer | Create report + enrich | `DisasterReportCreate` | `DisasterReportResponse` | 201, 401, 409 (duplicate), 422, 503 (weather API) |
| `/api/v1/disaster-reports` | GET | Bearer | List user's reports | None (newest first) | `list[DisasterReportHistoryItem]` | 200, 401 |
| `/api/v1/disaster-reports/{id}` | GET | Bearer | Get single report + status | None | `DisasterReportHistoryItem` | 200, 401, 404 (not found) |
| `/api/v1/disaster-reports/{id}/timeline` | GET | Bearer | Get all lifecycle events | None | `list[LifecycleEventResponse]` | 200, 401, 404 |
| `/api/v1/disaster-reports/{id}/status` | PATCH | Bearer | Update status (FSM) | `DisasterStatusUpdate` (status, note, eta) | `LifecycleEventResponse` | 200, 401, 404, 409 (invalid transition) |
| `/api/v1/disaster-reports/{id}/predict` | POST | Bearer | Predict impact + calc requirements | None | `DisasterPredictionResponse` | 200, 401, 404, 503 (model missing), 500 (inference error) |
| `/api/v1/disaster-reports/{id}/allocate` | POST | Bearer | Allocate calculated resources | None | `ResourceAllocationResponse` | 200, 401, 404, 409 (not predicted), 503 (inventory missing) |
| `/api/v1/disaster-reports/{id}/route` | GET | Bearer | Plan route to nearest warehouse | None | `RoutePlanResponse` | 200, 401, 404, 503 |
| `/api/v1/disaster-reports/{id}/shelters` | GET | Bearer | Recommend shelters (query: limit=1-100) | None (limit param) | `ShelterRecommendationResponse` | 200, 401, 404, 503 (shelter data missing) |

### Notification Endpoints

| Endpoint | Method | Auth | Query Params | Response Schema | Status Codes |
|---|---|---|---|---|---|
| `/api/v1/notifications` | GET | Bearer | `unread_only: bool` (optional) | `list[NotificationResponse]` (newest first) | 200, 401 |
| `/api/v1/notifications/{id}/read` | PATCH | Bearer | None | `NotificationResponse` (is_read=true) | 200, 401, 404 |

### Live Updates Endpoints

| Endpoint | Method | Auth | Response Format | Keep-Alive | Status Codes |
|---|---|---|---|---|---|
| `/api/v1/updates/stream` | GET | Bearer | Server-Sent Events (text/event-stream) | `: ` every 15s | 200, 401, Stream closed on client disconnect |

**SSE Event Types:**
```
event: connected
data: {"status": "connected"}

event: update
data: {"type": "lifecycle"|"notification", "data": {...}}

: keep-alive
```

---

## Module Deep Dives

### Backend Services Layer

| Service File | Primary Functions | Dependencies | Key Side Effects |
|---|---|---|---|
| [`model_service.py`](backend/app/services/model_service.py) | `load_model()` (cached), `predict_impact(features)` | joblib, pandas, `notebooks/impact_prediction_model.pkl` | FileNotFoundError if model missing; raises ValueError if inputs not finite |
| [`allocation_service.py`](backend/app/services/allocation_service.py) | `load_inventory()`, `list_warehouses()`, `haversine_distance_km()`, `allocate_resources()` | pandas, `datasets/inventory.csv` | Reads CSV every call (no caching); greedy nearest-warehouse algorithm; can return partial shortages |
| [`realtime_data_service.py`](backend/app/services/realtime_data_service.py) | `get_current_weather()`, `calculate_weather_score()`, `estimate_population_density()`, `get_infrastructure_score()` | requests, Open-Meteo API, Overpass API | Calls external HTTP APIs on every report creation; graceful fallback for OSM failure; logs warnings |
| [`lifecycle_service.py`](backend/app/services/lifecycle_service.py) | `current_status()`, `add_event()` | DB session, `live_update_service`, `notification_service` | Validates FSM transitions; publishes SSE; creates notification on state change |
| [`notification_service.py`](backend/app/services/notification_service.py) | `create_notification()` | DB session, `live_update_service` | Inserts Notification record; publishes SSE event immediately (sync) |
| [`live_update_service.py`](backend/app/services/live_update_service.py) | `subscribe()`, `unsubscribe()`, `publish()` | Python Queue (stdlib), json | In-memory; no persistence; messages lost if app restart; subscribers dict mutated globally |
| [`duplicate_report_service.py`](backend/app/services/duplicate_report_service.py) | `distance_km()`, `find_duplicate_report()` | DB session, math/geometry | Queries DB for recent disasters; returns match within 2km radius + 30min window + ±0.5 magnitude |
| [`resource_planning_service.py`](backend/app/services/resource_planning_service.py) | `calculate_requirements()` | math.ceil | Pure function; deterministic; applies demographic percentages + impact-based multiplier |
| [`route_service.py`](backend/app/services/route_service.py) | `plan_route()` | `allocation_service`, requests, OSRM API | Queries OSRM for routing; fallback haversine + naive time estimate if OSRM fails; returns distance, duration, ETA, geometry |
| [`shelter_service.py`](backend/app/services/shelter_service.py) | `recommend_shelters()` | pandas, `datasets/shelter_infrastructure.parquet` | Loads parquet file on every call; greedy allocation by distance; returns up to `limit` shelters |

**Cross-service dependencies:**
- `lifecycle_service` calls `live_update_service` and `notification_service`
- `notification_service` calls `live_update_service`
- `allocation_service` used by `route_service` and `disaster_reports` routes
- All data services read static files without cache (performance risk at scale)

---

### Database Schema

**Tables (5 total):**

| Table | Columns | PKs / FKs | Purpose |
|---|---|---|---|
| `users` | id (PK), email (UNIQUE), full_name, hashed_password, created_at, updated_at | PK: id; UNIQUE: email | User accounts; argon2 hashed passwords |
| `revoked_tokens` | id (PK), jti (UNIQUE), user_id (FK), expires_at, revoked_at | PK: id; FK: user_id → users; UNIQUE: jti | JWT blacklist for logout; indexed by jti for fast lookup |
| `disaster_reports` | id (PK), user_id (FK), disaster_type, lat, lon, magnitude, affected_population, temperature, humidity, rainfall, wind_speed, weather_score, population_density, infrastructure_score, predicted_impact_score (nullable), created_at | PK: id; FK: user_id → users; INDEX: user_id | Core disaster event record; all enriched fields stored for audit trail |
| `disaster_lifecycle_events` | id (PK), report_id (FK), user_id (FK), status, note, estimated_arrival_at, created_at | PK: id; FK: report_id → disaster_reports (CASCADE), user_id → users (CASCADE); INDEX: report_id | Immutable audit log of status transitions; no UPDATE; append-only |
| `notifications` | id (PK), user_id (FK), report_id (FK, nullable), notification_type, title, message, is_read, created_at | PK: id; FK: user_id → users (CASCADE), report_id → disaster_reports (CASCADE); INDEX: user_id | User-visible alerts; read flag for UI; no DELETE (archive instead) |

**Foreign Key Constraints:**
- `disaster_reports.user_id` → `users.id` (no explicit CASCADE; orphan reports if user deleted)
- `revoked_tokens.user_id` → `users.id` (CASCADE DELETE; clean up tokens on user delete)
- `disaster_lifecycle_events.report_id` → `disaster_reports.id` (CASCADE DELETE; events deleted if report deleted)
- `disaster_lifecycle_events.user_id` → `users.id` (CASCADE DELETE; history deleted if user deleted)
- `notifications.user_id` → `users.id` (CASCADE DELETE; all user's notifications deleted)
- `notifications.report_id` → `disaster_reports.id` (SET NULL; notifications orphaned if report deleted, not ideal)

**Indexes:**
- PK indexes (default)
- `disaster_reports.user_id` (for listing user's reports)
- `revoked_tokens.jti` (for logout token validation)
- `disaster_lifecycle_events.report_id` (for timeline queries)
- `notifications.user_id` (for listing user's notifications)

**No transaction isolation issues noted; all operations are user-scoped or immutable-append.**

---

### Frontend State Management

**AuthContext** ([`AuthContext.jsx`](frontend/src/context/AuthContext.jsx)):

```javascript
const [user, setUser] = useState(null);                       // Current user object
const [token, setToken] = useState(() => ...localStorage);    // JWT from storage
const [status, setStatus] = useState("checking" | "signed-in" | "signed-out");
```

**Lifecycle:**
1. App mounts → status = token ? "checking" : "signed-out"
2. If token in storage → call `/api/v1/users/me` to validate
3. If 401 or network error → `clearSession()` (logout)
4. `login()` → stores token + user in context + localStorage
5. `logout()` → calls `/api/v1/auth/logout`, clears both
6. Unauthorized handler ([`api.js`](frontend/src/services/api.js) interceptor) calls `clearSession()` on any 401

**localStorage keys:**
- `access_token` (JWT string; persisted across page reloads)

**Risks:**
- localStorage is XSS-vulnerable; token can be stolen by malicious script injected into page
- No refresh token; if token expires during session, user forced to re-login
- Token TTL hardcoded server-side (60 min by default); frontend has no knowledge of expiry

---

### Frontend Pages & Components

**Main Pages (7 Total)**

| Page | Route | Auth Required | Purpose | Key Components | API Calls |
|---|---|---|---|---|---|
| Login | `/login` | No | Email + password authentication | Form, error display | `authApi.login()` → POST `/api/v1/auth/login` |
| Register | `/register` | No | Account creation | Form, validation display | `authApi.register()` → POST `/api/v1/auth/register` |
| Resources | `/resources` | Yes | Main dashboard: disaster reports CRUD | `ReportForm` (create), `ReportCard` (list with predict/allocate buttons), `RequirementsTable` | `reportsApi.createReport()`, `listReports()`, `predictReport()`, `allocateReport()` |
| Resource Allocation | `/resource-allocation` | Yes | Manual allocation (no report needed) | , `AllocationResult` | `allocationApi.allocateManually()` → POST `/api/v1/resource-allocation` |
| Resource Shortages | `/resource-shortages` | Yes | Inventory analysis | Warehouse filter, low-stock table | `warehouseApi.getWarehouses()`, client-side heuristic (findLowStock: <25% avg) |
| Predictions | `/predictions` | Yes | Direct impact prediction | Direct form (5 features), result display | `api.post("/api/v1/predictions/impact")` → POST `/api/v1/predictions/impact` |
| Profile | `/profile` | Yes | User info + update | Display user data, edit full_name form | `authApi.getProfile()`, `updateProfile()` |

**Reusable Components (12 Total)**

| Component | Purpose | Props | Usage |
|---|---|---|---|
| `Badge.jsx` | Status badge with color coding | status (reported, assessed, allocated, dispatched, completed) | Disaster report cards, timeline |
| `Button.jsx` | Styled button | variant, disabled, onClick | Forms, CTA buttons |
| `Card.jsx` | Container component | children, className | Report cards, result panels |
| `Container.jsx` | Page wrapper | children | All pages (max-width, margin) |
| `ErrorMessage.jsx` | Inline error alert | message, closeable | Form validation errors |
| `Input.jsx` | Form input wrapper | type, label, value, onChange, error | All forms |
| `Loading.jsx` | Spinner/skeleton | type (skeleton, spinner) | Async operations |
| `Popup.jsx` | Modal dialog | title, children, onClose, onConfirm | Confirmations, details |
| `ProgressBar.jsx` | Resource allocation progress vis | allocated, required, shortage | Allocation results |
| `ProtectedRoute.jsx` | Auth guard wrapper | children | Wraps all protected routes; redirects to /login if no token |
| `Sidebar.jsx` | Navigation menu | activeRoute | All authenticated pages; links to all routes |
| `Table.jsx` | Data table | columns, rows, onRowClick | Notifications, warehouses, shortages |

**ProtectedRoute** component wraps authenticated routes; if no token, redirects to `/login`.

### Frontend Page Components

| Page | Route | Purpose | API Calls |
|---|---|---|---|
| Login | `/login` | Email + password form → calls `authApi.login()` | POST `/api/v1/auth/login` |
| Register | `/register` | Email + full name + password form → calls `authApi.register()` | POST `/api/v1/auth/register` |
| Resources | `/resources` | List warehouses + inventory (read-only reference) | GET `/api/v1/warehouses` |
| Resource Allocation | `/resource-allocation` | Input lat/lon + required quantities → allocate from warehouses | POST `/api/v1/resource-allocation` |
| Resource Shortages | `/resource-shortages` | (Not implemented; TODO) | — |
| Predictions | `/predictions` | Manual impact prediction (input 5 features) → calls model | POST `/api/v1/predictions/impact` |
| Profile | `/profile` | View user email + update full name | GET `/api/v1/users/me`, PATCH `/api/v1/users/me` |

---

### ML Models

**Impact Prediction Model:**

- **Path:** [`notebooks/impact_prediction_model.pkl`](notebooks/impact_prediction_model.pkl)
- **Type:** Pre-trained sklearn pipeline (likely DecisionTree or composite estimator)
- **Input features (exact order required):** `["Magnitude", "WeatherScore", "WindSpeed", "PopulationDensity", "InfrastructureScore"]`
- **Output:** float (predicted impact score, likely 0–100 or 0–1 normalized)
- **Loaded by:** [`model_service.load_model()`](backend/app/services/model_service.py#L12) with `@lru_cache` decorator (singleton per process)
- **Inference:** [`model_service.predict_impact()`](backend/app/services/model_service.py#L18) → pandas DataFrame → pipeline.predict() → first element
- **Training:** [`models/train_decision_tree.py`](models/train_decision_tree.py) and [`models/train_xgboost.py`](models/train_xgboost.py) reference; final model path in production is `notebooks/impact_prediction_model.pkl`

**Feature Engineering Pipeline:**

1. **Magnitude:** User input (1–15 scale for earthquakes)
2. **WeatherScore:** Computed from temp + humidity + rainfall (0–1 normalized)
3. **WindSpeed:** Open-Meteo API fetch (km/h)
4. **PopulationDensity:** Affected population / (π × 25²) km² area
5. **InfrastructureScore:** Nearby OSM facilities / 50 (capped 1.0), or 0.5 fallback

**Resource Requirement Models:**

Three separate decision-tree regressors for:
- [`models/Ambulances_Required_DecisionTree.joblib`](models/Ambulances_Required_DecisionTree.joblib)
- [`models/Rescue_Teams_Required_DecisionTree.joblib`](models/Rescue_Teams_Required_DecisionTree.joblib)
- [`models/Water_Required_Liters_DecisionTree.joblib`](models/Water_Required_Liters_DecisionTree.joblib)

**Currently unused** by the web service; legacy from scripting phase. Web service uses deterministic [`resource_planning_service.calculate_requirements()`](backend/app/services/resource_planning_service.py) instead.

---

## Cross-Cutting Concerns

### Authentication & Authorization

**JWT Implementation:**
- **Issuance:** [`security.create_access_token()`](backend/app/security.py#L22) → payload `{ sub: user_id, jti: uuid, exp: now + expiry }` → encoded with `JWT_SECRET_KEY` using HS256
- **Validation:** [`dependencies.get_current_token()`](backend/app/dependencies.py#L16) → decode, check jti not blacklisted, user exists
- **User extraction:** [`dependencies.get_current_user()`](backend/app/dependencies.py#L29) → call `get_current_token()`, then db.get(User, user_id)
- **Logout:** Insert jti into `revoked_tokens` table with expiry; on next request, jti lookup rejects token

**Password Security:**
- **Hashing:** [`security.hash_password()`](backend/app/security.py#L12) → `pwdlib` with argon2 (recommended params)
- **Verification:** [`security.verify_password()`](backend/app/security.py#L16) → constant-time comparison

**Frontend Auth Handling:**
- **Token storage:** localStorage (XSS-vulnerable; best-effort defense: no token in cookies)
- **Interceptor:** [`api.js`](frontend/src/services/api.js) adds `Authorization: Bearer <token>` to all requests
- **Session recovery:** On app startup, if token in localStorage, validate via GET `/api/v1/users/me`; if 401, clear session

**Scope & Assumptions:**
- All endpoints (except /login, /register, /health) require Bearer token
- User can only access their own data (own disaster reports, own notifications)
- No role-based access control (all authenticated users are equivalent)
- No multi-tenant isolation (single shared DB)

---

### Error Handling

**Backend:**
- `HTTPException(status_code=...)` raised by route handlers; FastAPI serializes as JSON error response
- Common codes:
  - `400 Bad Request`: Invalid input (e.g., resource quantities negative)
  - `401 Unauthorized`: Missing/invalid/expired token
  - `403 Forbidden`: (Not used; no authorization layer)
  - `404 Not Found`: Resource not found (e.g., report_id doesn't exist or not owned by user)
  - `409 Conflict`: Business logic conflict (duplicate report, invalid status transition)
  - `422 Unprocessable Entity`: Validation error (Pydantic schema mismatch)
  - `503 Service Unavailable`: External API failure (weather, OSM, model file) or data file missing

**Frontend:**
- Axios interceptor ([`api.js`](frontend/src/services/api.js)) catches 401 → calls `clearSession()` → redirect to login
- Route handlers (pages) call `.catch()` on promises; typically log error + show toast notification (not implemented in current codebase; improvement needed)
- No try-catch in most page components; unhandled errors may cause white screen

**Logging:**
- Backend: `logging.getLogger(__name__)` used in [`realtime_data_service.py`](backend/app/services/realtime_data_service.py) for OSM API failures; otherwise no structured logging
- Frontend: No centralized logging; errors silent or console.log

---

### Configuration & Environment Variables

**Backend:** ([`config.py`](backend/app/config.py)) — Pydantic `BaseSettings` with defaults:

| Env Var | Default | Purpose | Read By |
|---|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/disaster_response` | PostgreSQL connection string | `database.py` → `create_engine()` |
| `JWT_SECRET_KEY` | `"change-this-to-a-long-random-secret-before-production"` | HMAC key for JWT signing | `security.py` → `create_access_token()`, `dependencies.py` → decode |
| `JWT_ALGORITHM` | `"HS256"` | JWT algorithm | `security.py`, `dependencies.py` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT expiry time | `security.py` → timedelta(minutes=...) |

**Frontend:** (hardcoded URLs in components & api.js)
- **Base API URL:** Assumed to be `http://localhost:8000` or inferred from current origin; no explicit env var loading
- **CORS allowed origins:** Backend config hard-codes localhost ports 3000 + 5173

**Loaded via:**
- Backend: Pydantic reads .env file (if exists) or env vars; see [`pydantic_settings.BaseSettings`](https://docs.pydantic.dev/latest/api/base_settings/)
- Frontend: No env var loading; hardcoded or injected at build time (not configured in current Vite setup)

---

### Data Validation & Constraints

**Pydantic Schemas:**

| Schema | Constraints | Used By |
|---|---|---|
| `UserRegister` | email (valid), full_name (2–120 chars), password (8–128 chars) | POST `/api/v1/auth/register` |
| `UserLogin` | email (valid), password (1–128 chars) | POST `/api/v1/auth/login` |
| `UserUpdate` | full_name (2–120 chars) | PATCH `/api/v1/users/me` |
| `ImpactPredictionRequest` | 5 float fields, must be finite numbers | POST `/api/v1/predictions/impact` |
| `ResourceAllocationRequest` | lat (±90), lon (±180), required_resources (dict with ≥1 entry, all ≥0) | POST `/api/v1/resource-allocation` |
| `DisasterReportCreate` | type (2–50 chars), lat (±90), lon (±180), magnitude (>0, ≤15), population (>0) | POST `/api/v1/disaster-reports` |
| `DisasterStatusUpdate` | status (enum: reported\|assessed\|allocated\|dispatched\|completed), note (≤500 chars), estimated_arrival_at (datetime, nullable) | PATCH `/api/v1/disaster-reports/{id}/status` |

**Database Constraints (SQLAlchemy):**
- `User.email`: UNIQUE, NOT NULL, indexed
- `RevokedToken.jti`: UNIQUE, NOT NULL, indexed
- `DisasterReport.user_id`: NOT NULL, FK (no cascade)
- `DisasterLifecycleEvent`: report_id + user_id both NOT NULL, FKs with CASCADE
- `Notification.user_id`: NOT NULL, FK with CASCADE

**Business Logic Constraints:**
- Duplicate detection: within 2km + 30min window + ±0.5 magnitude (see [`duplicate_report_service.py`](backend/app/services/duplicate_report_service.py))
- Lifecycle FSM: valid transitions enforced in [`lifecycle_service.add_event()`](backend/app/services/lifecycle_service.py#L28); invalid transition → ValueError → 409 Conflict
- Resource allocation: greedy nearest-warehouse algorithm; can return partial shortages (OK)

---

## Known Coupling & Fragility

### 1. **Tight coupling: ML model feature order**
   - **Where:** [`model_service.predict_impact()`](backend/app/services/model_service.py#L15) hardcodes feature column order
   - **Risk:** If model pickle retrains with different feature names/order, predictions silently wrong or crash with KeyError
   - **Fix:** Add feature metadata to pickle (e.g., versioned wrapper class)
   - **Brittleness Score:** 🔴 HIGH — silent failure mode

### 2. **Data file dependencies: Inventory CSV must exist**
   - **Where:** [`allocation_service.load_inventory()`](backend/app/services/allocation_service.py#L22) reads `datasets/inventory.csv`
   - **Risk:** If CSV missing, all allocation endpoints return 503; no fallback data source
   - **Observation:** File path is relative-to-module, so running tests from different dir may fail
   - **Fix:** Use environment variable or config path; ship default inventory with app
   - **Brittleness Score:** 🟡 MEDIUM — affects all resource allocation

### 3. **Shelter data: Parquet file optional, but allocation silently fails**
   - **Where:** [`shelter_service.recommend_shelters()`](backend/app/services/shelter_service.py#L11) expects `datasets/shelter_infrastructure.parquet`
   - **Risk:** If file missing, 503 (not used by web routes yet; TODO feature)
   - **Observation:** `/disaster-reports/{id}/predict` route calls shelter_service indirectly (not used in current frontend)
   - **Brittleness Score:** 🟡 MEDIUM — not critical path yet

### 4. **External API: Open-Meteo weather mandatory for report creation**
   - **Where:** [`realtime_data_service.get_current_weather()`](backend/app/services/realtime_data_service.py#L13) called during report creation
   - **Risk:** If API unavailable, disaster report cannot be filed (503); no offline mode
   - **Observation:** Infrastructure score has fallback 0.5; weather does not
   - **Fix:** Implement cached weather fallback; allow user to input weather manually
   - **Brittleness Score:** 🔴 HIGH — blocks critical user flow

### 5. **Overpass API: OSM queries unreviewed for correctness**
   - **Where:** [`realtime_data_service.get_infrastructure_score()`](backend/app/services/realtime_data_service.py#L38) posts Overpass query
   - **Risk:** Query may not match intended schema (hospitals, clinics, etc.); counts may be inflated/deflated
   - **Observation:** Has fallback 0.5; graceful degradation OK
   - **Fix:** Query validation + unit test with mock response
   - **Brittleness Score:** 🟡 MEDIUM — gracefully handled

### 6. **In-memory SSE queue: No persistence, limited capacity**
   - **Where:** [`live_update_service.py`](backend/app/services/live_update_service.py#L6) uses Python Queue (FIFO, in-memory)
   - **Risk:** If backend restarts, all queued messages lost; if queue fills, `put()` blocks (unlikely at small scale)
   - **Observation:** Frontend EventSource reconnects; missed events not replayed
   - **Fix:** Use Redis Pub/Sub or database-backed message queue for multi-instance deployment
   - **Brittleness Score:** 🟡 MEDIUM — acceptable for single-instance dev; breaks at scale

### 7. **Circular data enrichment: Weather + infrastructure score required before report stored**
   - **Where:** [`disaster_reports.py:create_disaster_report()`](backend/app/routers/disaster_reports.py#L36) calls both APIs before DB commit
   - **Risk:** If one API times out, entire report creation fails; partial enrichment not allowed
   - **Observation:** Could decouple: store report, enrich async, update later
   - **Fix:** Queue enrichment tasks; allow report creation without full enrichment
   - **Brittleness Score:** 🟡 MEDIUM — user-facing latency + failure rate risk

### 8. **Duplicate detection: Spatial accuracy unvalidated**
   - **Where:** [`duplicate_report_service.find_duplicate_report()`](backend/app/services/duplicate_report_service.py#L29) uses haversine; threshold 2km
   - **Risk:** Haversine approximation; threshold chosen arbitrarily (no justification in code)
   - **Observation:** Prevents accidental re-reports but may reject valid nearby disasters
   - **Fix:** Document threshold rationale; consider user feedback loop
   - **Brittleness Score:** 🟡 MEDIUM — business logic, not security-critical

### 9. **Resource requirement logic: Hardcoded percentages, not ML-driven**
   - **Where:** [`resource_planning_service.calculate_requirements()`](backend/app/services/resource_planning_service.py#L6) uses static population breakdowns (27% children, 60% adults, 13% elderly)
   - **Risk:** Demographic assumptions not validated for all regions/disaster types; multiplier (1.25× if impact ≥ 70) arbitrary
   - **Observation:** Should integrate ML predictions instead of rules; currently unused joblib models suggest this was planned
   - **Fix:** Use trained resource requirement models ([`models/Ambulances_Required_DecisionTree.joblib`](models/Ambulances_Required_DecisionTree.joblib), etc.)
   - **Brittleness Score:** 🟡 MEDIUM — business logic, lower accuracy than intended

### 10. **DB Foreign Key missing CASCADE on disaster_reports.user_id**
   - **Where:** [`models.py:DisasterReport`](backend/app/models.py#L27) FK to users.id
   - **Risk:** If user deleted, orphan disaster_reports remain; violates referential integrity intent
   - **Observation:** Unlikely at scale (user deletion rare), but data consistency issue
   - **Fix:** Add `ondelete="CASCADE"` or implement soft deletes
   - **Brittleness Score:** 🟢 LOW — edge case, data integrity only

### 11. **Notifications.report_id SET NULL on cascade**
   - **Where:** [`models.py:Notification`](backend/app/models.py#L65) FK to disaster_reports.id with no explicit constraint
   - **Risk:** If disaster report deleted, notifications orphaned (report_id = NULL); UI may break if code assumes report_id always populated
   - **Observation:** Inconsistent with DisasterLifecycleEvent (CASCADE DELETE)
   - **Fix:** Use CASCADE DELETE consistently; archive notifications instead
   - **Brittleness Score:** 🟡 MEDIUM — inconsistent behavior

### 12. **JWT revocation requires DB query on every request**
   - **Where:** [`dependencies.get_current_token()`](backend/app/dependencies.py#L16) queries `revoked_tokens` table
   - **Risk:** Scales poorly; every API call hits DB even if token valid (no cache invalidation)
   - **Observation:** Small table, indexed by jti; acceptable for dev scale
   - **Fix:** Cache revoked tokens in Redis with TTL; reduce DB queries
   - **Brittleness Score:** 🟡 MEDIUM — performance, not correctness

### 13. **CORS hardcoded to localhost ports**
   - **Where:** [`main.py`](backend/app/main.py#L18) CORSMiddleware allows_origins list
   - **Risk:** No production host configured; deployment will fail with CORS errors
   - **Fix:** Move to env var `ALLOWED_ORIGINS`; default to `["http://localhost:3000"]` for dev
   - **Brittleness Score:** 🔴 HIGH — deployment blocker

### 14. **No rate limiting or DDoS protection**
   - **Where:** All routes accept unlimited requests
   - **Risk:** Open-Meteo API quota can be exceeded; no back-pressure on clients
   - **Fix:** Add FastAPI rate limiting middleware (e.g., slowapi)
   - **Brittleness Score:** 🟡 MEDIUM — availability risk

### 15. **Latitude/longitude validation only range-checked, not geographic validity**
   - **Where:** Pydantic schemas accept -90 to 90 (lat), -180 to 180 (lon)
   - **Risk:** Allows invalid combos (e.g., 0, 0 on equator in ocean); no check for land/feasible locations
   - **Observation:** Works for testing; unlikely to matter for production
   - **Fix:** Validate against land/country GIS data if needed
   - **Brittleness Score:** 🟢 LOW — edge case

---

## External Dependencies

### Load-Bearing APIs

| Service | URL | Purpose | Failure Mode | Fallback |
|---|---|---|---|---|
| **Open-Meteo** | https://api.open-meteo.com/v1/forecast | Current weather (temp, humidity, rain, wind) | Timeout, 503, invalid JSON | None; blocks report creation → 503 to user |
| **Overpass OSM** | https://overpass-api.de/api/interpreter | Nearby infrastructure (hospitals, schools, etc.) | Rate limit, 429, timeout, query error | Graceful: log warning, return score 0.5 |
| **OSRM** | https://router.project-osrm.org/route/v1/driving | Route planning (distance, duration) | Timeout, 429 | Fallback: haversine + naive 50 km/h estimate |

### Load-Bearing Libraries

| Library | Version | Usage | Risk If Removed |
|---|---|---|---|
| **FastAPI** | ≥0.115.0 | Web framework | Entire backend breaks |
| **SQLAlchemy** | ≥2.0.0 | ORM | DB queries break |
| **psycopg** | ≥3.2.0 (binary) | PostgreSQL driver | DB connection fails |
| **Pydantic** | ≥2.0 (via pydantic-settings) | Schema validation | No input validation → SQL injection risk |
| **PyJWT** | ≥2.9.0 | JWT encoding/decoding | Auth breaks |
| **pwdlib[argon2]** | ≥0.2.0 | Password hashing | Plaintext passwords or weak hash |
| **joblib** | ≥1.4.0 | ML model serialization | Model loading fails |
| **pandas** | ≥2.1.0 | Data manipulation (inventory, shelters) | Allocation logic breaks |
| **scikit-learn** | ≥1.4.0 | Impact prediction model (sklearn pipeline) | Model predictions fail |
| **requests** | ≥2.31.0 | HTTP client (weather, OSM, OSRM) | External API calls fail |
| **React** | ^19.2.7 | Frontend framework | Frontend breaks |
| **axios** | ^1.18.1 | Frontend HTTP client | API calls from frontend fail |
| **react-router-dom** | ^7.18.1 | Frontend routing | Page navigation breaks |

---

## Environment & Configuration

### Backend Configuration

**File:** [`backend/app/config.py`](backend/app/config.py)

```python
class Settings(BaseSettings):
    app_name: str = "Disaster Response API"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/disaster_response"
    jwt_secret_key: str = "change-this-to-a-long-random-secret-before-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
```

**Actual vars read from system:**
- Env vars (via pydantic_settings)
- `.env` file (if exists in working directory)
- Defaults (hardcoded)

**Secrets exposure risk:** `JWT_SECRET_KEY` default is weak + public; **must be overridden in production** via env var.

### Database Initialization

**File:** [`backend/app/database.py`](backend/app/database.py)

```python
engine = create_engine(database_url, pool_pre_ping=True)  # Validates connection on reuse
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass  # ORM declarative base

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Lifespan hook** in [`main.py`](backend/app/main.py#L11):

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)  # Create tables on startup
    yield
```

Tables created (if not exist) on every app startup; migrations not used (simple create_all strategy).

### Frontend Configuration

**Build config:** [`frontend/vite.config.js`](frontend/vite.config.js)

```javascript
export default defineConfig({
  plugins: [react()],
})
```

**No env var loading; API base URL hardcoded in [`api.js`](frontend/src/services/api.js):**

```javascript
// Assumed: http://localhost:8000 (development default)
```

**Production deployment:** Must inject API URL at build time or use environment-specific config (not implemented).

### Test Configuration

**File:** [`backend/tests/test_user_api.py`](backend/tests/test_user_api.py#L5)

```python
os.environ["DATABASE_URL"] = "postgresql://postgres:Aashrith@localhost:5432/disaster_response"
os.environ["JWT_SECRET_KEY"] = "..."

# Override get_db dependency to use SQLite in-memory DB
test_engine = create_engine("sqlite:///./test_user_api.db", connect_args={"check_same_thread": False})
app.dependency_overrides[get_db] = override_get_db
```

**Tests run against local SQLite; PostgreSQL credentials hardcoded (security risk for CI/CD).**

---

## Appendix: File Location Map

### Backend Core

- **Entry:** [`backend/app/main.py`](backend/app/main.py)
- **Models:** [`backend/app/models.py`](backend/app/models.py)
- **Database:** [`backend/app/database.py`](backend/app/database.py)
- **Config:** [`backend/app/config.py`](backend/app/config.py)
- **Security:** [`backend/app/security.py`](backend/app/security.py)
- **Dependencies:** [`backend/app/dependencies.py`](backend/app/dependencies.py)
- **Schemas:** [`backend/app/schemas.py`](backend/app/schemas.py)

### Backend Routers

- [`backend/app/routers/auth.py`](backend/app/routers/auth.py) — Register, login, logout
- [`backend/app/routers/users.py`](backend/app/routers/users.py) — Profile get/update
- [`backend/app/routers/predictions.py`](backend/app/routers/predictions.py) — Impact prediction
- [`backend/app/routers/allocations.py`](backend/app/routers/allocations.py) — Direct resource allocation
- [`backend/app/routers/disaster_reports.py`](backend/app/routers/disaster_reports.py) — Report CRUD + predict + allocate + timeline
- [`backend/app/routers/warehouses.py`](backend/app/routers/warehouses.py) — List warehouses
- [`backend/app/routers/notifications.py`](backend/app/routers/notifications.py) — Notification list + mark read
- [`backend/app/routers/updates.py`](backend/app/routers/updates.py) — SSE stream

### Backend Services

- [`backend/app/services/model_service.py`](backend/app/services/model_service.py) — ML inference
- [`backend/app/services/allocation_service.py`](backend/app/services/allocation_service.py) — Warehouse allocation
- [`backend/app/services/realtime_data_service.py`](backend/app/services/realtime_data_service.py) — Weather, OSM, population enrichment
- [`backend/app/services/lifecycle_service.py`](backend/app/services/lifecycle_service.py) — Disaster state machine
- [`backend/app/services/notification_service.py`](backend/app/services/notification_service.py) — Notification creation
- [`backend/app/services/live_update_service.py`](backend/app/services/live_update_service.py) — SSE pub/sub
- [`backend/app/services/duplicate_report_service.py`](backend/app/services/duplicate_report_service.py) — Duplicate detection
- [`backend/app/services/resource_planning_service.py`](backend/app/services/resource_planning_service.py) — Resource requirement calculation
- [`backend/app/services/route_service.py`](backend/app/services/route_service.py) — Route planning
- [`backend/app/services/shelter_service.py`](backend/app/services/shelter_service.py) — Shelter recommendation

### Frontend Core

- **Entry:** [`frontend/src/main.jsx`](frontend/src/main.jsx)
- **App Root:** [`frontend/src/App.jsx`](frontend/src/App.jsx)
- **Auth Context:** [`frontend/src/context/AuthContext.jsx`](frontend/src/context/AuthContext.jsx)
- **API Client:** [`frontend/src/services/api.js`](frontend/src/services/api.js)
- **Protected Route:** [`frontend/src/components/ProtectedRoute.jsx`](frontend/src/components/ProtectedRoute.jsx)

### Frontend Pages

- [`frontend/src/pages/login/Login.jsx`](frontend/src/pages/login/Login.jsx)
- [`frontend/src/pages/register/Register.jsx`](frontend/src/pages/register/Register.jsx)
- [`frontend/src/pages/resources/Resources.jsx`](frontend/src/pages/resources/Resources.jsx)
- [`frontend/src/pages/resource-allocation/ResourceAllocation.jsx`](frontend/src/pages/resource-allocation/ResourceAllocation.jsx)
- [`frontend/src/pages/predictions/Predictions.jsx`](frontend/src/pages/predictions/Predictions.jsx)
- [`frontend/src/pages/profile/Profile.jsx`](frontend/src/pages/profile/Profile.jsx)

### Frontend Modules (API Clients)

- [`frontend/src/modules/auth/authApi.js`](frontend/src/modules/auth/authApi.js)
- [`frontend/src/modules/allocation/allocationApi.js`](frontend/src/modules/allocation/allocationApi.js)
- [`frontend/src/modules/reports/reportsApi.js`](frontend/src/modules/reports/reportsApi.js)
- [`frontend/src/modules/warehouses/warehousesApi.js`](frontend/src/modules/warehouses/warehousesApi.js)

### Data & Models

- **Inventory:** [`datasets/inventory.csv`](datasets/inventory.csv)
- **Shelters:** [`datasets/shelter_infrastructure.parquet`](datasets/shelter_infrastructure.parquet)
- **Impact Model:** [`notebooks/impact_prediction_model.pkl`](notebooks/impact_prediction_model.pkl)
- **Legacy models:** [`models/Ambulances_Required_DecisionTree.joblib`](models/Ambulances_Required_DecisionTree.joblib), etc.

### Tests

- [`backend/tests/test_user_api.py`](backend/tests/test_user_api.py)

### Config

- **Backend requirements:** [`backend/requirements.txt`](backend/requirements.txt)
- **Frontend config:** [`frontend/package.json`](frontend/package.json), [`frontend/vite.config.js`](frontend/vite.config.js)

---

## Summary

This system is a **modular, API-first disaster response platform** combining:
- **Frontend:** React SPA with token-based auth
- **Backend:** FastAPI + PostgreSQL with service-oriented architecture
- **Data:** External APIs (weather, OSM, routing) + static ML models + CSV inventory
- **Critical paths:** Disaster reporting → enrichment → impact prediction → resource allocation

**Strengths:**
- Clear separation of concerns (routers, services, DB)
- Type safety (Pydantic schemas, TypeScript-ready)
- Immutable audit trail (disaster_lifecycle_events append-only)
- Real-time updates (SSE)

**Fragilities:**
- External API dependency (weather mandatory for report creation; no offline fallback)
- Hard-coded feature order for ML inference (silent failure if model changes)
- Single-instance SSE queue (breaks at horizontal scale)
- No rate limiting or DDoS protection
- Test DB credentials hardcoded
- CORS whitelist hardcoded to localhost (deployment risk)

**Improvement priorities:**
1. Externalize configuration (env vars for all secrets, CORS, API URLs)
2. Add Redis for token blacklist caching + message queue
3. Decouple external API calls (queue enrichment tasks; allow offline mode)
4. Implement rate limiting
5. Use trained ML models for resource requirements (not hardcoded rules)
6. Add structured logging + monitoring
7. Document feature engineering pipeline + model versioning
