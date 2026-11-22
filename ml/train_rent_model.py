from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from app.db import db_cursor

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "rent_model.joblib"

FEATURES = ["bedrooms", "property_type", "town"]
CATEGORICAL = ["property_type", "town"]
TARGET = "listed_rent_pcm"


def load_data():
    sql = "SELECT bedrooms, property_type, town, listed_rent_pcm FROM properties"
    with db_cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    data = pd.DataFrame(rows)
    data[TARGET] = data[TARGET].astype(float)
    return data


def make_pipeline(model):
    preprocess = ColumnTransformer(
        [("categories", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL)],
        remainder="passthrough",  # bedrooms is already a number
    )
    return Pipeline([("preprocess", preprocess), ("model", model)])


def evaluate(name, model, X, y, folds):
    # Every row is predicted by a model that never saw it during training.
    predictions = cross_val_predict(make_pipeline(model), X, y, cv=folds)
    residuals = y - predictions  # actual minus predicted
    result = {
        "name": name,
        "model": model,
        "mae": float(mean_absolute_error(y, predictions)),
        "r2": float(r2_score(y, predictions)),
        "residual_p10": float(np.percentile(residuals, 10)),
        "residual_p90": float(np.percentile(residuals, 90)),
    }
    print(f"{name:<14} MAE £{result['mae']:6.1f}   R2 {result['r2']:6.3f}")
    return result


def main():
    data = load_data()
    X = data[FEATURES]
    y = data[TARGET]
    print(f"Training on {len(data)} properties")

    folds = KFold(n_splits=5, shuffle=True, random_state=42)
    candidates = [
        ("baseline mean", DummyRegressor()),
        ("linear", LinearRegression()),
        ("random forest", RandomForestRegressor(
            n_estimators=300, min_samples_leaf=2, random_state=42)),
    ]
    results = [evaluate(name, model, X, y, folds) for name, model in candidates]

    # The baseline is only a yardstick, so it is never chosen.
    real_models = [r for r in results if r["name"] != "baseline mean"]
    best = min(real_models, key=lambda r: r["mae"])
    print(f"Chosen model: {best['name']}")

    final = make_pipeline(best["model"]).fit(X, y)

    MODEL_PATH.parent.mkdir(exist_ok=True)
    joblib.dump(
        {
            "pipeline": final,
            "features": FEATURES,
            "model_name": best["name"],
            "mae": best["mae"],
            "r2": best["r2"],
            "residual_p10": best["residual_p10"],
            "residual_p90": best["residual_p90"],
            "trained_rows": len(data),
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "towns": sorted(data["town"].unique().tolist()),
            "property_types": sorted(data["property_type"].unique().tolist()),
        },
        MODEL_PATH,
    )
    print(f"Saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()
