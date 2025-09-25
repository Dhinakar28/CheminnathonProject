"""
Lightweight inference helpers for the web UI. These mirror the Streamlit inference logic
but avoid importing streamlit so they can be used from a Flask app.
"""
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from .preprocess import preprocess_pipeline, scale_features
from .train_rul import build_rul, infer_columns
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler


def _load_meta_near_model(model_path):
    try:
        model_path = Path(model_path)
        # try conventional meta filenames nearby
        cand = model_path.parent / f"{model_path.stem}__meta.json"
        if cand.exists():
            return json.load(open(cand))
        # fallback patterns
        for p in model_path.parent.glob('*__meta.json'):
            try:
                m = json.load(open(p))
                # best-effort: prefer meta that references same file
                if 'model_path' in m and Path(m['model_path']).name == model_path.name:
                    return m
            except Exception:
                continue
    except Exception:
        pass
    return None


def _align_features(X: pd.DataFrame, trained_cols: list):
    # Add missing cols filled with 0, drop extra, reorder
    X = X.copy()
    missing = [c for c in trained_cols if c not in X.columns]
    extra = [c for c in X.columns if c not in trained_cols]
    if missing:
        for c in missing:
            X[c] = 0
    if extra:
        X = X.drop(columns=extra)
    X = X[trained_cols]
    return X


def run_anomaly_inference(model_path, scaler_path, df):
    iso = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    proc = preprocess_pipeline(df, do_feature_engineering=False)
    X = proc.select_dtypes(include=[np.number]).fillna(0)

    meta = _load_meta_near_model(model_path)
    if meta and isinstance(meta.get('feature_columns'), list):
        X = _align_features(X, meta['feature_columns'])

    # final check
    if hasattr(scaler, 'n_features_in_') and X.shape[1] != scaler.n_features_in_:
        # try best-effort: pad or trim
        if X.shape[1] < scaler.n_features_in_:
            for i in range(scaler.n_features_in_ - X.shape[1]):
                X[f'_pad_{i}'] = 0
        else:
            X = X.iloc[:, :scaler.n_features_in_]

    Xs = scaler.transform(X)
    scores = iso.decision_function(Xs)
    preds = iso.predict(Xs)
    # convert to lists for JSON
    preds_list = np.asarray(preds).tolist()
    scores_list = np.asarray(scores).tolist()
    n_samples = int(len(preds_list))
    n_anomalies = int(sum(1 for p in preds_list if p == -1))
    anomaly_rate = n_anomalies / max(1, n_samples)
    # small sample for debugging
    sample_preds = preds_list[:20]
    summary = {'n_samples': n_samples, 'n_anomalies': n_anomalies, 'anomaly_rate': float(anomaly_rate)}

    # drill-down: return top anomalous rows (first N) with top contributing numeric features
    anom_indexes = [i for i, p in enumerate(preds_list) if p == -1]
    anom_details = []
    try:
        top_n = min(10, len(anom_indexes))
        if top_n > 0:
            # compute robust z-scores on numeric features
            numeric = X.select_dtypes(include=[np.number])
            med = numeric.median()
            std = numeric.std(ddof=0).replace(0, 1e-9)
            for idx in anom_indexes[:top_n]:
                row = numeric.iloc[idx]
                # top contributing features by absolute z-score
                z = ((row - med) / std).abs()
                topk = z.sort_values(ascending=False).head(4).index.tolist()
                contrib = []
                for f in topk:
                    val = row[f]
                    zl = float(((row[f] - med[f]) / std[f]))
                    contrib.append({'feature': f, 'value': float(val), 'z_score': round(zl, 2)})
                # include a compact snapshot of the row (first 8 numeric cols)
                snapshot = {c: float(numeric.iloc[idx][c]) for c in numeric.columns[:8]}
                anom_details.append({'index': int(idx), 'snapshot': snapshot, 'top_features': contrib})
    except Exception:
        anom_details = []

    # remediation suggestions (generic) — these are high-level and should be validated by engineers
    suggestions = []
    if anomaly_rate > 0.1:
        suggestions.append('HIGH ANOMALY RATE — stop production and perform immediate inspection of sensors and mechanical systems.')
        suggestions.append('Prioritize units with highest anomaly scores for manual inspection and run diagnostic routines.')
    elif anomaly_rate > 0.02:
        suggestions.append('Moderate anomaly rate — investigate sensors with frequent anomalies and review recent maintenance logs.')
    else:
        suggestions.append('Low anomaly rate — monitor and schedule routine checks. Consider recalibrating sensors if isolated spikes observed.')

    return {'preds': preds_list, 'scores': scores_list, 'sample_preds': sample_preds, 'summary': summary, 'details': anom_details, 'suggestions': suggestions, 'meta': meta}


def run_classifier_inference(model_path, scaler_path, df, target_col=None):
    clf = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    proc = preprocess_pipeline(df, do_feature_engineering=False)
    if target_col and target_col in proc.columns:
        X = proc.drop(columns=[target_col])
    else:
        X = proc.select_dtypes(include=[np.number]).fillna(0)

    meta = _load_meta_near_model(model_path)
    if meta and isinstance(meta.get('feature_columns'), list):
        X = _align_features(X, meta['feature_columns'])

    if hasattr(scaler, 'n_features_in_') and X.shape[1] != scaler.n_features_in_:
        if X.shape[1] < scaler.n_features_in_:
            for i in range(scaler.n_features_in_ - X.shape[1]):
                X[f'_pad_{i}'] = 0
        else:
            X = X.iloc[:, :scaler.n_features_in_]

    Xs = scaler.transform(X)
    preds = clf.predict(Xs)
    probs = None
    try:
        probs = clf.predict_proba(Xs)
    except Exception:
        probs = None
    preds_list = np.asarray(preds).tolist()
    probs_list = np.asarray(probs).tolist() if probs is not None else None
    unique_preds = list(np.unique(preds_list))
    # counts per class
    try:
        counts = pd.Series(preds_list).value_counts().to_dict()
        # convert keys to strings for JSON stability
        counts = {str(k): int(v) for k, v in counts.items()}
    except Exception:
        counts = {}
    # top class
    top_class = None
    if counts:
        top_class = max(counts.items(), key=lambda kv: kv[1])[0]
    sample_preds = preds_list[:50]
    summary = {'n_samples': int(len(preds_list)), 'counts': counts, 'top_class': top_class}
    return {'preds': preds_list, 'probs': probs_list, 'sample_preds': sample_preds, 'summary': summary, 'meta': meta}


def run_rul_inference(model_path, scaler_path, df, id_col=None, cycle_col=None):
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)

    df_temp = df.copy()
    if not id_col or not cycle_col:
        id_col_inferred, cycle_col_inferred = infer_columns(df_temp)
        if id_col_inferred and cycle_col_inferred:
            id_col = id_col_inferred
            cycle_col = cycle_col_inferred

    if id_col and cycle_col and id_col in df_temp.columns and cycle_col in df_temp.columns:
        df_temp = build_rul(df_temp, id_col, cycle_col)
        df_proc = preprocess_pipeline(df_temp.drop(columns=[id_col, cycle_col]), do_feature_engineering=False)
    else:
        df_proc = preprocess_pipeline(df_temp, do_feature_engineering=False)

    X = df_proc.select_dtypes(include=[np.number]).fillna(0)

    meta = _load_meta_near_model(model_path)
    if meta and isinstance(meta.get('feature_columns'), list):
        X = _align_features(X, meta['feature_columns'])

    if hasattr(scaler, 'n_features_in_') and X.shape[1] != scaler.n_features_in_:
        if X.shape[1] < scaler.n_features_in_:
            for i in range(scaler.n_features_in_ - X.shape[1]):
                X[f'_pad_{i}'] = 0
        else:
            X = X.iloc[:, :scaler.n_features_in_]

    Xs = scaler.transform(X)
    preds = model.predict(Xs)
    preds_list = np.asarray(preds).tolist()
    n = int(len(preds_list))
    sample_preds = preds_list[:50]
    # basic stats and percentiles
    median = float(np.median(preds_list)) if n > 0 else None
    mean = float(np.mean(preds_list)) if n > 0 else None
    p10 = float(np.percentile(preds_list, 10)) if n > 0 else None
    p25 = float(np.percentile(preds_list, 25)) if n > 0 else None
    p75 = float(np.percentile(preds_list, 75)) if n > 0 else None
    p90 = float(np.percentile(preds_list, 90)) if n > 0 else None
    # histogram (10 bins)
    try:
        hist_counts, hist_edges = np.histogram(preds_list, bins=10)
        # create readable bin labels
        bins = [f"{hist_edges[i]:.1f} - {hist_edges[i+1]:.1f}" for i in range(len(hist_edges)-1)]
        hist_counts = [int(x) for x in hist_counts]
    except Exception:
        bins = []
        hist_counts = []
    summary = {'n_samples': n, 'median': median, 'mean': mean, 'p10': p10, 'p25': p25, 'p75': p75, 'p90': p90, 'hist_bins': bins, 'hist_counts': hist_counts}
    return {'preds': preds_list, 'sample_preds': sample_preds, 'summary': summary, 'meta': meta}


def generate_maintenance_report(rul_preds, anom_preds, clf_preds, failure_modes_map):
    report_items = []
    if anom_preds is not None:
        anom_rate = anom_preds.get('n_anomalies', 0) / max(1, anom_preds.get('n_samples', 1))
        if anom_rate > 0.05:
            report_items.append(f"CRITICAL ANOMALY ALERT: anomaly rate {anom_rate:.1%}")
        elif anom_rate > 0:
            report_items.append(f"UNUSUAL BEHAVIOR: anomaly rate {anom_rate:.1%}")

    if rul_preds is not None and rul_preds.get('preds') is not None:
        median_rul = float(np.median(rul_preds['preds']))
        if median_rul <= 5:
            report_items.append(f"IMMINENT FAILURE: median RUL {median_rul:.1f} cycles")
        elif median_rul <= 20:
            report_items.append(f"URGENT MAINTENANCE: median RUL {median_rul:.1f} cycles")
        else:
            report_items.append(f"HEALTHY: median RUL {median_rul:.1f} cycles")

    if clf_preds is not None and clf_preds.get('preds') is not None:
        mapped = [failure_modes_map.get(str(int(p)), 'Unknown') for p in clf_preds['preds']]
        counts = pd.Series(mapped).value_counts()
        if 'none' in counts.index:
            counts = counts.drop('none')
        if counts.size > 0:
            for mode, cnt in counts.items():
                report_items.append(f"{mode}: {cnt} instances")

    if not report_items:
        report_items.append('EQUIPMENT HEALTH: OK')

    return report_items


def run_noise_robust_isof(df: pd.DataFrame, contamination=0.01, n_estimators=200, max_samples='auto', smoothing=False, smooth_window=3, random_state=42):
    """Run a local, noise-robust IsolationForest on the provided dataframe.

    Returns a JSON-serializable dict with preds, scores, summary and details.
    This function intentionally does not modify or overwrite any saved models or artifacts.
    """
    proc = preprocess_pipeline(df, do_feature_engineering=False)
    X = proc.select_dtypes(include=[np.number]).fillna(0)

    if X.shape[1] == 0:
        return {'error': 'no numeric features', 'preds': None, 'scores': None, 'summary': None}

    # optional median smoothing to reduce high-frequency noise
    if smoothing and isinstance(smooth_window, int) and smooth_window > 1:
        try:
            X = X.rolling(window=smooth_window, min_periods=1, center=True).median()
            X = X.fillna(method='bfill').fillna(method='ffill').fillna(0)
        except Exception:
            X = X.fillna(0)

    scaler = RobustScaler()
    try:
        Xs = scaler.fit_transform(X)
    except Exception:
        Xs = X.values

    iso = IsolationForest(n_estimators=int(n_estimators), contamination=float(contamination), max_samples=max_samples, random_state=int(random_state))
    iso.fit(Xs)
    scores = iso.decision_function(Xs)
    preds = iso.predict(Xs)

    preds_list = np.asarray(preds).tolist()
    scores_list = np.asarray(scores).tolist()
    n_samples = int(len(preds_list))
    n_anomalies = int(sum(1 for p in preds_list if p == -1))
    anomaly_rate = n_anomalies / max(1, n_samples)
    summary = {'n_samples': n_samples, 'n_anomalies': n_anomalies, 'anomaly_rate': float(anomaly_rate)}

    # small drill-down similar to run_anomaly_inference: top anomalous rows and top contributing features
    anom_indexes = [i for i, p in enumerate(preds_list) if p == -1]
    anom_details = []
    try:
        top_n = min(10, len(anom_indexes))
        if top_n > 0:
            numeric = X.select_dtypes(include=[np.number])
            med = numeric.median()
            std = numeric.std(ddof=0).replace(0, 1e-9)
            for idx in anom_indexes[:top_n]:
                row = numeric.iloc[idx]
                z = ((row - med) / std).abs()
                topk = z.sort_values(ascending=False).head(4).index.tolist()
                contrib = []
                for f in topk:
                    val = row[f]
                    zl = float(((row[f] - med[f]) / std[f]))
                    contrib.append({'feature': f, 'value': float(val), 'z_score': round(zl, 2)})
                snapshot = {c: float(numeric.iloc[idx][c]) for c in numeric.columns[:8]}
                anom_details.append({'index': int(idx), 'snapshot': snapshot, 'top_features': contrib})
    except Exception:
        anom_details = []

    suggestions = []
    if anomaly_rate > 0.1:
        suggestions.append('HIGH ANOMALY RATE — consider detailed inspection or tighter contamination.')
    elif anomaly_rate > 0.02:
        suggestions.append('Moderate anomaly rate — consider reviewing smoothing and contamination settings.')
    else:
        suggestions.append('Low anomaly rate — robust detector sees few anomalies.')

    return {'preds': preds_list, 'scores': scores_list, 'summary': summary, 'details': anom_details, 'suggestions': suggestions}
