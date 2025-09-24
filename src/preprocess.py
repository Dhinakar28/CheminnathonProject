"""
Preprocessing utilities: cleaning, simple feature engineering and scaling.
Designed to be robust to heterogeneous sensor datasets.
"""
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler


def basic_clean(df: pd.DataFrame, drop_threshold=0.5):
    """Drop columns with too many missing values, forward/backfill small gaps, convert non-numeric if possible."""
    df = df.copy()
    # coerce to numeric where possible
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    # drop columns with > drop_threshold fraction missing
    miss_frac = df.isna().mean()
    keep_cols = miss_frac[miss_frac <= drop_threshold].index.tolist()
    df = df[keep_cols]
    # small-gap interpolation
    df = df.interpolate(limit_direction="both", limit=10)
    # final fill (use ffill/bfill to avoid deprecated fillna(method=...))
    df = df.ffill().bfill().fillna(0)
    return df


def add_rolling_features(df: pd.DataFrame, windows=(3, 5, 10)):
    df = df.copy()
    for w in windows:
        df_rolled = df.rolling(window=w, min_periods=1).agg(["mean", "std"])
        # flatten multiindex
        df_rolled.columns = [f"{c[0]}_r{w}_{c[1]}" for c in df_rolled.columns]
        df = pd.concat([df, df_rolled], axis=1)
    return df


def add_lag_features(df: pd.DataFrame, lags=(1, 2, 3)):
    df = df.copy()
    for lag in lags:
        shifted = df.shift(lag)
        shifted.columns = [f"{c}_lag{lag}" for c in df.columns]
        df = pd.concat([df, shifted], axis=1)
    df = df.fillna(0)
    return df


def extract_features(df: pd.DataFrame):
    df = df.copy()
    numeric = df.select_dtypes(include=[np.number])
    # simple statistics
    stats = pd.DataFrame({
        "_mean": numeric.mean(),
        "_std": numeric.std(),
        "_min": numeric.min(),
        "_max": numeric.max()
    }).T
    # but keep time-series features per-row via rolling and lag
    df = add_rolling_features(numeric)
    df = add_lag_features(df)
    return df


def scale_features(X: pd.DataFrame, scaler: StandardScaler = None):
    if scaler is None:
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
    else:
        Xs = scaler.transform(X)
    Xs = pd.DataFrame(Xs, index=X.index, columns=X.columns)
    return Xs, scaler


def preprocess_pipeline(df: pd.DataFrame, do_feature_engineering=True):
    df = basic_clean(df)
    if do_feature_engineering:
        # attempt the full feature engineering, but guard against explosive feature counts
        df_fe = extract_features(df)
        # if number of features explodes (e.g., > 500), fall back to a lightweight set
        MAX_FEATURES = 500
        if df_fe.shape[1] > MAX_FEATURES:
            # lightweight fallback: rolling mean/std with small window and a single lag
            numeric = df.select_dtypes(include=[np.number])
            df_roll = numeric.rolling(window=3, min_periods=1).agg(["mean", "std"])
            df_roll.columns = [f"{c[0]}_r3_{c[1]}" for c in df_roll.columns]
            lag1 = numeric.shift(1).fillna(0)
            lag1.columns = [f"{c}_lag1" for c in numeric.columns]
            df_light = pd.concat([numeric, df_roll, lag1], axis=1)
            df = df_light
        else:
            df = df_fe
    # remove constant columns
    df = df.loc[:, df.nunique() > 1]
    return df


def save_processed(df: pd.DataFrame, out_path: str):
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)
    return p
