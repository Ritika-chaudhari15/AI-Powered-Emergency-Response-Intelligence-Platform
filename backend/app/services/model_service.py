from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd

MODEL_PATH = Path(__file__).resolve().parents[3] / "notebooks" / "impact_prediction_model.pkl"
FEATURE_COLUMNS = ["Magnitude", "WeatherScore", "WindSpeed", "PopulationDensity", "InfrastructureScore"]


@lru_cache
def load_model():
    """Load the trained pipeline once, rather than on every API request."""
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"Trained model not found at {MODEL_PATH}")
    return joblib.load(MODEL_PATH)


def predict_impact(features: dict[str, float]) -> float:
    """Run the exact feature order used when the impact model was trained."""
    model = load_model()
    input_frame = pd.DataFrame([[features[column] for column in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)
    return float(model.predict(input_frame)[0])
