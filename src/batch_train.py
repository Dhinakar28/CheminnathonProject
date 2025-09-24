"""
Batch training helper: discover datasets in raw folders and train models for top numeric targets.

Behavior / assumptions:
- For each discovered dataset (CSV or MAT) we pick up to `max_targets` numeric columns with highest variance as targets.
- We skip columns that look like identifiers (contain 'id', 'udi', 'product').
- Default model: RandomForest with `n_estimators` trees and `n_jobs` parallelism.
- Artifacts are saved under `models_batch/<dataset_stem>/`.

Run as module:
    python -m src.batch_train
"""
from pathlib import Path
import os
import json
import traceback
from types import SimpleNamespace

from .data_loader import find_raw_files, load_any
from .preprocess import basic_clean
from .train import train as train_fn

MAX_TARGETS = 1
N_ESTIMATORS = 10
N_JOBS = 1
OUT_BASE = "models_batch"


def is_id_col(col_name: str) -> bool:
    s = col_name.lower()
    return any(x in s for x in ("id", "udi", "product"))


def select_targets(df, max_targets=MAX_TARGETS):
    numeric = df.select_dtypes(include=["number"]).copy()
    # drop identifier-like columns
    numeric = numeric.loc[:, [c for c in numeric.columns if not is_id_col(c)]]
    if numeric.shape[1] == 0:
        return []
    variances = numeric.var(axis=0).sort_values(ascending=False)
    targets = [c for c in variances.index.tolist() if variances[c] > 0]
    return targets[:max_targets]


def ensure_outdir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def main():
    files = find_raw_files()
    if not files:
        print("No raw files found in data/raw or raw directories.")
        return

    summary = {}
    for f in files:
        try:
            print(f"\nProcessing file: {f}")
            df = load_any(f)
            df_clean = basic_clean(df)
            targets = select_targets(df_clean)
            if not targets:
                print("  No suitable numeric targets found, skipping.")
                continue

            out_base = Path(OUT_BASE) / f.stem
            ensure_outdir(out_base)
            summary[str(f)] = {}
            for t in targets:
                print(f"  Training target: {t}")
                args = SimpleNamespace()
                args.file = str(f)
                args.target = t
                args.outdir = str(out_base)
                args.test_size = 0.2
                args.n_estimators = N_ESTIMATORS
                args.n_jobs = N_JOBS
                args.feature_engineering = False
                try:
                    train_fn(args)
                    # read meta JSON
                    meta_name = f"{f.stem}__{t.replace(' ', '_')}__meta.json"
                    meta_path = out_base / meta_name
                    if meta_path.exists():
                        with open(meta_path, 'r') as mf:
                            meta = json.load(mf)
                        summary[str(f)][t] = meta.get('metrics', {})
                    else:
                        summary[str(f)][t] = {"status": "no_meta_found"}
                except Exception as e:
                    print(f"    Failed training target {t}: {e}")
                    traceback.print_exc()
                    summary[str(f)][t] = {"status": "error", "error": str(e)}

        except Exception as e:
            print(f"Failed processing file {f}: {e}")
            traceback.print_exc()

    # write overall summary
    out_sum = Path(OUT_BASE) / "summary.json"
    with open(out_sum, 'w') as of:
        json.dump(summary, of, indent=2)

    print('\nBatch training complete. Summary saved to', out_sum)


if __name__ == '__main__':
    main()
