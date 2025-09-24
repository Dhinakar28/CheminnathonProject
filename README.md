# CheminnathonProject

This repository contains sensor datasets and helper scripts to preprocess and train predictive-maintenance models.

Quick start

1. Install dependencies (use a venv):

```powershell
python -m pip install -r requirements.txt
```

2. List available raw datasets:

```powershell
python -c "from src.data_loader import find_raw_files; print('\n'.join(map(str, find_raw_files())))"
```

3. Train a model on a file and target column (example using ai4i2020):

```powershell
python -m src.train --file data/raw/ai4i2020.csv --target "Air temperature (K)" --outdir models
```

4. Predict using a saved model:

```powershell
python -m src.predict --model models/ai4i2020__Air_temperature_(K)__rf.joblib --scaler models/ai4i2020__Air_temperature_(K)__scaler.joblib --input data/raw/ai4i2020.csv --out preds.csv
```

Notes
- The scripts use a small feature-engineering pipeline (rolling statistics, lags) and a RandomForestRegressor by default. You can adapt `src/train.py` to use XGBoost/LightGBM or neural nets if desired.
- If your target column name doesn't match exactly, pass any substring and the script will try to match a column.

Classification example (failure-mode detection)

```powershell
python -m src.train_classifier --file data/raw/ai4i2020.csv --target "Machine failure" --outdir models_clf --no-feature-engineering

python -m src.predict_classifier --model models_clf/ai4i2020__Machine_failure__rf_clf.joblib --scaler models_clf/ai4i2020__Machine_failure__scaler.joblib --input data/raw/ai4i2020.csv --out preds_clf.csv
```

Unified auto-train (pick a task)

```powershell
# anomaly detection
python -m src.auto_train --task anomaly --file data/raw/ai4i2020.csv --outdir models_auto_anom

# classification
python -m src.auto_train --task classify --file data/raw/ai4i2020.csv --target "Machine failure" --outdir models_auto_clf

# regression (e.g., RUL or a sensor reading)
python -m src.auto_train --task regression --file data/raw/ai4i2020.csv --target "Tool wear [min]" --outdir models_auto_reg
```

Streamlit dashboard

1. Install dependencies (if not already):

```powershell
python -m pip install -r requirements.txt
```

2. Run the dashboard (PowerShell):

```powershell
python -m streamlit run app/streamlit_dashboard.py
```

The app allows uploading CSV/MAT/TXT files, previews the dataset, shows quick plots, and — if models were produced by the automated training scripts under `models_auto_run/` — runs anomaly, classifier and RUL inference and displays a simple equipment status (OK / Needs maintenance / Critical).