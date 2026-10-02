"""Two-year view: is Starbucks traffic above 2024, or only recovering? (Advan, Starbucks vs Dunkin')

    python src/advan_two_year.py

For FY26 Q2-Q4 (the quarters with two full years of Advan history), same-store visit growth vs the same
13 weeks 104 weeks earlier, for Starbucks company-operated stores and for Dunkin'. Reported two-year U.S.
comparable transactions are compounded from the quarterly releases for comparison (FY26 Q4 not yet reported).
Advan understates the size of moves (~2.4x vs reported in our validation), so compare Starbucks with Dunkin'
and the direction, not the magnitude.

Outputs: outputs/advan/two_year.csv, two_year_results.json, two_year.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs/advan"
sys.path.insert(0, str(ROOT.parent / "starbucks_hiring/src"))
sys.path.insert(0, str(ROOT / "src"))
import charts as C  # noqa: E402
from advan_validation import QUARTERS, load  # noqa: E402


def same_store(d: pd.DataFrame, start: pd.Timestamp, lag_weeks: int, stores=None) -> dict:
    cur = pd.date_range(start, periods=13, freq="7D")
    cur = cur[cur <= d["week"].max()]
    prev = cur - pd.Timedelta(weeks=lag_weeks)
    x = d if stores is None else d[d["ID_STORE"].isin(stores)]
    a = x[x["week"].isin(cur)].groupby("ID_STORE")["visits"].agg(["mean", "size"])
    b = x[x["week"].isin(prev)].groupby("ID_STORE")["visits"].agg(["mean", "size"])
    j = a.join(b, lsuffix="_c", rsuffix="_p", how="inner")
    need = max(1, int(round(len(cur) * 0.85)))
    j = j[(j["size_c"] >= need) & (j["size_p"] >= need) & (j["mean_p"] > 0)]
    y = 100 * (j["mean_c"] / j["mean_p"] - 1)
    keep = y.between(*y.quantile([0.01, 0.99]))
    j, y = j[keep], y[keep]
    return {"stores": int(len(j)), "median_pct": round(float(y.median()), 2),
            "aggregate_pct": round(float(100 * (j["mean_c"].sum() / j["mean_p"].sum() - 1)), 2)}


def main() -> None:
    sb, dk = load("data/raw/advan", "Starbucks"), load("data/raw/advan_competitors", "Dunkin")
    co = set(pd.read_csv(OUT / "store_visits_yoy.csv", dtype={"placekey": str})["placekey"])
    rep = {q: tx for q, _, tx, _ in QUARTERS}
    rows = []
    for i, (name, start, tx, _) in enumerate(QUARTERS):
        s = pd.Timestamp(start)
        if s - pd.Timedelta(weeks=104) < sb["week"].min():
            continue
        prior_name = QUARTERS[i - 4][0] if i >= 4 else None   # same fiscal quarter one year earlier
        prior_tx = rep.get(prior_name) if prior_name else None
        two_yr_reported = (round(100 * ((1 + tx / 100) * (1 + prior_tx / 100) - 1), 2)
                           if tx is not None and prior_tx is not None else None)
        s2, d2 = same_store(sb, s, 104, co), same_store(dk, s, 104)
        s1, d1 = same_store(sb, s, 52, co), same_store(dk, s, 52)
        rows.append({"quarter": name, "start": start,
                     "reported_tx_yoy_pct": tx, "reported_tx_prior_year_pct": prior_tx, "reported_tx_two_year_pct": two_yr_reported,
                     "sbux_two_year_median_pct": s2["median_pct"], "dunkin_two_year_median_pct": d2["median_pct"],
                     "sbux_minus_dunkin_two_year_pp": round(s2["median_pct"] - d2["median_pct"], 2),
                     "sbux_one_year_median_pct": s1["median_pct"], "dunkin_one_year_median_pct": d1["median_pct"],
                     "sbux_stores": s2["stores"], "dunkin_stores": d2["stores"]})
    t = pd.DataFrame(rows)
    t.to_csv(OUT / "two_year.csv", index=False)
    res = {"quarters": t.to_dict(orient="records"),
           "note": "Two-year = same 13 weeks 104 weeks earlier (FY24 equivalent). Reported two-year compounds the two YoY figures."}
    (OUT / "two_year_results.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    x = range(len(t))
    w = 0.38
    ax.bar([i - w / 2 for i in x], t["sbux_two_year_median_pct"], width=w, color=C.BLUE, label="Starbucks (company-operated)", zorder=2)
    ax.bar([i + w / 2 for i in x], t["dunkin_two_year_median_pct"], width=w, color=C.GRAY, label="Dunkin'", zorder=2)
    for i, r in t.iterrows():
        for dx, v in ((-w / 2, r["sbux_two_year_median_pct"]), (w / 2, r["dunkin_two_year_median_pct"])):
            ax.text(i + dx, v, f"{v:+.1f}%", ha="center", va="bottom" if v >= 0 else "top", fontsize=8.5, color=C.INK_2)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_xticks(list(x), [f"{q}\n(reported 2-yr tx: {'n/a' if pd.isna(r) else f'{r:+.1f}%'})"
                            for q, r in zip(t["quarter"], t["reported_tx_two_year_pct"])], fontsize=8.5)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Same-store visits vs 2 years earlier (%)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Two years on: Starbucks traffic vs 2024, compared with Dunkin'")
    C._finish(fig, ax, OUT / "two_year.png",
              "Median same-store visits vs the same 13 weeks two years earlier (Advan) · Starbucks fiscal quarters",
              note="Advan understates the size of moves vs reported transactions; compare the two brands. Panel changes affect both equally.")


if __name__ == "__main__":
    main()
