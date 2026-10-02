"""Download Advan (via Dewey) patterns files and keep only Starbucks rows.

Install:  pip install deweydatapy@git+https://github.com/Dewey-Data/deweydatapy
API key:  Dewey app -> Connections -> Add Connection
Endpoint: select the Advan product -> Get / Subscribe -> Connect to API

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
             "normalized_visits_by_total_visits", "visits_by_day"]


ENV_FILE = ROOT / ".dewey_env"   # optional, git-ignored: lines DEWEY_API_KEY=... and DEWEY_ADVAN_PATH=...


def creds() -> tuple[str, str]:
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            k, _, v = line.strip().removeprefix("export ").partition("=")
            if k in ("DEWEY_API_KEY", "DEWEY_ADVAN_PATH") and v and not os.environ.get(k):
                os.environ[k] = v.strip().strip("'\"")
    key, path = os.environ.get("DEWEY_API_KEY"), os.environ.get("DEWEY_ADVAN_PATH")
    if not key or not path:
        sys.exit("Set DEWEY_API_KEY and DEWEY_ADVAN_PATH in this terminal or in .dewey_env (see docstring).")
    if path.startswith("akv") or path == key:  # a key pasted into the path field
        sys.exit("DEWEY_ADVAN_PATH holds an API key, not the dataset's API URL "
                 "(https://app.deweydata.io/external-api/v3/products/<id>/files).")
    return key, path


def ddp():
    try:
        import deweydatapy
        return deweydatapy
    except ImportError:
        sys.exit("pip install deweydatapy")


# Advan "Weekly Patterns Plus" (Dewey project datasets, 2026) uses different names than the
# classic SafeGraph-style schema; map them onto the names the analysis expects.
# ID_STORE is the per-location ID (PERSISTENT_ID is brand-level there).
NEW_SCHEMA = {"id_store": "placekey", "brand": "brands", "visit_counts": "raw_visit_counts",
              "visitor_counts": "raw_visitor_counts"}
EXTRA_COLS = ["iso_country_code", "msa_code", "open_date", "close_date", "naics_code"]


def filter_file(path: Path) -> int:
    """Append Starbucks (U.S.) rows of one file to OUT; return rows kept. Reads in chunks."""
    kept = 0
    if path.suffix == ".parquet":
        chunks = [pd.read_parquet(path)]
    else:
        chunks = pd.read_csv(path, chunksize=250_000, dtype=str, low_memory=False)
    for ch in chunks:
        ch.columns = [c.lower() for c in ch.columns]
        if "id_store" in ch.columns:
            ch = ch.drop(columns=[c for c in ("placekey",) if c in ch.columns]).rename(columns=NEW_SCHEMA)
        if "iso_country_code" in ch.columns:
            ch = ch[ch["iso_country_code"] == "US"]
        name = ch.get("brands", pd.Series("", index=ch.index)).fillna("") + " " + \
            ch.get("location_name", pd.Series("", index=ch.index)).fillna("")
        sb = ch[name.str.contains("starbucks", case=False)]
        sb = sb[[c for c in KEEP_COLS + EXTRA_COLS if c in sb.columns]]
        if len(sb):
            sb.to_csv(OUT, mode="a", header=not OUT.exists(), index=False, compression="gzip")
            kept += len(sb)
    return kept


V1 = "https://api.deweydata.io/api/v1/external/data"


def v1_files(key: str, ds: str, after: str | None, before: str | None) -> list[dict]:
    """List download links for a Dewey project dataset (prj_...__cdst_...) via the v1 API."""
    import requests
    out, page = [], 1
    while True:
        params = {"page": page}
        if after:
            params["partition_key_after"] = after
        if before:
            params["partition_key_before"] = before
        r = requests.get(f"{V1}/{ds}/files", params=params, headers={"X-API-Key": key}, timeout=120)
        r.raise_for_status()
        j = r.json()
        out += j["download_links"]
        if page >= j["total_pages"]:
            return out
        page += 1


def v1_download(key: str, ds: str, after: str | None, before: str | None, check: bool, workers: int = 4) -> None:
    """Download project-dataset files (resumable: skips files already on disk at full size)."""
    import requests
    from concurrent.futures import ThreadPoolExecutor
    meta = requests.get(f"{V1}/{ds}/metadata", headers={"X-API-Key": key}, timeout=60).json()
    print({k: meta.get(k) for k in ("total_files", "total_partitions", "partition_column", "min_partition_key", "max_partition_key")},
          f"total_size_MB={meta.get('total_size', 0) / 1e6:,.0f}")
    links = v1_files(key, ds, after, before)
    size = sum(l.get("file_size_bytes", 0) for l in links)
    print(f"{len(links)} files in window {after}..{before}, {size / 1e6:,.0f} MB")
    if check:
        for l in links[:5]:
            print({k: v for k, v in l.items() if k != "link"})
        return

    def get(l: dict) -> str:
        part = str(l.get("partition_key", "")).replace("/", "-")
        dest = RAW / f"{part}__{l['file_name']}"
        if dest.exists() and dest.stat().st_size == l.get("file_size_bytes"):
            return f"skip {dest.name}"
        tmp = dest.with_suffix(dest.suffix + ".part")
        with requests.get(l["link"], stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        tmp.replace(dest)
        return f"ok {dest.name}"

    with ThreadPoolExecutor(workers) as ex:
        for i, msg in enumerate(ex.map(get, links), 1):
            if i % 10 == 0 or i == len(links):
                print(f"[{i}/{len(links)}] {msg}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="show metadata and file list only")
    ap.add_argument("--start", help="YYYY-MM-DD")
    ap.add_argument("--end", help="YYYY-MM-DD")
    ap.add_argument("--keep-raw", action="store_true")
    ap.add_argument("--local", action="store_true", help="filter files already placed in data/raw/advan/")
    ap.add_argument("--raw-dir", help="download folder (default data/raw/advan); use a separate folder per dataset")
    args = ap.parse_args()
    global RAW, DONE
    if args.raw_dir:
        RAW = (ROOT / args.raw_dir) if not Path(args.raw_dir).is_absolute() else Path(args.raw_dir)
        DONE = RAW / "_done.txt"
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set(DONE.read_text().splitlines()) if DONE.exists() else set()

    if args.local:
        for f in sorted(p for p in RAW.iterdir() if p.suffix in (".csv", ".gz", ".parquet") and p.name not in done):
            n = filter_file(f)
            print(f"{f.name}: kept {n} Starbucks rows")
            with DONE.open("a") as h:
                h.write(f.name + "\n")
        return

    key, path = creds()
    if path.startswith("prj_"):          # Dewey project dataset -> newer v1 API
        v1_download(key, path, args.start, args.end, args.check)
        return
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
        # Dewey renumbers file names per requested date range, so track progress by a
        # range-independent key instead of the name.
        key = "|".join(str(row[c].iloc[0]) for c in ("partition_key", "file_size_bytes", "modified_at") if c in row)
        if key in done:
            continue
        d.download_files(row, str(RAW), skip_exists=True)
        local = RAW / fname
        n = filter_file(local)
        print(f"[{i + 1}/{len(files)}] {fname}: kept {n} Starbucks rows", flush=True)
        if not args.keep_raw:
            local.unlink(missing_ok=True)
        with DONE.open("a") as h:
            h.write(key + "\n")
    _ = meta


if __name__ == "__main__":
    main()
