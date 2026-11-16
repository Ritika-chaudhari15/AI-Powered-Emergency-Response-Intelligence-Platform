import os
import pandas as pd

print("Loading datasets...")

# Load datasets
gdacs = pd.read_csv("datasets/raw/gdacs.csv")
weather = pd.read_csv("datasets/raw/weather.csv")
osm = pd.read_csv("datasets/raw/osm.csv")
worldpop = pd.read_csv("datasets/raw/worldpop.csv")

# -----------------------------
# Step 1: Clean column names
# -----------------------------
gdacs.columns = gdacs.columns.str.strip()
weather.columns = weather.columns.str.strip()
osm.columns = osm.columns.str.strip()
worldpop.columns = worldpop.columns.str.strip()

# -----------------------------
# Step 2: Merge GDACS + Weather
# -----------------------------
merged = pd.merge(
    gdacs,
    weather,
    on=["Latitude", "Longitude"],
    how="left",
    suffixes=("", "_weather")
)

# -----------------------------
# Step 3: Merge WorldPop
# -----------------------------
merged = pd.merge(
    merged,
    worldpop,
    on=["Latitude", "Longitude"],
    how="left",
    suffixes=("", "_pop")
)

# -----------------------------
# Step 4: Merge OSM
# -----------------------------
merged = pd.merge(
    merged,
    osm,
    on=["Latitude", "Longitude"],
    how="left",
    suffixes=("", "_osm")
)

# -----------------------------
# Step 5: Remove leftover suffix noise safely
# -----------------------------
merged.columns = merged.columns.str.replace(r"_x$|_y$", "", regex=True)

# -----------------------------
# Step 6: Create output folder
# -----------------------------
os.makedirs("datasets/processed", exist_ok=True)

# -----------------------------
# Step 7: Save final dataset
# -----------------------------
output_path = "datasets/processed/merged_dataset.csv"
merged.to_csv(output_path, index=False)

print("\nMerged dataset created successfully!")
print(f"Saved to: {output_path}")

print("\nPreview:")
print(merged.head())