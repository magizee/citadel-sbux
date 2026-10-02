"""Workstream 9: peak load. Did the traffic recovery land in peak hours (needs more staff per shift) or
off-peak hours (absorbed by staff already on the floor)?

    python src/peak_load.py

Source: Advan Weekly Patterns VISITS_BY_EACH_HOUR (168 values, hour-of-week, local time, Monday 00:00 first).
Per store-week the field is sparse (steps of one scaled device), so everything is pooled: store x 13-week window sums,
or national sums across stores.
Sample: open company-operated Starbucks (store panel) and Dunkin' (comparison), same stores in both windows.
Windows: latest 13 weeks (to the last Advan week) vs the same 13 weeks a year earlier; national profiles by fiscal quarter.

Day-parts (local hour of day): early 4-7, morning peak 7-10, midday 10-14, afternoon 14-17, evening 17-22, overnight 22-4.
Outputs: 08_peak_load/ (daypart_growth.csv, profiles_by_fq.csv, store_peak.csv, results.json), charts/08_peak_load.png
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from hiring_pressure import ols_fe
from lab import LAB, OPS, save_json

OUT = LAB / "08_peak_load"
DAYPARTS = {"early 4–7": range(4, 7), "morning peak 7–10": range(7, 10), "midday 10–14": range(10, 14),
            "afternoon 14–17": range(14, 17), "evening 17–22": range(17, 22), "overnight 22–4": list(range(22, 24)) + list(range(0, 4))}
COLS = ["ID_STORE", "BRAND", "ISO_COUNTRY_CODE", "DATE_RANGE_START", "VISITS_BY_EACH_HOUR"]


def fq(week: pd.Timestamp) -> str:
    y = week.year + (week.month >= 10)
    return f"FY{y % 100} Q{((week.month - 10) % 12) // 3 + 1}"


def load_hours(folder: str, brand: str, keep: set | None) -> tuple[np.ndarray, pd.DataFrame]:
    """Returns (H: n x 168 hourly visits, meta: ID_STORE, week) for one brand."""
    mats, metas = [], []
    for f in sorted((OPS / folder).glob("*.parquet")):
        d = pd.read_parquet(f, columns=COLS)
        d = d[(d["ISO_COUNTRY_CODE"] == "US") & d["BRAND"].fillna("").str.contains(brand, case=False) & d["VISITS_BY_EACH_HOUR"].notna()]
        if keep is not None:
            d = d[d["ID_STORE"].isin(keep)]
        if d.empty:
            continue
        h = np.array([json.loads(s) for s in d["VISITS_BY_EACH_HOUR"]], dtype=float)
        ok = h.shape[1] == 168 if h.ndim == 2 else False
        if not ok:
            continue
        mats.append(h)
        metas.append(pd.DataFrame({"ID_STORE": d["ID_STORE"].values,
                                   "week": pd.to_datetime(d["DATE_RANGE_START"].astype(str).str[:10]).values}))
    return np.vstack(mats), pd.concat(metas, ignore_index=True)


def visit_growth(folder: str, brand: str, stores: list, cur_w, ly_w) -> dict:
    """Pooled and per-store VISIT_COUNTS growth for the same stores and windows."""
    frames = []
    for f in sorted((OPS / folder).glob("*.parquet")):
        d = pd.read_parquet(f, columns=["ID_STORE", "BRAND", "ISO_COUNTRY_CODE", "DATE_RANGE_START", "VISIT_COUNTS"])
        d = d[(d["ISO_COUNTRY_CODE"] == "US") & d["BRAND"].fillna("").str.contains(brand, case=False) & d["ID_STORE"].isin(stores)]
        frames.append(d)
    d = pd.concat(frames)
    d["week"] = pd.to_datetime(d["DATE_RANGE_START"].astype(str).str[:10])
    d["v"] = pd.to_numeric(d["VISIT_COUNTS"], errors="coerce")
    c = d[d["week"].isin(cur_w)].groupby("ID_STORE")["v"].mean()
    l = d[d["week"].isin(ly_w)].groupby("ID_STORE")["v"].mean()
    j = pd.concat([c.rename("c"), l.rename("l")], axis=1).dropna()
    return {"growth": float(j["c"].sum() / j["l"].sum() - 1), "store_growth": 100 * (j["c"] / j["l"] - 1)}


def hod(h: np.ndarray) -> np.ndarray:
    """168 hour-of-week -> 24 hour-of-day (summed over the 7 days)."""
    return h.reshape(-1, 7, 24).sum(axis=1)


def dayparts(h24: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame({k: h24[:, list(v)].sum(axis=1) for k, v in DAYPARTS.items()})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(LAB / "01_store_panel/store_panel.csv", dtype={"store_id": str, "msa": str})
    co = set(panel.loc[panel["company_operated"] & panel["status"].eq("open"), "store_id"])
    res = {}
    store_tables, profiles, dp_rows = {}, [], []
    for name, folder, brand, keep in (("Starbucks", "data/raw/advan", "Starbucks", co),
                                      ("Dunkin'", "data/raw/advan_competitors", "Dunkin", None)):
        H, meta = load_hours(folder, brand, keep)
        H24 = hod(H)
        last = meta["week"].max()
        cur_w = pd.date_range(end=last, periods=13, freq="7D")
        ly_w = cur_w - pd.Timedelta(weeks=52)
        meta["win"] = np.where(meta["week"].isin(cur_w), "cur", np.where(meta["week"].isin(ly_w), "ly", ""))
        meta["fq"] = meta["week"].map(fq)

        # national hour-of-day profile by fiscal quarter (stores present in both windows not required here)
        prof = pd.DataFrame(H24).groupby(meta["fq"].values).sum()
        prof = prof.div(prof.sum(axis=1), axis=0)
        prof["brand"] = name
        profiles.append(prof)

        # same-store windows
        sel = meta["win"] != ""
        g = pd.DataFrame(H24[sel.values]).groupby([meta.loc[sel, "ID_STORE"].values, meta.loc[sel, "win"].values]).sum()
        n = meta[sel].groupby(["ID_STORE", "win"]).size()
        g = g[n.reindex(g.index).values >= 10]  # >= 10 of 13 weeks with hourly data
        cur = g.xs("cur", level=1)
        ly = g.xs("ly", level=1)
        both = cur.index.intersection(ly.index)
        cur, ly = cur.loc[both], ly.loc[both]
        # weekly-average normalisation (weeks observed may differ by one or two)
        nc = n.xs("cur", level=1).loc[both].values[:, None]
        nl = n.xs("ly", level=1).loc[both].values[:, None]
        cur, ly = cur / nc, ly / nl
        # Hourly LEVELS are not consistent over time (coverage of the hourly field changes), so only time-of-day SHARES
        # are taken from it. Growth comes from VISIT_COUNTS (the 13-week windows in the store panel / Dunkin' loader).
        dcur, dly = dayparts(cur.values), dayparts(ly.values)
        sh_c = dcur.sum() / dcur.sum().sum()
        sh_l = dly.sum() / dly.sum().sum()
        vc = visit_growth(folder, brand, list(both), cur_w, ly_w)
        for k in DAYPARTS:
            implied = (1 + vc["growth"]) * sh_c[k] / sh_l[k] - 1
            dp_rows.append({"brand": name, "daypart": k, "share_ly_pct": round(100 * sh_l[k], 2), "share_now_pct": round(100 * sh_c[k], 2),
                            "share_change_pp": round(100 * (sh_c[k] - sh_l[k]), 2),
                            "implied_daypart_growth_pct": round(100 * implied, 2),
                            "contribution_to_growth_pct": round(100 * (sh_c[k] * (1 + vc["growth"]) - sh_l[k]) / vc["growth"], 1)})
        pk = list(DAYPARTS["morning peak 7–10"])
        st = pd.DataFrame(index=both)
        st["peak_share_ly"] = ly[pk].sum(axis=1).values / ly.sum(axis=1).values
        st["peak_share_now"] = cur[pk].sum(axis=1).values / cur.sum(axis=1).values
        st["d_peak_share_pp"] = 100 * (st["peak_share_now"] - st["peak_share_ly"])
        st = st.join(vc["store_growth"].rename("growth"))
        store_tables[name] = st
        res[name] = {"same_stores": len(both), "weeks_cur": [str(cur_w[0].date()), str(cur_w[-1].date())],
                     "visit_counts_growth_pct": round(100 * vc["growth"], 2),
                     "peak_share_ly_pct": round(100 * sh_l["morning peak 7–10"], 2),
                     "peak_share_now_pct": round(100 * sh_c["morning peak 7–10"], 2),
                     "busiest_hour_share_now_pct": round(100 * float(cur.sum().max() / cur.sum().sum()), 2),
                     "busiest_hour": int(cur.sum().idxmax())}
        print(name, res[name])

    dp = pd.DataFrame(dp_rows)
    dp.to_csv(OUT / "daypart_growth.csv", index=False)
    prof = pd.concat(profiles)
    prof.to_csv(OUT / "profiles_by_fq.csv")
    s = store_tables["Starbucks"].join(panel.set_index("store_id")[["msa", "weekly_hours_2026_09", "visits_per_operating_hour", "visits_per_week_13w_ly"]])
    s = s[s["growth"].between(*s["growth"].quantile([0.01, 0.99]))].dropna(subset=["msa"])
    s.index.name = "store_id"
    s = s.reset_index()
    s["log_visits"] = np.log(s["visits_per_week_13w_ly"])
    s.to_csv(OUT / "store_peak.csv", index=False)
    reg = ols_fe(s, "d_peak_share_pp", ["growth", "log_visits"])
    s["cohort"] = pd.cut(s["growth"], [-1e9, 0, 5, 10, 1e9], labels=["< 0%", "0–5%", "5–10%", "> 10%"])
    coh = s.groupby("cohort", observed=True).agg(stores=("store_id", "size"), growth=("growth", "median"),
                                                peak_share_ly=("peak_share_ly", "mean"), peak_share_now=("peak_share_now", "mean"),
                                                d_peak_share_pp=("d_peak_share_pp", "mean")).round(4).reset_index()
    coh.to_csv(OUT / "peak_by_growth_cohort.csv", index=False)
    # Peak-share trend by fiscal quarter
    pk_cols = list(DAYPARTS["morning peak 7–10"])
    trend = prof.groupby("brand").apply(lambda x: (100 * x[pk_cols].sum(axis=1)).round(2), include_groups=False)
    res["daypart_growth"] = dp.to_dict(orient="records")
    res["store_regression_d_peak_share_on_growth"] = {"b_per_1pp": reg["b_growth"], "se": reg["se_growth"], "t": reg["t_growth"], "n": reg["n"]}
    res["cohorts"] = coh.to_dict(orient="records")
    res["peak_share_by_fq_pct"] = {b: v.droplevel(0).to_dict() if isinstance(v.index, pd.MultiIndex) else v.to_dict()
                                   for b, v in trend.groupby(level=0)}
    save_json(res, OUT / "results.json")
    print(dp.to_string(index=False))
    print(coh.to_string(index=False))
    print(reg)
    print(trend)
    chart(dp, prof, coh)


def chart(dp: pd.DataFrame, prof: pd.DataFrame, coh: pd.DataFrame) -> None:
    import sys
    sys.path.insert(0, str(LAB.parent / "_research_archive/starbucks_hiring/src"))
    import charts as C
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.2))
    ax = axes[0]
    sb = prof[prof["brand"] == "Starbucks"].drop(columns="brand")
    for q, col, lab in ((sb.index[sb.index.str.startswith("FY25")][1] if any(sb.index.str.startswith("FY25")) else sb.index[0], C.GRAY, None),
                        (sb.index[-2], C.BLUE, None)):
        ax.plot(range(24), 100 * sb.loc[q].values, color=col, linewidth=2, label=q)
    ax.set_xticks(range(0, 24, 3), [f"{h}:00" for h in range(0, 24, 3)], fontsize=8)
    ax.set_ylabel("% of daily visits")
    ax.set_title("Starbucks visits by hour of day", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax = axes[1]
    order = list(DAYPARTS)[:-1]
    x = np.arange(len(order))
    for i, (b, col) in enumerate((("Starbucks", C.BLUE), ("Dunkin'", C.GRAY))):
        v = dp[dp["brand"] == b].set_index("daypart").loc[order, "share_change_pp"]
        ax.bar(x + (i - 0.5) * 0.36, v, width=0.34, color=col, label=b)
        for xi, vi in zip(x, v):
            ax.text(xi + (i - 0.5) * 0.36, vi, f"{vi:+.2f}", ha="center", va="bottom" if vi >= 0 else "top", fontsize=7, color=C.INK_2)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_xticks(x, [o.replace(" ", "\n", 1) for o in order], fontsize=7)
    ax.set_ylabel("change in share of visits, pp YoY")
    ax.set_title("Where the visit mix shifted (latest 13 wks vs year ago)", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="x", visible=False)
    ax = axes[2]
    xx = np.arange(len(coh))
    ax.bar(xx, coh["d_peak_share_pp"], width=0.6, color=C.BLUE)
    for xi, vi in zip(xx, coh["d_peak_share_pp"]):
        ax.text(xi, vi, f"{vi:+.2f}", ha="center", va="bottom" if vi >= 0 else "top", fontsize=8, color=C.INK_2)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.set_xticks(xx, [f"{c}\n(n={n:,})" for c, n in zip(coh["cohort"], coh["stores"])], fontsize=8)
    ax.set_ylabel("change in 7–10 am share, pp YoY")
    ax.set_title("Starbucks: 7–10 am share change by store traffic growth", fontsize=10)
    ax.grid(axis="x", visible=False)
    fig.suptitle("Where did the extra visits land? Time-of-day mix of visits", x=0.01, y=0.99, ha="left", fontsize=12, fontweight="semibold")
    fig.text(0.01, 0.01, "Advan VISITS_BY_EACH_HOUR (local time), pooled over 13-week windows · company-operated Starbucks, all Dunkin' · panel sample, relative only",
             fontsize=8, color=C.INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    fig.savefig(LAB / "charts/08_peak_load.png", dpi=200)


if __name__ == "__main__":
    main()
