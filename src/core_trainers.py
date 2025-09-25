"""
Core trainer functions (no CLI). These are safe to import and call programmatically.
"""
from pathlib import Path
import joblib
import json
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, accuracy_score, f1_score, precision_score, recall_score

from .data_loader import load_any, find_raw_files
from .preprocess import preprocess_pipeline, scale_features


def train_regression(file: str, target: str, outdir: str = 'models_reg', test_size: float = 0.2, n_estimators: int = 50, n_jobs: int = 1, feature_engineering: bool = True):
    p = Path(file)
    df = load_any(p)
    df_proc = preprocess_pipeline(df, do_feature_engineering=feature_engineering)
    # find target
    if target not in df_proc.columns:
        possible = [c for c in df_proc.columns if target.lower() in c.lower()]
        if possible:
            target_col = possible[0]
        else:
            raise ValueError(f'Target {target} not found')
    else:
        target_col = target

    X = df_proc.drop(columns=[target_col]).select_dtypes(include=[np.number]).fillna(0)
    y = df_proc[target_col]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)
    X_train_s, scaler = scale_features(X_train)
    X_test_s, _ = scale_features(X_test, scaler=scaler)

    model = RandomForestRegressor(n_estimators=n_estimators, random_state=42, n_jobs=n_jobs)
    model.fit(X_train_s, y_train)
    y_pred = model.predict(X_test_s)
    metrics = {'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred))), 'mae': float(mean_absolute_error(y_test, y_pred))}

    outp = Path(outdir)
    outp.mkdir(parents=True, exist_ok=True)
    model_path = outp / f"{p.stem}__{target_col.replace(' ', '_')}__rf.joblib"
    scaler_path = outp / f"{p.stem}__{target_col.replace(' ', '_')}__scaler.joblib"
    meta_path = outp / f"{p.stem}__{target_col.replace(' ', '_')}__meta.json"

    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    with open(meta_path, 'w') as f:
        json.dump({'file': str(p), 'target': target_col, 'metrics': metrics, 'model_path': str(model_path), 'scaler_path': str(scaler_path)}, f, indent=2)

    return {'model': str(model_path), 'scaler': str(scaler_path), 'metrics': metrics}


def train_classification(file: str, target: str, outdir: str = 'models_clf', test_size: float = 0.2, n_estimators: int = 50, n_jobs: int = 1, feature_engineering: bool = True):
    p = Path(file)
    df = load_any(p)
    df_proc = preprocess_pipeline(df, do_feature_engineering=feature_engineering)
    if target not in df_proc.columns:
        possible = [c for c in df_proc.columns if target.lower() in c.lower()]
        if possible:
            target_col = possible[0]
        else:
            raise ValueError(f'Target {target} not found')
    else:
        target_col = target

    X = df_proc.drop(columns=[target_col]).select_dtypes(include=[np.number]).fillna(0)
    y = df_proc[target_col]

    if y.dtype.kind in 'fc':
        y = y.round().astype(int)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42, stratify=y if len(np.unique(y))>1 else None)
    # record feature columns so we can align at inference time
    feature_columns = list(X_train.columns)
    X_train_s, scaler = scale_features(X_train)
    X_test_s, _ = scale_features(X_test, scaler=scaler)

    clf = RandomForestClassifier(n_estimators=n_estimators, random_state=42, n_jobs=n_jobs)
    clf.fit(X_train_s, y_train)
    y_pred = clf.predict(X_test_s)

    metrics = {'accuracy': float(accuracy_score(y_test, y_pred)), 'f1_macro': float(f1_score(y_test, y_pred, average='macro', zero_division=0))}

    outp = Path(outdir)
    outp.mkdir(parents=True, exist_ok=True)
    model_path = outp / f"{p.stem}__{target_col.replace(' ', '_')}__rf_clf.joblib"
    scaler_path = outp / f"{p.stem}__{target_col.replace(' ', '_')}__scaler.joblib"
    meta_path = outp / f"{p.stem}__{target_col.replace(' ', '_')}__meta.json"

    joblib.dump(clf, model_path)
    joblib.dump(scaler, scaler_path)
    with open(meta_path, 'w') as f:
        json.dump({'file': str(p), 'target': target_col, 'metrics': metrics, 'model_path': str(model_path), 'scaler_path': str(scaler_path), 'feature_columns': feature_columns}, f, indent=2)

    return {'model': str(model_path), 'scaler': str(scaler_path), 'metrics': metrics}


def train_anomaly_model(file: str, outdir: str = 'models_anom', contamination: float = 0.01, feature_engineering: bool = True):
    p = Path(file)
    df = load_any(p)
    df_proc = preprocess_pipeline(df, do_feature_engineering=feature_engineering)
    X = df_proc.select_dtypes(include=[np.number]).fillna(0)
    # record features present at training time
    feature_columns = list(X.columns)
    Xs, scaler = scale_features(X)
    iso = IsolationForest(contamination=contamination, random_state=42)
    iso.fit(Xs)

    outp = Path(outdir)
    outp.mkdir(parents=True, exist_ok=True)
    model_path = outp / f"{p.stem}__isof.joblib"
    scaler_path = outp / f"{p.stem}__scaler.joblib"
    meta_path = outp / f"{p.stem}__meta.json"
    joblib.dump(iso, model_path)
    joblib.dump(scaler, scaler_path)

    scores = iso.decision_function(Xs)
    preds = iso.predict(Xs)
    n_anom = int((preds == -1).sum())
    meta = {'file': str(p), 'n_samples': int(Xs.shape[0]), 'n_features': int(Xs.shape[1]), 'n_anomalies': n_anom, 'feature_columns': feature_columns}
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    return {'model': str(model_path), 'scaler': str(scaler_path), 'meta': meta}


def train_rul_model(file: str, id_col: str, cycle_col: str, outdir: str = 'models_rul', n_estimators: int = 10, n_jobs: int = 1, feature_engineering: bool = True):
    # reuse train_rul logic but simplified
    p = Path(file)
    df = load_any(p)
    if id_col not in df.columns or cycle_col not in df.columns:
        raise ValueError('id_col or cycle_col not present')
    df2 = df.copy()
    df2['_rul_unit_max'] = df2.groupby(id_col)[cycle_col].transform('max')
    df2['RUL'] = df2['_rul_unit_max'] - df2[cycle_col]

    df_proc = preprocess_pipeline(df2.drop(columns=[id_col, cycle_col]), do_feature_engineering=feature_engineering)
    if 'RUL' not in df_proc.columns:
        df_proc = pd.concat([df_proc.reset_index(drop=True), df2['RUL'].reset_index(drop=True)], axis=1)

    X = df_proc.drop(columns=['RUL']).select_dtypes(include=[np.number]).fillna(0)
    y = df_proc['RUL']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    # record feature columns used for training so inference can align columns later
    feature_columns = list(X_train.columns)
    X_train_s, scaler = scale_features(X_train)
    X_test_s, _ = scale_features(X_test, scaler=scaler)
    model = RandomForestRegressor(n_estimators=n_estimators, random_state=42, n_jobs=n_jobs)
    model.fit(X_train_s, y_train)
    y_pred = model.predict(X_test_s)
    metrics = {'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred))), 'mae': float(mean_absolute_error(y_test, y_pred))}

    outp = Path(outdir)
    outp.mkdir(parents=True, exist_ok=True)
    model_path = outp / f"{p.stem}__RUL__rf.joblib"
    scaler_path = outp / f"{p.stem}__RUL__scaler.joblib"
    meta_path = outp / f"{p.stem}__RUL__meta.json"
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    with open(meta_path, 'w') as f:
        json.dump({'file': str(p), 'metrics': metrics, 'model_path': str(model_path), 'scaler_path': str(scaler_path), 'id_col': id_col, 'cycle_col': cycle_col, 'feature_columns': feature_columns}, f, indent=2)
    return {'model': str(model_path), 'scaler': str(scaler_path), 'metrics': metrics}
