"""One-day cross-sectional analysis of the national snapshot.

    python src/analyze.py --snapshot-date 2026-10-01

Input : data/processed/<date>/starbucks_jobs_US.csv  (from merge_states.py)
Output: data/processed/<date>/store_summary.csv       one row per store_key (retail postings)
        data/processed/<date>/market_summary.csv      state, city/state, and role summaries
        outputs/national_summary.json                 headline metrics
        outputs/oldest_retail_postings.csv            20 oldest retail postings
        outputs/oldest_leadership_postings.csv        20 oldest store/district manager postings
        outputs/charts/*.png + *.csv                  charts and their underlying data

Definitions
-----------
retail          role_bucket != NON_RETAIL
days_open       snapshot_date - posted_date (UTC date of backend posted_ts)
hiring store    a store_key with >= 1 active retail posting
leadership      STORE_MANAGER + DISTRICT_MANAGER postings
Metro: no metro definitions are available offline, so "city" = city + state as
written in the posting address (e.g. Brooklyn and New York are separate).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from common import PROJECT_ROOT, load_config, processed_dir, today_str

ROLES = ["BARISTA", "SHIFT_SUPERVISOR", "STORE_MANAGER", "DISTRICT_MANAGER", "OTHER_RETAIL"]
LEADERSHIP = ["STORE_MANAGER", "DISTRICT_MANAGER"]
FRONTLINE = ["BARISTA", "SHIFT_SUPERVISOR", "STORE_MANAGER"]

# Minimum hiring stores for a geography to appear in rankings/charts, so tiny
# markets with a handful of stores do not dominate. Documented in the outputs.
MIN_STORES_STATE = 30
MIN_STORES_CITY = 15

OUT = PROJECT_ROOT / "outputs"
CHARTS = OUT / "charts"


def load(cfg: dict, snapshot_date: str) -> pd.DataFrame:
    df = pd.read_csv(processed_dir(cfg, snapshot_date) / "starbucks_jobs_US.csv",
                     dtype={"store_number": str, "job_id": str, "postal_code": str, "posted_ts_raw": str})
    df["days_open"] = df["days_since_posted"].astype(float)
    df["is_retail"] = df["role_bucket"] != "NON_RETAIL"
    return df


# --------------------------------------------------------------------------- #
# Store level
# --------------------------------------------------------------------------- #

def build_store_summary(retail: pd.DataFrame) -> pd.DataFrame:
    """One row per store_key with role counts, posting age and role-mix flags."""
    s = retail[retail["store_key"].notna()]

    def n(role):
        return ("role_bucket", lambda x: int((x == role).sum()))

    out = s.groupby("store_key").agg(
        store_number=("store_number", "first"),
        store_name=("store_name", "first"),
        street_address=("street_address", "first"),
        city=("city", "first"),
        state=("state", "first"),
        latitude=("latitude", "first"),
        longitude=("longitude", "first"),
        active_postings=("job_id", "nunique"),
        barista_postings=n("BARISTA"),
        shift_supervisor_postings=n("SHIFT_SUPERVISOR"),
        store_manager_postings=n("STORE_MANAGER"),
        district_manager_postings=n("DISTRICT_MANAGER"),
        other_retail_postings=n("OTHER_RETAIL"),
        median_days_open=("days_open", "median"),
        max_days_open=("days_open", "max"),
        pct_postings_over_30_days=("days_open", lambda x: round(100 * (x > 30).mean(), 1)),
        pct_postings_over_60_days=("days_open", lambda x: round(100 * (x > 60).mean(), 1)),
        n_role_types=("role_bucket", "nunique"),
    ).reset_index()
    out["has_barista_opening"] = out["barista_postings"] > 0
    out["has_shift_supervisor_opening"] = out["shift_supervisor_postings"] > 0
    out["has_store_manager_opening"] = out["store_manager_postings"] > 0
    out["has_multiple_roles_open"] = out["n_role_types"] > 1
    out["has_barista_supervisor_manager"] = (out["has_barista_opening"] & out["has_shift_supervisor_opening"]
                                             & out["has_store_manager_opening"])
    out["store_key_type"] = out["store_key"].str.split(":").str[0]
    return out.drop(columns="n_role_types").sort_values(["state", "city", "store_key"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Market level
# --------------------------------------------------------------------------- #

def market_metrics(g: pd.DataFrame) -> dict:
    stores = g["store_key"].nunique()
    n = len(g)
    c = g["role_bucket"].value_counts()
    sm, dm = int(c.get("STORE_MANAGER", 0)), int(c.get("DISTRICT_MANAGER", 0))
    return {
        "unique_stores_hiring": stores,
        "active_retail_postings": n,
        "postings_per_hiring_store": round(n / stores, 3) if stores else None,
        "barista_postings": int(c.get("BARISTA", 0)),
        "shift_supervisor_postings": int(c.get("SHIFT_SUPERVISOR", 0)),
        "store_manager_postings": sm,
        "district_manager_postings": dm,
        "other_retail_postings": int(c.get("OTHER_RETAIL", 0)),
        "median_days_open": g["days_open"].median(),
        "pct_over_30_days": round(100 * (g["days_open"] > 30).mean(), 1),
        "pct_over_60_days": round(100 * (g["days_open"] > 60).mean(), 1),
        "share_barista": round(100 * c.get("BARISTA", 0) / n, 1) if n else None,
        "share_shift_supervisor": round(100 * c.get("SHIFT_SUPERVISOR", 0) / n, 1) if n else None,
        "share_store_manager": round(100 * sm / n, 1) if n else None,
        "leadership_vacancy_intensity": round((sm + dm) / stores, 4) if stores else None,
    }


def build_market_summary(retail: pd.DataFrame, stores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    multi = stores.groupby("state")["has_multiple_roles_open"].mean()
    for st, g in retail.groupby("state"):
        rows.append({"geography_level": "state", "geography": st, "state": st, **market_metrics(g),
                     "pct_hiring_stores_multi_role": round(100 * multi.get(st, float("nan")), 1),
                     "meets_ranking_threshold": g["store_key"].nunique() >= MIN_STORES_STATE})
    cmulti = stores.groupby(["city", "state"])["has_multiple_roles_open"].mean()
    for (city, st), g in retail.groupby(["city", "state"]):
        rows.append({"geography_level": "city", "geography": f"{city}, {st}", "state": st, **market_metrics(g),
                     "pct_hiring_stores_multi_role": round(100 * cmulti.get((city, st), float("nan")), 1),
                     "meets_ranking_threshold": g["store_key"].nunique() >= MIN_STORES_CITY})
    for role, g in retail.groupby("role_bucket"):
        rows.append({"geography_level": "role", "geography": role, "state": None, **market_metrics(g),
                     "pct_hiring_stores_multi_role": None, "meets_ranking_threshold": True})
    rows.append({"geography_level": "national", "geography": "US", "state": None, **market_metrics(retail),
                 "pct_hiring_stores_multi_role": round(100 * stores["has_multiple_roles_open"].mean(), 1),
                 "meets_ranking_threshold": True})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# National summary
# --------------------------------------------------------------------------- #

def national_summary(df: pd.DataFrame, retail: pd.DataFrame, stores: pd.DataFrame, snapshot_date: str) -> dict:
    hs = len(stores)
    def share(mask):
        return {"stores": int(mask.sum()), "pct_of_hiring_stores": round(100 * mask.mean(), 1)}
    return {
        "snapshot_date": snapshot_date,
        "total_unique_postings": int(df["job_id"].nunique()),
        "retail_postings": int(len(retail)),
        "non_retail_postings": int((~df["is_retail"]).sum()),
        "unique_stores_represented_all_postings": int(df["store_key"].nunique()),
        "unique_stores_with_retail_posting": hs,
        "unique_store_numbers_with_retail_posting": int(stores["store_number"].nunique()),
        "retail_postings_per_hiring_store": round(len(retail) / hs, 3),
        "retail_postings_without_store_key": int(retail["store_key"].isna().sum()),
        "median_retail_posting_age_days": float(retail["days_open"].median()),
        "mean_retail_posting_age_days": round(float(retail["days_open"].mean()), 1),
        "pct_retail_over_30_days": round(100 * (retail["days_open"] > 30).mean(), 1),
        "pct_retail_over_60_days": round(100 * (retail["days_open"] > 60).mean(), 1),
        "pct_retail_over_90_days": round(100 * (retail["days_open"] > 90).mean(), 1),
        "role_mix": {r: {"postings": int((retail["role_bucket"] == r).sum()),
                         "share_pct": round(100 * (retail["role_bucket"] == r).mean(), 1)} for r in ROLES},
        "stores_with_barista_opening": share(stores["has_barista_opening"]),
        "stores_with_shift_supervisor_opening": share(stores["has_shift_supervisor_opening"]),
        "stores_with_store_manager_opening": share(stores["has_store_manager_opening"]),
        "stores_with_multiple_role_types": share(stores["has_multiple_roles_open"]),
        "stores_with_barista_supervisor_and_manager": share(stores["has_barista_supervisor_manager"]),
        "leadership_postings": int(retail["role_bucket"].isin(LEADERSHIP).sum()),
        "leadership_vacancy_intensity_national": round(retail["role_bucket"].isin(LEADERSHIP).sum() / hs, 4),
        "states_with_postings": int(retail["state"].nunique()),
        "ranking_thresholds": {"min_hiring_stores_state": MIN_STORES_STATE, "min_hiring_stores_city": MIN_STORES_CITY},
    }


def oldest(retail: pd.DataFrame, mask, n=20) -> pd.DataFrame:
    cols = ["job_id", "job_title_raw", "role_bucket", "store_number", "store_name", "city", "state",
            "posted_date", "days_open", "job_url"]
    return retail[mask].sort_values(["days_open", "job_id"], ascending=[False, True]).head(n)[cols]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot-date", default=today_str())
    ap.add_argument("--national-count", type=int, help="server count for 'United States' (QA completeness check)")
    ap.add_argument("--config")
    args = ap.parse_args()
    cfg = load_config(args.config)

    df = load(cfg, args.snapshot_date)
    retail = df[df["is_retail"]].copy()
    stores = build_store_summary(retail)
    market = build_market_summary(retail, stores)
    summary = national_summary(df, retail, stores, args.snapshot_date)

    pdir = processed_dir(cfg, args.snapshot_date)
    stores.to_csv(pdir / "store_summary.csv", index=False)
    market.to_csv(pdir / "market_summary.csv", index=False)
    OUT.mkdir(exist_ok=True)
    (OUT / "national_summary.json").write_text(json.dumps(summary, indent=2))
    oldest(retail, retail.index == retail.index).to_csv(OUT / "oldest_retail_postings.csv", index=False)
    oldest(retail, retail["role_bucket"].isin(LEADERSHIP)).to_csv(OUT / "oldest_leadership_postings.csv", index=False)

    import charts  # local module; imported late so the data step runs without matplotlib
    charts.make_all(retail, stores, market, summary, CHARTS)

    # Store-level role patterns + neutral review lists, and automated QA.
    import qa
    import store_patterns
    national_csv = pdir / "starbucks_jobs_US.csv"
    summary["store_patterns"] = store_patterns.write_all(store_patterns.load_retail(national_csv), OUT / "tables",
                                                         MIN_STORES_STATE, MIN_STORES_CITY)
    (OUT / "national_summary.json").write_text(json.dumps(summary, indent=2))
    res = qa.run_checks(df, args.national_count)
    lines = ["# QA report: national postings", "", f"{len(df)} postings", "", "| Status | Check | Detail |", "|---|---|---|"]
    (OUT / "qa_report.md").write_text("\n".join(lines + [f"| {s_} | {n_} | {d_.replace('|', '/')} |" for s_, n_, d_ in res]) + "\n")

    print(json.dumps(summary, indent=2))
    print(f"\nWrote {pdir / 'store_summary.csv'} ({len(stores)} stores), {pdir / 'market_summary.csv'} "
          f"({len(market)} rows), outputs/ and outputs/charts/")


if __name__ == "__main__":
    main()
