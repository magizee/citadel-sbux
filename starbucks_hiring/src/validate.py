"""Print a validation report for one run (pilot, point/text search, or state cross-check).

    python src/validate.py                                   # pilot
    python src/validate.py --run-name state_CA --snapshot-date 2026-10-01

Reads the run's raw rows, cleaned rows and per-search manifests (no network
access). The report is printed and saved to
data/processed/<date>/<run_name>_validation.txt.
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout

import pandas as pd

from common import load_config, processed_dir, raw_dir, searches_dir, today_str


def pct(n: int, d: int) -> str:
    return f"{(100 * n / d):.1f}%" if d else "n/a"


def load_manifests(cfg: dict, snapshot_date: str, run_name: str) -> list[dict]:
    rm = json.loads((raw_dir(cfg, snapshot_date) / "runs" / f"{run_name}.json").read_text())
    sdir = searches_dir(cfg, snapshot_date)
    return [json.loads((sdir / f"{sid}.json").read_text()) for sid in rm["search_ids"]
            if (sdir / f"{sid}.json").exists()]


def store_consistency(clean: pd.DataFrame) -> pd.DataFrame:
    """For each store number with 2+ postings: do name / address / coordinates agree?"""
    multi = clean[clean["store_number"].notna()].groupby("store_number").filter(lambda g: len(g) > 1)
    out = []
    for sn, g in multi.groupby("store_number"):
        out.append({
            "store_number": sn,
            "postings": len(g),
            "names": g["store_name"].nunique(dropna=False),
            "addresses": g["street_address"].nunique(dropna=False),
            "latlongs": g[["latitude", "longitude"]].astype(str).agg(",".join, axis=1).nunique(),
            "store_name": g["store_name"].iloc[0],
            "street_address": g["street_address"].iloc[0],
            "latlong": f"{g['latitude'].iloc[0]},{g['longitude'].iloc[0]}",
        })
    df = pd.DataFrame(out)
    if len(df):
        df["consistent"] = (df["names"] == 1) & (df["addresses"] == 1) & (df["latlongs"] == 1)
    return df


def report(cfg: dict, snapshot_date: str, run_name: str, max_results: int | None) -> None:
    raw = pd.read_csv(raw_dir(cfg, snapshot_date) / f"{run_name}.csv", dtype=str)
    clean = pd.read_csv(processed_dir(cfg, snapshot_date) / f"{run_name}_clean.csv",
                        dtype={"store_number": str, "job_id": str, "postal_code": str, "posted_ts_raw": str})
    mans = load_manifests(cfg, snapshot_date, run_name)
    n_raw, n = len(raw), len(clean)
    retail = clean[clean["role_bucket"] != "NON_RETAIL"]
    checks: list[tuple[str, bool, str]] = []

    print("=" * 78)
    print(f"VALIDATION REPORT  run={run_name}  snapshot={snapshot_date}")
    print("=" * 78)

    # ---- searches / pagination --------------------------------------------
    print("Searches:")
    for m in mans:
        u = m["search_unit"]
        print(f"  {u['search_id']}: location={u['query_location']!r} radius_km={u['query_radius_km']} "
              f"status={m['status']} reported={m.get('reported_count_first')}->{m.get('reported_count_last')} "
              f"pages={m.get('pages')} unique={m.get('unique_postings')} applied={m.get('applied_filters')}")
    remote_ok = all((m.get("applied_filters") or {}).get("includeRemote") == ["0"] for m in mans)
    checks.append(("remote jobs excluded (server applied includeRemote=0)", remote_ok, ""))
    bad = [m["search_unit"]["search_id"] for m in mans if m["status"] not in ("complete", "capped")]
    checks.append(("every search complete (or intentionally capped)", not bad, ", ".join(bad)))

    # ---- totals -------------------------------------------------------------
    print()
    print(f"Discovery rows (raw)      : {n_raw}")
    print(f"Unique postings (cleaned) : {n}")
    print(f"Unique job IDs            : {clean['job_id'].nunique()}  (missing: {clean['job_id'].isna().sum()})")
    print(f"Duplicate discoveries     : {n_raw - n}")
    print(f"Unique store numbers      : {clean['store_number'].nunique()}  (unique store_keys: {clean['store_key'].nunique()})")
    print(f"Missing store number      : {pct(clean['store_number'].isna().sum(), n)} of all; "
          f"{pct(retail['store_number'].isna().sum(), len(retail))} of retail")
    print(f"Missing street address    : {pct(clean['street_address'].isna().sum(), n)}")
    print(f"Missing postal code       : {pct(clean['postal_code'].isna().sum(), n)} (not exposed by the site)")
    print(f"Missing lat/long          : {pct(clean['latitude'].isna().sum(), n)} "
          f"(retail: {pct(retail['latitude'].isna().sum(), len(retail))})")
    print(f"Missing posted_ts_raw     : {pct(clean['posted_ts_raw'].isna().sum(), n)}")
    print(f"posted_date range         : {clean['posted_date'].min()} .. {clean['posted_date'].max()}")
    print(f"work_location_option      : {clean['work_location_option'].value_counts().to_dict()}")
    print()
    print("Role counts: " + ", ".join(f"{k}={v}" for k, v in clean["role_bucket"].value_counts().items()))
    print("States (primary location): " + ", ".join(f"{k}={v}" for k, v in clean["state"].value_counts(dropna=False).items()))
    multi = clean[clean["n_locations"] > 1]
    if len(multi):
        print(f"Multi-location postings ({len(multi)}): primary location chosen nearest the search centre")
        for _, r in multi.iterrows():
            print(f"    {r.job_id} {r.job_title_raw[:55]!r} -> {r.city}, {r.state}  (all states: {r.all_states})")

    if max_results:
        checks.append((f"unique postings <= {max_results}", n <= max_results, ""))
    checks.append(("dedup_key unique", clean["dedup_key"].is_unique, ""))
    checks.append(("every posting has a job_id", clean["job_id"].notna().all(), ""))
    checks.append(("store numbers are digit strings (leading zeros kept)",
                   clean["store_number"].dropna().str.fullmatch(r"\d+").all(), ""))
    ts_ok = clean["posted_ts_raw"].notna().all() and clean["posted_date"].notna().all()
    checks.append(("every posting has backend posted_ts -> posted_date", ts_ok, ""))

    # ---- retail postings without a store number -------------------------
    print()
    nostore = retail[retail["store_number"].isna()]
    print(f"Retail postings without store_number ({len(nostore)}):")
    for _, r in nostore.iterrows():
        print(f"    {r.job_id} | {r.job_title_raw} | {r.role_bucket} | {r.street_address}, {r.city}, {r.state} "
              f"| n_locations={r.n_locations} | store_key={r.store_key}")
    titles_with_store = nostore["job_title_raw"].str.contains(r"store\s*#", case=False, na=False).sum()
    checks.append(("no retail title containing 'Store#' left unparsed", titles_with_store == 0, ""))

    # ---- store aggregation key -------------------------------------------
    print()
    sc = store_consistency(clean)
    print(f"Store-number consistency ({len(sc)} stores with 2+ postings):")
    if len(sc):
        with pd.option_context("display.width", 250, "display.max_colwidth", 40):
            print(sc.head(10).to_string(index=False))
        incons = sc[~sc["consistent"]]
        if len(incons):
            print("  INCONSISTENT stores:")
            print(incons.to_string(index=False))
        checks.append((f"store_number -> one name/address/latlong ({len(sc)} multi-posting stores)",
                       len(incons) == 0 and len(sc) >= 5, ""))

    # ---- state-search cross-check -----------------------------------------
    sid = mans[0]["search_unit"]["search_id"] if mans else ""
    if sid.startswith("state_"):
        st = sid.split("_", 1)[1]
        share = (clean["state"] == st).mean()
        print(f"\nState cross-check: {share:.1%} of postings are in {st}")
        radius = (mans[0].get("applied_filters") or {}).get("distance")
        checks.append((f"state query not radius-limited (distance={radius})", radius is None, ""))

    print()
    print("Checks:")
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' -> ' + detail) if detail else ''}")

    print()
    print("10 random cleaned records for manual review:")
    cols = ["job_id", "job_title_raw", "role_bucket", "store_number", "store_name", "street_address",
            "city", "state", "posted_date", "days_since_posted", "latitude", "longitude"]
    with pd.option_context("display.max_columns", None, "display.width", 250, "display.max_colwidth", 42):
        print(clean.sample(min(10, n), random_state=42)[cols].to_string(index=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-name", default=None, help="default: pilot.run_name")
    ap.add_argument("--snapshot-date", default=today_str())
    ap.add_argument("--max-results", type=int, help="expected cap (default: pilot.max_results for the pilot)")
    ap.add_argument("--config")
    args = ap.parse_args()
    cfg = load_config(args.config)
    run_name = args.run_name or cfg["pilot"]["run_name"]
    max_results = args.max_results or (cfg["pilot"]["max_results"] if run_name == cfg["pilot"]["run_name"] else None)

    buf = io.StringIO()
    with redirect_stdout(buf):
        report(cfg, args.snapshot_date, run_name, max_results)
    text = buf.getvalue()
    print(text)
    out = processed_dir(cfg, args.snapshot_date) / f"{run_name}_validation.txt"
    out.write_text(text, encoding="utf-8")
    print(f"(saved to {out})")


if __name__ == "__main__":
    main()
