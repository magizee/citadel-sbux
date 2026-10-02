"""Merge a multi-search run into one national dataset, then partition by state.

FUTURE STEP: not run yet. Collection geography (search units) is separate from
output geography (states): postings are deduplicated by job_id across every
search that found them, and each posting's state comes from its own address.

    python src/merge_states.py --snapshot-date 2026-10-01               # national grid run
    python src/merge_states.py --snapshot-date 2026-10-01 --run-name state_CA

Inputs : data/raw/<date>/<run>.csv, <run>_discoveries.csv, <run>_latlong.csv,
         data/raw/<date>/searches/*.json (per-search manifests)
Outputs: data/processed/<date>/starbucks_jobs_US.csv      (one row per posting, US only)
         data/processed/<date>/by_state/<ST>.csv           (derived partitions)
         data/processed/<date>/merge_report.txt
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout

import pandas as pd

from clean_jobs import clean_raw, read_raw
from common import load_config, processed_dir, raw_dir, searches_dir, today_str


def merge(cfg: dict, snapshot_date: str, run_name: str, national_count: int | None) -> None:
    raw, latlong = read_raw(cfg, snapshot_date, run_name)
    clean = clean_raw(raw, latlong, cfg["api"]["job_url_base"])
    us = clean[clean["country"] == "US"].reset_index(drop=True)

    out_dir = processed_dir(cfg, snapshot_date)
    (out_dir / "by_state").mkdir(parents=True, exist_ok=True)
    us.to_csv(out_dir / "starbucks_jobs_US.csv", index=False)
    for st, g in us.groupby("state"):
        g.to_csv(out_dir / "by_state" / f"{st}.csv", index=False)

    # ---- per-search completeness ------------------------------------------
    rm = json.loads((raw_dir(cfg, snapshot_date) / "runs" / f"{run_name}.json").read_text())
    sdir = searches_dir(cfg, snapshot_date)
    mans = [json.loads((sdir / f"{s}.json").read_text()) for s in rm["search_ids"] if (sdir / f"{s}.json").exists()]
    status = pd.Series([m["status"] for m in mans]).value_counts()
    not_ok = [m["search_unit"]["search_id"] for m in mans if m["status"] in ("incomplete", "capped")]
    truncated = [m["search_unit"]["search_id"] for m in mans
                 if m["status"] == "complete" and m.get("facet_truncated")]

    print("=" * 72)
    print(f"NATIONAL MERGE REPORT  run={run_name}  snapshot={snapshot_date}")
    print("=" * 72)
    print(f"Searches                  : {len(mans)}  {status.to_dict()}")
    print(f"Incomplete/capped searches: {len(not_ok)} {not_ok[:20]}")
    print(f"Leaf searches with truncated coordinate facet: {len(truncated)} {truncated[:20]}")
    print(f"Discovery rows            : {len(raw)}")
    print(f"Unique postings (all)     : {len(clean)}")
    print(f"Unique postings (US)      : {len(us)}")
    print(f"Raw duplicate rate        : {1 - len(clean) / max(len(raw), 1):.1%} "
          f"(mean searches per posting {clean['n_searches'].mean():.2f})")
    print(f"Unique stores (store_number): {us['store_number'].nunique()}  | store_keys: {us['store_key'].nunique()}")
    print(f"Missing lat/long (US)     : {us['latitude'].isna().mean():.1%}")
    if national_count:
        print(f"Server national count     : {national_count}  -> collected {len(us) / national_count:.1%}")
    print()

    # ---- state partitions --------------------------------------------------
    per = us.groupby("state").agg(postings=("dedup_key", "nunique"),
                                  stores=("store_number", "nunique"),
                                  retail=("role_bucket", lambda s: int((s != "NON_RETAIL").sum())))
    expected = set(cfg["states"])
    missing = sorted(expected - set(per.index))
    low = per[per["postings"] < cfg["merge"]["low_count_threshold"]]
    print("Postings by state (assigned from each posting's own address):")
    with pd.option_context("display.max_rows", 100):
        print(per.sort_values("postings", ascending=False).to_string())
    print()
    print(f"States with no postings   : {missing or 'none'}")
    print(f"States below {cfg['merge']['low_count_threshold']} postings: {list(low.index) or 'none'}")
    multi_state = us[us["all_states"].str.contains(";", na=False)]
    print(f"Postings listing several states (assigned to primary location): {len(multi_state)}")
    print()
    print(f"Wrote {out_dir / 'starbucks_jobs_US.csv'} and by_state/*.csv (store/market summaries: analyze.py)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot-date", default=today_str())
    ap.add_argument("--run-name", help="default: national.run_name")
    ap.add_argument("--national-count", type=int,
                    help='server count for location="United States" (1 request) for the completeness check')
    ap.add_argument("--config")
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_name = args.run_name or cfg["national"]["run_name"]

    buf = io.StringIO()
    with redirect_stdout(buf):
        merge(cfg, args.snapshot_date, run_name, args.national_count)
    text = buf.getvalue()
    print(text)
    (processed_dir(cfg, args.snapshot_date) / "merge_report.txt").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
