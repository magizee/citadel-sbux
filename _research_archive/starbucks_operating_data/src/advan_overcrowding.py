"""Overcrowding / closure-transfer analysis (Advan via Dewey).

    python src/advan_overcrowding.py

Run after advan_analysis.py. Tests the "overbuilt network" angle:
  1. Cannibalization: visits per store vs. nearby store density (levels, within metro).
  2. Pruning: share of locations closed since Oct 2025 by density quintile.
  3. Transfer: same-store visit growth by distance to the nearest closure (Jul 2025 - Aug 2026).
  4. Does the "faster growth near manager vacancies" survive once closure transfer is removed?

Inputs : outputs/advan/store_visits_yoy.csv, data/processed/advan_starbucks.csv.gz
Outputs: outputs/advan/overcrowding_results.json, density_quintiles.csv, yoy_by_closure_distance.csv,
         overcrowding_visits_by_density.png, overcrowding_closures_by_density.png, yoy_by_closure_distance.png
Descriptive. Advan includes licensed locations; GPS-panel visits may undercount dense urban stores.
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

KM = 15
CLOSURE_WINDOW = ("2025-07-01", "2026-09-01")   # closures that fall between the YoY comparison windows


def haversine_matrix_min(lat, lon, plat, plon, chunk=2000):
    """Min distance (km) from each (lat, lon) to the point set; also count within KM."""
    pa, po = np.radians(plat)[None, :], np.radians(plon)[None, :]
    mins, counts = [], []
    for i in range(0, len(lat), chunk):
        la, lo = np.radians(lat[i:i + chunk])[:, None], np.radians(lon[i:i + chunk])[:, None]
        h = np.sin((pa - la) / 2) ** 2 + np.cos(la) * np.cos(pa) * np.sin((po - lo) / 2) ** 2
        d = 2 * 6371 * np.arcsin(np.sqrt(h))
        mins.append(d.min(axis=1))
        counts.append((d <= KM).sum(axis=1))
    return np.concatenate(mins), np.concatenate(counts)


def main() -> None:
    st = pd.read_csv(OUT / "store_visits_yoy.csv", dtype={"locator_id": str, "placekey": str})
    adv = pd.read_csv(ROOT / "data/processed/advan_starbucks.csv.gz",
                      usecols=["placekey", "close_date", "latitude", "longitude", "date_range_start", "msa_code"], dtype=str)
    last = adv.sort_values("date_range_start").drop_duplicates("placekey", keep="last").copy()
    last[["latitude", "longitude"]] = last[["latitude", "longitude"]].astype(float)
    cd = pd.to_datetime(last["close_date"].str[:10], errors="coerce")
    last["closed_since_oct25"] = (cd >= "2025-10-01") & (cd < "2030-01-01")
    closed = last[(cd >= CLOSURE_WINDOW[0]) & (cd < CLOSURE_WINDOW[1])]

    # Density among all Starbucks-branded locations (Advan) and distance to nearest closure
    _, dens_all = haversine_matrix_min(last["latitude"].to_numpy(), last["longitude"].to_numpy(),
                                       last["latitude"].to_numpy(), last["longitude"].to_numpy())
    last["density"] = dens_all - 1
    s = st.merge(last[["placekey", "density", "msa_code"]], on="placekey")
    lat, lon = s["latitude"].astype(float).to_numpy(), s["longitude"].astype(float).to_numpy()
    s["km_to_nearest_closure"], _ = haversine_matrix_min(lat, lon, closed["latitude"].to_numpy(), closed["longitude"].to_numpy())
    s["near_closure_2km"] = s["km_to_nearest_closure"] <= 2
    res = {"stores": len(s), "closures_in_window": len(closed), "closure_window": CLOSURE_WINDOW}

    # 1-2. Density quintiles: visits per store, growth, closure rate
    labels = ["Q1 least dense", "Q2", "Q3", "Q4", "Q5 most dense"]
    s["dens_q"] = pd.qcut(s["density"], 5, labels=labels)
    last["dens_q"] = pd.qcut(last["density"], 5, labels=labels)
    q = s.groupby("dens_q", observed=True).agg(stores=("placekey", "size"), median_nearby_locations=("density", "median"),
                                               weekly_visits_per_store=("v_cur", "median"),
                                               visits_yoy_pct=("visits_yoy_pct", "median"))
    q["pct_locations_closed_since_oct25"] = last.groupby("dens_q", observed=True)["closed_since_oct25"].mean().mul(100).round(2)
    q = q.round(2).reset_index()
    q.to_csv(OUT / "density_quintiles.csv", index=False)
    res["density_quintiles"] = q.to_dict(orient="records")

    m = s[s["msa_code"].notna()].copy()
    m["lv_vs_msa"] = np.log(m["v_cur"]) - np.log(m["v_cur"]).groupby(m["msa_code"]).transform("median")
    m["ld_vs_msa"] = np.log1p(m["density"]) - np.log1p(m["density"]).groupby(m["msa_code"]).transform("median")
    res["within_msa_elasticity_visits_per_store_to_density"] = round(float(np.polyfit(m["ld_vs_msa"], m["lv_vs_msa"], 1)[0]), 3)

    # 3. Growth by distance to the nearest closure
    m["yoy_vs_msa"] = m["visits_yoy_pct"] - m.groupby("msa_code")["visits_yoy_pct"].transform("median")
    bins = [0, 1, 2, 5, 10, 1e9]
    names = ["< 1 km", "1–2 km", "2–5 km", "5–10 km", "> 10 km"]
    m["closure_dist"] = pd.cut(m["km_to_nearest_closure"], bins, labels=names, right=False)
    dd = m.groupby("closure_dist", observed=True).agg(stores=("placekey", "size"),
                                                      visits_yoy_pct=("visits_yoy_pct", "median"),
                                                      yoy_vs_metro_pp=("yoy_vs_msa", "median")).round(2).reset_index()
    dd.to_csv(OUT / "yoy_by_closure_distance.csv", index=False)
    res["yoy_by_closure_distance"] = dd.to_dict(orient="records")
    near = s["near_closure_2km"]
    res["transfer"] = {"stores_within_2km_of_closure": int(near.sum()), "share_of_stores_pct": round(100 * near.mean(), 1),
                       "median_yoy_near": round(float(s.loc[near, "visits_yoy_pct"].median()), 2),
                       "median_yoy_not_near": round(float(s.loc[~near, "visits_yoy_pct"].median()), 2),
                       "mean_yoy_all": round(float(s["visits_yoy_pct"].mean()), 2),
                       "mean_yoy_excluding_near": round(float(s.loc[~near, "visits_yoy_pct"].mean()), 2)}

    # 4. Leadership-vacancy effect with closure transfer removed (within metro)
    keep = m[~m["near_closure_2km"]]
    res["leadership_effect_within_msa_excluding_closure_adjacent"] = {
        z: keep.groupby(z)["yoy_vs_msa"].median().round(2).to_dict() for z in ("leadership_zone", "persistent_leadership_zone")}
    (OUT / "overcrowding_results.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))

    # Charts
    import matplotlib.pyplot as plt
    q["label"] = q["dens_q"].astype(str) + "\n(" + q["median_nearby_locations"].astype(int).astype(str) + " nearby)"
    for col, title, fname, fmt, sub in [
        ("weekly_visits_per_store", "Weekly visits per store by local Starbucks density", "overcrowding_visits_by_density.png",
         "{:,.0f}", f"Median weekly visits (Advan), Jun–Sep 2026 · density = Starbucks locations within {KM} km"),
        ("pct_locations_closed_since_oct25", "Share of locations closed since Oct 2025, by density", "overcrowding_closures_by_density.png",
         "{:.1f}%", f"U.S. Starbucks-branded locations (incl. licensed) · density = locations within {KM} km")]:
        fig, ax = plt.subplots(figsize=(8, 3.8))
        ax.bar(range(len(q)), q[col], color=C.BLUE, width=0.62, zorder=2)
        ax.set_xticks(range(len(q)), q["label"], fontsize=8.5)
        ax.grid(axis="x", visible=False)
        for x_, v_ in enumerate(q[col]):
            ax.text(x_, v_, fmt.format(v_), ha="center", va="bottom", fontsize=9, color=C.INK_2)
        ax.set_title(title)
        C._finish(fig, ax, OUT / fname, sub,
                  note="Dense urban visit counts may be understated by GPS panels." if "visits" in col else
                  "Closures verified: 92% of closed locations are absent from Starbucks' store locator.")
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.bar(range(len(dd)), dd["yoy_vs_metro_pp"], color=[C.BLUE if v > 0.3 else C.BLUE_LIGHT for v in dd["yoy_vs_metro_pp"]],
           width=0.62, zorder=2)
    ax.axhline(0, color=C.INK_2, linewidth=1)
    ax.set_xticks(range(len(dd)), [f"{n}\n(n={k:,})" for n, k in zip(dd["closure_dist"], dd["stores"])], fontsize=8.5)
    ax.grid(axis="x", visible=False)
    for x_, v_ in enumerate(dd["yoy_vs_metro_pp"]):
        ax.text(x_, v_, f"{v_:+.1f} pp", ha="center", va="bottom" if v_ >= 0 else "top", fontsize=9, color=C.INK_2)
    ax.set_ylabel("Visits YoY vs metro median (pp)")
    ax.set_xlabel("Distance to the nearest Starbucks closed Jul 2025 – Aug 2026")
    ax.set_title("Stores next to a closure absorb its traffic")
    C._finish(fig, ax, OUT / "yoy_by_closure_distance.png",
              f"Same-store visits, Jun–Sep 2026 vs 2025 · {res['closures_in_window']} closures in window",
              note="Transfer from closed stores flatters same-store growth at nearby survivors.")


if __name__ == "__main__":
    main()
