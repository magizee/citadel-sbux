"""Did Dunkin' foot traffic rise near Starbucks closures?

    python src/advan_dunkin_near_closures.py

1. Cross-section: Dunkin' same-store visit growth (Jun 29 - Sep 21 2026 vs the same weeks of 2025) by distance
   to the nearest Starbucks location closed Jul 2025 - Aug 2026; raw and relative to the metro's Dunkin' median.
2. Event study around the Oct-2025 Starbucks closure wave (week of 2025-10-13): Dunkin' stores within 1 km /
   1-2 km of a closed Starbucks (and > 2 km from other Starbucks closures) vs Dunkin' stores > 5 km from any
   Starbucks closure in the same metro. 26 weeks before to 48 weeks after.
3. Diversion: extra weekly Dunkin' visits near closures (vs control-growth counterfactual) / closed Starbucks
   stores' pre-closure weekly visits.
Same Advan panel for both brands. Outputs: outputs/advan/dunkin_near_closures_*.csv/.json/.png
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
sys.path.insert(0, str(ROOT / "src"))
import charts as C  # noqa: E402
from advan_cannibalization import EVENT_WEEK, POST, PRE, load_panel, min_dist  # noqa: E402

WIN26 = ("2026-06-29", "2026-09-21")


def load_dunkin() -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = ["ID_STORE", "BRAND", "ISO_COUNTRY_CODE", "VISIT_COUNTS", "MSA_CODE", "DATE_RANGE_START", "LATITUDE", "LONGITUDE"]
    frames = []
    for f in sorted((ROOT / "data/raw/advan_competitors").glob("*.parquet")):
        d = pd.read_parquet(f, columns=cols)
        frames.append(d[(d["ISO_COUNTRY_CODE"] == "US") & d["BRAND"].fillna("").str.contains("Dunkin", case=False)])
    d = pd.concat(frames, ignore_index=True)
    d["week"] = pd.to_datetime(d["DATE_RANGE_START"].astype(str).str[:10])
    d["visits"] = pd.to_numeric(d["VISIT_COUNTS"], errors="coerce")
    loc = d.sort_values("week").groupby("ID_STORE").agg(lat=("LATITUDE", "last"), lon=("LONGITUDE", "last"),
                                                        msa=("MSA_CODE", "last")).reset_index()
    loc[["lat", "lon"]] = loc[["lat", "lon"]].astype(float)
    return d[["ID_STORE", "week", "visits"]].rename(columns={"ID_STORE": "store"}), loc.rename(columns={"ID_STORE": "store"})


def main() -> None:
    dk, dloc = load_dunkin()
    _, sloc = load_panel()                                     # Starbucks locations with close dates
    closed_any = sloc[(sloc["close"] >= "2025-07-01") & (sloc["close"] < "2026-09-01")]
    wave = sloc[(sloc["close"] >= "2025-10-01") & (sloc["close"] < "2025-11-01")]
    other = sloc[(sloc["close"] >= "2025-04-01") & (sloc["close"] < "2026-10-01") & ~sloc.index.isin(wave.index)]
    dloc["km_any"] = min_dist(dloc["lat"].values, dloc["lon"].values, closed_any["lat"].values, closed_any["lon"].values)
    dloc["km_wave"] = min_dist(dloc["lat"].values, dloc["lon"].values, wave["lat"].values, wave["lon"].values)
    dloc["km_other"] = min_dist(dloc["lat"].values, dloc["lon"].values, other["lat"].values, other["lon"].values)
    res = {"dunkin_stores": len(dloc), "starbucks_closures_jul25_aug26": len(closed_any), "oct25_wave": len(wave)}

    # 1. Cross-section
    cur = pd.date_range(*WIN26, freq="7D")
    prev = cur - pd.Timedelta(weeks=52)
    a = dk[dk["week"].isin(cur)].groupby("store")["visits"].agg(["mean", "size"])
    b = dk[dk["week"].isin(prev)].groupby("store")["visits"].agg(["mean", "size"])
    y = a.join(b, lsuffix="_c", rsuffix="_p", how="inner")
    y = y[(y["size_c"] >= 11) & (y["size_p"] >= 11) & (y["mean_p"] > 0)]
    y["yoy"] = 100 * (y["mean_c"] / y["mean_p"] - 1)
    y = y[y["yoy"].between(*y["yoy"].quantile([0.01, 0.99]))].join(dloc.set_index("store"))
    y = y[y["msa"].notna()]
    y["yoy_vs_metro"] = y["yoy"] - y.groupby("msa")["yoy"].transform("median")
    y["band"] = pd.cut(y["km_any"], [0, 1, 2, 5, 10, 1e9], labels=["< 1 km", "1–2 km", "2–5 km", "5–10 km", "> 10 km"], right=False)
    xs = y.groupby("band", observed=True).agg(dunkin_stores=("yoy", "size"), raw_visits_yoy_pct=("yoy", "median"),
                                              yoy_vs_metro_pp=("yoy_vs_metro", "median")).round(2).reset_index()
    xs.to_csv(OUT / "dunkin_near_closures_cross_section.csv", index=False)
    res["cross_section"] = xs.to_dict(orient="records")
    rng = np.random.default_rng(0)
    near, far = y[y["km_any"] < 1]["yoy_vs_metro"].to_numpy(), y[y["km_any"] >= 5]["yoy_vs_metro"].to_numpy()
    boot = [np.median(rng.choice(near, len(near))) - np.median(rng.choice(far, len(far))) for _ in range(2000)]
    res["cross_section_near_minus_far_pp"] = {"estimate": round(float(np.median(near) - np.median(far)), 2),
                                              "ci95": [round(float(np.percentile(boot, 2.5)), 2), round(float(np.percentile(boot, 97.5)), 2)]}

    # 2. Event study around the Oct-2025 wave
    dloc["group"] = np.select(
        [(dloc["km_wave"] <= 1) & (dloc["km_other"] > 2), (dloc["km_wave"] > 1) & (dloc["km_wave"] <= 2) & (dloc["km_other"] > 2),
         np.minimum(dloc["km_wave"], dloc["km_other"]) > 5], ["< 1 km", "1–2 km", "control"], "excluded")
    tm = set(dloc.loc[dloc["group"].isin(["< 1 km", "1–2 km"]), "msa"].dropna())
    dloc.loc[(dloc["group"] == "control") & ~dloc["msa"].isin(tm), "group"] = "excluded"
    weeks = pd.date_range(EVENT_WEEK - pd.Timedelta(weeks=PRE), EVENT_WEEK + pd.Timedelta(weeks=POST), freq="7D")
    p = dk[dk["week"].isin(weeks) & (dk["visits"] > 0)].merge(dloc[["store", "group", "msa"]], on="store")
    p = p[p["group"] != "excluded"]
    nw = p.groupby("store")["week"].nunique()
    p = p[p["store"].isin(nw[nw >= len(weeks) - 3].index)]
    p["et"] = ((p["week"] - EVENT_WEEK).dt.days // 7).astype(int)
    p["y"] = np.log(p["visits"])
    p["y_rel"] = p["y"] - p["store"].map(p[p["et"] < 0].groupby("store")["y"].mean())
    p = p.join(p[p["group"] == "control"].groupby(["msa", "week"])["y_rel"].mean().rename("ctrl"), on=["msa", "week"])
    p["gap"] = p["y_rel"] - p["ctrl"]
    rows = []
    res["event_study"] = {}
    for g in ("< 1 km", "1–2 km"):
        gg = p[(p["group"] == g)].dropna(subset=["gap"])
        piv = gg.pivot_table(index="store", columns="et", values="gap")
        stores = piv.index.to_numpy()
        for et in piv.columns:
            rows.append({"group": g, "event_week": int(et), "gap_pct": 100 * (np.exp(piv[et].mean()) - 1), "stores": len(stores)})
        did = piv[[c for c in piv.columns if 4 <= c <= POST]].mean(axis=1) - piv[[c for c in piv.columns if c < 0]].mean(axis=1)
        bd = [did.loc[rng.choice(stores, len(stores))].mean() for _ in range(1000)]
        res["event_study"][g] = {"dunkin_stores": len(stores), "did_pct": round(100 * (np.exp(did.mean()) - 1), 2),
                                 "ci95_pct": [round(100 * (np.exp(np.percentile(bd, 2.5)) - 1), 2),
                                              round(100 * (np.exp(np.percentile(bd, 97.5)) - 1), 2)]}
    es = pd.DataFrame(rows)
    es.to_csv(OUT / "dunkin_near_closures_event_study.csv", index=False)
    res["event_study_controls"] = int(p.loc[p["group"] == "control", "store"].nunique())

    # 3. Diversion to Dunkin' within 2 km
    pre_lvl = p[p["et"] < 0].groupby("store")["visits"].mean()
    p["extra"] = p["visits"] - p["store"].map(pre_lvl) * np.exp(p["ctrl"])
    extra = p[(p["et"] >= 4) & p["group"].isin(["< 1 km", "1–2 km"])].groupby("store")["extra"].mean().sum()
    sbp, _ = load_panel()
    closed_pre = sbp[sbp["placekey"].isin(wave["placekey"]) & (sbp["week"] >= EVENT_WEEK - pd.Timedelta(weeks=PRE))
                     & (sbp["week"] < EVENT_WEEK - pd.Timedelta(weeks=4))].groupby("placekey")["visits"].mean().sum()
    res["diversion_to_dunkin_within_2km_pct"] = round(100 * float(extra) / float(closed_pre), 1)
    res["note"] = "Lower bound (excludes Dunkin' near other Starbucks closures). Compare: Starbucks neighbours recaptured ~4% within 2 km."
    (OUT / "dunkin_near_closures_results.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))

    # Charts
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.bar(range(len(xs)), xs["yoy_vs_metro_pp"], color=[C.BLUE if v > 0.3 else C.BLUE_LIGHT for v in xs["yoy_vs_metro_pp"]], width=0.6, zorder=2)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_xticks(range(len(xs)), [f"{b}\n(n={n:,})" for b, n in zip(xs["band"], xs["dunkin_stores"])], fontsize=8.5)
    for x_, v_ in enumerate(xs["yoy_vs_metro_pp"]):
        ax.text(x_, v_, f"{v_:+.1f} pp", ha="center", va="bottom" if v_ >= 0 else "top", fontsize=9, color=C.INK_2)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Dunkin' visits YoY vs metro (pp)")
    ax.set_xlabel("Distance from the Dunkin' to the nearest Starbucks closed Jul 2025 – Aug 2026")
    ax.set_title("Dunkin' traffic growth by distance to a Starbucks closure")
    C._finish(fig, ax, OUT / "dunkin_near_closures_cross_section.png",
              "Dunkin' same-store visits, Jun 29 – Sep 21 2026 vs same weeks 2025, relative to Dunkin' in the same metro",
              note="Advan via Dewey. Same panel as the Starbucks data.")
    fig, ax = plt.subplots(figsize=(9, 3.8))
    for g, col in (("< 1 km", C.BLUE), ("1–2 km", "#eb6834")):
        gg = es[es["group"] == g].sort_values("event_week")
        r = res["event_study"][g]
        ax.plot(gg["event_week"], gg["gap_pct"], color=col, linewidth=2,
                label=f"Dunkin' {g} from a closure: {r['did_pct']:+.1f}% (95% CI {r['ci95_pct'][0]:+.1f} to {r['ci95_pct'][1]:+.1f}; n={r['dunkin_stores']})")
    ax.axvline(0, color=C.INK_2, linewidth=1)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_xlabel("Weeks relative to the October 2025 Starbucks closure wave")
    ax.set_ylabel("Dunkin' visits vs controls (%)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Dunkin' visits after nearby Starbucks closed")
    C._finish(fig, ax, OUT / "dunkin_near_closures_event_study.png",
              f"Dunkin' near Oct-2025 Starbucks closures vs Dunkin' > 5 km from any closure, same metros (n={res['event_study_controls']:,} controls)",
              note=f"Diversion: Dunkin' within 2 km gained ≈ {res['diversion_to_dunkin_within_2km_pct']}% of the closed Starbucks' visits (lower bound).")


if __name__ == "__main__":
    main()
