"""
Load a saved model and make predictions on a dataset or a new sample CSV.
"""
from pathlib import Path
import joblib
import pandas as pd

from .data_loader import load_any
from .preprocess import preprocess_pipeline, scale_features


def predict(model_path: str, scaler_path: str, input_path: str, target_col: str = None):
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    df = load_any(input_path)
    df_proc = preprocess_pipeline(df)
    if target_col and target_col in df_proc.columns:
        X = df_proc.drop(columns=[target_col])
    else:
        # assume model trained on a set of features; try to align columns
        X = df_proc
    Xs, _ = scale_features(X, scaler=scaler)
    preds = model.predict(Xs)
    out = pd.DataFrame({"prediction": preds})
    return out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--scaler", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--target", default=None)
    parser.add_argument("--out", default="predictions.csv")
    args = parser.parse_args()
    outdf = predict(args.model, args.scaler, args.input, args.target)
    outdf.to_csv(args.out, index=False)
    print("Wrote:", args.out)
