"""
Orchestrator to run anomaly detection, classification (if label present), and RUL (if id/cycle present)
on all discovered datasets in data/raw and raw. Uses conservative defaults to avoid long runs.

It will create per-dataset subfolders under models_auto_run/ with artifacts and a summary JSON.
"""
from pathlib import Path
import json
import sys
from pathlib import Path as _Path

# Ensure repository root is on sys.path when running this script directly
REPO_ROOT = _Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data_loader import find_raw_files, load_any
from src.preprocess import basic_clean
from src.anomaly import train_anomaly
from src.train_classifier import train as train_clf
from src.train_rul import train_rul

OUT_BASE = Path('models_auto_run')
OUT_BASE.mkdir(exist_ok=True)


def is_failure_col(col):
    s = col.lower()
    return 'failure' in s or 'fault' in s or 'fault_mode' in s or 'mode' in s


def infer_id_cycle(df):
    cols = df.columns.tolist()
    lower = [c.lower() for c in cols]
    id_col = None
    cycle_col = None
    for i, c in enumerate(lower):
        if any(x in c for x in ('id', 'unit', 'asset', 'serial', 'machine')) and id_col is None:
            id_col = cols[i]
        if any(x in c for x in ('cycle', 'time', 'op_cycle', 'timestamp', 'cycle_no')) and cycle_col is None:
            cycle_col = cols[i]
    return id_col, cycle_col


def main():
    files = find_raw_files()
    summary = {}
    for f in files:
        print(f"\nProcessing {f}")
        summary[str(f)] = {}
        try:
            df = load_any(f)
            # run anomaly (fast)
            print('  Running anomaly detection...')
            anom_outdir = OUT_BASE / f.stem / 'anomaly'
            anom_outdir.mkdir(parents=True, exist_ok=True)
            try:
                res_anom = train_anomaly(str(f), outdir=str(anom_outdir), do_feature_engineering=False)
                summary[str(f)]['anomaly'] = res_anom
            except Exception as e:
                summary[str(f)]['anomaly'] = {'error': str(e)}

            # classification if failure-like column exists
            fail_cols = [c for c in df.columns if is_failure_col(c)]
            if fail_cols:
                t = fail_cols[0]
                print(f'  Running classifier for target {t}...')
                clf_outdir = OUT_BASE / f.stem / 'classifier'
                clf_outdir.mkdir(parents=True, exist_ok=True)
                try:
                    args = type('a', (), {})()
                    args.file = str(f)
                    args.target = t
                    args.outdir = str(clf_outdir)
                    args.test_size = 0.2
                    args.n_estimators = 10
                    args.n_jobs = 1
                    args.no_feature_engineering = True
                    train_clf(args)
                    summary[str(f)]['classifier'] = {'target': t, 'outdir': str(clf_outdir)}
                except Exception as e:
                    summary[str(f)]['classifier'] = {'error': str(e)}

            # RUL if id+cycle present
            idc, cyc = infer_id_cycle(df)
            if idc and cyc:
                print(f'  Running RUL training inferred id={idc}, cycle={cyc}...')
                rul_outdir = OUT_BASE / f.stem / 'rul'
                rul_outdir.mkdir(parents=True, exist_ok=True)
                try:
                    res_rul = train_rul(str(f), outdir=str(rul_outdir), id_col=idc, cycle_col=cyc, n_estimators=10, n_jobs=1, no_feature_engineering=True)
                    summary[str(f)]['rul'] = res_rul
                except Exception as e:
                    summary[str(f)]['rul'] = {'error': str(e)}
            else:
                summary[str(f)]['rul'] = {'status': 'no_id_cycle_found'}

        except Exception as e:
            print('  Top-level error for file:', e)
            summary[str(f)]['error'] = str(e)

    # save summary
    outp = OUT_BASE / 'summary.json'
    with open(outp, 'w') as f:
        json.dump(summary, f, indent=2)

    print('\nDone. Summary at', outp)


if __name__ == '__main__':
    main()
