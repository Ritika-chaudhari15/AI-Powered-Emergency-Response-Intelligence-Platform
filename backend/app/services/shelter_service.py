from pathlib import Path

import pandas as pd

from app.services.allocation_service import haversine_distance_km


SHELTER_PATH = Path(__file__).resolve().parents[3] / "datasets" / "shelter_infrastructure.parquet"


def recommend_shelters(latitude: float, longitude: float, affected_population: int, limit: int = 20) -> dict:
    if not SHELTER_PATH.is_file():
        raise FileNotFoundError(f"Shelter data not found at {SHELTER_PATH}")
    shelters = pd.read_parquet(SHELTER_PATH)
    required = {"Latitude", "Longitude", "EstimatedCapacity"}
    if not required.issubset(shelters.columns):
        raise ValueError("Shelter data is missing required location or capacity columns")
    shelters = shelters.copy()
    shelters["distance_km"] = shelters.apply(
        lambda row: haversine_distance_km(latitude, longitude, float(row.Latitude), float(row.Longitude)), axis=1
    )
    remaining, recommended = affected_population, []
    for index, row in shelters.sort_values("distance_km").head(limit).iterrows():
        capacity = max(int(row.EstimatedCapacity), 0)
        allocated = min(remaining, capacity)
        remaining -= allocated
        shelter_name = row.get("name", None)
        if shelter_name is None or pd.isna(shelter_name) or not str(shelter_name).strip():
            shelter_name = "Unnamed Shelter"
        recommended.append({
            "shelter_id": str(row.get("id", index)), "name": str(shelter_name),
            "distance_km": round(float(row.distance_km), 2), "available_capacity": capacity, "allocated_people": allocated,
        })
        if remaining == 0:
            break
    return {"affected_population": affected_population, "allocated_people": affected_population - remaining,
            "waiting_people": remaining, "allocation_status": "Fully Allocated" if remaining == 0 else "Partially Allocated",
            "shelters": recommended}
