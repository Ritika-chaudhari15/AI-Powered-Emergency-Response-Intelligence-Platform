"""Fetch and transform current weather into the model's engineered weather features."""

import logging

import requests


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
logger = logging.getLogger(__name__)


def get_current_weather(latitude: float, longitude: float) -> dict[str, float]:
    """Fetch current weather for the disaster location from Open-Meteo."""
    response = requests.get(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        },
        timeout=10,
    )
    response.raise_for_status()
    current = response.json()["current"]
    return {
        "temperature": float(current["temperature_2m"]),
        "humidity": float(current["relative_humidity_2m"]),
        "rainfall": float(current["precipitation"]),
        "wind_speed": float(current["wind_speed_10m"]),
    }


def calculate_weather_score(weather: dict[str, float]) -> float:
    """Create a 0–1 weather score from temperature, humidity, and precipitation."""
    temperature_score = min(max(weather["temperature"] / 50.0, 0.0), 1.0)
    humidity_score = min(max(weather["humidity"] / 100.0, 0.0), 1.0)
    rainfall_score = min(max(weather["rainfall"] / 50.0, 0.0), 1.0)
    return round((temperature_score + humidity_score + rainfall_score) / 3, 6)


def estimate_population_density(affected_population: int) -> float:
    """Use the affected population over a 25 km response area as a density proxy."""
    return round(affected_population / (3.141592653589793 * 25 ** 2), 6)


def get_infrastructure_score(latitude: float, longitude: float) -> float:
    """Use nearby OSM hospitals, clinics, schools, and fire stations to score infrastructure."""
    query = f"""
    [out:json][timeout:10];
    (
      nwr["amenity"~"hospital|clinic|school|fire_station"](around:25000,{latitude},{longitude});
    );
    out center;
    """
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            headers={"User-Agent": "DisasterResponseManagementSystem/1.0"},
            timeout=20,
        )
        response.raise_for_status()
        facility_count = len(response.json()["elements"])
        # A higher number of nearby response facilities means stronger infrastructure.
        return round(min(facility_count / 50.0, 1.0), 6)
    except (requests.RequestException, KeyError, TypeError, ValueError) as error:
        # Overpass can reject or rate-limit public queries. Do not prevent a field
        # team from recording a disaster report when this optional enrichment fails.
        logger.warning("OSM infrastructure lookup failed; using neutral score: %s", error)
        return 0.5
