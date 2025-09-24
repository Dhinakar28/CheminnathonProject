"""
Train a regressor for a selected dataset and target sensor column.
Usage example (from repo root):
    python -m src.train --file data/raw/ai4i2020.csv --target "Air temperature (K)"

The script will:
- load dataset
- run preprocessing pipeline
- split into train/test
- train a RandomForestRegressor
- evaluate and save model + scaler
"""
import argparse
from pathlib import Path
import joblib
import json

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from .core_trainers import train_regression
from .data_loader import load_any, find_raw_files
from .preprocess import preprocess_pipeline, scale_features


def train(args):
    # wrapper to call core trainer
    res = train_regression(args.file, target=args.target, outdir=args.outdir, test_size=args.test_size, n_estimators=args.n_estimators, n_jobs=args.n_jobs, feature_engineering=getattr(args, 'feature_engineering', True))
    print('Regression train result:', res)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to dataset file (csv or mat) or filename located in raw folders")
    parser.add_argument("--target", required=True, help="Target column name (exact or substring) to predict")
    parser.add_argument("--outdir", default="models", help="Output folder to save model and artifacts")
    parser.add_argument("--test-size", type=float, default=0.2, help="Test size fraction")
    parser.add_argument("--n-estimators", type=int, default=100, help="Number of trees for RandomForest")
    parser.add_argument("--n-jobs", type=int, default=1, help="n_jobs for RandomForest (-1 for all cores)")
    parser.add_argument("--no-feature-engineering", dest='feature_engineering', action='store_false', help="Disable rolling/lag feature engineering to speed up training")
    parser.set_defaults(feature_engineering=True)
    args = parser.parse_args()
    try:
        train(args)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("Training failed:", e)
        raise
