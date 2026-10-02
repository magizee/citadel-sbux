"""Store-level role patterns and neutral "worth a manual look" candidate lists.

Works on any cleaned postings file (pilot or national):

    python src/store_patterns.py --input data/processed/2026-10-01/pilot/pilot_jobs_clean.csv \
        --out outputs/tables/pilot
    python src/store_patterns.py --input data/processed/2026-10-01/starbucks_jobs_US.csv \
        --out outputs/tables

Outputs (in --out):
    store_role_patterns.csv        one row per hiring store: role counts, role set, flags
    role_combination_frequency.csv how often each exact set of open roles occurs
    duplicate_role_frequency.csv   stores with 2+ postings for the same role
    high_intensity_stores.csv      stores with non-standard hiring patterns (see FLAGS)
    old_posting_stores.csv         stores with a posting much older than its role's norm
    leadership_opening_markets.csv / old_posting_markets.csv / high_intensity_markets.csv

The flags mark deviations from the dominant standing pattern (one barista +
one shift-supervisor requisition per store). They are candidates for manual
review, NOT evidence of a staffing problem.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROLES = ["BARISTA", "SHIFT_SUPERVISOR", "STORE_MANAGER", "DISTRICT_MANAGER", "OTHER_RETAIL"]
SHORT = {"BARISTA": "B", "SHIFT_SUPERVISOR": "SS", "STORE_MANAGER": "SM",
         "DISTRICT_MANAGER": "DM", "OTHER_RETAIL": "OTHER"}


def load_retail(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"store_number": str, "job_id": str, "postal_code": str})
    df["days_open"] = df["days_since_posted"].astype(float)
    return df[df["role_bucket"] != "NON_RETAIL"].copy()


def role_set_label(row) -> str:
    return " + ".join(r for r in ROLES if row[r] > 0)


def store_patterns(retail: pd.DataFrame) -> pd.DataFrame:
    """One row per store_key with per-role counts, the exact role set and review flags."""
    s = retail[retail["store_key"].notna()]
    counts = s.pivot_table(index="store_key", columns="role_bucket", values="job_id",
                           aggfunc="count", fill_value=0).reindex(columns=ROLES, fill_value=0)
    meta = s.groupby("store_key").agg(store_number=("store_number", "first"), store_name=("store_name", "first"),
                                      city=("city", "first"), state=("state", "first"),
                                      active_postings=("job_id", "count"),
                                      max_days_open=("days_open", "max"),
                                      n_locations_max=("n_locations", "max"))
    st = meta.join(counts).reset_index()
    st["n_role_types"] = (st[ROLES] > 0).sum(axis=1)
    st["role_set"] = st.apply(role_set_label, axis=1)
    st["max_same_role_postings"] = st[ROLES].max(axis=1)
    st["duplicate_roles"] = st.apply(lambda r: ",".join(f"{SHORT[x]}x{r[x]}" for x in ROLES if r[x] > 1), axis=1)

    # Age relative to the national (or input-wide) norm for the same role:
    # a posting is "old for its role" if it is above that role's 90th percentile.
    p90 = retail.groupby("role_bucket")["days_open"].quantile(0.9)
    s = s.assign(role_p90=s["role_bucket"].map(p90))
    old = s[s["days_open"] > s["role_p90"]].groupby("store_key").size()
    st["postings_older_than_role_p90"] = st["store_key"].map(old).fillna(0).astype(int)

    combo_share = st["role_set"].map(st["role_set"].value_counts(normalize=True))
    postings_p99 = st["active_postings"].quantile(0.99)
    st["flag_same_role_duplicate"] = st["max_same_role_postings"] > 1
    st["flag_3plus_role_types"] = st["n_role_types"] >= 3
    st["flag_barista_supervisor_manager"] = (st["BARISTA"] > 0) & (st["SHIFT_SUPERVISOR"] > 0) & (st["STORE_MANAGER"] > 0)
    st["flag_manager_plus_multiple_frontline"] = (st["STORE_MANAGER"] > 0) & ((st["BARISTA"] + st["SHIFT_SUPERVISOR"]) >= 2)
    st["flag_old_for_role"] = st["postings_older_than_role_p90"] > 0
    st["flag_high_postings"] = st["active_postings"] > max(postings_p99, 2)
    st["flag_unusual_role_set"] = combo_share < 0.01
    st["flag_nonstandard_location"] = st["store_key"].str.startswith("addr:") | (st["n_locations_max"] > 1)
    flag_cols = [c for c in st.columns if c.startswith("flag_")]
    st["n_flags"] = st[flag_cols].sum(axis=1)
    return st.sort_values(["n_flags", "active_postings"], ascending=False).reset_index(drop=True)


def combination_frequency(st: pd.DataFrame) -> pd.DataFrame:
    n = len(st)
    rows = [{"pattern": k, "stores": v} for k, v in st["role_set"].value_counts().items()]
    # The specific patterns requested, including duplicate-role patterns (which
    # overlap the exact role sets above).
    named = {
        "BARISTA only": st["role_set"] == "BARISTA",
        "SHIFT_SUPERVISOR only": st["role_set"] == "SHIFT_SUPERVISOR",
        "BARISTA + SHIFT_SUPERVISOR (exactly)": st["role_set"] == "BARISTA + SHIFT_SUPERVISOR",
        "BARISTA + SHIFT_SUPERVISOR + STORE_MANAGER (any extras)": st["flag_barista_supervisor_manager"],
        "STORE_MANAGER only": st["role_set"] == "STORE_MANAGER",
        "multiple BARISTA postings": st["BARISTA"] > 1,
        "multiple SHIFT_SUPERVISOR postings": st["SHIFT_SUPERVISOR"] > 1,
        "multiple STORE_MANAGER postings": st["STORE_MANAGER"] > 1,
        "standard pattern: exactly 1 BARISTA + 1 SHIFT_SUPERVISOR, nothing else":
            (st["role_set"] == "BARISTA + SHIFT_SUPERVISOR") & (st["BARISTA"] == 1) & (st["SHIFT_SUPERVISOR"] == 1),
    }
    named_rows = [{"pattern": k, "stores": int(m.sum())} for k, m in named.items()]
    out = pd.DataFrame([{"table": "exact_role_set", **r} for r in rows]
                       + [{"table": "requested_pattern", **r} for r in named_rows])
    out["pct_of_hiring_stores"] = (100 * out["stores"] / n).round(1)
    return out


def market_flags(retail: pd.DataFrame, st: pd.DataFrame, level: str, min_stores: int) -> pd.DataFrame:
    """Market metrics for review lists; only markets with >= min_stores hiring stores."""
    key = ["state"] if level == "state" else ["city", "state"]
    r = retail.copy()
    p90 = r.groupby("role_bucket")["days_open"].quantile(0.9)
    r["old_for_role"] = r["days_open"] > r["role_bucket"].map(p90)
    g = r.groupby(key).agg(active_retail_postings=("job_id", "count"),
                           unique_stores_hiring=("store_key", "nunique"),
                           leadership_postings=("role_bucket", lambda x: int(x.isin(["STORE_MANAGER", "DISTRICT_MANAGER"]).sum())),
                           pct_over_30_days=("days_open", lambda x: round(100 * (x > 30).mean(), 1)),
                           pct_over_60_days=("days_open", lambda x: round(100 * (x > 60).mean(), 1)),
                           pct_old_for_role=("old_for_role", lambda x: round(100 * x.mean(), 1)),
                           median_days_open=("days_open", "median"))
    sg = st.groupby(key).agg(pct_stores_same_role_duplicate=("flag_same_role_duplicate", lambda x: round(100 * x.mean(), 1)),
                             pct_stores_3plus_roles=("flag_3plus_role_types", lambda x: round(100 * x.mean(), 1)))
    g = g.join(sg).reset_index()
    g["postings_per_hiring_store"] = (g["active_retail_postings"] / g["unique_stores_hiring"]).round(3)
    g["leadership_vacancy_intensity"] = (g["leadership_postings"] / g["unique_stores_hiring"]).round(4)
    g["market_level"] = level
    return g[g["unique_stores_hiring"] >= min_stores]


def write_all(retail: pd.DataFrame, out: Path, min_state: int = 30, min_city: int = 15) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    st = store_patterns(retail)
    st.to_csv(out / "store_role_patterns.csv", index=False)
    combination_frequency(st).to_csv(out / "role_combination_frequency.csv", index=False)
    st[st["flag_same_role_duplicate"]].to_csv(out / "duplicate_role_frequency.csv", index=False)
    hi_cols = ["flag_same_role_duplicate", "flag_3plus_role_types", "flag_barista_supervisor_manager",
               "flag_manager_plus_multiple_frontline", "flag_high_postings", "flag_unusual_role_set"]
    st[st[hi_cols].any(axis=1)].to_csv(out / "high_intensity_stores.csv", index=False)
    st[st["flag_old_for_role"]].sort_values("max_days_open", ascending=False).to_csv(out / "old_posting_stores.csv", index=False)

    mk = pd.concat([market_flags(retail, st, "state", min_state), market_flags(retail, st, "city", min_city)])
    mk.sort_values("leadership_vacancy_intensity", ascending=False).to_csv(out / "leadership_opening_markets.csv", index=False)
    mk.sort_values("pct_over_30_days", ascending=False).to_csv(out / "old_posting_markets.csv", index=False)
    mk.sort_values("postings_per_hiring_store", ascending=False).to_csv(out / "high_intensity_markets.csv", index=False)
    return {"stores": len(st), "flag_counts": {c: int(st[c].sum()) for c in st.columns if c.startswith("flag_")},
            "markets_meeting_threshold": len(mk), "thresholds": {"min_stores_state": min_state, "min_stores_city": min_city}}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--min-stores-state", type=int, default=30)
    ap.add_argument("--min-stores-city", type=int, default=15)
    args = ap.parse_args()
    print(write_all(load_retail(args.input), Path(args.out), args.min_stores_state, args.min_stores_city))


if __name__ == "__main__":
    main()
