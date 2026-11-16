import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score

df = pd.read_csv(r"C:\Users\RITIKA CHAUDHARI\Downloads\merged.csv")

print("Dataset Shape:", df.shape)
encoder = LabelEncoder()
for col in ["Disaster Type", "Alert Level"]:
    if col in df.columns:
        df[col] = encoder.fit_transform(df[col].astype(str))
        
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
    "Priority Score"
]

feature_columns = [col for col in feature_columns if col in df.columns]

X = df[feature_columns]

print("\nFeatures Used:")
print(feature_columns)

target_columns = [
    "Food Kits Required",
    "Medical Kits Required",
    "Water Required (Liters)",
    "Rescue Teams Required",
    "Ambulances Required"
]

target_columns = [col for col in target_columns if col in df.columns]

print("\nTargets Used:")
print(target_columns)

for target in target_columns:

    print("\nTraining Model for:", target)

    Y = df[target]

    X_train, X_test, Y_train, Y_test = train_test_split(
        X,
        Y,
        test_size=0.2,
        random_state=42
    )


    model = DecisionTreeRegressor(random_state=42)

    
    model.fit(X_train, Y_train)

    
    prediction = model.predict(X_test)

    
    mae = mean_absolute_error(Y_test, prediction)
    r2 = r2_score(Y_test, prediction)

    print("MAE :", round(mae, 2))
    print("R² Score :", round(r2, 4))

    # Save Model
    filename = target.replace(" ", "_").replace("(", "").replace(")", "") + "_DecisionTree.joblib"

    joblib.dump(model, filename)
