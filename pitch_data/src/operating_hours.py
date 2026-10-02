"""Workstream 4: operating hours as a labor/resource proxy, across store-locator snapshots.

    python src/operating_hours.py

Snapshots (All the Places `starbucks_us`, i.e. Starbucks' own store locator; CC0):
  2024-07-06 (partial), 2025-08-16 (pre-closure), 2026-01-17, 2026-04-18, plus 2026-09-26 (store universe).
Stores are linked across snapshots by the locator ID (`ref`), company-operated only.

Tests:
  1. Are hours changing over time (weekly hours, opening/closing times, weekend hours)?
  2. Do stores with strong traffic growth extend hours?           (hours change Aug-25 -> Sep-26 vs Advan YoY growth)
  3. Did stores that closed in Oct 2025 have reduced hours beforehand? (Aug-25 hours, closed vs survivors)
  4. Do stores with hiring pressure have shorter / reduced hours?  (HPI from 02_hiring_pressure)
  5. Visits per operating hour over time: Advan weekly visits (13 weeks around each snapshot) / weekly hours.
Outputs: 04_operating_hours/ (store_hours_panel.csv, results.json, charts)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from lab import LAB, UNIV, load_advan, parse_hours, save_json, weekly_hours

OUT = LAB / "04_operating_hours"
SNAPS = {"2024-07": "starbucks_us_2024-07-06-13-31-59.geojson", "2025-08": "starbucks_us_2025-08-16-13-32-10.geojson",
         "2026-01": "starbucks_us_2026-01-17-13-32-44.geojson", "2026-04": "starbucks_us_2026-04-18-13-32-31.geojson"}


def read_snapshot(path: Path) -> pd.DataFrame:
    # One feature per line; parse line by line so a truncated download (missing the closing "]}") still loads
    fs = []
    for line in path.read_text().splitlines():
        line = line.strip().rstrip(",")
        if line.startswith('{"type": "Feature"'):
            try:
                fs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    rows = []
    for f in fs:
        p, g = f["properties"], f.get("geometry") or {}
        lon, lat = (g.get("coordinates") or [None, None])[:2]
        rows.append({"locator_id": str(p.get("ref")), "ownership_type": p.get("ownership_type"),
                     "opening_hours": p.get("opening_hours"), "latitude": lat, "longitude": lon, "state": p.get("addr:state")})
    return pd.DataFrame(rows).drop_duplicates("locator_id")


def features(oh) -> dict:
    h = parse_hours(oh)
    if not h:
        return {"weekly_hours": None, "weekday_open": None, "weekday_close": None, "weekend_hours": None}
    we = [c - o for d, (o, c) in h.items() if d in ("Sa", "Su")]
    return {"weekly_hours": round(sum(c - o for o, c in h.values()), 2), "weekday_open": h.get("We", (None, None))[0],
            "weekday_close": h.get("We", (None, None))[1], "weekend_hours": round(sum(we), 2) if we else None}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = LAB / "data/raw/alltheplaces"
    snaps = {k: read_snapshot(raw / v) for k, v in SNAPS.items() if (raw / v).exists()}
    cur = pd.read_csv(UNIV / "data/processed/starbucks_store_universe.csv", dtype={"locator_id": str})
    snaps["2026-09"] = cur[["locator_id", "ownership_type", "opening_hours", "latitude", "longitude", "state"]]
    wide = None
    counts = {}
    for k, s in snaps.items():
        s = s[s["ownership_type"] == "CO"].copy()
        f = s["opening_hours"].apply(features).apply(pd.Series)
        s = pd.concat([s[["locator_id", "latitude", "longitude", "state"]], f], axis=1)
        counts[k] = {"co_locations": len(s), "with_hours": int(s["weekly_hours"].notna().sum()),
                     "median_weekly_hours": float(s["weekly_hours"].median()),
                     "mean_weekly_hours": round(float(s["weekly_hours"].mean()), 2),
                     "pct_open_by_5am": round(100 * float((s["weekday_open"] <= 5).mean()), 1),
                     "median_weekday_close": float(s["weekday_close"].median())}
        s = s.rename(columns={c: f"{c}_{k}" for c in s.columns if c != "locator_id"})
        wide = s if wide is None else wide.merge(s, on="locator_id", how="outer")
    res = {"snapshots": counts}

    # Link to the store panel (Advan traffic, HPI, closure status) via locator_id
    panel = pd.read_csv(LAB / "01_store_panel/store_panel.csv", dtype={"store_id": str, "locator_id": str})
    hpi = pd.read_csv(LAB / "02_hiring_pressure/store_hpi.csv", dtype={"store_id": str})[["store_id", "HPI_full", "HPI_persistence"]]
    w = wide.copy()
    # Closed stores are missing from the 2026 locator: match Advan locations to the Aug-2025 snapshot by coordinates
    from lab import nearest_match
    aug = snaps["2025-08"][snaps["2025-08"]["ownership_type"] == "CO"].reset_index(drop=True)
    idx = nearest_match(panel["lat"].values, panel["lon"].values, aug, 75)
    panel["locator_id_aug25"] = [aug.at[i, "locator_id"] if i >= 0 else None for i in idx]
    pl = panel[panel["locator_id_aug25"].notna()][["store_id", "locator_id_aug25", "status", "close_date", "msa",
                                                      "visits_yoy_pct", "visits_per_week_13w", "traffic_pctile_in_metro"]]
    w = w.merge(pl, left_on="locator_id", right_on="locator_id_aug25", how="left").merge(hpi, on="store_id", how="left")
    w["hours_change_aug25_sep26"] = w["weekly_hours_2026-09"] - w["weekly_hours_2025-08"]
    w.to_csv(OUT / "store_hours_panel.csv", index=False)

    both = w.dropna(subset=["weekly_hours_2025-08", "weekly_hours_2026-09"])
    ch = both["hours_change_aug25_sep26"]
    res["hours_change_aug25_to_sep26_same_store"] = {
        "stores": len(both), "mean_change_h": round(float(ch.mean()), 2), "median_change_h": float(ch.median()),
        "pct_increased": round(100 * float((ch > 0.25).mean()), 1), "pct_decreased": round(100 * float((ch < -0.25).mean()), 1),
        "pct_unchanged": round(100 * float((ch.abs() <= 0.25).mean()), 1),
        "open_time_change_median_h": float((both["weekday_open_2026-09"] - both["weekday_open_2025-08"]).median()),
        "close_time_change_median_h": float((both["weekday_close_2026-09"] - both["weekday_close_2025-08"]).median())}

    # 2. growth vs hours change (surviving, company-operated, with traffic)
    g = both.dropna(subset=["visits_yoy_pct"]).copy()
    g = g[g["visits_yoy_pct"].between(*g["visits_yoy_pct"].quantile([0.01, 0.99]))]
    g["cohort"] = pd.cut(g["visits_yoy_pct"], [-1e9, 0, 5, 10, 1e9], labels=["< 0%", "0–5%", "5–10%", "> 10%"])
    gc = g.groupby("cohort", observed=True).agg(stores=("locator_id", "size"), mean_hours_change=("hours_change_aug25_sep26", "mean"),
                                                pct_extended=("hours_change_aug25_sep26", lambda x: round(100 * (x > 0.25).mean(), 1)),
                                                pct_reduced=("hours_change_aug25_sep26", lambda x: round(100 * (x < -0.25).mean(), 1))).round(3).reset_index()
    res["traffic_growth_vs_hours_change"] = gc.to_dict(orient="records")
    res["spearman_growth_vs_hours_change"] = round(float(g["visits_yoy_pct"].rank().corr(g["hours_change_aug25_sep26"].rank())), 3)

    # 3. closed in Oct 2025 vs survivors: Aug-2025 hours
    a = w.dropna(subset=["weekly_hours_2025-08"]).copy()
    a["closed_oct25"] = pd.to_datetime(a["close_date"]).between("2025-09-01", "2025-11-30")
    a["survivor"] = a["status"].eq("open")
    cl = a[a["closed_oct25"]]
    sv = a[a["survivor"]]
    res["pre_closure_hours"] = {"closed_n": len(cl), "closed_median_weekly_hours_aug25": float(cl["weekly_hours_2025-08"].median()),
                                "survivor_median_weekly_hours_aug25": float(sv["weekly_hours_2025-08"].median()),
                                "closed_mean": round(float(cl["weekly_hours_2025-08"].mean()), 2),
                                "survivor_mean": round(float(sv["weekly_hours_2025-08"].mean()), 2),
                                "closed_pct_below_100h": round(100 * float((cl["weekly_hours_2025-08"] < 100).mean()), 1),
                                "survivor_pct_below_100h": round(100 * float((sv["weekly_hours_2025-08"] < 100).mean()), 1)}
    # Did closures cut hours before closing? (Jul-2024 partial snapshot -> Aug-2025)
    pre = a.dropna(subset=["weekly_hours_2024-07"])
    pre_ch = pre["weekly_hours_2025-08"] - pre["weekly_hours_2024-07"]
    res["hours_change_jul24_aug25"] = {"closed_n": int(pre["closed_oct25"].sum()), "survivor_n": int(pre["survivor"].sum()),
                                       "closed_mean_change": round(float(pre_ch[pre["closed_oct25"]].mean()), 2) if pre["closed_oct25"].any() else None,
                                       "survivor_mean_change": round(float(pre_ch[pre["survivor"]].mean()), 2) if pre["survivor"].any() else None,
                                       "note": "Jul-2024 snapshot is partial (small spider output); indicative only."}

    # 4. HPI vs hours
    h = w.dropna(subset=["HPI_full", "weekly_hours_2026-09"])
    res["hpi_vs_hours"] = {"spearman_HPI_full_vs_weekly_hours": round(float(h["HPI_full"].rank().corr(h["weekly_hours_2026-09"].rank())), 3),
                           "spearman_HPI_full_vs_hours_change": round(float(h["HPI_full"].rank().corr(h["hours_change_aug25_sep26"].rank())), 3),
                           "mean_hours_by_HPI_full": h.groupby("HPI_full")["weekly_hours_2026-09"].mean().round(2).to_dict()}

    # 5. visits per operating hour over time (13 weeks around each snapshot), same company-operated survivors
    sb = load_advan("Starbucks")[["ID_STORE", "week", "visits"]]
    windows = {"2025-08": "2025-08-16", "2026-01": "2026-01-17", "2026-04": "2026-04-18", "2026-09": "2026-09-21"}
    surv = w[w["status"].eq("open")].dropna(subset=[f"weekly_hours_{k}" for k in windows])
    vph = {}
    for k, center in windows.items():
        c = pd.Timestamp(center)
        wk = pd.date_range(c - pd.Timedelta(weeks=6), c + pd.Timedelta(weeks=6), freq="7D")
        wk = wk[wk <= sb["week"].max()]
        v = sb[sb["week"].isin(sb["week"].unique()[(sb["week"].unique() >= wk.min()) & (sb["week"].unique() <= wk.max())])]
        mv = v.groupby("ID_STORE")["visits"].mean()
        x = surv.join(mv.rename("v"), on="store_id").dropna(subset=["v"])
        vph[k] = {"stores": len(x), "median_visits_per_week": float(x["v"].median()),
                  "median_weekly_hours": float(x[f"weekly_hours_{k}"].median()),
                  "median_visits_per_operating_hour": round(float((x["v"] / x[f"weekly_hours_{k}"]).median()), 2)}
    res["visits_per_operating_hour_over_time"] = vph
    save_json(res, OUT / "results.json")
    print(json.dumps(res, indent=1, default=str))
    chart(gc, cl, sv, vph)


def chart(gc: pd.DataFrame, cl: pd.DataFrame, sv: pd.DataFrame, vph: dict) -> None:
    import sys
    sys.path.insert(0, str(LAB.parent / "_research_archive/starbucks_hiring/src"))
    import charts as C
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.9))
    ax = axes[0]
    ax.bar(range(len(gc)), gc["mean_hours_change"], color=C.BLUE, width=0.6, zorder=2)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_xticks(range(len(gc)), [f"{c}\n(n={n:,})" for c, n in zip(gc["cohort"], gc["stores"])], fontsize=8)
    for x_, y_ in enumerate(gc["mean_hours_change"]):
        ax.text(x_, y_, f"{y_:+.1f} h", ha="center", va="bottom" if y_ >= 0 else "top", fontsize=8, color=C.INK_2)
    ax.set_title("Change in weekly hours, Aug 2025 to Sep 2026\nby store traffic growth (YoY)", fontsize=10)
    ax.set_ylabel("mean change, hours / week")
    ax.grid(axis="x", visible=False)
    ax = axes[1]
    bins = np.arange(60, 141, 4)
    ax.hist(sv["weekly_hours_2025-08"].clip(60, 140), bins=bins, density=True, color=C.GRAY, label=f"Survivors (n={len(sv):,})", zorder=2)
    ax.hist(cl["weekly_hours_2025-08"].clip(60, 140), bins=bins, density=True, histtype="step", linewidth=2, color=C.BLUE,
            label=f"Closed Oct 2025 (n={len(cl):,})", zorder=3)
    ax.set_title("Weekly hours in Aug 2025 (pre-closure)\nmedian 101.5 h closed vs 112 h survivors", fontsize=10)
    ax.set_xlabel("weekly operating hours")
    ax.set_yticks([])
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax = axes[2]
    ks = list(vph)
    vals = [vph[k]["median_visits_per_operating_hour"] for k in ks]
    ax.plot(range(len(ks)), vals, color=C.BLUE, linewidth=2, marker="o", markersize=7, zorder=3)
    for x_, y_ in enumerate(vals):
        ax.text(x_ + 0.12, y_ + 0.3, f"{y_:.1f}", ha="center", fontsize=8, color=C.INK_2)
    ax.set_xticks(range(len(ks)), ["Aug 25", "Jan 26", "Apr 26", "Sep 26"], fontsize=8)
    ax.set_ylim(min(vals) - 2, max(vals) + 2)
    ax.set_title("Median Advan visits per operating hour\n(same ~8,400 surviving stores; seasonal)", fontsize=10)
    fig.suptitle("Operating hours: barely moved; growing stores added ~2 h/week, closed stores had ~10 h/week shorter hours",
                 x=0.01, y=0.99, ha="left", fontsize=12, fontweight="semibold")
    fig.text(0.01, 0.01, "Company-operated stores · hours from the Starbucks store locator (All the Places snapshots) · visits: Advan (panel sample, relative only)",
             fontsize=8, color=C.INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    fig.savefig(LAB / "charts/04_operating_hours.png", dpi=200)


if __name__ == "__main__":
    main()
