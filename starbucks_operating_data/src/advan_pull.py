"""Download Advan (via Dewey) patterns files and keep only Starbucks rows.

Credentials come from environment variables (never hard-code or commit them):
    export DEWEY_API_KEY='...'
    export DEWEY_ADVAN_PATH='https://app.deweydata.io/external-api/v3/products/<id>/files'

Steps:
    python src/advan_pull.py --check                                   # list files + sizes, download nothing
    python src/advan_pull.py --start 2024-01-01 --end 2024-03-31       # small test window
    python src/advan_pull.py --start 2024-01-01 --end 2026-09-30       # full window

Each file is downloaded, filtered to Starbucks rows (brand or name contains "starbucks"),
appended to data/processed/advan_starbucks.csv.gz, and the unfiltered file is deleted
(unless --keep-raw). Re-running skips files already processed (data/raw/advan/_done.txt).

Manual alternative: put Starbucks-filtered CSV/CSV.GZ/Parquet exports from the Dewey
website in data/raw/advan/ and run with --local.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/advan"
OUT = ROOT / "data/processed/advan_starbucks.csv.gz"
DONE = RAW / "_done.txt"
KEEP_COLS = ["placekey", "location_name", "brands", "street_address", "city", "region", "postal_code",
             "latitude", "longitude", "date_range_start", "date_range_end", "raw_visit_counts",
             "raw_visitor_counts", "median_dwell", "normalized_visits_by_state_scaling",
             "normalized_visits_by_total_visits", "visits_by_day", "popularity_by_hour"]


def creds() -> tuple[str, str]:
    key, path = os.environ.get("DEWEY_API_KEY"), os.environ.get("DEWEY_ADVAN_PATH")
    if not key or not path:
        sys.exit("Set DEWEY_API_KEY and DEWEY_ADVAN_PATH in this terminal first (see docstring).")
    return key, path


def ddp():
    try:
        import deweydatapy
        return deweydatapy
    except ImportError:
        sys.exit("pip install deweydatapy")


def filter_file(path: Path) -> int:
    """Append Starbucks rows of one file to OUT; return rows kept. Reads in chunks."""
    kept = 0
    if path.suffix == ".parquet":
        chunks = [pd.read_parquet(path)]
    else:
        chunks = pd.read_csv(path, chunksize=250_000, dtype=str, low_memory=False)
    for ch in chunks:
        ch.columns = [c.lower() for c in ch.columns]
        name = ch.get("brands", pd.Series("", index=ch.index)).fillna("") + " " + \
            ch.get("location_name", pd.Series("", index=ch.index)).fillna("")
        sb = ch[name.str.contains("starbucks", case=False)]
        sb = sb[[c for c in KEEP_COLS if c in sb.columns]]
        if len(sb):
            sb.to_csv(OUT, mode="a", header=not OUT.exists(), index=False, compression="gzip")
            kept += len(sb)
    return kept


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="show metadata and file list only")
    ap.add_argument("--start", help="YYYY-MM-DD")
    ap.add_argument("--end", help="YYYY-MM-DD")
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--local", action="store_true", help="filter files already placed in data/raw/advan/")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set(DONE.read_text().split()) if DONE.exists() else set()

    if args.local:
        for f in sorted(p for p in RAW.iterdir() if p.suffix in (".csv", ".gz", ".parquet") and p.name not in done):
            n = filter_file(f)
            print(f"{f.name}: kept {n} Starbucks rows")
            with DONE.open("a") as h:
                h.write(f.name + "\n")
        return

    key, path = creds()
    d = ddp()
    meta = d.get_meta(key, path, print_meta=True)
    files = d.get_file_list(key, path, start_date=args.start, end_date=args.end, print_info=True)
    if args.check:
        print(files.head(20).to_string())
        size_cols = [c for c in files.columns if "size" in c.lower()]
        if size_cols:
            print("total size (as reported):", files[size_cols[0]].sum())
        print(f"{len(files)} files in window. Nothing downloaded (--check).")
        return
    name_col = next(c for c in files.columns if c.lower() in ("file_name", "filename", "name"))
    for i in range(len(files)):
        row = files.iloc[[i]]
        fname = str(row[name_col].iloc[0])
        if fname in done:
            continue
        d.download_files(row, str(RAW), skip_exists=True)
        local = RAW / fname
        n = filter_file(local)
        print(f"[{i + 1}/{len(files)}] {fname}: kept {n} Starbucks rows", flush=True)
        if not args.keep_raw:
            local.unlink(missing_ok=True)
        with DONE.open("a") as h:
            h.write(fname + "\n")
    _ = meta


if __name__ == "__main__":
    main()
