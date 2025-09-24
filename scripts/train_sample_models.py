"""Train quick baseline models (anomaly, classifier, RUL) on data/raw/sample_maintenance.csv
Saves artifacts under models_auto_run/sample_maintenance/{anomaly,classifier,rul}
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core_trainers import train_anomaly_model, train_classification, train_rul_model


if __name__ == '__main__':
    f = 'data/raw/sample_maintenance.csv'
    print('Training anomaly...')
    res_an = train_anomaly_model(f, outdir='models_auto_run/sample_maintenance/anomaly', contamination=0.02, feature_engineering=False)
    print('Anomaly done:', res_an)

    print('Training classifier (failure_flag)...')
    res_clf = train_classification(f, target='failure_flag', outdir='models_auto_run/sample_maintenance/classifier', n_estimators=16, n_jobs=1, feature_engineering=False)
    print('Classifier done:', res_clf)

    print('Training RUL...')
    res_rul = train_rul_model(f, id_col='unit', cycle_col='cycle', outdir='models_auto_run/sample_maintenance/rul', n_estimators=16, n_jobs=1, feature_engineering=False)
    print('RUL done:', res_rul)
