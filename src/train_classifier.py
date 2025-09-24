"""
Train a classifier for failure-mode detection on a chosen dataset and target label.
Usage:
  python -m src.train_classifier --file data/raw/ai4i2020.csv --target "Machine failure" --outdir models_clf

This script reuses the preprocessing pipeline and trains a RandomForestClassifier baseline.
"""
import argparse
from pathlib import Path
import joblib
import json

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, confusion_matrix

from .core_trainers import train_classification
from .data_loader import load_any, find_raw_files
from .preprocess import preprocess_pipeline, scale_features


def train(args):
    res = train_classification(args.file, args.target, outdir=args.outdir, test_size=args.test_size, n_estimators=args.n_estimators, n_jobs=args.n_jobs, feature_engineering=not args.no_feature_engineering)
    print('Classification train result:', res)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--outdir', default='models_clf')
    parser.add_argument('--test-size', type=float, default=0.2)
    parser.add_argument('--n-estimators', type=int, default=100)
    parser.add_argument('--n-jobs', type=int, default=1)
    parser.add_argument('--no-feature-engineering', action='store_true', help='Disable heavy feature engineering')
    args = parser.parse_args()
    train(args)
