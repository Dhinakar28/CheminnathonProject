"""
Train a simple RUL estimator by inferring RUL from unit id and cycle columns.
The script will try to find identifier and cycle-like columns automatically; you can pass names explicitly.

Usage:
  python -m src.train_rul --file data/raw/some.csv --id-col Unit --cycle-col cycle --outdir models_rul
"""
import argparse
from pathlib import Path
import joblib
import json

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error

from .core_trainers import train_rul_model
from .data_loader import load_any, find_raw_files
from .preprocess import preprocess_pipeline, scale_features


def infer_columns(df: pd.DataFrame):
    cols = df.columns.tolist()
    lower = [c.lower() for c in cols]
    id_candidates = [cols[i] for i, c in enumerate(lower) if any(x in c for x in ('id', 'unit', 'udi', 'serial', 'asset'))]
    cycle_candidates = [cols[i] for i, c in enumerate(lower) if any(x in c for x in ('cycle', 'time', 'op_cycle', 'timestamp'))]
    id_col = id_candidates[0] if id_candidates else None
    cycle_col = cycle_candidates[0] if cycle_candidates else None
    return id_col, cycle_col


def build_rul(df: pd.DataFrame, id_col: str, cycle_col: str):
    # compute RUL per-row: for each unit id, RUL = max(cycle) - cycle
    df = df.copy()
    df['_rul_unit_max'] = df.groupby(id_col)[cycle_col].transform('max')
    df['RUL'] = df['_rul_unit_max'] - df[cycle_col]
    return df


def train_rul(file: str, outdir: str = 'models_rul', id_col: str = None, cycle_col: str = None, n_estimators: int = 10, n_jobs: int = 1, no_feature_engineering: bool = True):
    # wrapper that calls core trainer
    return train_rul_model(file, id_col=id_col, cycle_col=cycle_col, outdir=outdir, n_estimators=n_estimators, n_jobs=n_jobs, feature_engineering=not no_feature_engineering)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--outdir', default='models_rul')
    parser.add_argument('--id-col', default=None)
    parser.add_argument('--cycle-col', default=None)
    parser.add_argument('--n-estimators', type=int, default=10)
    parser.add_argument('--n-jobs', type=int, default=1)
    parser.add_argument('--no-feature-engineering', action='store_true')
    args = parser.parse_args()
    res = train_rul(args.file, outdir=args.outdir, id_col=args.id_col, cycle_col=args.cycle_col, n_estimators=args.n_estimators, n_jobs=args.n_jobs, no_feature_engineering=args.no_feature_engineering)
    print('RUL train result:', res)
