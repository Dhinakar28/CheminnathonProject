"""
Utilities to discover and load datasets from the repository `raw` folders (.csv and .mat).
"""
from pathlib import Path
import pandas as pd
import numpy as np
from scipy import io

RAW_FOLDERS = [Path(__file__).resolve().parents[1] / "data" / "raw",
               Path(__file__).resolve().parents[1] / "raw"]


def find_raw_files(exts=(".csv", ".mat", ".txt", ".dat")):
    """Return list of raw files (csv and mat) found in project-level raw folders."""
    files = []
    for d in RAW_FOLDERS:
        if d.exists():
            for ext in exts:
                files.extend(list(d.rglob(f"*{ext}")))
    return sorted(files)


def load_csv(path):
    path = Path(path)
    df = pd.read_csv(path)
    return df


def load_txt(path):
    """Load whitespace-delimited text files. If the file has no header and resembles
    the CMAPSS format (unit, cycle, 3 settings, many sensors), assign meaningful names.
    Otherwise return a DataFrame with generic column names.
    """
    path = Path(path)
    # try reading with a regex separator; do not treat first row as header
    try:
        df = pd.read_csv(path, sep=r"\s+", header=None, comment="#", engine='python', encoding='utf-8')
    except Exception:
        # fallback to latin1 if utf-8 decoding fails
        try:
            df = pd.read_csv(path, sep=r"\s+", header=None, comment="#", engine='python', encoding='latin1')
        except Exception:
            # last-resort: let pandas try with default settings
            df = pd.read_csv(path, sep=r"\s+", header=None, engine='python')

    # if file already has a header-like first row (non-numeric tokens), try to read header
    # inspect first line
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        first = f.readline().strip()
    has_header = any(not tok.replace('.', '', 1).lstrip('-').isdigit() for tok in first.split())
    if has_header:
        try:
            try:
                df2 = pd.read_csv(path, sep=r"\s+", header=0, comment="#", engine='python', encoding='utf-8')
            except Exception:
                df2 = pd.read_csv(path, sep=r"\s+", header=0, comment="#", engine='python', encoding='latin1')
            return df2
        except Exception:
            pass

    # If number of columns looks like CMAPSS (>=5), name them: unit, cycle, setting1..3, s1..sN
    ncol = df.shape[1]
    if ncol >= 5:
        names = []
        names.append('unit')
        names.append('cycle')
        # next three operational settings (may not exist; handle if less)
        n_settings = min(3, max(0, ncol - 2 - 1))
        for i in range(1, 4):
            if 2 + i - 1 < ncol:
                names.append(f'operational_setting_{i}')
        # remaining are sensors
        sensors_start = len(names)
        n_sensors = ncol - sensors_start
        for i in range(1, n_sensors + 1):
            names.append(f's{i}')
        # if names length mismatch, fallback to generic
        if len(names) == ncol:
            df.columns = names
            return df

    # generic column names
    df.columns = [f'c{i}' for i in range(ncol)]
    return df


def _mat_to_df(matdict):
    # heuristics: find the first array with 2D shape where rows >= cols
    for k, v in matdict.items():
        if k.startswith("__"):
            continue
        if isinstance(v, np.ndarray):
            if v.ndim == 2:
                arr = v
                # convert to dataframe columns
                cols = [f"c{i}" for i in range(arr.shape[1])]
                try:
                    return pd.DataFrame(arr, columns=cols)
                except Exception:
                    return pd.DataFrame(arr)
    # fallback: try to convert any ndarray
    for k, v in matdict.items():
        if isinstance(v, np.ndarray):
            return pd.DataFrame(v)
    # nothing convertible
    return pd.DataFrame()


def load_mat(path):
    path = Path(path)
    mat = io.loadmat(path)
    df = _mat_to_df(mat)
    return df


def load_any(path):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    if p.suffix.lower() == ".csv":
        return load_csv(p)
    if p.suffix.lower() == ".mat":
        return load_mat(p)
    if p.suffix.lower() in (".txt", ".dat"):
        return load_txt(p)
    raise ValueError("Unsupported file type: %s" % p.suffix)
