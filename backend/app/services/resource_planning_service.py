"""Rule-based resource requirements used before warehouse allocation."""

from math import ceil


def calculate_requirements(affected_population: int, disaster_type: str, predicted_impact_score: float) -> dict[str, int]:
    """Calculate all resources stocked in each warehouse for a three-day response."""
    children = affected_population * 0.27
    adults = affected_population * 0.60
    elderly = affected_population * 0.13
    critical_patients = ceil(affected_population * 0.05)
    severity_multiplier = 1.25 if predicted_impact_score >= 70 else 1.0
    supplies = {
        "Food Packets": ceil(affected_population * 3 * 3 * severity_multiplier),
        "Water Bottles": ceil(affected_population * 5 * 3 * severity_multiplier),
        "Medical Kits": ceil((children * 0.10 + adults * 0.05 + elderly * 0.15) * severity_multiplier),
        "Blankets": ceil(affected_population * severity_multiplier),
        "Temporary Tents": ceil(affected_population / 5),
        "Rescue Teams": ceil(affected_population / 250),
        "Ambulances": ceil(critical_patients / 4),
        "Boats": ceil(affected_population / 5000) if disaster_type.lower() == "flood" else 0,
        "Helicopters": ceil(critical_patients / 400) if predicted_impact_score >= 70 else 0,
    }
    total_weight_kg = (
        supplies["Food Packets"] * 0.5
        + supplies["Water Bottles"] * 1.0
        + supplies["Medical Kits"] * 0.3
        + supplies["Blankets"] * 2.5
        + supplies["Temporary Tents"] * 20.0
    )
    supplies["Trucks"] = ceil(total_weight_kg / 8000)
    return supplies
