"""
Simple anomaly detection helpers using IsolationForest.
Provides train and predict helpers for early-fault detection.
"""
from pathlib import Path
import joblib
import json
import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest

from .core_trainers import train_anomaly_model


def train_anomaly(input_path: str, outdir: str = 'models_anomaly', contamination: float = 0.01, do_feature_engineering: bool = True):
    # wrapper that calls core trainer
    return train_anomaly_model(input_path, outdir=outdir, contamination=contamination, feature_engineering=do_feature_engineering)
