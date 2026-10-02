"""Starbucks vs Dunkin' foot traffic (Advan via Dewey): share, same-store momentum, closure leakage.

    python src/advan_competitor_share.py

Both brands come from the same Advan phone panel, so panel-size changes cancel in shares and in
relative growth. "Share" = Starbucks visits / (Starbucks + Dunkin' visits); it is a two-brand share,
NOT a share of the whole coffee market (the competitor dataset holds only Dunkin' and Tim Hortons).

Inputs : data/raw/advan/*.parquet (Starbucks), data/raw/advan_competitors/*.parquet (Dunkin'/Tim Hortons)
         outputs/advan/store_visits_yoy.csv (leadership-zone flags for Starbucks stores)
Outputs: outputs/advan/competitor_*.csv, competitor_share_results.json, competitor_*.png
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

COLS = ["ID_STORE", "BRAND", "ISO_COUNTRY_CODE", "VISIT_COUNTS", "MSA_CODE", "DATE_RANGE_START", "CLOSE_DATE"]
WIN26 = ("2026-06-29", "2026-09-21")      # latest 13 weeks; prior-year window is 52 weeks earlier


def load(folder: str, brand_filter) -> pd.DataFrame:
    frames = []
    for f in sorted((ROOT / folder).glob("*.parquet")):
        d = pd.read_parquet(f, columns=COLS)
        d = d[(d["ISO_COUNTRY_CODE"] == "US") & brand_filter(d["BRAND"].fillna(""))]
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d["week"] = pd.to_datetime(d["DATE_RANGE_START"].astype(str).str[:10])
    d["visits"] = pd.to_numeric(d["VISIT_COUNTS"], errors="coerce")
    return d.drop(columns=["ISO_COUNTRY_CODE", "VISIT_COUNTS", "DATE_RANGE_START"])


def same_store_yoy(d: pd.DataFrame) -> pd.Series:
    """Per-location mean weekly visits, latest 13 weeks vs the same weeks 52 weeks earlier (>= 11 weeks each)."""
    cur = pd.date_range(WIN26[0], WIN26[1], freq="7D")
    prev = cur - pd.Timedelta(weeks=52)
    a = d[d["week"].isin(cur)].groupby("ID_STORE")["visits"].agg(["mean", "size"])
    b = d[d["week"].isin(prev)].groupby("ID_STORE")["visits"].agg(["mean", "size"])
    j = a.join(b, lsuffix="_c", rsuffix="_p", how="inner")
    j = j[(j["size_c"] >= 11) & (j["size_p"] >= 11) & (j["mean_p"] > 0)]
    y = 100 * (j["mean_c"] / j["mean_p"] - 1)
    lo, hi = y.quantile([0.01, 0.99])
    return y[y.between(lo, hi)]


def main() -> None:
    sb = load("data/raw/advan", lambda b: b.str.contains("Starbucks", case=False))
    dk = load("data/raw/advan_competitors", lambda b: b.str.contains("Dunkin", case=False))
    res = {"note": "Two-brand share (Starbucks vs Dunkin'); same Advan panel for both.",
           "starbucks_rows": len(sb), "dunkin_rows": len(dk)}

    # 1. National weekly totals and share
    w = pd.DataFrame({"starbucks_visits": sb.groupby("week")["visits"].sum(),
                      "dunkin_visits": dk.groupby("week")["visits"].sum(),
                      "starbucks_locations": sb.groupby("week")["ID_STORE"].nunique(),
                      "dunkin_locations": dk.groupby("week")["ID_STORE"].nunique()}).dropna()
    w["starbucks_share_pct"] = 100 * w["starbucks_visits"] / (w["starbucks_visits"] + w["dunkin_visits"])
    w["sb_visits_per_location"] = w["starbucks_visits"] / w["starbucks_locations"]
    w["dk_visits_per_location"] = w["dunkin_visits"] / w["dunkin_locations"]
    w["share_yoy_pp"] = w["starbucks_share_pct"] - w["starbucks_share_pct"].shift(52)
    w.to_csv(OUT / "competitor_weekly.csv")
    cur = w.loc[WIN26[0]:WIN26[1]]
    prv = w.loc[str((pd.Timestamp(WIN26[0]) - pd.Timedelta(weeks=52)).date()):str((pd.Timestamp(WIN26[1]) - pd.Timedelta(weeks=52)).date())]
    res["national"] = {
        "share_2026_window_pct": round(float(cur["starbucks_share_pct"].mean()), 2),
        "share_2025_window_pct": round(float(prv["starbucks_share_pct"].mean()), 2),
        "share_change_pp": round(float(cur["starbucks_share_pct"].mean() - prv["starbucks_share_pct"].mean()), 2),
        "starbucks_total_visits_yoy_pct": round(100 * (cur["starbucks_visits"].mean() / prv["starbucks_visits"].mean() - 1), 2),
        "dunkin_total_visits_yoy_pct": round(100 * (cur["dunkin_visits"].mean() / prv["dunkin_visits"].mean() - 1), 2),
        "starbucks_locations_yoy_pct": round(100 * (cur["starbucks_locations"].mean() / prv["starbucks_locations"].mean() - 1), 2),
        "dunkin_locations_yoy_pct": round(100 * (cur["dunkin_locations"].mean() / prv["dunkin_locations"].mean() - 1), 2),
        "share_2024_first13w_pct": round(float(w["starbucks_share_pct"].iloc[:13].mean()), 2)}
    res["national"]["starbucks_total_minus_dunkin_total_pp"] = round(
        res["national"]["starbucks_total_visits_yoy_pct"] - res["national"]["dunkin_total_visits_yoy_pct"], 2)

    # 2. Same-store momentum (panel effects cancel in the difference)
    ys, yd = same_store_yoy(sb), same_store_yoy(dk)
    res["same_store"] = {"starbucks_median_pct": round(float(ys.median()), 2), "starbucks_stores": int(ys.size),
                         "dunkin_median_pct": round(float(yd.median()), 2), "dunkin_stores": int(yd.size),
                         "starbucks_minus_dunkin_pp": round(float(ys.median() - yd.median()), 2)}

    # 3. Metros: share change vs Starbucks closures and manager-vacancy exposure
    def msa_window(d, start, end):
        x = d[(d["week"] >= start) & (d["week"] <= end)]
        return x.groupby("MSA_CODE")["visits"].sum() / x["week"].nunique()
    s26, s25 = msa_window(sb, *WIN26), msa_window(sb, str((pd.Timestamp(WIN26[0]) - pd.Timedelta(weeks=52)).date()),
                                                  str((pd.Timestamp(WIN26[1]) - pd.Timedelta(weeks=52)).date()))
    d26, d25 = msa_window(dk, *WIN26), msa_window(dk, str((pd.Timestamp(WIN26[0]) - pd.Timedelta(weeks=52)).date()),
                                                  str((pd.Timestamp(WIN26[1]) - pd.Timedelta(weeks=52)).date()))
    m = pd.DataFrame({"sb26": s26, "sb25": s25, "dk26": d26, "dk25": d25}).dropna()
    m = m[(m[["sb25", "dk25"]] > 0).all(axis=1)]
    m["share25"], m["share26"] = 100 * m.sb25 / (m.sb25 + m.dk25), 100 * m.sb26 / (m.sb26 + m.dk26)
    m["share_change_pp"] = m["share26"] - m["share25"]
    last = sb.sort_values("week").drop_duplicates("ID_STORE", keep="last")
    cd = pd.to_datetime(last["CLOSE_DATE"].astype(str).str[:10], errors="coerce")
    closed = last[(cd >= "2025-07-01") & (cd < "2026-09-01")].groupby("MSA_CODE").size()
    sb_locs = sb[(sb["week"] >= "2025-06-30") & (sb["week"] <= "2025-09-22")].groupby("MSA_CODE")["ID_STORE"].nunique()
    m["sb_locations_2025"] = sb_locs
    m["sb_closures"] = closed.reindex(m.index).fillna(0)
    m["closures_per_100"] = 100 * m["sb_closures"] / m["sb_locations_2025"]
    yo = pd.read_csv(OUT / "store_visits_yoy.csv", dtype={"placekey": str})
    msa_map = sb.drop_duplicates("ID_STORE").set_index("ID_STORE")["MSA_CODE"]
    yo["msa"] = yo["placekey"].map(msa_map)
    m["pct_stores_near_persistent_vacancy"] = 100 * yo.groupby("msa")["persistent_leadership_zone"].mean()
    big = m[(m["sb_locations_2025"] >= 20) & (m["dk25"] > 0)].copy()
    big["closure_band"] = pd.cut(big["closures_per_100"], [-0.01, 0.001, 3, 6, 100], labels=["none", "0-3", "3-6", "6+"])
    band = big.groupby("closure_band", observed=True).agg(metros=("share_change_pp", "size"),
                                                          median_share_change_pp=("share_change_pp", "median"),
                                                          sb_locations=("sb_locations_2025", "sum")).round(2).reset_index()
    band.to_csv(OUT / "competitor_share_by_closure_band.csv", index=False)
    m.round(3).to_csv(OUT / "competitor_msa.csv")
    res["metros"] = {
        "metros_with_20plus_starbucks": len(big),
        "metros_losing_share_pct": round(100 * float((big["share_change_pp"] < 0).mean()), 1),
        "median_share_change_pp": round(float(big["share_change_pp"].median()), 2),
        "spearman_share_change_vs_closures_per_100": round(float(big["share_change_pp"].rank().corr(big["closures_per_100"].rank())), 3),
        "spearman_share_change_vs_persistent_vacancy_exposure": round(float(
            big["share_change_pp"].rank().corr(big["pct_stores_near_persistent_vacancy"].rank())), 3),
        "by_closure_band": band.to_dict(orient="records")}
    (OUT / "competitor_share_results.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))

    # Charts
    import matplotlib.pyplot as plt
    mo = w.resample("MS")[["starbucks_visits", "dunkin_visits"]].sum()
    mo = mo[mo.index < pd.Timestamp(WIN26[1]).replace(day=1)]
    mo["share"] = 100 * mo["starbucks_visits"] / (mo["starbucks_visits"] + mo["dunkin_visits"])
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(mo.index, mo["share"], color=C.BLUE, linewidth=2)
    ax.scatter(mo.index[-1], mo["share"].iloc[-1], color=C.BLUE, s=30, zorder=3)
    ax.text(mo.index[-1], mo["share"].iloc[-1], f"  {mo['share'].iloc[-1]:.1f}%", va="center", fontsize=9, color=C.INK_2)
    ax.axvline(pd.Timestamp("2025-10-13"), color=C.INK_2, linewidth=1)
    ax.text(pd.Timestamp("2025-10-13"), ax.get_ylim()[1], " Oct-2025 closures", va="top", fontsize=8.5, color=C.INK_2)
    ax.set_ylabel("Starbucks share of visits (%)")
    ax.set_title("Starbucks' share of Starbucks + Dunkin' visits")
    C._finish(fig, ax, OUT / "competitor_share_monthly.png",
              f"U.S. locations, monthly, Advan · share change Jun–Sep 2026 vs 2025: {res['national']['share_change_pp']:+.2f} pp",
              note="Two-brand share only (dataset holds Dunkin' and Tim Hortons). Same phone panel for both brands.")
    fig, ax = plt.subplots(figsize=(8, 3.4))
    vals = [res["same_store"]["starbucks_median_pct"], res["same_store"]["dunkin_median_pct"],
            res["national"]["starbucks_total_visits_yoy_pct"], res["national"]["dunkin_total_visits_yoy_pct"]]
    labels = ["Starbucks\nsame-store", "Dunkin'\nsame-store", "Starbucks\nall locations", "Dunkin'\nall locations"]
    ax.bar(range(4), vals, color=[C.BLUE, C.GRAY, C.BLUE, C.GRAY], width=0.6, zorder=2)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    for x_, v_ in enumerate(vals):
        ax.text(x_, v_, f"{v_:+.1f}%", ha="center", va="bottom" if v_ >= 0 else "top", fontsize=9, color=C.INK_2)
    ax.set_xticks(range(4), labels, fontsize=9)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Visits YoY (%)")
    ax.set_title("Visit growth: Starbucks vs Dunkin'")
    C._finish(fig, ax, OUT / "competitor_growth.png",
              "Jun 29 – Sep 21 2026 vs the same weeks of 2025 · same-store = median per location; all locations = total visits",
              note="Panel-size changes affect both brands equally, so compare the bars with each other, not with zero.")
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.bar(range(len(band)), band["median_share_change_pp"], color=C.BLUE, width=0.6, zorder=2)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_xticks(range(len(band)), [f"{b} per 100\n({n} metros)" for b, n in zip(band["closure_band"], band["metros"])], fontsize=8.5)
    for x_, v_ in enumerate(band["median_share_change_pp"]):
        ax.text(x_, v_, f"{v_:+.2f} pp", ha="center", va="bottom" if v_ >= 0 else "top", fontsize=9, color=C.INK_2)
    ax.grid(axis="x", visible=False)
    ax.set_xlabel("Starbucks closures Jul 2025 – Aug 2026 per 100 Starbucks locations in the metro")
    ax.set_ylabel("Share change (pp)")
    ax.set_title("Did Dunkin' gain where Starbucks closed stores?")
    C._finish(fig, ax, OUT / "competitor_share_by_closures.png",
              "Median change in Starbucks' share of Starbucks + Dunkin' visits, Jun–Sep 2026 vs 2025, metros with ≥ 20 Starbucks",
              note="Metro-level, descriptive.")


if __name__ == "__main__":
    main()
