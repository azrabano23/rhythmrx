"""Loader for the ShanghaiT2DM real continuous-glucose-monitoring dataset.

Zhao, Q., Zhu, J., Shen, X. et al. *Chinese diabetes datasets for data-driven
machine learning.* Scientific Data 10, 35 (2023). doi:10.1038/s41597-023-01940-7
Data (CC-BY 4.0): figshare collection 6310860.

100 type-2-diabetes patients (109 recording sessions), 15-minute CGM over 3–14
days, with timestamped meals, insulin, and oral hypoglycemic agents. This is the
real evidence base RhythmRX is validated against. Downloaded on demand into
`.data_cache/` (gitignored) — not vendored, since it carries its own license.
"""
from __future__ import annotations

import glob
import io
import os
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

_FIGSHARE_ZIP = "https://ndownloader.figshare.com/files/42966622"
_CACHE = Path(__file__).resolve().parent.parent / ".data_cache" / "shanghai"


def download(force: bool = False) -> Path:
    """Fetch + unzip the ~3.7 MB dataset into the cache; return its directory."""
    if (_CACHE / "Shanghai_T2DM").exists() and not force:
        return _CACHE
    _CACHE.mkdir(parents=True, exist_ok=True)
    with urlopen(_FIGSHARE_ZIP) as resp:
        blob = resp.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        z.extractall(_CACHE)
    return _CACHE


def t2dm_files() -> list[str]:
    """Paths to the per-patient T2DM recording files (.xls and .xlsx)."""
    download()
    files = sorted(glob.glob(str(_CACHE / "Shanghai_T2DM" / "*.xls*")))
    return [f for f in files if "__MACOSX" not in f]


def load_cgm(path: str) -> list[tuple[datetime, float]]:
    """Return [(timestamp, glucose mg/dL)] for one patient file (needs pandas+xlrd)."""
    import pandas as pd

    engine = "xlrd" if path.endswith(".xls") else "openpyxl"
    df = pd.read_excel(path, engine=engine)
    tcol = next(c for c in df.columns if "Date" in str(c))
    gcol = next(c for c in df.columns if "CGM" in str(c))
    df = df[[tcol, gcol]].dropna()
    df[tcol] = pd.to_datetime(df[tcol], errors="coerce")
    df = df.dropna()
    out: list[tuple[datetime, float]] = []
    for ts, g in zip(df[tcol], df[gcol]):
        try:
            out.append((ts.to_pydatetime(), float(g)))
        except (TypeError, ValueError):
            continue
    return out


def load_all_cgm(limit: int | None = None) -> list[tuple[str, list[tuple[datetime, float]]]]:
    """Load CGM for up to `limit` patients as (patient_id, readings)."""
    files = t2dm_files()
    if limit:
        files = files[:limit]
    out = []
    for f in files:
        pid = os.path.basename(f).split("_")[0]
        try:
            out.append((pid, load_cgm(f)))
        except Exception:
            continue
    return out


def load_session(path: str) -> dict:
    """Read one patient file once; return {'cgm': [(ts, mg/dL)], 'meals': [(ts, grams)]}.

    Meal grams are summed from the free-text "Dietary intake" column (e.g.
    'Boiled egg 40 g\\nCucumber 100 g' -> 140 g) — a usable proxy for meal size."""
    import re
    import pandas as pd

    engine = "xlrd" if path.endswith(".xls") else "openpyxl"
    df = pd.read_excel(path, engine=engine)
    tcol = next(c for c in df.columns if "Date" in str(c))
    gcol = next(c for c in df.columns if "CGM" in str(c))
    dcol = next((c for c in df.columns if "Dietary" in str(c)), None)
    ts_all = pd.to_datetime(df[tcol], errors="coerce")

    cgm: list[tuple[datetime, float]] = []
    for ts, g in zip(ts_all, df[gcol]):
        if pd.isna(ts) or pd.isna(g):
            continue
        try:
            cgm.append((ts.to_pydatetime(), float(g)))
        except (TypeError, ValueError):
            continue

    meals: list[tuple[datetime, float]] = []
    if dcol is not None:
        for ts, txt in zip(ts_all, df[dcol]):
            if pd.isna(ts) or pd.isna(txt):
                continue
            grams = sum(float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*g", str(txt)))
            if grams > 0:
                meals.append((ts.to_pydatetime(), grams))
    return {"cgm": cgm, "meals": meals}


def load_all_sessions(limit: int | None = None) -> list[tuple[str, dict]]:
    """Load up to `limit` patients as (patient_id, {'cgm','meals'})."""
    files = t2dm_files()
    if limit:
        files = files[:limit]
    out = []
    for f in files:
        pid = os.path.basename(f).split("_")[0]
        try:
            out.append((pid, load_session(f)))
        except Exception:
            continue
    return out
