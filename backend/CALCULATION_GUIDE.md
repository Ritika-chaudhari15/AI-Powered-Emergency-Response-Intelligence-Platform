# Backend Calculation and Storage Guide

This guide documents the values shown by the live disaster-report APIs. It distinguishes the saved values, calculated values, and model result so they can be explained during a review.

## Backend and database

The backend is a **FastAPI** application using **SQLAlchemy** as its database layer. The configured database is **PostgreSQL**: `DATABASE_URL` is read from `backend/.env` (with a PostgreSQL default in `app/config.py`).

The API creates the following tables on application startup:

- `users` — registered account data.
- `revoked_tokens` — invalidated logout tokens.
- `disaster_reports` — disaster information, live API data, derived model inputs, and the prediction described below.

`POST /api/v1/disaster-reports` writes one row into `disaster_reports`. In a usual PostgreSQL installation it is stored in the `public.disaster_reports` table in the database named by `DATABASE_URL`. To inspect it in pgAdmin or psql:

```sql
SELECT *
FROM disaster_reports
ORDER BY id DESC;
```

The report row belongs to the authenticated user through `user_id`. The raw user input stored in the row is `disaster_type`, `latitude`, `longitude`, `magnitude`, and `affected_population`.

## Field calculations

| Field | Source / calculation | Stored? |
|---|---|---|
| `weather_score` | Derived from current Open-Meteo weather. Formula below. | Yes, in `disaster_reports.weather_score` |
| `population_density` | Estimated from affected population over a 25 km response area. Formula below. | Yes, in `disaster_reports.population_density` |
| `infrastructure_score` | Nearby OpenStreetMap facility count, normalised to 0–1. Formula below. | Yes, in `disaster_reports.infrastructure_score` |
| `predicted_impact_score` | Output from the saved trained XGBoost model. | Yes, after `/predict` is called |
| `estimated_requirements` | Rule-based response plan for all ten warehouse resources. | No; calculated and returned by `/predict` and `/allocate` |

### `weather_score`

`GET https://api.open-meteo.com/v1/forecast` supplies the current temperature, relative humidity, precipitation, and wind speed for the supplied coordinates. `wind_speed` is passed directly to the prediction model. The score uses the other three values:

```text
temperature_score = clamp(temperature_celsius / 50, 0, 1)
humidity_score    = clamp(relative_humidity_percent / 100, 0, 1)
rainfall_score    = clamp(precipitation_mm / 50, 0, 1)

weather_score = round((temperature_score + humidity_score + rainfall_score) / 3, 6)
```

`clamp(value, 0, 1)` limits a value to the inclusive range 0–1. For example, 26.3 °C, 91% humidity, and 0 mm precipitation produces `(0.526 + 0.91 + 0) / 3 = 0.478667`.

### `population_density`

The user supplies affected population, not a technical density value. The backend estimates density over a circular 25 km emergency-response area:

```text
response_area_km2 = pi * 25^2
population_density = round(affected_population / response_area_km2, 6)
```

For 1,000 affected people, this is `1000 / (pi * 625) = 0.509296` people/km².

### `infrastructure_score`

The backend sends an OpenStreetMap Overpass query around the disaster coordinates with a 25 km radius. It counts matching hospitals, clinics, schools, and fire stations:

```text
infrastructure_score = round(min(nearby_facility_count / 50, 1), 6)
```

The score is 0 when no matching facilities are returned, and reaches 1 when 50 or more are returned. Public Overpass servers can rate-limit or time out. In that case, report creation still succeeds and the backend uses the documented neutral fallback:

```text
infrastructure_score = 0.5
```

### `predicted_impact_score`

The saved model file is `notebooks/impact_prediction_model.pkl`. It is loaded once, then called with these features in exactly this order:

```text
[Magnitude, WeatherScore, WindSpeed, PopulationDensity, InfrastructureScore]
```

In code, this is:

```python
model.predict(input_frame)[0]
```

Because this is a trained XGBoost pipeline, there is no single fixed arithmetic formula for the final score: the model combines decision trees learned during training. The input-feature engineering and model prediction are separate from the resource rules below.

## `estimated_requirements`

This object is a three-day, rule-based plan created after the model produces an impact score. Let:

```text
P = affected_population
I = predicted_impact_score
M = 1.25 if I >= 70, otherwise 1.0
children = 0.27 * P
adults = 0.60 * P
elderly = 0.13 * P
critical_patients = ceil(0.05 * P)
```

The population split is a backend planning assumption because the live API asks for total affected population only.

| Resource | Rule |
|---|---|
| Food Packets | `ceil(P * 3 packets/day * 3 days * M)` |
| Water Bottles | `ceil(P * 5 bottles/day * 3 days * M)` |
| Medical Kits | `ceil((0.10 * children + 0.05 * adults + 0.15 * elderly) * M)` |
| Blankets | `ceil(P * M)` |
| Temporary Tents | `ceil(P / 5)` |
| Rescue Teams | `ceil(P / 250)` |
| Ambulances | `ceil(critical_patients / 4)` |
| Boats | `ceil(P / 5000)` only for a Flood; otherwise `0` |
| Helicopters | `ceil(critical_patients / 400)` only when `I >= 70`; otherwise `0` |
| Trucks | `ceil(total_supply_weight_kg / 8000)` |

Truck weight is calculated as:

```text
total_supply_weight_kg =
    0.5 * food_packets
  + 1.0 * water_bottles
  + 0.3 * medical_kits
  + 2.5 * blankets
  + 20.0 * temporary_tents
```

The base quantities and coverage values come from the simulation rules in `notebooks/Simulation Phase/Transportation_Planning.ipynb`. The backend implementation is in `app/services/resource_planning_service.py`.

## Allocation after requirements are calculated

`POST /api/v1/disaster-reports/{report_id}/allocate` calculates the same requirements and then uses `datasets/inventory.csv`.

For every resource independently, warehouses are sorted by Haversine (great-circle) distance from the disaster location. The backend takes available stock from the nearest warehouse first, then takes the remainder from the next-nearest warehouse, continuing until the requirement is fulfilled or all warehouses are exhausted.

The allocation response reports `required`, `allocated`, `shortage`, and the warehouse-by-warehouse `supplies` list. It is a simulation: `inventory.csv` is not modified.
