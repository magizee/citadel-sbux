"""Workstream 8 (light): are new stores as productive as the stores that were closed / the mature base?

    python src/new_store_productivity.py

New store = Advan OPEN_DATE between 2024-03-01 and 2026-06-30, company-operated (store-locator match), still open.
Productivity = latest 13-week visits per week and visits per operating hour (Sep-2026 hours), relative to mature
company-operated stores (open before 2024) in the same metro. Ramp = visits by weeks since opening, relative to the
metro's mature median in the same week.
Outputs: 07_new_store_productivity/ (new_stores.csv, ramp.csv, results.json), charts/07_new_store_productivity.png
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from lab import LAB, load_advan, save_json

OUT = LAB / "07_new_store_productivity"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = pd.read_csv(LAB / "01_store_panel/store_panel.csv", dtype={"store_id": str, "msa": str},
                    parse_dates=["open_date", "close_date", "first_week"])
    co = p[p["company_operated"] & p["status"].eq("open") & p["msa"].notna()].copy()
    co["new"] = co["open_date"].between("2024-03-01", "2026-06-30")
    co["mature"] = co["open_date"].isna() | (co["open_date"] < "2024-01-01")
    co = co[co["new"] | co["mature"]]
    mm = co[co["mature"]].groupby("msa")[["visits_per_week_13w", "visits_per_operating_hour"]].median()
    co = co.join(mm.add_suffix("_metro_mature"), on="msa")
    co["rel_visits"] = co["visits_per_week_13w"] / co["visits_per_week_13w_metro_mature"]
    co["rel_vph"] = co["visits_per_operating_hour"] / co["visits_per_operating_hour_metro_mature"]
    new = co[co["new"] & co["rel_visits"].notna()].copy()
    new["cohort"] = pd.cut(new["open_date"], pd.to_datetime(["2024-03-01", "2025-01-01", "2025-10-01", "2026-07-01"]),
                           labels=["Mar–Dec 2024", "Jan–Sep 2025", "Oct 2025–Jun 2026"], right=False)
    new.to_csv(OUT / "new_stores.csv", index=False)

    # Ramp: weekly visits since opening relative to metro mature median that week
    sb = load_advan("Starbucks")[["ID_STORE", "week", "visits"]]
    sb = sb.merge(co[["store_id", "msa", "new", "mature", "open_date"]], left_on="ID_STORE", right_on="store_id")
    med = sb[sb["mature"]].groupby(["msa", "week"])["visits"].median().rename("metro_med")
    n = sb[sb["new"]].join(med, on=["msa", "week"])
    n["weeks_since_open"] = ((n["week"] - n["open_date"]).dt.days // 7)
    n = n[n["weeks_since_open"].between(0, 104)]
    n["rel"] = n["visits"] / n["metro_med"]
    ramp = n.groupby("weeks_since_open").agg(stores=("store_id", "nunique"), median_rel=("rel", "median")).reset_index()
    ramp = ramp[ramp["stores"] >= 30]
    ramp.to_csv(OUT / "ramp.csv", index=False)

    closed = pd.read_csv(LAB / "06_closure_productivity/closed_vs_survivors.csv").set_index("metric")
    res = {"new_company_operated_stores": len(new),
           "by_cohort": new.groupby("cohort", observed=True).agg(stores=("store_id", "size"), median_rel_visits=("rel_visits", "median"),
                                                               median_rel_vph=("rel_vph", "median"),
                                                               median_weekly_hours=("weekly_hours_2026_09", "median"),
                                                               median_vph=("visits_per_operating_hour", "median")).round(3).reset_index().to_dict(orient="records"),
           "all_new_median_rel_visits": round(float(new["rel_visits"].median()), 3),
           "all_new_median_vph": round(float(new["visits_per_operating_hour"].median()), 2),
           "mature_median_vph": round(float(co.loc[co["mature"], "visits_per_operating_hour"].median()), 2),
           "closed_oct25_median_vph_pre_closure": float(closed.loc["visits_per_op_hour", "closed_median"]),
           "new_urbanicity_mix": new["urbanicity"].value_counts(normalize=True).round(3).to_dict(),
           "mature_urbanicity_mix": co.loc[co["mature"], "urbanicity"].value_counts(normalize=True).round(3).to_dict(),
           "ramp_rel_at_weeks": {int(w): float(r) for w, r in ramp.set_index("weeks_since_open")["median_rel"].round(3).items()
                                 if w in (4, 13, 26, 52, 78, 104)},
           "note": "Advan open dates are Advan's estimate of when the POI opened; new stores carry construction/pre-opening labor not visible here."}
    save_json(res, OUT / "results.json")
    import json
    print(json.dumps(res, indent=1, default=str))

    import sys
    sys.path.insert(0, str(LAB.parent / "_research_archive/starbucks_hiring/src"))
    import charts as C
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(ramp["weeks_since_open"], ramp["median_rel"], color=C.BLUE, linewidth=2)
    ax.axhline(1, color=C.INK_2, linewidth=0.8, linestyle="--")
    ax.text(ramp["weeks_since_open"].max(), 1.02, "mature store in same metro = 1.0", ha="right", fontsize=8, color=C.INK_2)
    ax.set_xlabel("weeks since opening")
    ax.set_ylabel("visits ÷ metro mature median")
    ax.set_title(f"New company-operated stores' traffic ramp (n = {len(new):,} opened Mar 2024 – Jun 2026)", loc="left", fontsize=11)
    fig.text(0.01, 0.01, "Advan weekly visits (panel sample, relative only) · open dates from Advan · company-operated via store locator",
             fontsize=8, color=C.INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(LAB / "charts/07_new_store_productivity.png", dpi=200)


if __name__ == "__main__":
    main()
