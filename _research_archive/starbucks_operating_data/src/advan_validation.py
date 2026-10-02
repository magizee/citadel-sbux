"""Step 1 + 3: validate Advan against reported U.S. comparable transactions, and repeat key metrics by quarter.

    python src/advan_validation.py

For each Starbucks fiscal quarter (13 weeks, Monday-start weeks) from FY25 Q2 to FY26 Q4:
  - Starbucks same-store visit growth vs the same 13 weeks one year (52 weeks) earlier, for stores matched to
    company-operated locations (what reported comps cover) and for all U.S. locations; median and aggregate.
  - Dunkin' same-store visit growth on the same weeks, and the Starbucks - Dunkin' gap (panel effects cancel).
  - Starbucks' share of Starbucks + Dunkin' visits, and its YoY change.
Compared with reported U.S. comparable transactions (Starbucks earnings releases / 8-Ks).
FY26 Q4 (Jun 29 - Sep 27 2026) is not yet reported: Advan gives an early read (data through Sep 27).

Outputs: outputs/advan/validation_quarterly.csv, validation_results.json, validation_vs_reported.png,
         rolling_vs_dunkin.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs/advan"
sys.path.insert(0, str(ROOT.parent / "starbucks_hiring/src"))
import charts as C  # noqa: E402

# Reported U.S. comparable transactions / comp sales (%), Starbucks earnings releases (8-K exhibit 99.1).
QUARTERS = [
    ("FY25 Q2", "2024-12-30", -4.0, -2.0),
    ("FY25 Q3", "2025-03-31", -4.0, -2.0),
    ("FY25 Q4", "2025-06-30", -1.0, 0.0),
    ("FY26 Q1", "2025-09-29", 3.0, 4.0),
    ("FY26 Q2", "2025-12-29", 4.3, 7.1),
    ("FY26 Q3", "2026-03-30", 4.2, 7.9),
    ("FY26 Q4", "2026-06-29", None, None),   # not yet reported; guidance: U.S. comps >= 6.5%
]
COLS = ["ID_STORE", "BRAND", "ISO_COUNTRY_CODE", "VISIT_COUNTS", "DATE_RANGE_START"]


def load(folder: str, brand: str) -> pd.DataFrame:
    frames = []
    for f in sorted((ROOT / folder).glob("*.parquet")):
        d = pd.read_parquet(f, columns=COLS)
        frames.append(d[(d["ISO_COUNTRY_CODE"] == "US") & d["BRAND"].fillna("").str.contains(brand, case=False)])
    d = pd.concat(frames, ignore_index=True)
    d["week"] = pd.to_datetime(d["DATE_RANGE_START"].astype(str).str[:10])
    d["visits"] = pd.to_numeric(d["VISIT_COUNTS"], errors="coerce")
    return d[["ID_STORE", "week", "visits"]]


def same_store(d: pd.DataFrame, start: pd.Timestamp, stores=None) -> dict:
    cur = pd.date_range(start, periods=13, freq="7D")
    cur = cur[cur <= d["week"].max()]
    prev = cur - pd.Timedelta(weeks=52)
    x = d if stores is None else d[d["ID_STORE"].isin(stores)]
    a = x[x["week"].isin(cur)].groupby("ID_STORE")["visits"].agg(["mean", "size"])
    b = x[x["week"].isin(prev)].groupby("ID_STORE")["visits"].agg(["mean", "size"])
    j = a.join(b, lsuffix="_c", rsuffix="_p", how="inner")
    need = max(1, int(round(len(cur) * 0.85)))
    j = j[(j["size_c"] >= need) & (j["size_p"] >= need) & (j["mean_p"] > 0)]
    y = 100 * (j["mean_c"] / j["mean_p"] - 1)
    keep = y.between(*y.quantile([0.01, 0.99]))
    j, y = j[keep], y[keep]
    return {"weeks": len(cur), "stores": int(len(j)), "median_pct": float(y.median()),
            "aggregate_pct": float(100 * (j["mean_c"].sum() / j["mean_p"].sum() - 1))}


def main() -> None:
    sb, dk = load("data/raw/advan", "Starbucks"), load("data/raw/advan_competitors", "Dunkin")
    co = set(pd.read_csv(OUT / "store_visits_yoy.csv", dtype={"placekey": str})["placekey"])   # CO-matched stores
    rows = []
    for name, start, rep_tx, rep_comp in QUARTERS:
        s = pd.Timestamp(start)
        sco, sall, d_ = same_store(sb, s, co), same_store(sb, s), same_store(dk, s)
        cur = pd.date_range(s, periods=13, freq="7D")
        cur = cur[cur <= sb["week"].max()]
        prev = cur - pd.Timedelta(weeks=52)
        sh = lambda w: sb[sb["week"].isin(w)]["visits"].sum() / (sb[sb["week"].isin(w)]["visits"].sum() + dk[dk["week"].isin(w)]["visits"].sum())  # noqa: E731
        rows.append({"quarter": name, "start": start, "weeks_of_data": sco["weeks"],
                     "reported_us_comp_transactions_pct": rep_tx, "reported_us_comp_sales_pct": rep_comp,
                     "sbux_co_same_store_median_pct": round(sco["median_pct"], 2),
                     "sbux_co_same_store_aggregate_pct": round(sco["aggregate_pct"], 2), "sbux_co_stores": sco["stores"],
                     "sbux_all_same_store_median_pct": round(sall["median_pct"], 2),
                     "dunkin_same_store_median_pct": round(d_["median_pct"], 2), "dunkin_stores": d_["stores"],
                     "sbux_minus_dunkin_pp": round(sco["median_pct"] - d_["median_pct"], 2),
                     "sbux_share_pct": round(100 * sh(cur), 2), "sbux_share_yoy_pp": round(100 * (sh(cur) - sh(prev)), 2)})
    q = pd.DataFrame(rows)
    q.to_csv(OUT / "validation_quarterly.csv", index=False)

    rep = q.dropna(subset=["reported_us_comp_transactions_pct"])
    res = {"quarters": q.to_dict(orient="records")}
    for col in ("sbux_co_same_store_median_pct", "sbux_co_same_store_aggregate_pct", "sbux_minus_dunkin_pp"):
        x, y = rep[col].to_numpy(), rep["reported_us_comp_transactions_pct"].to_numpy()
        slope, intercept = np.polyfit(x, y, 1)
        res[f"fit_{col}"] = {"pearson_r": round(float(np.corrcoef(x, y)[0, 1]), 3), "slope": round(float(slope), 3),
                             "intercept": round(float(intercept), 3),
                             "mean_gap_reported_minus_advan_pp": round(float((y - x).mean()), 2)}
    # Early read on FY26 Q4 from the best-fitting Advan series
    best = max(("sbux_co_same_store_median_pct", "sbux_co_same_store_aggregate_pct", "sbux_minus_dunkin_pp"),
               key=lambda c: res[f"fit_{c}"]["pearson_r"])
    f = res[f"fit_{best}"]
    q4 = q[q["quarter"] == "FY26 Q4"].iloc[0]
    res["fy26_q4_early_read"] = {"series": best, "advan_value": q4[best], "weeks_of_data": int(q4["weeks_of_data"]),
                                 "implied_us_comp_transactions_pct": round(f["slope"] * q4[best] + f["intercept"], 1),
                                 "note": "Linear fit on 6 reported quarters; indicative only."}
    (OUT / "validation_results.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))

    # Chart 1: reported transactions vs Advan same-store visits (same axis, % YoY)
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4))
    x = range(len(q))
    ax.plot(x, q["reported_us_comp_transactions_pct"], color=C.INK, linewidth=2, marker="o", label="Reported U.S. comparable transactions")
    ax.plot(x, q["sbux_co_same_store_aggregate_pct"], color=C.BLUE, linewidth=2, marker="o", label="Advan same-store visits (company-operated)")
    ax.plot(x, q["sbux_minus_dunkin_pp"], color="#eb6834", linewidth=2, marker="o", linestyle="-", label="Advan Starbucks minus Dunkin' (pp)")
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_xticks(list(x), [f"{a}\n({'reported' if pd.notna(r) else 'not yet reported'})" for a, r in zip(q["quarter"], q["reported_us_comp_transactions_pct"])], fontsize=8)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("YoY (%)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Does Advan foot traffic track Starbucks' reported transactions?")
    r1, r2 = res["fit_sbux_co_same_store_aggregate_pct"]["pearson_r"], res["fit_sbux_minus_dunkin_pp"]["pearson_r"]
    C._finish(fig, ax, OUT / "validation_vs_reported.png",
              f"Starbucks fiscal quarters · correlation with reported transactions: same-store r = {r1}, vs-Dunkin' gap r = {r2} (6 quarters)",
              note="Reported: Starbucks earnings releases (8-K). Advan via Dewey; same-store = 52-week YoY on stores with ≥ 11 of 13 weeks.")

    # Chart 2: rolling comparison vs Dunkin'
    fig, ax = plt.subplots(figsize=(9, 3.8))
    w = 0.38
    ax.bar([i - w / 2 for i in x], q["sbux_co_same_store_median_pct"], width=w, color=C.BLUE, label="Starbucks same-store visits", zorder=2)
    ax.bar([i + w / 2 for i in x], q["dunkin_same_store_median_pct"], width=w, color=C.GRAY, label="Dunkin' same-store visits", zorder=2)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_xticks(list(x), q["quarter"], fontsize=8.5)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Median YoY (%)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Starbucks vs Dunkin' same-store visits, by quarter")
    C._finish(fig, ax, OUT / "rolling_vs_dunkin.png",
              "Median per-location visit growth vs the same 13 weeks a year earlier · Starbucks fiscal quarters",
              note="FY26 Q4 uses data through Sep 21-27, 2026. Same Advan panel for both brands.")


if __name__ == "__main__":
    main()
