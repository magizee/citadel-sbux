"""Workstreams 2 + 3: Hiring Pressure Index and "does traffic growth require more hiring?"

    python src/hiring_pressure.py

Sample: open, company-operated Starbucks with traffic (Advan) and the careers snapshot (2026-10-01).

Hiring Pressure Index (HPI), three specifications (each component 0/1):
  HPI_full        manager vacancy within 5 km + oldest posting > 30 d + > 60 d + any re-posted requisition
                  + same-role duplicate (2+ postings for one role)
  HPI_persistence re-posted requisition + requisition older than 60 d + persistent manager vacancy within 5 km
  HPI_gap         missing a barista OR supervisor posting (a pipeline gap) + manager vacancy within 5 km
"Role disappears and reappears" needs a time series; see ../03_archive_hiring.

Tests (OLS with metro fixed effects, robust SE; descriptive, not causal):
  outcome ~ traffic growth (YoY %) + log traffic level + weekly hours + log(1 + Starbucks within 2 km)
            + log(1 + Dunkin' within 2 km) + metro FE
  Outcomes: each HPI, active postings, postings per 1,000 weekly visits, same-role duplicate, re-posted, oldest req age.
  Cohorts: YoY traffic growth < 0, 0-5, 5-10, > 10 %; outcomes demeaned by metro.
Outputs: 02_hiring_pressure/ (store_hpi.csv, regressions.csv, cohorts.csv, results.json, charts)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from lab import LAB, save_json

OUT = LAB / "02_hiring_pressure"


def demean(df: pd.DataFrame, cols: list[str], by: str) -> pd.DataFrame:
    return df[cols] - df.groupby(by)[cols].transform("mean")


def ols_fe(df: pd.DataFrame, y: str, xs: list[str], fe: str = "msa") -> dict:
    d = df[[y] + xs + [fe]].dropna()
    d = d[d.groupby(fe)[y].transform("size") >= 3]
    Y = demean(d, [y], fe)[y].to_numpy(float)
    X = demean(d, xs, fe).to_numpy(float)
    b = np.linalg.lstsq(X, Y, rcond=None)[0]
    e = Y - X @ b
    n, k = X.shape
    k_fe = d[fe].nunique()
    XtX = np.linalg.inv(X.T @ X)
    cov = XtX @ (X.T * e ** 2) @ X @ XtX * n / max(n - k - k_fe, 1)
    se = np.sqrt(np.diag(cov))
    return {"outcome": y, "n": n, **{f"b_{x}": round(float(b[i]), 5) for i, x in enumerate(xs)},
            **{f"se_{x}": round(float(se[i]), 5) for i, x in enumerate(xs)},
            "t_growth": round(float(b[0] / se[0]), 2), "outcome_mean": round(float(d[y].mean()), 4)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = pd.read_csv(LAB / "01_store_panel/store_panel.csv", dtype={"store_id": str, "locator_id": str, "msa": str})
    s = p[(p["status"] == "open") & p["company_operated"] & p["visits_yoy_pct"].notna() & p["msa"].notna()].copy()
    lo, hi = s["visits_yoy_pct"].quantile([0.01, 0.99])
    s = s[s["visits_yoy_pct"].between(lo, hi)]

    s["dup"] = ((s["barista_postings"] > 1) | (s["supervisor_postings"] > 1)).astype(int)
    s["mgr5"] = (s["mgr_vacancy_within_5km"] > 0).astype(int)
    s["pmgr5"] = (s["persistent_mgr_vacancy_within_5km"] > 0).astype(int)
    s["age30"] = (s["oldest_posting_age_days"] > 30).astype(int)
    s["age60"] = (s["oldest_posting_age_days"] > 60).astype(int)
    s["reposted"] = (s["reposted_requisitions"] > 0).astype(int)
    s["req60"] = (s["oldest_requisition_age_days"] > 60).astype(int)
    s["gap"] = ((s["barista_postings"] == 0) | (s["supervisor_postings"] == 0)).astype(int)
    s["HPI_full"] = s[["mgr5", "age30", "age60", "reposted", "dup"]].sum(axis=1)
    s["HPI_persistence"] = s[["reposted", "req60", "pmgr5"]].sum(axis=1)
    s["HPI_gap"] = s[["gap", "mgr5"]].sum(axis=1)

    s["log_visits"] = np.log(s["visits_per_week_13w"])
    s["log_sb2"] = np.log1p(s["starbucks_within_2km"])
    s["log_dk2"] = np.log1p(s["dunkin_within_2km"])
    s["growth"] = s["visits_yoy_pct"]
    xs = ["growth", "log_visits", "weekly_hours_2026_09", "log_sb2", "log_dk2"]
    outcomes = ["HPI_full", "HPI_persistence", "HPI_gap", "active_postings", "postings_per_1000_weekly_visits",
                "dup", "reposted", "oldest_requisition_age_days", "mgr5", "pmgr5", "gap"]
    reg = pd.DataFrame([ols_fe(s, y, xs) for y in outcomes])
    reg.to_csv(OUT / "regressions.csv", index=False)

    s["growth_cohort"] = pd.cut(s["growth"], [-1e9, 0, 5, 10, 1e9], labels=["< 0%", "0–5%", "5–10%", "> 10%"])
    dm = demean(s, outcomes, "msa").add_suffix("_vs_metro")
    s = s.join(dm)
    coh = s.groupby("growth_cohort", observed=True).agg(
        stores=("store_id", "size"), median_growth=("growth", "median"),
        **{f"{o}_mean": (o, "mean") for o in ["HPI_full", "HPI_persistence", "active_postings", "dup", "reposted", "mgr5", "pmgr5"]},
        **{f"{o}_vs_metro": (f"{o}_vs_metro", "mean") for o in ["HPI_full", "HPI_persistence", "active_postings", "dup", "pmgr5"]}
    ).round(4).reset_index()
    coh.to_csv(OUT / "cohorts.csv", index=False)

    # Traffic LEVEL (within metro) vs HPI, for comparison with growth
    s["level_q"] = pd.qcut(s["traffic_pctile_in_metro"], 5, labels=["Q1 quietest", "Q2", "Q3", "Q4", "Q5 busiest"])
    lev = s.groupby("level_q", observed=True).agg(stores=("store_id", "size"),
                                                  visits_per_op_hour=("visits_per_operating_hour", "median"),
                                                  **{f"{o}_mean": (o, "mean") for o in ["HPI_full", "HPI_persistence", "dup", "pmgr5", "active_postings"]}
                                                  ).round(4).reset_index()
    lev.to_csv(OUT / "by_traffic_level.csv", index=False)

    keep = ["store_id", "locator_id", "store_key", "msa", "state", "visits_per_week_13w", "visits_yoy_pct", "visits_2y_pct",
            "traffic_pctile_in_metro", "weekly_hours_2026_09", "visits_per_operating_hour", "active_postings",
            "barista_postings", "supervisor_postings", "store_manager_postings", "oldest_posting_age_days",
            "oldest_requisition_age_days", "reposted_requisitions", "mgr_vacancy_within_5km", "persistent_mgr_vacancy_within_5km",
            "dup", "gap", "HPI_full", "HPI_persistence", "HPI_gap", "growth_cohort", "urbanicity"]
    s[keep].to_csv(OUT / "store_hpi.csv", index=False)

    res = {"stores": len(s), "hpi_distribution": {h: s[h].value_counts().sort_index().to_dict() for h in ["HPI_full", "HPI_persistence", "HPI_gap"]},
           "component_rates": {c: round(float(s[c].mean()), 4) for c in ["mgr5", "pmgr5", "age30", "age60", "reposted", "req60", "dup", "gap"]},
           "regressions_growth_coefficient": {r["outcome"]: {"b_per_1pp_growth": r["b_growth"], "se": r["se_growth"], "t": r["t_growth"],
                                                             "b_per_10pp_growth": round(10 * r["b_growth"], 4), "outcome_mean": r["outcome_mean"]}
                                              for r in reg.to_dict(orient="records")},
           "cohorts": coh.to_dict(orient="records"), "by_traffic_level": lev.to_dict(orient="records")}
    save_json(res, OUT / "results.json")
    print(reg[["outcome", "n", "b_growth", "se_growth", "t_growth", "b_log_visits", "se_log_visits", "outcome_mean"]].to_string(index=False))
    print(coh.to_string(index=False))
    print(lev.to_string(index=False))

    import sys
    sys.path.insert(0, str(LAB.parent / "_research_archive/starbucks_hiring/src"))
    import charts as C
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.7))
    for ax, (col, title) in zip(axes, [("HPI_full_vs_metro", "Hiring Pressure Index (full)"),
                                       ("dup_vs_metro", "Same-role duplicate postings"),
                                       ("pmgr5_vs_metro", "Persistent manager vacancy ≤ 5 km")]):
        v = coh[col] * (100 if col != "HPI_full_vs_metro" else 1)
        ax.bar(range(len(coh)), v, color=C.BLUE, width=0.6, zorder=2)
        ax.axhline(0, color=C.INK_2, linewidth=0.8)
        ax.set_xticks(range(len(coh)), [f"{c}\n(n={n:,})" for c, n in zip(coh["growth_cohort"], coh["stores"])], fontsize=8)
        ax.grid(axis="x", visible=False)
        for x_, y_ in enumerate(v):
            ax.text(x_, y_, f"{y_:+.2f}" if col == "HPI_full_vs_metro" else f"{y_:+.1f}", ha="center",
                    va="bottom" if y_ >= 0 else "top", fontsize=8, color=C.INK_2)
        ax.set_title(title, fontsize=10, pad=6)
        ax.set_ylabel("index points vs metro" if col == "HPI_full_vs_metro" else "pp vs metro")
    fig.suptitle("Hiring pressure by store traffic growth (Jun–Sep 2026 vs 2025), relative to the store's metro",
                 x=0.01, y=0.98, ha="left", fontsize=12, fontweight="semibold")
    fig.text(0.01, 0.01, f"n = {len(s):,} open company-operated stores · careers snapshot Oct 1 2026 · Advan visits", fontsize=8, color=C.INK_2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    fig.savefig(LAB / "charts/02_hiring_pressure_by_traffic_growth.png", dpi=200)


if __name__ == "__main__":
    main()
