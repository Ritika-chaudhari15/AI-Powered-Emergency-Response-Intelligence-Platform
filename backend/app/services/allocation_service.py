"""Nearest-warehouse resource allocation using the project's inventory dataset."""

from collections import defaultdict
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import pandas as pd


INVENTORY_PATH = Path(__file__).resolve().parents[3] / "datasets" / "inventory.csv"
REQUIRED_COLUMNS = {
    "WarehouseID",
    "WarehouseName",
    "State",
    "Latitude",
    "Longitude",
    "Resource",
    "AvailableQuantity",
}


def load_inventory() -> pd.DataFrame:
    """Load the source inventory without modifying it; allocations are request simulations."""
    if not INVENTORY_PATH.is_file():
        raise FileNotFoundError(f"Inventory file not found at {INVENTORY_PATH}")
    inventory = pd.read_csv(INVENTORY_PATH)
    missing = REQUIRED_COLUMNS.difference(inventory.columns)
    if missing:
        raise ValueError(f"Inventory file is missing columns: {', '.join(sorted(missing))}")
    return inventory


def list_warehouses() -> list[dict]:
    """Return every warehouse with its location and currently available inventory."""
    inventory = load_inventory()
    warehouses: dict[str, dict] = {}

    for row in inventory.to_dict("records"):
        warehouse_id = str(row["WarehouseID"])
        warehouse = warehouses.setdefault(
            warehouse_id,
            {
                "warehouse_id": warehouse_id,
                "warehouse_name": str(row["WarehouseName"]),
                "state": str(row["State"]),
                "latitude": float(row["Latitude"]),
                "longitude": float(row["Longitude"]),
                "inventory": [],
            },
        )
        warehouse["inventory"].append(
            {
                "resource": str(row["Resource"]),
                "available_quantity": int(row["AvailableQuantity"]),
            }
        )

    return list(warehouses.values())


def haversine_distance_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    """Return the great-circle distance between two geographic coordinates."""
    latitude_a, longitude_a, latitude_b, longitude_b = map(
        radians, (latitude_a, longitude_a, latitude_b, longitude_b)
    )
    delta_latitude = latitude_b - latitude_a
    delta_longitude = longitude_b - longitude_a
    haversine = sin(delta_latitude / 2) ** 2 + cos(latitude_a) * cos(latitude_b) * sin(delta_longitude / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(haversine))


def allocate_resources(latitude: float, longitude: float, required_resources: dict[str, int]) -> dict:
    """Allocate each requested resource from warehouses in increasing distance order."""
    inventory = load_inventory()
    available_resources = set(inventory["Resource"])
    unknown_resources = set(required_resources).difference(available_resources)
    if unknown_resources:
        raise ValueError(f"Unknown resources: {', '.join(sorted(unknown_resources))}")

    warehouse_rows = inventory[
        ["WarehouseID", "WarehouseName", "State", "Latitude", "Longitude"]
    ].drop_duplicates(subset="WarehouseID")
    warehouses = []
    for row in warehouse_rows.to_dict("records"):
        row["distance_km"] = round(
            haversine_distance_km(latitude, longitude, float(row["Latitude"]), float(row["Longitude"])), 2
        )
        warehouses.append(row)
    warehouses.sort(key=lambda warehouse: warehouse["distance_km"])

    stock = defaultdict(dict)
    for row in inventory.to_dict("records"):
        stock[row["WarehouseID"]][row["Resource"]] = int(row["AvailableQuantity"])

    allocations = {}
    for resource, required in required_resources.items():
        remaining = required
        supplies = []
        for warehouse in warehouses:
            if remaining == 0:
                break
            available = stock[warehouse["WarehouseID"]].get(resource, 0)
            quantity = min(remaining, available)
            if quantity == 0:
                continue
            stock[warehouse["WarehouseID"]][resource] -= quantity
            remaining -= quantity
            supplies.append(
                {
                    "warehouse_id": warehouse["WarehouseID"],
                    "warehouse_name": warehouse["WarehouseName"],
                    "state": warehouse["State"],
                    "distance_km": warehouse["distance_km"],
                    "quantity": quantity,
                }
            )
        allocations[resource] = {
            "required": required,
            "allocated": required - remaining,
            "shortage": remaining,
            "supplies": supplies,
        }

    nearest = warehouses[0]
    return {
        "nearest_warehouse_id": nearest["WarehouseID"],
        "nearest_warehouse_name": nearest["WarehouseName"],
        "nearest_warehouse_distance_km": nearest["distance_km"],
        "allocation_status": "Complete" if all(item["shortage"] == 0 for item in allocations.values()) else "Partial",
        "allocations": allocations,
    }
