# Disaster Response Backend API

FastAPI backend for disaster reporting, live weather enrichment, impact prediction, resource allocation, transport planning, shelter recommendations, lifecycle tracking, notifications, and live frontend updates.

For the exact model and rule-based formulas, see [CALCULATION_GUIDE.md](CALCULATION_GUIDE.md).

## Features

- User registration, login, profile update, and JWT logout.
- Live disaster reports using Open-Meteo weather and OpenStreetMap infrastructure data.
- Trained impact-prediction model API.
- Rule-based requirements for food, water, medical kits, blankets, tents, teams, ambulances, trucks, boats, and helicopters.
- Nearest-warehouse allocation with next-nearest fallback when stock is insufficient.
- Warehouse directory with locations and available stock for every resource.
- Free OSRM driving route, transport duration, ETA, and GeoJSON map geometry.
- Nearby shelter recommendation and capacity allocation simulation.
- Disaster lifecycle: `reported → assessed → partially_allocated/allocated → dispatched → completed`.
- Persisted notifications for important events and shortages.
- Server-Sent Events (SSE) for live frontend updates.
- CORS for local React/Vite development.
- Database-backed inventory reservations with approval, dispatch, delivery, cancellation, and stock-return workflows.
- Responder-team directory, incident assignment, live operational status, skills, vehicles, tags, and ETA.
- Field-team road-risk reports for blocked roads, flood zones, damaged bridges, and unsafe areas; active risks create OSRM detour waypoints for later teams.
- Local, cache-backed UI and API-error translations for English plus all 22 scheduled Indian languages.
- Mugima's decision-support features: volunteer assignment, trend analytics, priority queue, and knowledge-base recommendations.

## Technology and storage

- API framework: FastAPI
- Database: PostgreSQL through SQLAlchemy
- Authentication: JWT bearer tokens and Argon2 password hashing
- Model: `notebooks/impact_prediction_model.pkl`
- Live services: Open-Meteo, OpenStreetMap Overpass, and public OSRM

Database tables are created when the server starts:

- `users`
- `revoked_tokens`
- `disaster_reports`
- `disaster_lifecycle_events`
- `notifications`
- `warehouse_stock`
- `resource_reservations`
- `resource_reservation_items`
- `responder_teams`
- `incident_team_assignments`
- `road_risk_reports`
- `translation_keys`
- `translation_values`
- `volunteers`
- `volunteer_assignments`
- `disaster_knowledge_entries`
- `knowledge_recommendation_feedback`

`warehouse_stock` is automatically seeded from `datasets/inventory.csv` the first time the API starts. After that, the database is the source of truth for operational reservations; the CSV is not modified.

## Setup

1. Create the PostgreSQL database:

   ```sql
   CREATE DATABASE disaster_response;
   ```

2. Activate the virtual environment from the project root:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. Install backend dependencies:

   ```powershell
   pip install -r backend\requirements.txt
   ```

4. Copy `backend/.env.example` to `backend/.env`, then set your PostgreSQL connection and a secure JWT secret.

5. Start the backend:

   ```powershell
   cd backend
   uvicorn app.main:app --reload
   ```

The backend runs at `http://127.0.0.1:8000`.

Open interactive Swagger documentation at `http://127.0.0.1:8000/docs`.

## Team checkout checklist

For every teammate to run the same backend after pulling from GitHub:

1. Pull the branch containing the `backend/` folder and the required data files.
2. Create and activate a fresh Python virtual environment, then run `pip install -r backend/requirements.txt` from the project root.
3. Copy `backend/.env.example` to `backend/.env`, set a unique `JWT_SECRET_KEY`, and configure `DATABASE_URL` for a local PostgreSQL database.
4. Start the API from the `backend` directory with `uvicorn app.main:app --reload`.

The repository includes the files required by the backend endpoints:

- `datasets/inventory.csv` for warehouse listing, allocation, and route planning.
- `datasets/shelter_infrastructure.parquet` for shelter recommendations.
- `notebooks/impact_prediction_model.pkl` for impact predictions.

Creating a disaster report requires access to Open-Meteo. Infrastructure lookup and route planning use public services but gracefully fall back when Overpass or OSRM is unavailable.

## Postman setup

1. Open Postman and click **New** → **HTTP Request**.
2. For JSON requests, open **Body** → **raw** → select **JSON**.
3. For protected endpoints, open **Authorization** → select **Bearer Token** → paste the login `access_token`.
4. Replace every `<report_id>` and `<notification_id>` in examples with real numeric IDs. Do not send `{report_id}` literally.

## API endpoint summary

| Method | Endpoint | Authentication | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/register` | No | Create account |
| POST | `/api/v1/auth/login` | No | Receive access token |
| POST | `/api/v1/auth/logout` | Yes | Revoke access token |
| GET | `/api/v1/users/me` | Yes | Read profile |
| PATCH | `/api/v1/users/me` | Yes | Update full name |
| GET | `/api/v1/warehouses` | Yes | List warehouses, locations, and inventory |
| GET | `/api/v1/operational-stock` | Yes | Current database-backed available inventory |
| POST | `/api/v1/disaster-reports` | Yes | Create live disaster report; rejects recent duplicates |
| GET | `/api/v1/disaster-reports` | Yes | Report history |
| GET | `/api/v1/disaster-reports/{report_id}` | Yes | One report |
| POST | `/api/v1/disaster-reports/{report_id}/predict` | Yes | Predict impact and requirements |
| POST | `/api/v1/disaster-reports/{report_id}/allocate` | Yes | Allocate every calculated resource |
| GET | `/api/v1/disaster-reports/{report_id}/route` | Yes | Warehouse route, duration, and ETA |
| GET | `/api/v1/disaster-reports/{report_id}/shelters` | Yes | Shelter recommendations |
| POST | `/api/v1/disaster-reports/{report_id}/reservations` | Yes | Reserve predicted requirements and deduct database stock |
| GET | `/api/v1/disaster-reports/{report_id}/reservations` | Yes | List operational reservations |
| PATCH | `/api/v1/disaster-reports/{report_id}/reservations/{reservation_id}` | Yes | Approve, dispatch, deliver, cancel, or return a reservation |
| POST | `/api/v1/responder-teams` | Yes | Create a responder team |
| GET | `/api/v1/responder-teams` | Yes | List responder teams |
| POST | `/api/v1/disaster-reports/{report_id}/teams` | Yes | Assign an available team to the incident |
| GET | `/api/v1/disaster-reports/{report_id}/teams` | Yes | List incident team assignments |
| PATCH | `/api/v1/disaster-reports/{report_id}/teams/{assignment_id}` | Yes | Update a deployed team's status and ETA |
| POST | `/api/v1/disaster-reports/{report_id}/road-risks` | Yes | Deployed team reports a route risk |
| GET | `/api/v1/disaster-reports/{report_id}/road-risks` | Yes | List route risks, optionally active only |
| PATCH | `/api/v1/disaster-reports/{report_id}/road-risks/{risk_id}` | Yes | Mark a risk active or cleared |
| GET | `/api/v1/disaster-reports/{report_id}/timeline` | Yes | Lifecycle history |
| PATCH | `/api/v1/disaster-reports/{report_id}/status` | Yes | Update lifecycle status |
| POST | `/api/v1/resource-allocation` | Yes | Manual allocation request |
| GET | `/api/v1/notifications` | Yes | List notifications |
| PATCH | `/api/v1/notifications/{notification_id}/read` | Yes | Mark notification read |
| GET | `/api/v1/updates/stream` | Yes | Live SSE stream |
| GET | `/api/v1/i18n/languages` | No | Languages for the public language selector |
| GET | `/api/v1/i18n/status` | No | Local translation-runtime diagnostics without loading the model |
| GET | `/api/v1/i18n/bundle` | No | Localized static UI text for the selected language |
| POST | `/api/v1/volunteers` | Yes | Register a coordinator-owned volunteer |
| GET | `/api/v1/volunteers` | Yes | List coordinator-owned volunteers |
| PATCH | `/api/v1/volunteers/{volunteer_id}/status` | Yes | Update availability |
| GET | `/api/v1/analytics/trends` | Yes | Historical disaster trends |
| GET | `/api/v1/analytics/priority-queue` | Yes | Rank active incidents by priority |
| POST | `/api/v1/knowledge-base` | Yes | Store response guidance |
| GET | `/api/v1/knowledge-base` | Yes | Search response guidance |
| GET | `/api/v1/disaster-reports/{report_id}/recommendations` | Yes | Get matched guidance and similar incidents |
| POST | `/api/v1/disaster-reports/{report_id}/recommendations/{knowledge_entry_id}/feedback` | Yes | Rate a recommendation |


---

## 1. Register

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/auth/register`  
**Authorization:** No authorization required.  
**Body:** **raw** → **JSON**

```json
{
  "email": "responder@example.com",
  "full_name": "Asha Responder",
  "password": "safe-password-123"
}
```

**Expected result:** `201 Created`. The response contains the new user ID, email, and name.

## 2. Login and save the token

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/auth/login`  
**Authorization:** No authorization required.  
**Body:** **raw** → **JSON**

```json
{
  "email": "responder@example.com",
  "password": "safe-password-123"
}
```

**Expected result:** `200 OK`.

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "responder@example.com",
    "full_name": "Asha Responder"
  }
}
```

Copy only `access_token`. Use it as the **Bearer Token** for all following protected endpoints.

## Warehouse directory

Use this endpoint to view the warehouse directory before making an allocation. It returns each warehouse's ID, name, state, coordinates, and available quantity for every resource in `datasets/inventory.csv`.

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/warehouses`  
**Authorization:** Bearer Token  
**Body:** None

**Expected result:** `200 OK`.

```json
[
  {
    "warehouse_id": "WH001",
    "warehouse_name": "Srinagar Warehouse",
    "state": "Jammu and Kashmir",
    "latitude": 34.0837,
    "longitude": 74.7973,
    "inventory": [
      {"resource": "Food Packets", "available_quantity": 2000000},
      {"resource": "Water Bottles", "available_quantity": 3000000}
    ]
  }
]
```

## 3. Create a live disaster report

This is the normal starting point for the disaster-response workflow. The user sends only simple field information. The backend fetches weather and calculates the technical model inputs.

**Method:** `POST`
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports`
**Authorization:** Bearer Token
**Body:** **raw** → **JSON**

```json
{
  "disaster_type": "Flood",
  "latitude": 13.0827,
  "longitude": 80.2707,
  "magnitude": 6.2,
  "affected_population": 1000
}
```

**Expected result:** `201 Created`. Save the numeric `id` from the response.

```json
{
  "id": 2,
  "disaster_type": "Flood",
  "latitude": 13.0827,
  "longitude": 80.2707,
  "magnitude": 6.2,
  "affected_population": 1000,
  "weather_score": 0.478667,
  "population_density": 0.509296,
  "infrastructure_score": 0.5,
  "predicted_impact_score": null
}
```

OpenStreetMap can occasionally rate-limit public requests. In that case, the report is still created with a neutral infrastructure score of `0.5`.

## 4. Predict impact and calculate requirements

Replace `<report_id>` with the ID from step 3. If the ID is `2`, the URL must end in `/2/predict`.

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/predict`  
**Authorization:** Bearer Token  
**Body:** No body.

Example URL:

```text
http://127.0.0.1:8000/api/v1/disaster-reports/2/predict
```

**Expected result:** `200 OK`. It contains `predicted_impact_score` and `estimated_requirements` for all ten inventory resources. The status changes from `reported` to `assessed`.

## 5. Allocate all calculated resources

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/allocate`  
**Authorization:** Bearer Token  
**Body:** No body.

Example URL:

```text
http://127.0.0.1:8000/api/v1/disaster-reports/2/allocate
```

**Expected result:** `200 OK`. Resources are taken from the nearest warehouse first. If a resource is insufficient, the next-nearest warehouse supplies the remainder. The response shows `required`, `allocated`, `shortage`, and `supplies` for each resource. A fully supplied request records lifecycle status `allocated`. If any resource has a shortage, `allocation_status` is `Partial` and the lifecycle records `partially_allocated`; the shortage quantity remains visible in the response and timeline.

## 6. Read disaster report history

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports`  
**Authorization:** Bearer Token  
**Body:** No body.

**Expected result:** `200 OK` with the signed-in user's reports, newest first. Each item includes `current_status`.

## 7. Read one disaster report

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>`  
**Authorization:** Bearer Token  
**Body:** No body.

Example:

```text
http://127.0.0.1:8000/api/v1/disaster-reports/2
```

## 8. Get a warehouse route, travel time, and ETA

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/route`  
**Authorization:** Bearer Token  
**Body:** No body.

**Expected result:** `200 OK`.

```json
{
  "warehouse_id": "WH015",
  "warehouse_name": "Chennai Warehouse",
  "distance_km": 18.4,
  "duration_minutes": 34.6,
  "estimated_arrival_at": "2026-07-22T18:30:00Z",
  "route_source": "osrm",
  "geometry": {"type": "LineString", "coordinates": []}
}
```

`geometry` is GeoJSON and can be drawn directly on a frontend map. If the free OSRM service is unavailable, `route_source` is `estimated_fallback`; duration is then estimated at 50 km/h.

## 9. Get shelter recommendations

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/shelters?limit=20`  
**Authorization:** Bearer Token  
**Body:** No body.

`limit` is optional and may be from `1` to `100`.

**Expected result:** `200 OK` with nearby shelters, each shelter's capacity, allocated people, and the number still waiting. This is a planning simulation and does not permanently change shelter capacity.

## 10. Read lifecycle timeline

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/timeline`  
**Authorization:** Bearer Token  
**Body:** No body.

**Expected result:** `200 OK` with ordered lifecycle events, notes, timestamps, and any estimated arrival time.

## 11. Mark a report as dispatched

The lifecycle must follow this order:

```text
reported → assessed → partially_allocated → allocated → dispatched → completed
```

`partially_allocated` is used only when at least one requested supply cannot be obtained. A later allocation/reservation attempt can move the report to `allocated` once all shortages are fulfilled; dispatch from a partial allocation is also allowed when sending the available emergency supplies is operationally necessary.

Call allocation before dispatching a report.

**Method:** `PATCH`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/status`  
**Authorization:** Bearer Token  
**Body:** **raw** → **JSON**

```json
{
  "status": "dispatched",
  "note": "Relief trucks departed from Chennai Warehouse.",
  "estimated_arrival_at": "2026-07-22T18:30:00Z"
}
```

Use the `estimated_arrival_at` value from the route endpoint if suitable. An invalid status transition returns `409 Conflict`.

## 12. Mark a report as completed

**Method:** `PATCH`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/status`  
**Authorization:** Bearer Token  
**Body:** **raw** → **JSON**

```json
{
  "status": "completed",
  "note": "Supplies delivered and field handover completed."
}
```

## 13. Manual resource allocation

Use this endpoint only when the frontend or coordinator already knows exact resource quantities. Otherwise use the report allocation endpoint in step 5.

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/resource-allocation`  
**Authorization:** Bearer Token  
**Body:** **raw** → **JSON**

```json
{
  "latitude": 23.4190,
  "longitude": 70.2320,
  "required_resources": {
    "Food Packets": 2500000,
    "Water Bottles": 1000000,
    "Medical Kits": 25000,
    "Blankets": 50000,
    "Temporary Tents": 10000,
    "Rescue Teams": 20,
    "Ambulances": 10,
    "Trucks": 15,
    "Boats": 0,
    "Helicopters": 0
  }
}
```

All resource names must match `datasets/inventory.csv` exactly. At least one quantity must be greater than zero. The inventory CSV is not changed; this is an allocation simulation.

This manual endpoint is not linked to a saved disaster report, so its response contains only warehouse allocation details and does **not** contain `volunteer_assignment`. To allocate resources for a saved report and view its already-assigned volunteers, use step 5: `POST /api/v1/disaster-reports/<report_id>/allocate`.

## 14. List notifications

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/notifications`  
**Authorization:** Bearer Token  
**Body:** No body.

For unread notifications only:

```text
http://127.0.0.1:8000/api/v1/notifications?unread_only=true
```

The backend creates notifications for lifecycle changes, high-impact predictions (score 70 or more), and resource shortages.

## 15. Mark a notification as read

**Method:** `PATCH`  
**URL:** `http://127.0.0.1:8000/api/v1/notifications/<notification_id>/read`  
**Authorization:** Bearer Token  
**Body:** No body.

Example:

```text
http://127.0.0.1:8000/api/v1/notifications/5/read
```

## 16. Test live Server-Sent Events updates

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/updates/stream`  
**Authorization:** Bearer Token  
**Body:** No body.

In Postman, keep this request open after clicking **Send**. In another Postman tab, create, predict, allocate, or update a report. The open stream receives `lifecycle` and `notification` events. A keep-alive message is sent every 15 seconds.

For browser integration, use `fetch` streaming or a token-aware SSE library because the standard browser `EventSource` object cannot send a custom Bearer Authorization header.



## 17. Profile and logout endpoints

### Read profile

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/users/me`  
**Authorization:** Bearer Token  
**Body:** No body.

### Update profile

**Method:** `PATCH`  
**URL:** `http://127.0.0.1:8000/api/v1/users/me`  
**Authorization:** Bearer Token  
**Body:** **raw** → **JSON**

```json
{
  "full_name": "Asha Relief Coordinator"
}
```

### Logout

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/auth/logout`  
**Authorization:** Bearer Token  
**Body:** No body.

The current token is revoked immediately. A later protected request using it returns `401 Unauthorized`.

## 18. Persistent inventory reservation and dispatch tracking

This is the operational replacement for a planning-only allocation. It stores every resource reservation in PostgreSQL and immediately deducts the reserved quantities from `warehouse_stock`, preventing the same stock from being reserved twice. Stock is restored only when a reservation is **cancelled** or marked **returned**.

First use steps 3 and 4 to create and predict a report. Then reserve the calculated requirements.

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/reservations`  
**Authorization:** Bearer Token  
**Body:** No body.

**Expected result:** `201 Created`. The response identifies every warehouse and item actually reserved. A partial reservation is still saved when stock is insufficient, so coordinators can see what is available without over-committing stock. It also returns `allocation_status: "Partial"` and an `allocations` summary with `required`, `allocated`, and `shortage` for every resource. This records the lifecycle event as `partially_allocated`; a complete reservation records `allocated`.

```json
{
  "id": 1,
  "report_id": 2,
  "status": "reserved",
  "items": [
    {"resource": "Food Packets", "quantity": 11250, "warehouse_id": "WH015", "warehouse_name": "Chennai Warehouse"}
  ]
}
```

Use this endpoint to inspect real remaining stock after a reservation:

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/operational-stock`  
**Authorization:** Bearer Token

Move the reservation through its operational workflow with the same URL below. Replace both placeholders with numeric IDs.

**Method:** `PATCH`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/reservations/<reservation_id>`  
**Authorization:** Bearer Token  
**Body:** **raw** → **JSON**

```json
{
  "status": "approved",
  "note": "Warehouse manager verified stock."
}
```

The allowed sequence is:

```text
reserved → approved → dispatched → delivered → returned
```

`cancelled` is allowed from `reserved`, `approved`, or `dispatched`, and returns all reserved quantities to operational stock. Use `returned` only after delivery when unused material physically returns to its source warehouse. Test the whole workflow by sending `approved`, `dispatched`, and `delivered` in order; attempting an invalid jump returns `409 Conflict`.

## 19. Incident assignment and responder management

Create a responder team once, including the team number, searchable tags, skills, and vehicles.

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/responder-teams`  
**Authorization:** Bearer Token  
**Body:** **raw** → **JSON**

```json
{
  "team_number": "TEAM-CHN-01",
  "tags": "water-rescue,medical",
  "skills": "Swift-water rescue, first aid",
  "vehicles": "2 boats, 1 ambulance"
}
```

Use `GET http://127.0.0.1:8000/api/v1/responder-teams` to view all teams and their current availability. A unique `team_number` is required.

Assign an available team to an incident:

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/teams`  
**Authorization:** Bearer Token  
**Body:** **raw** → **JSON**

```json
{
  "team_id": 1,
  "estimated_arrival_at": "2026-07-27T14:30:00Z",
  "note": "Deploy to the east-side evacuation point."
}
```

Assignment sets the team to `en_route`, so it cannot be assigned to another incident. Read assignments with `GET /api/v1/disaster-reports/<report_id>/teams`. Update its live status using:

**Method:** `PATCH`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/teams/<assignment_id>`  
**Authorization:** Bearer Token  
**Body:** **raw** → **JSON**

```json
{
  "status": "on_site",
  "note": "Team reached the incident area."
}
```

Use `assigned`, `en_route`, `on_site`, `returning`, and finally `completed`. A completed assignment resets the team to `available` for the next deployment.

## 20. Road closure and route-risk management

Only a team already assigned to the selected disaster may create a road-risk report. This prevents unverified teams from changing future-routing decisions. First assign the team as in step 20, then submit a risk.

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/road-risks`  
**Authorization:** Bearer Token  
**Body:** **raw** → **JSON**

```json
{
  "team_id": 1,
  "risk_type": "blocked_road",
  "severity": "high",
  "road_name": "East Coast Road",
  "description": "Flood water and debris have blocked both lanes near the bridge.",
  "latitude": 13.0500,
  "longitude": 80.1000
}
```

Allowed `risk_type` values are `blocked_road`, `flood_zone`, `damaged_bridge`, and `unsafe_area`. Severity is `low`, `medium`, `high`, or `critical`.

Read all reported risks with:

```text
GET http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/road-risks
```

For active risks only, add `?active_only=true`. The existing route endpoint now reads these active database records. When an active risk lies near the warehouse-to-incident route, it adds a detour waypoint before requesting OSRM, keeping the next deployment away from the reported location. The route response contains `excluded_road_risk_ids` and `route_safety_status: "risk_aware_detour"`.

After a team verifies that the danger is gone, clear it:

**Method:** `PATCH`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/road-risks/<risk_id>`  
**Authorization:** Bearer Token  
**Body:** **raw** → **JSON**

```json
{
  "status": "cleared"
}
```

Cleared risks remain stored for later infrastructure-damage analysis, but are excluded from future route-detour calculations.

## 21. Local IndicTrans2 multilingual support

The backend uses AI4Bharat IndicTrans2 locally to translate application text into English plus all 22 scheduled Indian languages. There is no paid inference endpoint and no per-request API charge. The model files are explicitly downloaded once, stored only under `backend/models/`, and then used fully offline.

### 21.1 Supported languages

The public language selector endpoint supports English plus Assamese, Bengali, Bodo, Dogri, Gujarati, Hindi, Kannada, Kashmiri, Konkani, Maithili, Malayalam, Manipuri, Marathi, Nepali, Odia, Punjabi, Sanskrit, Santali, Sindhi, Tamil, Telugu, and Urdu.

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/i18n/languages`  
**Authorization:** No authorization required.

This endpoint is public so the login page can load the language selector before a user signs in. Send the selected locale in every request using `Accept-Language`, for example `ta-IN`, `hi-IN`, or `te-IN`. The optional `?lang=ta` query parameter is available for Postman/browser testing. Every response includes `Content-Language` with the selected code.

### 21.2 One-time local model setup

Install the Python requirements first. The version pins below are required: `transformers==4.51.0` is compatible with IndicTransToolkit 1.1.1, and `accelerate` supplies the model-loading helper used by Transformers. Then accept the model access conditions on Hugging Face and run the explicit downloader once from the `backend` folder:

```powershell
pip install -r requirements.txt
python scripts/download_indictrans_model.py
```

IndicTrans2 is a gated model. Before the command can download anything, sign in at [the model page](https://huggingface.co/ai4bharat/indictrans2-en-indic-dist-200M) and accept its access conditions. If the script reports `GatedRepoError` or `401 Unauthorized`, create a new Hugging Face token with **Read** permission and use it only in the current PowerShell window:

```powershell
$env:HF_TOKEN='hf_your_new_read_token'
python scripts/download_indictrans_model.py
Remove-Item Env:HF_TOKEN
```

Do not put this download token in `.env`, do not commit it, and do not send it to the frontend. It is used by the one-time downloader only; the running backend does not need an API key or internet access.

The downloader uses the Hugging Face Python download API, not `git clone` and not Git LFS. It requests only the model runtime files (`model.safetensors`, `model.SRC`, `model.TGT`, tokenizer/config files, and model Python code) and writes them to `backend/models/indictrans2-en-indic-dist-200M`. That directory is ignored by Git. It does not run automatically when FastAPI/PyCharm starts, so it cannot silently start a large download.

Set the optional local settings in `backend/.env`:

```env
INDICTRANS_MODEL_PATH=models/indictrans2-en-indic-dist-200M
INDICTRANS_DEVICE=auto
INDICTRANS_BATCH_SIZE=4
```

`auto` uses a CUDA GPU if available; otherwise it uses CPU. Cold bundles are translated in small batches (`INDICTRANS_BATCH_SIZE`, default `4`) to limit VRAM use. If CUDA runs out of memory in `auto` mode, the request transparently reloads the model on CPU and retries; later requests keep using CPU until the backend restarts. CPU inference works but the first translation and uncached bundles can be slow and need substantial RAM. The model is only loaded on the first uncached non-English request, never during application startup. The application holds it in memory afterward for speed. The runtime disables the model's generation key/value cache because this checkpoint's custom decoder is incompatible with newer Transformers cache objects; this affects only the initial uncached translation and does not affect translation correctness.

IndicTransToolkit documents Linux/macOS as its supported environment. The project has also been verified with the pinned dependencies on this Windows Python 3.10 virtual environment; WSL2 Ubuntu remains the recommended fallback if a new Windows machine has native package-installation problems. The model checkpoint is roughly a few GB, depending on the published files and Hugging Face cache format; Python packages such as PyTorch require additional disk space. Neither uses Git LFS or creates a 98 GB clone.

The Hugging Face token, if required for the gated one-time download, is used only by that command and is not required by the running backend. Never put a token in frontend code.

### 21.3 Database cache design

Two database tables provide persistent translation caching:

- `translation_keys`: a stable application/API key and its English source text, for example `nav.dashboard` -> `Dashboard`.
- `translation_values`: the translated text for one key and locale, generated by IndicTrans2. A unique `(translation_key_id, locale)` constraint prevents duplicate cached values.

The request path is optimized as follows:

```text
RAM LRU cache -> PostgreSQL translation_values cache -> local IndicTrans2 model -> save to PostgreSQL and RAM cache
```

The first request for a key/language may run the local model. Every later request uses the in-memory cache or persistent database cache, so no model inference is needed. A cold UI bundle translates all missing keys in one batch rather than one translation per key. Cached translations survive an API restart.

### 21.4 Public UI translation bundle

The frontend can request all seeded static UI text before login:

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/i18n/bundle`  
**Authorization:** No authorization required.  
**Header:** `Accept-Language: ta-IN`

The response contains a key/value map suitable for a frontend translation store:

```json
{
  "locale": "ta",
  "translations": {
    "app.name": "...",
    "nav.dashboard": "...",
    "auth.login": "...",
    "status.partially_allocated": "...",
    "disaster.flood": "..."
  }
}
```

On a cache miss, the bundle may take longer while IndicTrans2 creates the translation. Later bundle requests are served from cache. The frontend should fetch this bundle immediately after language selection and render its login page, navigation, buttons, statuses, and disaster labels from the returned keys.

### 21.5 Frontend integration contract

The backend provides the translations; the frontend is responsible for replacing every visible static label with a translation key. It must not send translated labels as API codes.

1. On the login screen, load `GET /api/v1/i18n/languages` and show the returned `supported` values in a selector. This endpoint needs no access token.
2. Store the chosen language code (for example, `ta`) in browser storage and in frontend state. Default to `en`.
3. When it changes, request `GET /api/v1/i18n/bundle` with `Accept-Language: <code>-IN` (or simply `<code>`), replace the translation map in state, and re-render the app.
4. Add `Accept-Language: <code>-IN` to every later API request, including authenticated requests. API `HTTPException` messages then use the selected locale. Keep the bearer token logic unchanged.
5. Render UI text through a helper such as `t("nav.dashboard")`; fall back to the English key/source when a key is absent. Do this for pages, navigation, buttons, form labels, empty states, status labels, and disaster-type labels.
6. Keep API/database enums stable. For example, show `t("disaster.flood")`, but send and store `"flood"`; show `t("status.dispatched")`, but send `"dispatched"` to the status endpoint.

Minimal frontend request pattern:

```javascript
const language = localStorage.getItem("language") || "en";

const response = await fetch("http://127.0.0.1:8000/api/v1/i18n/bundle", {
  headers: { "Accept-Language": `${language}-IN` },
});
const { translations } = await response.json();
// Save `language` and `translations` in the app's global state, then re-render.
```

For every normal API request, add the same `Accept-Language` header beside `Authorization` where applicable. When adding a new static frontend string, add it to `STATIC_CATALOG` before using its key so it is included in every bundle.

### 21.6 API errors and future endpoints

All FastAPI `HTTPException` text is translated through the same cache pipeline. New API endpoints automatically participate when they raise normal `HTTPException` errors. The first occurrence of a new English message creates a hashed API key in `translation_keys`; subsequent occurrences reuse its cached translations.

For static labels added to the frontend, add the English key/source pair to `STATIC_CATALOG` in `app/services/translation_service.py`. The backend seeds it into `translation_keys`, and `/api/v1/i18n/bundle` translates and caches it on demand. This is the required convention for new static UI values.

Keep calculation and database codes language-neutral. For example, the frontend displays Tamil `வெள்ளம்`, sends `"disaster_type": "flood"`, the backend stores/returns `flood`, and the frontend renders the localized label. The backend accepts Unicode free-text input for fields such as notes, descriptions, names, skills, and vehicles.

### 21.7 Postman tests

1. Send `GET http://127.0.0.1:8000/api/v1/i18n/languages` without authentication and verify all 23 entries (English plus 22 scheduled Indian languages).
2. Run `python scripts/download_indictrans_model.py` once, then send `GET http://127.0.0.1:8000/api/v1/i18n/status`. Confirm `translation_provider` is `local_indictrans2` and `model_files_present` is `true`. The status request does not load the model.
3. Send `GET http://127.0.0.1:8000/api/v1/i18n/bundle` with header `Accept-Language: ta-IN`. Verify `Content-Language: ta` and a translated `translations` object. The first non-English cache miss loads the local model and can take time.
4. Send the identical bundle request again. It should return the same translation bundle from cache without running IndicTrans2 again.
5. Send an invalid login request with `Accept-Language: hi-IN` and verify that the `401` error is returned in Hindi after its first translation is cached.
6. To test missing-model handling, temporarily rename `backend/models/indictrans2-en-indic-dist-200M`, restart the backend, and request an uncached language bundle. The API returns `503 Service Unavailable` with setup instructions rather than downloading anything. Restore the original folder afterward.

## Mugima's Features

The following five features are grouped separately because they were integrated from Mugima's backend contribution. Unless explicitly stated otherwise, first log in using step 2 and use the returned `access_token` in Postman: **Authorization** → **Bearer Token**. Replace every placeholder such as `<report_id>`, `<volunteer_id>`, and `<knowledge_entry_id>` with a real numeric ID.

### 1. Duplicate disaster-report prevention

This feature is part of the existing disaster-report creation endpoint. It prevents the same incident from being entered twice before live weather and infrastructure data is fetched. A report is a duplicate only when it has the same disaster type, is within 2 km, is submitted within 30 minutes, and its magnitude differs by no more than 0.5.

#### Create report and test duplicate detection

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports`  
**Authentication:** Bearer Token required.  
**Body:** **raw** → **JSON**

```json
{
  "disaster_type": "flood",
  "latitude": 13.0827,
  "longitude": 80.2707,
  "magnitude": 6.2,
  "affected_population": 1000
}
```

The first request returns `201 Created` and contains the new report `id`. Send the identical request again immediately. The second request returns `409 Conflict`:

```json
{
  "detail": {
    "message": "Duplicate disaster report detected.",
    "existing_report_id": 2
  }
}
```

To create a valid different report, change the disaster type, choose a location more than 2 km away, change magnitude by more than 0.5, or wait 30 minutes.

### 2. Volunteer management and impact-based assignment

This feature registers coordinator-owned volunteers and automatically assigns the nearest available volunteers after a report is predicted. Low impact assigns 25% of available volunteers (minimum one), moderate impact assigns 50%, and high impact assigns all available volunteers. A repeated prediction returns the existing assignment; it does not consume more volunteers.

#### Register a volunteer

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/volunteers`  
**Authentication:** Bearer Token required.  
**Body:** **raw** → **JSON**

```json
{
  "name": "Anita Rao",
  "email": "anita.rao@example.com",
  "phone": "9876543210",
  "latitude": 13.0830,
  "longitude": 80.2710,
  "skill": "Medical"
}
```

Expected result: `201 Created`. The new volunteer starts with `"availability": "Available"`. Create two or more volunteers at different coordinates to test nearest-volunteer selection.

#### List volunteers

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/volunteers`  
**Authentication:** Bearer Token required.  
**Body:** None.

Expected result: `200 OK` with only the signed-in coordinator's volunteers.

#### Get one volunteer

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/volunteers/<volunteer_id>`  
**Authentication:** Bearer Token required.  
**Body:** None.

Expected result: `200 OK`. An unknown ID, or another user's volunteer ID, returns `404 Not Found`.

#### Update volunteer availability

**Method:** `PATCH`  
**URL:** `http://127.0.0.1:8000/api/v1/volunteers/<volunteer_id>/status`  
**Authentication:** Bearer Token required.  
**Body:** **raw** → **JSON**

```json
{
  "availability": "Available"
}
```

Allowed values are `Available`, `Busy`, and `Unavailable`. Use this endpoint to return a volunteer to service after their assignment is complete.

#### Predict a report and assign volunteers

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/predict`  
**Authentication:** Bearer Token required.  
**Body:** None.

Expected result: `200 OK`. Along with the ML impact score and resource requirements, the response contains `volunteer_assignment`, including the available count before assignment, assigned count, volunteer names, skills, and status. Confirm the closest volunteers are selected and their status changes to `Busy` in the list endpoint.

#### Read volunteer assignment during allocation

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/allocate`  
**Authentication:** Bearer Token required.  
**Body:** None.

Expected result: `200 OK`. The allocation result includes the existing `volunteer_assignment` summary beside warehouse-resource allocation details.

### 3. Disaster trend analytics

Trend Analytics helps a coordinator identify recurring disaster types, affected population, and patterns in historical reporting. It only analyses reports belonging to the signed-in user. Average impact uses reports that have a saved ML prediction.

#### Get disaster trends

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/analytics/trends?days=365`  
**Authentication:** Bearer Token required.  
**Body:** None.

`days` is optional and supports values from `1` to `3650`; its default is `365`.

Expected result: `200 OK` with `total_reports`, `predicted_reports`, `average_impact_score`, `total_affected_population`, `most_frequent_disaster_type`, `disaster_type_breakdown`, and `daily_trend`.

Postman test: create reports of at least two disaster types, predict some of them, then call this endpoint. Verify that the totals match your own reports and that `predicted_reports` only counts reports for which the prediction endpoint was called.

### 4. Disaster priority queue

The Priority Queue ranks incidents so the response team can handle the most urgent active reports first. The priority score is `75% impact score + 25% normalised magnitude severity`. It uses the saved ML impact prediction when available; otherwise it provides a transparent estimate and labels it as `estimated`.

#### Get the priority queue

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/analytics/priority-queue?include_completed=false&limit=50`  
**Authentication:** Bearer Token required.  
**Body:** None.

`include_completed` is optional and defaults to `false`. `limit` is optional, defaults to `50`, and accepts values from `1` to `200`.

Expected result: `200 OK` with ranked items. Every item includes `rank`, `priority_score`, `impact_score`, `impact_score_source`, severity, current lifecycle status, and creation time.

Postman test: create two or more reports with different magnitude or prediction results. Call the queue and verify descending `priority_score` and ranks beginning at 1. Mark a report `completed` with the status endpoint, call the queue again, and confirm it is hidden unless `include_completed=true` is used.

### 5. Disaster knowledge base and recommendations

The Knowledge Base stores best practices, past responses, and lessons learned. When guidance is requested for a report, entries matching the report's disaster type and severity appear first. The API also returns similar historical reports and a built-in disaster-specific playbook if no matching entry exists.

#### Create a knowledge-base entry

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/knowledge-base`  
**Authentication:** Bearer Token required.  
**Body:** **raw** → **JSON**

```json
{
  "title": "High-severity flood response",
  "entry_type": "best_practice",
  "content": "Deploy water, medical, and evacuation teams before access routes are cut off.",
  "disaster_type": "flood",
  "severity": "High",
  "tags": ["water", "medical", "evacuation"]
}
```

Allowed `entry_type` values are `best_practice`, `past_response`, and `lesson_learned`. Severity is optional and may be `Low`, `Moderate`, or `High`. The response returns the new entry ID; save it as `<knowledge_entry_id>` for feedback testing.

#### Search knowledge-base entries

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/knowledge-base?disaster_type=flood&entry_type=best_practice&severity=High`  
**Authentication:** Bearer Token required.  
**Body:** None.

All filters are optional. Expected result: `200 OK` with entries created by the signed-in user.

#### Get recommendations for a disaster report

**Method:** `GET`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/recommendations?limit=5`  
**Authentication:** Bearer Token required.  
**Body:** None.

`limit` is optional and supports values from `1` to `20`. Expected result: `200 OK` with `recommended_strategy`, `recommendation_source`, matching strategies and their `match_reasons`, plus `similar_disasters`. Create and predict a high-impact flood report, then verify that the entry above yields `"recommendation_source": "knowledge_base"`. A report with no matching entry returns `"recommendation_source": "default_playbook"`.

#### Rate a recommendation

**Method:** `POST`  
**URL:** `http://127.0.0.1:8000/api/v1/disaster-reports/<report_id>/recommendations/<knowledge_entry_id>/feedback`  
**Authentication:** Bearer Token required.  
**Body:** **raw** → **JSON**

```json
{
  "rating": 5,
  "comment": "The evacuation checklist was useful for field deployment."
}
```

`rating` must be an integer from `1` to `5`; `comment` is optional. Expected result: `201 Created`, recording the feedback against that report and knowledge entry.

## Testing

From the `backend` folder, run:

```powershell
pytest -q
```

`pytest -q` discovers all automated backend tests in `backend/tests`. The current 12 tests cover authentication and token revocation; 23-language discovery; cache-first local IndicTrans2 behavior with a mock engine; safe `503` handling when the local model is unavailable; canonical disaster-type validation; prediction; warehouse allocation; partial-allocation lifecycle status; duplicate prevention; notifications; reservations; responder teams; assignments; and road-risk workflows. Tests mock the local model, so they do not require a model download. A passing run reports `12 passed`; future files named `test_*.py` are discovered automatically.

