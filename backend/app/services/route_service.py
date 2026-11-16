from datetime import datetime, timedelta, timezone

import requests

from app.services import allocation_service


OSRM_URL = "https://router.project-osrm.org/route/v1/driving"


def route_between(origin_latitude: float, origin_longitude: float, destination_latitude: float, destination_longitude: float,
                  road_risks: list[dict] | None = None) -> dict:
    """Return a drivable geometry from a current vehicle position to a destination."""
    road_risks = road_risks or []
    direct = allocation_service.haversine_distance_km(origin_latitude, origin_longitude, destination_latitude, destination_longitude)
    waypoints, excluded_risk_ids = [], []
    for risk in road_risks:
        risk_lat, risk_lon = float(risk["latitude"]), float(risk["longitude"])
        via = (allocation_service.haversine_distance_km(origin_latitude, origin_longitude, risk_lat, risk_lon)
               + allocation_service.haversine_distance_km(risk_lat, risk_lon, destination_latitude, destination_longitude))
        if via <= direct * 1.2:
            waypoints.append(f"{risk_lon + 0.12},{risk_lat + 0.12}")
            excluded_risk_ids.append(int(risk["id"]))
    coordinates = ";".join([f"{origin_longitude},{origin_latitude}", *waypoints, f"{destination_longitude},{destination_latitude}"])
    try:
        response = requests.get(f"{OSRM_URL}/{coordinates}", params={"overview": "full", "geometries": "geojson"}, timeout=15)
        response.raise_for_status()
        route = response.json()["routes"][0]
        distance_km, duration_minutes, geometry, source = route["distance"] / 1000, route["duration"] / 60, route["geometry"], "osrm"
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        distance_km, duration_minutes, geometry, source = direct, direct / 50 * 60, {"type": "LineString", "coordinates": [[origin_longitude, origin_latitude], [destination_longitude, destination_latitude]]}, "estimated_fallback"
    return {"distance_km": round(distance_km, 2), "duration_minutes": round(duration_minutes, 1), "geometry": geometry,
            "route_source": source, "excluded_road_risk_ids": excluded_risk_ids,
            "route_safety_status": "risk_aware_detour" if waypoints else ("risks_not_on_route" if road_risks else "no_active_risks")}


def plan_route(latitude: float, longitude: float, road_risks: list[dict] | None = None) -> dict:
    """Route from the nearest warehouse to the disaster location using free public OSRM."""
    inventory = allocation_service.load_inventory()
    warehouses = inventory[["WarehouseID", "WarehouseName", "State", "Latitude", "Longitude"]].drop_duplicates("WarehouseID")
    warehouses["distance_to_disaster_km"] = warehouses.apply(
        lambda row: allocation_service.haversine_distance_km(latitude, longitude, float(row.Latitude), float(row.Longitude)), axis=1
    )
    warehouse = warehouses.sort_values("distance_to_disaster_km").iloc[0]
    route = route_between(float(warehouse.Latitude), float(warehouse.Longitude), latitude, longitude, road_risks)
    distance_km, duration_minutes, geometry, source = route["distance_km"], route["duration_minutes"], route["geometry"], route["route_source"]
    eta = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
    return {
        "warehouse_id": warehouse.WarehouseID, "warehouse_name": warehouse.WarehouseName, "warehouse_state": warehouse.State,
        "distance_km": round(distance_km, 2), "duration_minutes": round(duration_minutes, 1),
        "estimated_arrival_at": eta, "route_source": source, "geometry": geometry,
        "excluded_road_risk_ids": route["excluded_road_risk_ids"], "route_safety_status": route["route_safety_status"],
    }
