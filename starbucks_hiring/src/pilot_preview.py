"""Preview analysis on the 250-posting NYC pilot (NOT nationally representative).

Exercises the same code the national analysis uses (analyze.py, charts.py,
store_patterns.py) so it can run as soon as the national CSV exists.

    python src/pilot_preview.py --snapshot-date 2026-10-01

Outputs: outputs/charts/pilot/*.png, outputs/tables/pilot/*.csv,
         outputs/tables/pilot/pilot_metrics.json
"""

from __future__ import annotations

import argparse
import json
import string

import pandas as pd

import charts
import store_patterns
from analyze import build_store_summary, national_summary
from common import PROJECT_ROOT, load_config, processed_dir, today_str

LABEL = "NYC PILOT — NOT NATIONALLY REPRESENTATIVE"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot-date", default=today_str())
    args = ap.parse_args()
    cfg = load_config()

    path = processed_dir(cfg, args.snapshot_date) / "pilot" / "pilot_jobs_clean.csv"
    df = pd.read_csv(path, dtype={"store_number": str, "job_id": str, "postal_code": str})
    df["days_open"] = df["days_since_posted"].astype(float)
    df["is_retail"] = df["role_bucket"] != "NON_RETAIL"
    retail = df[df["is_retail"]].copy()

    charts_dir = PROJECT_ROOT / "outputs" / "charts" / "pilot"
    tables_dir = PROJECT_ROOT / "outputs" / "tables" / "pilot"
    charts.BANNER, charts.TABLE_DIR = LABEL, tables_dir
    charts_dir.mkdir(parents=True, exist_ok=True)

    stores = build_store_summary(retail)
    stores.to_csv(tables_dir / "pilot_store_summary.csv", index=False)
    summary = national_summary(df, retail, stores, args.snapshot_date)
    pat = store_patterns.write_all(store_patterns.load_retail(path), tables_dir, min_state=30, min_city=5)

    st = pd.read_csv(tables_dir / "store_role_patterns.csv")
    summary.update({
        "label": LABEL,
        "stores_with_same_role_duplicate": int(st["flag_same_role_duplicate"].sum()),
        "stores_with_manager_posting": int((st["STORE_MANAGER"] > 0).sum()),
        "stores_standard_1B_1SS_only": int(((st["role_set"] == "BARISTA + SHIFT_SUPERVISOR")
                                           & (st["BARISTA"] == 1) & (st["SHIFT_SUPERVISOR"] == 1)).sum()),
        "pattern_flags": pat["flag_counts"],
    })
    (tables_dir / "pilot_metrics.json").write_text(json.dumps(summary, indent=2))

    charts.role_mix(retail, charts_dir)
    charts.posting_age(retail, charts_dir)
    charts.multi_role(stores, charts_dir)
    charts.age_by_role(retail, charts_dir)

    # Same-role duplicate requisitions by store (which stores deviate from 1 per role)
    dup = st[st["flag_same_role_duplicate"]].copy()
    def name(r):
        if isinstance(r["store_name"], str):
            return string.capwords(r["store_name"].lower())
        return string.capwords(r["store_key"].split(":", 1)[1].split("|")[0])   # street address for address-keyed stores
    dup["store"] = dup.apply(lambda r: f"{name(r)[:32]} ({r['duplicate_roles']})", axis=1)
    if len(dup):
        charts._hbar(dup, "store", "active_postings", "Stores with more than one posting for the same role",
                     "Active retail postings per store · brackets: B = barista, OTHER = other in-store",
                     charts_dir / "08_same_role_duplicates.png", "{:,.0f}",
                     note="All are large or special formats: Reserve Roastery (61 9th Ave), Reserve stores, Macy's Herald Square.")
        charts._table(dup[["store_key", "store_name", "city", "state", "role_set", "duplicate_roles", "active_postings"]],
                      charts_dir, "08_same_role_duplicates.csv")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
