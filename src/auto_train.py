"""
Unified auto-train CLI. Usage:
  python -m src.auto_train --task anomaly --file data/raw/ai4i2020.csv --outdir models_auto

Tasks: anomaly | classify | regression
"""
import argparse
from pathlib import Path
import json

from .core_trainers import train_anomaly_model, train_classification, train_regression, train_rul_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', required=True, choices=['anomaly', 'classify', 'regression'])
    parser.add_argument('--file', required=True)
    parser.add_argument('--target', required=False)
    parser.add_argument('--outdir', default='models_auto')
    parser.add_argument('--n-estimators', type=int, default=50)
    parser.add_argument('--n-jobs', type=int, default=1)
    parser.add_argument('--no-feature-engineering', action='store_true')
    args = parser.parse_args()

    if args.task == 'anomaly':
        res = train_anomaly_model(args.file, outdir=args.outdir, feature_engineering=not args.no_feature_engineering)
        print('Anomaly model saved:', res)
    elif args.task == 'classify':
        if not args.target:
            raise SystemExit('Classification requires --target')
        res = train_classification(args.file, args.target, outdir=args.outdir, test_size=0.2, n_estimators=args.n_estimators, n_jobs=args.n_jobs, feature_engineering=not args.no_feature_engineering)
        print('Classification result:', res)
    elif args.task == 'regression':
        if not args.target:
            raise SystemExit('Regression requires --target')
        res = train_regression(args.file, args.target, outdir=args.outdir, test_size=0.2, n_estimators=args.n_estimators, n_jobs=args.n_jobs, feature_engineering=not args.no_feature_engineering)
        print('Regression result:', res)
    elif args.task == 'rul':
        # RUL estimation: train using id/cycle inference not implemented here; call train_rul_model separately when columns are known
        raise SystemExit('Use the `rul` task only when you provide id/cycle columns via the train_rul CLI or call core functions programmatically')


if __name__ == '__main__':
    main()
