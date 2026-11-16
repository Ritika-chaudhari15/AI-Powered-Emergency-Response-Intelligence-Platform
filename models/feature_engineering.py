import os
import pandas as pd
from sklearn.preprocessing import LabelEncoder
import joblib


input_path = r"C:\Users\RITIKA CHAUDHARI\Downloads\merged.csv"
df = pd.read_csv(input_path)
print(f"Dataset Shape: {df.shape}")

df.columns = df.columns.str.strip()

numeric_columns = [
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
    "Priority Score",
    "Rescue Teams Required",
    "Ambulances Required",
    "Water Required (Liters)"
]
for col in numeric_columns:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].fillna(df[col].median())

encoders = {}
categorical_columns = [
    "Disaster Type",
    "Alert Level"
]
for col in categorical_columns:
    encoder = LabelEncoder()
    df[col] = encoder.fit_transform(df[col].astype(str))
    encoders[col] = encoder

os.makedirs("models", exist_ok=True)
joblib.dump(
    encoders["Disaster Type"],
    "models/disaster_encoder.pkl"
)
joblib.dump(
    encoders["Alert Level"],
    "models/alert_encoder.pkl"
)
print("Encoders saved successfully.")

# Weather Risk
df["Weather Risk"] = (
    0.5 * df["Rainfall (mm)"] +
    0.3 * df["Wind Speed (km/h)"] +
    0.2 * df["Temperature (°C)"]
)


df = df.rename(columns={"Infrastructure Score": "Infrastructure Score (Weighted)"})
df["Infrastructure Score"] = (
    df["Hospitals"] +
    df["Shelters"]
)

# Accessibility Score
df["Accessibility Score"] = (
    df["Road Count"] /
    (df["Population Density"] + 1)
)



# Food Kits Required: 1 kit per person (individual kits)
df["Food Kits Required"] = df["Population Affected"].round().astype(int)

# Medical Kits Required: tied to People Injured + a population baseline
# (1 kit per 100 affected people, plus 1 kit per injured person)
import numpy as np
df["Medical Kits Required"] = (
    df["People Injured"] + np.ceil(df["Population Affected"] / 100)
).astype(int)


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
    "Weather Risk",
    "Infrastructure Score",
    "Infrastructure Score (Weighted)",
    "Accessibility Score",
    "Vulnerability Score",
    "Impact Score",
    "Priority Score",
    "Food Kits Required",
    "Medical Kits Required",
    "Rescue Teams Required",
    "Ambulances Required",
    "Water Required (Liters)"
]
df = df[feature_columns]


os.makedirs("datasets/processed", exist_ok=True)
output_path = "datasets/processed/model_ready.csv"
df.to_csv(output_path, index=False)

print(f"Saved to: {output_path}")
print(df.columns.tolist())
print(df.head())
print("\n===== NORMALIZATION VALUES =====\n")

columns = [
    "Severity",
    "Population Affected",
    "Population Density",
    "Hospitals",
    "Shelters",
    "Road Count",
    "People Injured",
    "Total Deaths"
]

for col in columns:
    print(f"{col}:")
    print("Min =", df[col].min())
    print("Max =", df[col].max())
    print()