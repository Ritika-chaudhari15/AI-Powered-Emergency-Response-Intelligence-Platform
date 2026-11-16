import pandas as pd
import joblib
import os

inventory = pd.read_csv(r"C:\Users\RITIKA CHAUDHARI\Documents\GitHub\AI-Based-Disaster-Response-Management-System-for-Resource-Allocation-and-Relief-Coordina_Jun_2026\models\inventory.csv")
inventory = dict(zip(inventory["Inventory"], inventory["Availability"]))

# =====================================================
# LOAD TRAINED MODELS
# =====================================================

BASE_DIR = os.path.dirname(__file__)

water_model = joblib.load(
    os.path.join(BASE_DIR,
    "Water_Required_Liters_DecisionTree.joblib")
)

rescue_model = joblib.load(
    os.path.join(BASE_DIR,
    "Rescue_Teams_Required_DecisionTree.joblib")
)

ambulance_model = joblib.load(
    os.path.join(BASE_DIR,
    "Ambulances_Required_DecisionTree.joblib")
)

# =====================================================
# SAMPLE DISASTER
# =====================================================

data = {
    "Disaster Type": "Flood",
    "Alert Level": "Green",
    "Severity": 2.0,
    "Severity Score": 20,
    "Population Affected": 80,
    "People Injured": 9,
    "Total Deaths": 3,
    "Latitude": 10.3333,
    "Longitude": 33.7685,
    "Temperature (°C)": 29,   
    "Rainfall (mm)": 10,
    "Wind Speed (km/h)": 15,
    "Population Density": 18000,
    "Road Count": 250,
    "Hospitals": 18,
    "Shelters": 25,
    "Infrastructure Score": 70,
    "Vulnerability Score": 20,
    "Impact Score": 30,
    "Priority Score": 36
}

# =====================================================
# CREATE DATAFRAME
# =====================================================

df = pd.DataFrame([data])

# =====================================================
# TEMPORARY ENCODING
# Replace after saving encoders
# =====================================================

df["Disaster Type"] = 1
df["Alert Level"] = 0

# =====================================================
# KEEP ONLY TRAINING FEATURES
# =====================================================

feature_columns = [
    "Disaster Type",
    "Alert Level",
    "Severity",
    "Severity Score",
    "Population Affected",
    "People Injured",
    "Total Deaths",
    "Latitude",
    "Longitude",
    "Temperature (°C)",
    "Rainfall (mm)",
    "Wind Speed (km/h)",
    "Population Density",
    "Road Count",
    "Hospitals",
    "Shelters",
    "Infrastructure Score",
    "Vulnerability Score",
    "Impact Score",
    "Priority Score"
]

df = df[feature_columns]

# =====================================================
# MODEL PREDICTIONS
# =====================================================


water = water_model.predict(df)[0]
rescue = rescue_model.predict(df)[0]
ambulance = ambulance_model.predict(df)[0]
food = data["Population Affected"] // 5
medical = data["People Injured"]
blankets = data["Population Affected"] // 4
vehicles = round(rescue)
boats = 5 if data["Disaster Type"] == "Flood" else 0
helicopters = max(1, round(rescue / 10))

# =====================================================
# REQUIRED RESOURCES
# =====================================================

required = {
    "Water(in ltr)": round(water),
    "Food kit": food,
    "Medical kit": medical,
    "Vehicals": vehicles,
    "Ambulances": round(ambulance),
    "Blankets": blankets,
    "Boat": boats,
    "Helicopter": helicopters
}

# =====================================================
# DISPLAY RESULTS
# =====================================================

print("\n" + "=" * 60)
print("DISASTER DETAILS")
print("=" * 60)

for key, value in data.items():
    print(f"{key:<30}: {value:,}" if isinstance(value, int) else f"{key:<30}: {value}")

print("\n" + "=" * 60)
print("MODEL PREDICTIONS")
print("=" * 60)

print(f"{'Water Required (Liters)':<30}: {round(water):,}")
print(f"{'Food Kits Required':<30}: {food:,}")
print(f"{'Medical Kits Required':<30}: {medical:,}")
print(f"{'Rescue Teams Required':<30}: {round(rescue):,}")
print(f"{'Vehicles Required':<30}: {vehicles:,}")
print(f"{'Ambulances Required':<30}: {round(ambulance):,}")
print(f"{'Blankets Required':<30}: {blankets:,}")
print(f"{'Boats Required':<30}: {boats:,}")
print(f"{'Helicopters Required':<30}: {helicopters:,}")

print("\n" + "=" * 80)
print("INVENTORY STATUS")
print("=" * 80)

print(f"{'Resource':<20}{'Required':>15}{'Available':>15}{'Status':>15}")
print("-" * 70)

for item in required:

    needed = required[item]
    available = inventory[item]

    status = "SHORTAGE" if needed > available else "SUFFICIENT"

    print(
        f"{item:<20} "
        f"{needed:>15,} "
        f"{available:>15,} "
        f"{status:>15} "
    )


print("\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)

for item in required:

    needed = required[item]
    available = inventory[item]

    if needed > available:
        print(f"• {item:<20}: Need {needed - available:,} additional units")
    else:
        print(f"• {item:<20}:  Inventory Sufficient")