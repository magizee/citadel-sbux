"""Workstream 10: wage-rate pressure where Starbucks operates (BLS QCEW).

    python src/qcew_wages.py

Source: BLS Quarterly Census of Employment and Wages, open data API (no key):
  https://data.bls.gov/cew/data/api/{year}/{qtr}/industry/{naics}.csv   (all areas, one industry, one quarter)
Industries: 722515 Snack and nonalcoholic beverage bars (coffee shops; Starbucks' own industry)
            722513 Limited-service restaurants (fast food; the broader labor pool)
Private ownership (own_code 5). County rows = agglvl_code 78, state 58, national 18.
Starbucks footprint: county FIPS of each company-operated store = first 5 digits of Advan POI_CBG.

avg_wkly_wage = total wages / employees, so it moves with BOTH hourly rates and hours per worker (part-time mix).

Calendar -> Starbucks fiscal quarter: cal Q1 = FY Q2, Q2 = FY Q3, Q3 = FY Q4, Q4 = next FY Q1.
Outputs: 09_wages/ (qcew_national.csv, starbucks_weighted_wages.csv, county_panel.csv, results.json), charts/09_wages.png
"""

from __future__ import annotations

import glob
import time

import numpy as np
import pandas as pd
import requests

from lab import LAB, OPS, save_json

OUT = LAB / "09_wages"
RAW = LAB / "data/raw/qcew"
INDUSTRIES = {"722515": "coffee & snack bars", "722513": "limited-service restaurants"}
QUARTERS = [(y, q) for y in (2023, 2024, 2025, 2026) for q in (1, 2, 3, 4)]


def fetch(year: int, qtr: int, naics: str) -> pd.DataFrame | None:
    path = RAW / f"{year}_q{qtr}_{naics}.csv"
    if not path.exists():
        r = requests.get(f"https://data.bls.gov/cew/data/api/{year}/{qtr}/industry/{naics}.csv", timeout=60)
        if r.status_code != 200 or not r.text.startswith('"area_fips"'):
            return None
        path.write_text(r.text)
        time.sleep(0.5)
    d = pd.read_csv(path, dtype={"area_fips": str, "industry_code": str, "disclosure_code": str})
    return d[d["own_code"] == 5]


def fiscal_label(year: int, qtr: int) -> str:
    fy, fq = (year + 1, 1) if qtr == 4 else (year, qtr + 1)
    return f"FY{fy % 100} Q{fq}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    frames = []
    for (y, q) in QUARTERS:
        for n in INDUSTRIES:
            d = fetch(y, q, n)
            if d is not None:
                frames.append(d)
    q = pd.concat(frames, ignore_index=True)
    q["emp"] = q[["month1_emplvl", "month2_emplvl", "month3_emplvl"]].mean(axis=1)
    q["period"] = q["year"].astype(str) + " Q" + q["qtr"].astype(str)
    q["fiscal"] = [fiscal_label(a, b) for a, b in zip(q["year"], q["qtr"])]
    have = sorted(q["period"].unique())
    print("quarters:", have[0], "->", have[-1])

    # National
    nat = q[q["agglvl_code"] == 18][["industry_code", "period", "fiscal", "qtrly_estabs", "emp", "avg_wkly_wage",
                                      "oty_avg_wkly_wage_pct_chg", "oty_month3_emplvl_pct_chg", "oty_qtrly_estabs_pct_chg"]]
    nat = nat.sort_values(["industry_code", "period"])
    nat.to_csv(OUT / "qcew_national.csv", index=False)

    # Starbucks footprint by county (company-operated, open now and at Aug 2025)
    panel = pd.read_csv(LAB / "01_store_panel/store_panel.csv", dtype={"store_id": str, "msa": str},
                        parse_dates=["close_date"])
    cbg = []
    for f in sorted(glob.glob(str(OPS / "data/raw/advan/*.parquet"))):
        cbg.append(pd.read_parquet(f, columns=["ID_STORE", "POI_CBG"]))
    cbg = pd.concat(cbg).dropna().drop_duplicates("ID_STORE", keep="last")
    cbg["county"] = cbg["POI_CBG"].astype(str).str.zfill(12).str[:5]
    panel = panel.merge(cbg[["ID_STORE", "county"]], left_on="store_id", right_on="ID_STORE", how="left")
    # company-operated: matched in the Sep-2026 locator, or (closed stores) in the Aug-2025 locator via 04's hours panel
    aug = pd.read_csv(LAB / "04_operating_hours/store_hours_panel.csv", dtype={"store_id": str}, usecols=["store_id", "weekly_hours_2025-08"])
    aug_co = set(aug.loc[aug["weekly_hours_2025-08"].notna(), "store_id"].dropna())
    co = panel[(panel["company_operated"] | panel["store_id"].isin(aug_co)) & panel["county"].notna()]
    open_now = co[co["status"].eq("open")]
    weights = open_now.groupby("county").size().rename("sbux_stores")

    cty = q[q["agglvl_code"] == 78].copy()
    cty["county"] = cty["area_fips"]
    cty["disclosed"] = cty["disclosure_code"].isna() & (cty["avg_wkly_wage"] > 0)
    rows = []
    for (ind, per), g in cty.groupby(["industry_code", "period"]):
        g = g.join(weights, on="county")
        g = g[g["sbux_stores"].notna()]
        ok = g[g["disclosed"] & g["oty_avg_wkly_wage_pct_chg"].notna() & (g["oty_disclosure_code"].isna())]
        w = ok["sbux_stores"]
        rows.append({"industry_code": ind, "period": per, "fiscal": g["fiscal"].iloc[0],
                     "store_coverage_pct": round(100 * w.sum() / weights.sum(), 1),
                     "sbux_weighted_wage_yoy_pct": round(float(np.average(ok["oty_avg_wkly_wage_pct_chg"], weights=w)), 2) if len(ok) else None,
                     "sbux_weighted_avg_wkly_wage": round(float(np.average(ok["avg_wkly_wage"], weights=w)), 0) if len(ok) else None,
                     "sbux_weighted_emp_yoy_pct": round(float(np.average(ok["oty_month3_emplvl_pct_chg"], weights=w)), 2) if len(ok) else None})
    sw = pd.DataFrame(rows).sort_values(["industry_code", "period"])
    sw = sw.merge(nat[["industry_code", "period", "oty_avg_wkly_wage_pct_chg", "oty_month3_emplvl_pct_chg"]]
                  .rename(columns={"oty_avg_wkly_wage_pct_chg": "national_wage_yoy_pct", "oty_month3_emplvl_pct_chg": "national_emp_yoy_pct"}),
                  on=["industry_code", "period"], how="left")
    sw.to_csv(OUT / "starbucks_weighted_wages.csv", index=False)

    # Compare with filings: NA store opex and revenue growth by fiscal quarter
    lev = pd.read_csv(LAB / "tables/operating_leverage.csv")
    cmp_ = sw[sw["industry_code"] == "722515"][["fiscal", "sbux_weighted_wage_yoy_pct", "national_wage_yoy_pct"]] \
        .merge(sw[sw["industry_code"] == "722513"][["fiscal", "sbux_weighted_wage_yoy_pct"]].rename(columns={"sbux_weighted_wage_yoy_pct": "fastfood_wage_yoy_pct"}), on="fiscal") \
        .merge(lev, left_on="fiscal", right_on="fiscal_quarter", how="inner")
    cmp_["opex_growth_minus_wage_growth_pp"] = (cmp_["store_opex_yoy_pct"] - cmp_["sbux_weighted_wage_yoy_pct"]).round(2)
    cmp_.to_csv(OUT / "wages_vs_store_opex.csv", index=False)

    # County cross-section: wage level/growth vs Oct-2025 closures and Starbucks traffic growth
    latest = cty[(cty["industry_code"] == "722513") & cty["disclosed"]]
    pre = latest[latest["period"] == "2025 Q2"].set_index("county")
    cp = co.copy()
    cp["closed_oct25"] = cp["close_date"].between("2025-09-01", "2025-11-30")
    cp = cp[cp["closed_oct25"] | cp["status"].eq("open")]
    agg = cp.groupby("county").agg(stores=("store_id", "size"), closed=("closed_oct25", "sum"),
                                   state=("state", "first"), yoy=("visits_yoy_pct", "median"))
    agg = agg.join(pre[["avg_wkly_wage", "oty_avg_wkly_wage_pct_chg"]].rename(
        columns={"avg_wkly_wage": "ff_wage_2025q2", "oty_avg_wkly_wage_pct_chg": "ff_wage_yoy_2025q2"})).dropna(subset=["ff_wage_2025q2"])
    agg = agg[agg["stores"] >= 3]
    agg["closure_rate_pct"] = 100 * agg["closed"] / agg["stores"]
    agg["wage_q"] = pd.qcut(agg["ff_wage_2025q2"], 5, labels=["Q1 lowest", "Q2", "Q3", "Q4", "Q5 highest"])
    byq = agg.groupby("wage_q", observed=True).apply(lambda g: pd.Series({
        "counties": len(g), "stores": int(g["stores"].sum()), "median_weekly_wage": float(g["ff_wage_2025q2"].median()),
        "closure_rate_pct": round(100 * g["closed"].sum() / g["stores"].sum(), 2),
        "median_store_yoy_traffic_pct": round(float(np.average(g["yoy"].fillna(g["yoy"].median()), weights=g["stores"])), 2)}),
        include_groups=False).reset_index()
    agg.to_csv(OUT / "county_panel.csv")
    byq.to_csv(OUT / "closures_by_county_wage_level.csv", index=False)

    ca = q[(q["agglvl_code"] == 58) & (q["area_fips"] == "06000")][["industry_code", "period", "avg_wkly_wage", "oty_avg_wkly_wage_pct_chg", "oty_month3_emplvl_pct_chg"]]
    res = {"quarters_available": [have[0], have[-1]],
           "starbucks_weighted": sw.to_dict(orient="records"),
           "wages_vs_store_opex": cmp_.to_dict(orient="records"),
           "closures_by_county_fastfood_wage_level": byq.to_dict(orient="records"),
           "california_state": ca.sort_values(["industry_code", "period"]).to_dict(orient="records"),
           "footprint": {"co_open_stores_with_county": int(len(open_now)), "counties": int(weights.size)}}
    save_json(res, OUT / "results.json")
    pd.set_option("display.width", 200)
    print(sw.to_string(index=False))
    print(cmp_.to_string(index=False))
    print(byq.to_string(index=False))
    print(ca.to_string(index=False))
    chart(sw, cmp_)


def chart(sw: pd.DataFrame, cmp_: pd.DataFrame) -> None:
    import sys
    sys.path.insert(0, str(LAB.parent / "_research_archive/starbucks_hiring/src"))
    import charts as C
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    ax = axes[0]
    for ind, col in (("722515", C.BLUE), ("722513", C.GRAY)):
        g = sw[(sw["industry_code"] == ind) & sw["sbux_weighted_wage_yoy_pct"].notna()]
        ax.plot(range(len(g)), g["sbux_weighted_wage_yoy_pct"], color=col, linewidth=2, marker="o", markersize=5,
                label=f"{INDUSTRIES[ind]} ({ind})")
        ticks = g["fiscal"].str.replace(" ", "\n").tolist()
    ax.set_xticks(range(len(ticks)), ticks, fontsize=7)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_ylabel("avg weekly wage, YoY %")
    ax.set_title("Wage growth in counties where Starbucks operates\n(weighted by company-operated stores)", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax = axes[1]
    x = np.arange(len(cmp_))
    ax.bar(x - 0.27, cmp_["store_opex_yoy_pct"], width=0.26, color=C.BLUE, label="Starbucks NA store opex")
    ax.bar(x, cmp_["revenue_yoy_pct"], width=0.26, color=C.BLUE_LIGHT, label="Starbucks NA company-op revenue")
    ax.bar(x + 0.27, cmp_["sbux_weighted_wage_yoy_pct"], width=0.26, color=C.GRAY, label="Coffee-bar wages, SBUX counties")
    ax.set_xticks(x, cmp_["fiscal"].str.replace(" ", "\n"), fontsize=8)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_ylabel("YoY growth, %")
    ax.set_title("Store costs vs revenue vs market wage growth", fontsize=10)
    ax.legend(fontsize=7.5, frameon=False, loc="upper right")
    ax.grid(axis="x", visible=False)
    fig.suptitle("Market wage growth explains only part of Starbucks' store-cost growth", x=0.01, y=0.99, ha="left",
                 fontsize=12, fontweight="semibold")
    fig.text(0.01, 0.01, "BLS QCEW private-sector county data (avg weekly wage = wages ÷ employees; mixes hourly rate and hours) · Starbucks 8-K filings",
             fontsize=8, color=C.INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    fig.savefig(LAB / "charts/09_wages.png", dpi=200)


if __name__ == "__main__":
    main()
