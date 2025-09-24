"""
Retrain RUL models for any existing RUL meta under models_auto_run/*/rul that are missing 'feature_columns'.
This script runs with conservative settings (n_estimators=10, n_jobs=1, no_feature_engineering=True) to be quick.
Run:
    python scripts/retrain_missing_rul.py
"""
from pathlib import Path
import sys
import json

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.train_rul import train_rul, infer_columns
from src.data_loader import load_any

MODELS_BASE = Path('models_auto_run')
meta_paths = list(MODELS_BASE.rglob('*__RUL__meta.json'))
if not meta_paths:
    print('No RUL meta files found under models_auto_run/.')
    raise SystemExit(0)

retrained = []
for mp in meta_paths:
    try:
        print('\nChecking', mp)
        meta = json.load(open(mp))
        if isinstance(meta, dict) and 'feature_columns' in meta:
            print('  Already has feature_columns; skipping')
            continue
        # find original data file
        data_file = meta.get('file') if isinstance(meta, dict) else None
        if not data_file:
            print('  No "file" key in meta; skipping')
            continue
        data_path = Path(data_file)
        if not data_path.exists():
            # try relative to repo root
            data_path = (REPO_ROOT / data_file).resolve()
        if not data_path.exists():
            print('  Data file not found:', data_file)
            continue
        # load data and infer id/cycle
        df = load_any(data_path)
        id_col, cycle_col = infer_columns(df)
        if not id_col or not cycle_col:
            print(f'  Could not infer id/cycle for {data_path}; skipping')
            continue
        outdir = mp.parent
        print(f'  Retraining RUL for {data_path} with id={id_col}, cycle={cycle_col} -> outdir={outdir}')
        try:
            res = train_rul(str(data_path), outdir=str(outdir), id_col=id_col, cycle_col=cycle_col, n_estimators=10, n_jobs=1, no_feature_engineering=True)
            print('  Retrain result:', res)
            retrained.append((str(mp), res))
        except Exception as e:
            print('  Retrain failed:', e)
    except Exception as e:
        print('Error while processing', mp, e)

print('\nDone. Retrained:', len(retrained))
for m, r in retrained:
    print(' -', m, '->', r)
