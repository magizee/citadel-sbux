"""Workstream 6 (service quality): does traffic growth come with longer visits (a wait-time / congestion proxy)?

    python src/service_quality.py

Source: Advan Weekly Patterns MEDIAN_DWELL (minutes, per store-week) and BUCKETED_DWELL_TIMES (<5, 5-20, 21-60, 61-240, >240).
Dwell = time a phone is detected at the store. For a coffee shop it mixes order-to-pickup wait AND sit-down time, so a
rise can mean slower service OR more people staying (Starbucks' "Back to Starbucks" café push encourages staying).
Dunkin' (mostly grab-and-go) is the comparison.

Tests:
  1. Same-store median dwell and share of visits >= 5 min over time, Starbucks (company-operated) vs Dunkin'.
  2. Store level: change in dwell (latest 13 weeks vs same weeks a year earlier) vs traffic growth, metro FE.
     If growth is absorbed without service strain, fast-growing stores should not see dwell rise more.
Outputs: 05_service_quality/ (weekly_dwell.csv, store_dwell_change.csv, results.json), charts/05_service_quality.png
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from hiring_pressure import ols_fe
from lab import LAB, OPS, save_json

OUT = LAB / "05_service_quality"
COLS = ["ID_STORE", "BRAND", "ISO_COUNTRY_CODE", "DATE_RANGE_START", "VISIT_COUNTS", "MEDIAN_DWELL", "BUCKETED_DWELL_TIMES"]


def load(folder: str, brand: str) -> pd.DataFrame:
    frames = []
    for f in sorted((OPS / folder).glob("*.parquet")):
        d = pd.read_parquet(f, columns=COLS)
        frames.append(d[(d["ISO_COUNTRY_CODE"] == "US") & d["BRAND"].fillna("").str.contains(brand, case=False)])
    d = pd.concat(frames, ignore_index=True)
    d["week"] = pd.to_datetime(d["DATE_RANGE_START"].astype(str).str[:10])
    d["visits"] = pd.to_numeric(d["VISIT_COUNTS"], errors="coerce")
    d["dwell"] = pd.to_numeric(d["MEDIAN_DWELL"], errors="coerce")
    b = d["BUCKETED_DWELL_TIMES"].dropna().map(json.loads)
    d.loc[b.index, "lt5"] = b.map(lambda x: x.get("<5", 0))
    d.loc[b.index, "bucket_total"] = b.map(lambda x: sum(x.values()))
    d = d[d["dwell"].between(1, 120)]  # drop employee / all-day devices
    return d[["ID_STORE", "week", "visits", "dwell", "lt5", "bucket_total"]]


def window(d: pd.DataFrame, end: pd.Timestamp, n: int = 13) -> pd.DataFrame:
    w = d[d["week"].isin(pd.date_range(end=end, periods=n, freq="7D"))]
    g = w.groupby("ID_STORE").agg(dwell=("dwell", "median"), lt5=("lt5", "sum"), bt=("bucket_total", "sum"),
                                  visits=("visits", "mean"), weeks=("week", "size"))
    g["share_ge5"] = 1 - g["lt5"] / g["bt"]
    return g[g["weeks"] >= 10]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(LAB / "01_store_panel/store_panel.csv", dtype={"store_id": str, "msa": str})
    co = set(panel.loc[panel["company_operated"] & panel["status"].eq("open"), "store_id"])
    sb = load("data/raw/advan", "Starbucks")
    sb = sb[sb["ID_STORE"].isin(co)]
    dk = load("data/raw/advan_competitors", "Dunkin")

    # 1. weekly national series (median of store medians; visit-weighted share >= 5 min), balanced-ish panels
    rows = []
    for name, d in (("Starbucks (company-operated)", sb), ("Dunkin'", dk)):
        g = d.groupby("week").agg(median_dwell=("dwell", "median"), lt5=("lt5", "sum"), bt=("bucket_total", "sum"), stores=("ID_STORE", "nunique"))
        g["share_ge5_pct"] = 100 * (1 - g["lt5"] / g["bt"])
        g["brand"] = name
        rows.append(g.reset_index())
    wk = pd.concat(rows)
    wk.to_csv(OUT / "weekly_dwell.csv", index=False)

    # 2. store-level YoY change vs traffic growth
    last = sb["week"].max()
    res = {"weeks": [str(sb["week"].min().date()), str(last.date())]}
    out = {}
    for name, d in (("starbucks", sb), ("dunkin", dk)):
        cur, ly = window(d, last), window(d, last - pd.Timedelta(weeks=52))
        j = cur.join(ly, rsuffix="_ly", how="inner")
        j["d_dwell"] = j["dwell"] - j["dwell_ly"]
        j["d_share_ge5_pp"] = 100 * (j["share_ge5"] - j["share_ge5_ly"])
        j["growth"] = 100 * (j["visits"] / j["visits_ly"] - 1)
        j = j[j["growth"].between(*j["growth"].quantile([0.01, 0.99]))]
        out[name] = j
        res[f"{name}_same_store"] = {"stores": len(j), "median_dwell_ly": float(j["dwell_ly"].median()), "median_dwell_now": float(j["dwell"].median()),
                                     "mean_d_dwell_min": round(float(j["d_dwell"].mean()), 3),
                                     "share_ge5_ly_pct": round(100 * float(j["share_ge5_ly"].mean()), 2),
                                     "share_ge5_now_pct": round(100 * float(j["share_ge5"].mean()), 2),
                                     "mean_d_share_ge5_pp": round(float(j["d_share_ge5_pp"].mean()), 2)}
    s = out["starbucks"].join(panel.set_index("store_id")[["msa", "visits_per_week_13w"]], how="left").dropna(subset=["msa"])
    s["log_visits"] = np.log(s["visits_ly"])
    s = s.reset_index().rename(columns={"index": "store_id", "ID_STORE": "store_id"})
    reg = pd.DataFrame([ols_fe(s, y, ["growth", "log_visits"]) for y in ["d_dwell", "d_share_ge5_pp"]])
    s["cohort"] = pd.cut(s["growth"], [-1e9, 0, 5, 10, 1e9], labels=["< 0%", "0–5%", "5–10%", "> 10%"])
    coh = s.groupby("cohort", observed=True).agg(stores=("store_id", "size"), d_dwell=("d_dwell", "mean"),
                                                d_share_ge5_pp=("d_share_ge5_pp", "mean"), share_ge5_now=("share_ge5", "mean")).round(3).reset_index()
    s.to_csv(OUT / "store_dwell_change.csv", index=False)
    coh.to_csv(OUT / "dwell_by_growth_cohort.csv", index=False)
    res["regressions_metroFE"] = {r["outcome"]: {"b_per_1pp_growth": r["b_growth"], "se": r["se_growth"], "t": r["t_growth"], "n": r["n"]}
                                  for r in reg.to_dict(orient="records")}
    res["cohorts"] = coh.to_dict(orient="records")
    # Same-store weekly series index: FY-quarter means of the visit-weighted share >= 5 min
    wk["q"] = wk["week"].dt.to_period("Q-SEP")
    res["share_ge5_by_fiscal_quarter"] = wk.groupby(["brand", "q"])["share_ge5_pct"].mean().round(2).unstack(0).astype(float) \
        .rename(index=lambda p: f"FY{str(p.qyear)[2:]} Q{p.quarter}").to_dict()
    save_json(res, OUT / "results.json")
    print(json.dumps(res, indent=1, default=str))
    chart(wk, coh)


def chart(wk: pd.DataFrame, coh: pd.DataFrame) -> None:
    import sys
    sys.path.insert(0, str(LAB.parent / "_research_archive/starbucks_hiring/src"))
    import charts as C
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4))
    ax = axes[0]
    for name, col in (("Starbucks (company-operated)", C.BLUE), ("Dunkin'", C.GRAY)):
        g = wk[wk["brand"] == name].set_index("week")["share_ge5_pct"].rolling(4, min_periods=2).mean()
        ax.plot(g.index, g.values, color=col, linewidth=2, label=name)
    ax.set_ylabel("% of visits lasting ≥ 5 min (4-wk avg)")
    ax.set_title("Longer visits: share of visits ≥ 5 minutes", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax = axes[1]
    ax.bar(range(len(coh)), coh["d_share_ge5_pp"], color=C.BLUE, width=0.6)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    for x_, y_ in enumerate(coh["d_share_ge5_pp"]):
        ax.text(x_, y_, f"{y_:+.1f}", ha="center", va="bottom" if y_ >= 0 else "top", fontsize=8, color=C.INK_2)
    ax.set_xticks(range(len(coh)), [f"{c}\n(n={n:,})" for c, n in zip(coh["cohort"], coh["stores"])], fontsize=8)
    ax.set_ylabel("YoY change, pp")
    ax.set_title("Change in share of visits ≥ 5 min, by store traffic growth (YoY)", fontsize=10)
    ax.grid(axis="x", visible=False)
    fig.suptitle("Service-time proxy: Advan dwell time (mixes waiting and sitting)", x=0.01, y=0.99, ha="left", fontsize=12, fontweight="semibold")
    fig.text(0.01, 0.01, "Advan Weekly Patterns MEDIAN_DWELL / BUCKETED_DWELL_TIMES · panel sample, relative only",
             fontsize=8, color=C.INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    fig.savefig(LAB / "charts/05_service_quality.png", dpi=200)


if __name__ == "__main__":
    main()
