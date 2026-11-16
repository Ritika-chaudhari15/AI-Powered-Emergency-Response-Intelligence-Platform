import numpy as np
import pandas as pd


DATA_DIR = r"C:\Users\RITIKA CHAUDHARI\Downloads\disaster_data_cleaned (1)\cleaned_data"
OUT_PATH = r"C:\Users\RITIKA CHAUDHARI\Downloads\merged.csv"

    
DEFAULTS = {
    "Population Density": 12, "Road Count": 110, "Hospitals": 3, "Shelters": 3,
    "Temperature (°C)": 23, "Rainfall (mm)": 40, "Wind Speed (km/h)": 20,
}
eq = pd.read_csv(f"{DATA_DIR}/earthquake_cleaned.csv")
eq_std = pd.DataFrame({
    "Source": "earthquake_cleaned",
    "Disaster Type": "Earthquake",
    "Country": eq["place"].str.split(",").str[-1].str.strip(),
    "Location": eq["place"],
    "Date": pd.to_datetime(eq["time"], format="mixed", errors="coerce").dt.date.astype(str),
    "Latitude": eq["latitude"],
    "Longitude": eq["longitude"],
    "Severity": eq["mag"],
    "Population Affected": 100,         
    "People Injured": 0,                 
    "Total Deaths": 0,                  
})

em = pd.read_csv(f"{DATA_DIR}/emdat_cleaned.csv")
em_std = pd.DataFrame({
    "Source": "emdat_cleaned",
    "Disaster Type": em["disaster_type"],
    "Country": em["country"],
    "Location": em["location"],
    "Date": em["start_date"],
    "Latitude": em["latitude"],
    "Longitude": em["longitude"],
    "Severity": em["magnitude"],
    "Population Affected": em["total_affected"],
    "People Injured": em["no_injured"],  
    "Total Deaths": em["total_deaths"],  
})

gd = pd.read_csv(f"{DATA_DIR}/global_disaster_cleaned.csv")
gd_std = pd.DataFrame({
    "Source": "global_disaster_cleaned",
    "Disaster Type": gd["disaster_type"],
    "Country": gd["country"],
    "Location": gd["country"],           
    "Date": gd["date"],
    "Latitude": gd["latitude"],
    "Longitude": gd["longitude"],
    "Severity": gd["severity_index"],
    "Population Affected": gd["casualties"],
    "People Injured": 0,                 
    "Total Deaths": gd["casualties"],   
})

merged = pd.concat([eq_std, em_std, gd_std], ignore_index=True, sort=False)

 
merged["Population Affected"] = merged["Population Affected"].fillna(100)
merged["Severity"] = merged["Severity"].fillna(0)
merged["People Injured"] = merged["People Injured"].fillna(0)
merged["Total Deaths"] = merged["Total Deaths"].fillna(0)


for col, default_val in DEFAULTS.items():
    merged[col] = default_val

def normalize(series, group=None):
    """0-1 min-max normalization, done per Disaster Type so wildly different
    units across sources (e.g. earthquake magnitude vs. flood area) don't
    get squashed by one extreme outlier."""
    if group is not None:
        lo = series.groupby(group).transform("min")
        hi = series.groupby(group).transform("max")
    else:
        lo, hi = series.min(), series.max()
    span = (hi - lo)
    span = span.where(span != 0, 1) if hasattr(span, "where") else (span if span != 0 else 1)
    return (series - lo) / span

dtype = merged["Disaster Type"]
M = normalize(merged["Severity"], dtype)             
A = normalize(merged["Population Affected"], dtype)  
P = normalize(merged["Population Density"], dtype)
I = (normalize(merged["Hospitals"], dtype)
     + normalize(merged["Shelters"], dtype)
     + normalize(merged["Road Count"], dtype)) / 3 

merged["Severity Score"] = ((0.40 * M + 0.30 * A + 0.20 * P + 0.10 * I) * 100).round(2)
merged["Infrastructure Score"] = (I * 100).round(2)
merged["Alert Level"] = np.select(
    [merged["Severity Score"] < 40, merged["Severity Score"] < 70],
    ["Green", "Orange"],
    default="Red",
)


max_pop = merged["Population Affected"].max()
merged["Vulnerability Score"] = (
    0.6 * (merged["Severity Score"] / 100) + 0.4 * (merged["Population Affected"] / max_pop)
).round(3)


A_impact = normalize(merged["Population Affected"], dtype) 
J_impact = normalize(merged["People Injured"], dtype)
D_impact = normalize(merged["Total Deaths"], dtype)

merged["Impact Score"] = (
    0.40 * (merged["Severity Score"] / 100)
    + 0.30 * A_impact
    + 0.20 * J_impact
    + 0.10 * D_impact
) * 100
merged["Impact Score"] = merged["Impact Score"].round(2)


merged["Priority Score"] = (
    0.25 * (merged["Severity Score"] / 100)
    + 0.25 * (merged["Impact Score"] / 100)
    + 0.25 * merged["Vulnerability Score"]
    + 0.25 * (1 - merged["Infrastructure Score"] / 100)
) * 100
merged["Priority Score"] = merged["Priority Score"].round(2)


density_factor = 1 + normalize(merged["Population Density"], dtype)
merged["Water Required (Liters)"] = (
    merged["Population Affected"] * 5 * 5 * density_factor
).round().astype(int)


merged["Rescue Teams Required"] = np.maximum(1, np.ceil(merged["Population Affected"] / 500)).astype(int)
merged["Ambulances Required"] = np.maximum(1, np.ceil(merged["Population Affected"] / 1000)).astype(int)


merged["Location"] = merged["Location"].fillna("Unknown")
merged["Date"] = merged["Date"].fillna("Not Available")

FINAL_COLUMNS = [
    "Source", "Disaster Type", "Country", "Location", "Date",
    "Alert Level", "Severity", "Severity Score", "Population Affected",
    "People Injured", "Total Deaths",
    "Latitude", "Longitude", "Temperature (°C)", "Rainfall (mm)",
    "Wind Speed (km/h)", "Population Density", "Road Count", "Hospitals",
    "Shelters", "Infrastructure Score", "Vulnerability Score", "Impact Score",
    "Priority Score",
    "Rescue Teams Required", "Ambulances Required", "Water Required (Liters)",
]
merged = merged[FINAL_COLUMNS]
merged.to_csv(OUT_PATH, index=False)
print(f"Merged {len(merged)} rows -> {OUT_PATH}")
print(merged["Source"].value_counts())