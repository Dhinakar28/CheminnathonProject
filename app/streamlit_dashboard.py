import streamlit as st
from pathlib import Path
import joblib
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data_loader import load_any
from src.preprocess import preprocess_pipeline, scale_features
from src.train_rul import build_rul, infer_columns


MODELS_DIR = Path('models_auto_run')


def list_available_rul_models():
    """Return a list of available RUL model stems and their paths under MODELS_DIR."""
    out = []
    if not MODELS_DIR.exists():
        return out
    for ds in MODELS_DIR.iterdir():
        if not ds.is_dir():
            continue
        rul = ds / 'rul'
        if not rul.exists():
            continue
        # find meta files
        for meta in rul.glob('*__RUL__meta.json'):
            stem = meta.name.replace('__RUL__meta.json', '')
            model_file = rul / f"{stem}__RUL__rf.joblib"
            scaler_file = rul / f"{stem}__RUL__scaler.joblib"
            if model_file.exists() and scaler_file.exists():
                try:
                    meta_obj = json.load(open(meta))
                except Exception:
                    meta_obj = {}
                out.append((f"{ds.name}/{stem}", {
                    'meta': meta_obj,
                    'model': str(model_file),
                    'scaler': str(scaler_file),
                    'path': str(meta)
                }))
    return out

def find_models_for_dataset(stem: str):
    res = {'anomaly': None, 'classifier': None, 'rul': None}
    base = MODELS_DIR
    if not base.exists():
        return res
    
    dsdir = base / stem
    if not dsdir.exists():
        return res

    # Anomaly Model
    an = dsdir / 'anomaly'
    if an.exists():
        meta_file = an / f"{stem}__isof__meta.json"
        model_file = an / f"{stem}__isof.joblib"
        scaler_file = an / f"{stem}__scaler.joblib"
        
        if model_file.exists() and scaler_file.exists():
            res['anomaly'] = {
                'meta': json.load(open(meta_file)) if meta_file.exists() else {},
                'model': str(model_file),
                'scaler': str(scaler_file)
            }

    # Classifier Model
    clf = dsdir / 'classifier'
    if clf.exists():
        meta_files = list(clf.glob(f"{stem}*__meta.json"))
        if meta_files:
            meta = json.load(open(meta_files[0]))
            target = meta.get('target')
            model_file = clf / f"{stem}__{target.replace(' ', '_')}__rf_clf.joblib"
            scaler_file = clf / f"{stem}__{target.replace(' ', '_')}__scaler.joblib"
            if model_file.exists() and scaler_file.exists():
                res['classifier'] = {
                    'meta': meta,
                    'model': str(model_file),
                    'scaler': str(scaler_file)
                }

    # RUL Model
    rul = dsdir / 'rul'
    if rul.exists():
        meta_file = rul / f"{stem}__RUL__meta.json"
        model_file = rul / f"{stem}__RUL__rf.joblib"
        scaler_file = rul / f"{stem}__RUL__scaler.joblib"
        
        if model_file.exists() and scaler_file.exists():
            res['rul'] = {
                'meta': json.load(open(meta_file)) if meta_file.exists() else {},
                'model': str(model_file),
                'scaler': str(scaler_file)
            }
            
    return res


def run_anomaly_inference(model_path, scaler_path, df):
    iso = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    proc = preprocess_pipeline(df, do_feature_engineering=False)
    X = proc.select_dtypes(include=[np.number]).fillna(0)
    
    # Ensure columns match the training data
    if hasattr(scaler, 'n_features_in_') and X.shape[1] != scaler.n_features_in_:
        st.warning("Warning: The number of features in the loaded data doesn't match the scaler. Anomaly prediction may be unreliable.")
        return None, None
    
    Xs = scaler.transform(X)
    scores = iso.decision_function(Xs)
    preds = iso.predict(Xs)
    return preds, scores


def run_classifier_inference(model_path, scaler_path, df, target_col=None):
    clf = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    proc = preprocess_pipeline(df, do_feature_engineering=False)
    if target_col and target_col in proc.columns:
        X = proc.drop(columns=[target_col])
    else:
        X = proc.select_dtypes(include=[np.number]).fillna(0)
    
    if hasattr(scaler, 'n_features_in_') and X.shape[1] != scaler.n_features_in_:
        st.warning("Warning: The number of features in the loaded data doesn't match the scaler. Classification prediction may be unreliable.")
        return None, None

    Xs = scaler.transform(X)
    preds = clf.predict(Xs)
    probs = None
    try:
        probs = clf.predict_proba(Xs)
    except Exception:
        pass
    return preds, probs


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

    # Try to align features to those used at training if meta contains them
    meta = None
    try:
        # meta file expected next to model with name pattern <stem>__RUL__meta.json
        meta_path = Path(model_path).parent / f"{Path(model_path).stem}__meta.json"
        if not meta_path.exists():
            # also try the conventional meta filename
            meta_path = Path(model_path).parent / f"{Path(model_path).stem.replace('__RUL__rf','__RUL__meta')}.json"
        if meta_path.exists():
            with open(meta_path, 'r') as mf:
                meta = json.load(mf)
    except Exception:
        meta = None

    if meta and isinstance(meta.get('feature_columns'), list):
        trained_cols = meta['feature_columns']
        # add any missing columns as zeros, drop extra ones
        missing = [c for c in trained_cols if c not in X.columns]
        extra = [c for c in X.columns if c not in trained_cols]
        if missing:
            for c in missing:
                X[c] = 0
        if extra:
            X = X.drop(columns=extra)
        # reorder to match training
        X = X[trained_cols]

    # final check against scaler feature count
    if hasattr(scaler, 'n_features_in_') and X.shape[1] != scaler.n_features_in_:
        st.warning("Warning: The number of features after alignment doesn't match the scaler. Attempting to continue, but predictions may be degraded.")

    Xs = scaler.transform(X)
    preds = model.predict(Xs)
    return preds


def generate_maintenance_report(rul_preds, anom_preds, clf_preds, failure_modes_map):
    report_items = []
    
    # Anomaly Alert
    if anom_preds is not None:
        anom_rate = (anom_preds == -1).mean()
        if anom_rate > 0.05:
            report_items.append(f"**CRITICAL ANOMALY ALERT:** The system has detected an anomaly rate of **{anom_rate:.1%}**. This suggests an unusual operating condition that could lead to immediate failure. Immediate inspection is required. ⚠️")
        elif anom_rate > 0:
            report_items.append(f"**UNUSUAL BEHAVIOR DETECTED:** An anomaly rate of **{anom_rate:.1%}** was observed. This warrants close monitoring. 🧐")

    # RUL Prediction
    if rul_preds is not None and len(rul_preds) > 0:
        median_rul = np.median(rul_preds)
        if median_rul <= 5:
            report_items.append(f"**IMMINENT FAILURE:** The median Remaining Useful Life (RUL) is only **{median_rul:.1f} cycles**. Immediate maintenance is required to prevent catastrophic failure. 🚨")
        elif median_rul <= 20:
            report_items.append(f"**URGENT MAINTENANCE:** The median RUL is **{median_rul:.1f} cycles**. Maintenance is recommended within the next **{median_rul:.1f} cycles** to prevent unexpected downtime. 🔧")
        else:
            report_items.append(f"**HEALTHY:** The median RUL is **{median_rul:.1f} cycles**. The equipment is operating within normal limits. Regular monitoring is sufficient. ✅")

    # Failure Mode Diagnosis
    if clf_preds is not None:
        clf_preds_mapped = [failure_modes_map.get(str(int(p)), "Unknown") for p in clf_preds]
        failure_modes = pd.Series(clf_preds_mapped).value_counts()
        
        if 'none' in failure_modes.index:
            failure_modes = failure_modes.drop('none')
        if 'Unknown' in failure_modes.index:
            failure_modes = failure_modes.drop('Unknown')

        if not failure_modes.empty:
            report_items.append("**DIAGNOSIS:** The classifier predicts the following potential failure modes:")
            for mode, count in failure_modes.items():
                report_items.append(f" - **{mode}** detected in **{count}** instances.")

    if not report_items:
        report_items.append("**EQUIPMENT HEALTH: OK.** All systems are functioning within expected parameters. Continue regular monitoring.")

    return "\n\n".join(report_items)


def main():
    st.set_page_config(page_title='Equipment Health Dashboard', layout='wide')
    st.title('Equipment Health Dashboard')

    uploaded = st.file_uploader('Upload a CSV / MAT / TXT dataset', type=['csv', 'mat', 'txt', 'dat'])
    sample_selector = st.selectbox('Or choose a preloaded dataset', options=['--none--'] + [p.name for p in Path('data/raw').iterdir() if p.is_file()])

    df = None
    if uploaded is not None:
        tmp = Path('tmp_upload')
        tmp.mkdir(exist_ok=True)
        fp = tmp / uploaded.name
        with open(fp, 'wb') as f:
            f.write(uploaded.getbuffer())
        df = load_any(fp)
        stem = fp.stem
    elif sample_selector and sample_selector != '--none--':
        df = load_any(Path('data/raw') / sample_selector)
        stem = Path(sample_selector).stem
    else:
        st.info('Upload a dataset or choose a sample to begin')
        return

    st.subheader('Dataset Preview')
    st.dataframe(df.head(200))

    models = find_models_for_dataset(stem)
    st.subheader('Available Trained Models')
    st.json({k: bool(v) for k, v in models.items()})

    # If no RUL model was found for this stem, offer available RUL models from other datasets
    if not models.get('rul'):
        avail = list_available_rul_models()
        if avail:
            choices = ['--none--'] + [a[0] for a in avail]
            pick = st.selectbox('No exact RUL model found for this dataset. Choose an available RUL model to use instead', choices)
            if pick and pick != '--none--':
                # find chosen tuple
                for name, info in avail:
                    if name == pick:
                        models['rul'] = info
                        st.info(f'Using RUL model from: {name}')
                        break

    anom_preds = None
    clf_preds = None
    rul_preds = None
    
    # Heuristic mapping for classifier predictions
    failure_modes_map = {
        '0': 'none', '1': 'Tool Wear Failure', '2': 'Heat Dissipation Failure',
        '3': 'Power Failure', '4': 'Overstrain Failure', '5': 'Random Failure',
        '6': 'bearing', '7': 'wear', '8': 'electrical'
    }

    with st.spinner('Running models...'):
        if models['anomaly'] and models['anomaly'].get('model') and Path(models['anomaly']['model']).exists():
            try:
                anom_preds, anom_scores = run_anomaly_inference(models['anomaly']['model'], models['anomaly']['scaler'], df)
            except Exception as e:
                st.error(f'Anomaly inference failed: {e}')
                
        if models['classifier'] and models['classifier'].get('model') and Path(models['classifier']['model']).exists():
            try:
                clf_preds, probs = run_classifier_inference(models['classifier']['model'], models['classifier']['scaler'], df, target_col=models['classifier']['meta'].get('target'))
            except Exception as e:
                st.error(f'Classifier inference failed: {e}')

        if models['rul'] and models['rul'].get('model') and Path(models['rul']['model']).exists():
            try:
                rul_preds = run_rul_inference(models['rul']['model'], models['rul']['scaler'], df, id_col=models['rul']['meta'].get('id_col'), cycle_col=models['rul']['meta'].get('cycle_col'))
            except Exception as e:
                st.error(f'RUL inference failed: {e}')

    st.subheader('Equipment Health Report')
    st.markdown(generate_maintenance_report(rul_preds, anom_preds, clf_preds, failure_modes_map))

    st.subheader('Detailed Insights from Data and Models')

    numcols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numcols:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown('**Anomaly & Time-Series Plot**')
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.set_title(f'Time-series for {numcols[0]}')
            ax.set_xlabel('Index')
            ax.set_ylabel(numcols[0])
            ax.grid(True)
            
            ax.plot(df.index, df[numcols[0]], color='blue', label='Sensor Value')
            
            if anom_preds is not None:
                anomalies = df[anom_preds == -1]
                ax.scatter(anomalies.index, anomalies[numcols[0]], color='red', s=50, zorder=5, label='Anomaly Detected')
            
            ax.legend()
            st.pyplot(fig)
            st.markdown("This plot shows the raw sensor data over time. Red points indicate instances of detected **anomalies**, highlighting unusual behavior that may require investigation.")

        with col2:
            st.markdown('**Remaining Useful Life (RUL) Prediction**')
            if rul_preds is not None:
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.set_title('Remaining Useful Life (RUL) Prediction')
                ax.set_xlabel('Index')
                ax.set_ylabel('Predicted RUL')
                ax.grid(True)
                
                ax.plot(df.index, rul_preds, color='green')
                ax.axhline(y=20, color='orange', linestyle='--', label='Maintenance Threshold (20 cycles)')
                ax.axhline(y=5, color='red', linestyle='--', label='Critical Threshold (5 cycles)')
                
                ax.legend()
                st.pyplot(fig)
                st.markdown("This graph shows the equipment's remaining useful life. A sharp drop below the thresholds indicates a need for proactive maintenance.")
            else:
                st.info("RUL model not available for plotting.")

if __name__ == '__main__':
    main()