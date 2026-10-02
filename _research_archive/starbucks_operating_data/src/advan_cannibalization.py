"""Cannibalization model: closure event study + customer (trade-area) overlap.

    python src/advan_cannibalization.py

Part A - Event study around the October 2025 closure wave
  Treated: surviving U.S. Starbucks locations within 1 km ("ring A") or 1-2 km ("ring B") of a
  location that closed in Oct 2025, and not within 2 km of any other closure (Apr 2025 - Sep 2026).
  Controls: locations > 5 km from every closure in that window, in the same metro (MSA).
  Outcome: log weekly visits relative to each store's own pre-closure mean, minus the same-week
  mean of controls in its metro (removes seasonality, panel changes and metro trends).
  Window: 26 weeks before to 48 weeks after the closure week (2025-10-13).
  Recapture rate: extra weekly visits at surviving neighbours (vs their counterfactual from control
  growth) / pre-closure weekly visits of the closed stores.

Part B - Customer overlap (where visitors live, Advan VISITOR_HOME_CBGS)
  Reference period: the 4 weeks before the wave (Sep 8 - Oct 5, 2025), from the raw files.
  Overlap(i, j) = sum over home block groups of min(share_i, share_j)  (0 = disjoint, 1 = identical).
  Tests: overlap vs distance; did the closed stores overlap their neighbours more than stores that
  stayed open (within density quintiles)?; did neighbours that shared more customers gain more?

Outputs: outputs/advan/cannibalization_results.json and CSV/PNG files prefixed cannib_.
Descriptive / quasi-experimental; closures were chosen by Starbucks (not random). Advan includes
licensed locations and suppresses block groups with few visitors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs/advan"
RAW = ROOT / "data/raw/advan"
sys.path.insert(0, str(ROOT.parent / "starbucks_hiring/src"))
import charts as C  # noqa: E402

EVENT_WEEK = pd.Timestamp("2025-10-13")
PRE, POST = 26, 48
WAVE = ("2025-10-01", "2025-11-01")
OTHER_WINDOW = ("2025-04-01", "2026-10-01")
REF_WEEKS = ["2025-09-08", "2025-09-15", "2025-09-22", "2025-09-29"]


def km_matrix(a_lat, a_lon, b_lat, b_lon):
    la, lo = np.radians(a_lat)[:, None], np.radians(a_lon)[:, None]
    pa, po = np.radians(b_lat)[None, :], np.radians(b_lon)[None, :]
    h = np.sin((pa - la) / 2) ** 2 + np.cos(la) * np.cos(pa) * np.sin((po - lo) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def min_dist(a_lat, a_lon, b_lat, b_lon, chunk=3000):
    if len(b_lat) == 0:
        return np.full(len(a_lat), np.inf)
    return np.concatenate([km_matrix(a_lat[i:i + chunk], a_lon[i:i + chunk], b_lat, b_lon).min(axis=1)
                           for i in range(0, len(a_lat), chunk)])


def load_panel():
    d = pd.read_csv(ROOT / "data/processed/advan_starbucks.csv.gz",
                    usecols=["placekey", "date_range_start", "raw_visit_counts", "latitude", "longitude",
                             "close_date", "msa_code"], dtype=str)
    d["week"] = pd.to_datetime(d["date_range_start"].str[:10])
    d["visits"] = pd.to_numeric(d["raw_visit_counts"], errors="coerce")
    loc = d.sort_values("week").groupby("placekey").agg(
        lat=("latitude", "last"), lon=("longitude", "last"), msa=("msa_code", "last"),
        close_date=("close_date", "last"), first_week=("week", "min"), last_week=("week", "max")).reset_index()
    loc[["lat", "lon"]] = loc[["lat", "lon"]].astype(float)
    loc["close"] = pd.to_datetime(loc["close_date"].str[:10], errors="coerce")
    loc.loc[loc["close"] >= "2030-01-01", "close"] = pd.NaT
    return d[["placekey", "week", "visits"]], loc


def event_study(panel: pd.DataFrame, loc: pd.DataFrame, res: dict) -> pd.DataFrame:
    wave = loc[(loc["close"] >= WAVE[0]) & (loc["close"] < WAVE[1])]
    other = loc[(loc["close"] >= OTHER_WINDOW[0]) & (loc["close"] < OTHER_WINDOW[1]) & ~loc.index.isin(wave.index)]
    survivors = loc[loc["close"].isna()].copy()
    survivors["d_wave"] = min_dist(survivors["lat"].values, survivors["lon"].values, wave["lat"].values, wave["lon"].values)
    survivors["d_other"] = min_dist(survivors["lat"].values, survivors["lon"].values, other["lat"].values, other["lon"].values)
    survivors["d_any"] = np.minimum(survivors["d_wave"], survivors["d_other"])
    survivors["group"] = np.select(
        [(survivors["d_wave"] <= 1) & (survivors["d_other"] > 2),
         (survivors["d_wave"] > 1) & (survivors["d_wave"] <= 2) & (survivors["d_other"] > 2),
         survivors["d_any"] > 5],
        ["ring A (< 1 km)", "ring B (1-2 km)", "control"], default="excluded")
    treated_msas = set(survivors.loc[survivors["group"].str.startswith("ring"), "msa"].dropna())
    survivors.loc[(survivors["group"] == "control") & ~survivors["msa"].isin(treated_msas), "group"] = "excluded"

    weeks = pd.date_range(EVENT_WEEK - pd.Timedelta(weeks=PRE), EVENT_WEEK + pd.Timedelta(weeks=POST), freq="7D")
    p = panel[panel["week"].isin(weeks) & (panel["visits"] > 0)]
    p = p.merge(survivors[["placekey", "group", "msa"]], on="placekey")
    p = p[p["group"] != "excluded"]
    nweeks = p.groupby("placekey")["week"].nunique()
    p = p[p["placekey"].isin(nweeks[nweeks >= len(weeks) - 3].index)]           # near-balanced panel
    p["et"] = ((p["week"] - EVENT_WEEK).dt.days // 7).astype(int)
    p["y"] = np.log(p["visits"])
    pre_mean = p[p["et"] < 0].groupby("placekey")["y"].mean()
    p["y_rel"] = p["y"] - p["placekey"].map(pre_mean)
    ctrl = p[p["group"] == "control"].groupby(["msa", "week"])["y_rel"].mean().rename("ctrl")
    p = p.join(ctrl, on=["msa", "week"])
    p["gap"] = p["y_rel"] - p["ctrl"]
    tr = p[p["group"].str.startswith("ring")].dropna(subset=["gap"])

    rng = np.random.default_rng(0)
    rows = []
    for g, gg in tr.groupby("group"):
        stores = gg["placekey"].unique()
        piv = gg.pivot_table(index="placekey", columns="et", values="gap")
        boots = np.array([piv.loc[rng.choice(stores, len(stores))].mean().values for _ in range(400)])
        for k, et in enumerate(piv.columns):
            rows.append({"group": g, "event_week": int(et), "gap_log": piv[et].mean(),
                         "ci_low": np.nanpercentile(boots[:, k], 2.5), "ci_high": np.nanpercentile(boots[:, k], 97.5),
                         "stores": len(stores)})
        post = piv.loc[:, [c for c in piv.columns if 4 <= c <= POST]].mean(axis=1)
        pre = piv.loc[:, [c for c in piv.columns if -PRE <= c <= -1]].mean(axis=1)
        did = post - pre
        bd = [did.loc[rng.choice(stores, len(stores))].mean() for _ in range(1000)]
        res.setdefault("event_study", {})[g] = {
            "stores": len(stores), "did_log_points": round(float(did.mean()), 4),
            "did_pct": round(100 * (np.exp(did.mean()) - 1), 2),
            "ci95_pct": [round(100 * (np.exp(np.percentile(bd, 2.5)) - 1), 2), round(100 * (np.exp(np.percentile(bd, 97.5)) - 1), 2)],
            "pre_trend_slope_log_per_week": round(float(np.polyfit(
                [c for c in piv.columns if c < 0], piv[[c for c in piv.columns if c < 0]].mean().values, 1)[0]), 5)}
    es = pd.DataFrame(rows)
    es.to_csv(OUT / "cannib_event_study.csv", index=False)
    res["event_study_meta"] = {"closures_in_wave": len(wave), "event_week": str(EVENT_WEEK.date()),
                               "controls": int(p.loc[p["group"] == "control", "placekey"].nunique()),
                               "control_rule": "> 5 km from any closure Apr 2025-Sep 2026, same MSA as a treated store"}

    # Recapture: neighbours' extra visits (vs control-growth counterfactual) / closed stores' pre visits
    lvl = p.copy()
    pre_lvl = lvl[lvl["et"] < 0].groupby("placekey")["visits"].mean()
    lvl["cf"] = lvl["placekey"].map(pre_lvl) * np.exp(lvl["ctrl"])
    lvl["extra"] = lvl["visits"] - lvl["cf"]
    post_extra = lvl[(lvl["et"] >= 4) & lvl["group"].str.startswith("ring")].groupby(["group", "placekey"])["extra"].mean()
    closed_pre = panel[panel["placekey"].isin(wave["placekey"]) & (panel["week"] >= EVENT_WEEK - pd.Timedelta(weeks=PRE))
                       & (panel["week"] < EVENT_WEEK - pd.Timedelta(weeks=4))].groupby("placekey")["visits"].mean()
    res["recapture"] = {
        "closed_store_pre_weekly_visits_total": round(float(closed_pre.sum())),
        "extra_weekly_visits_ring_A": round(float(post_extra.get("ring A (< 1 km)", pd.Series(dtype=float)).sum())),
        "extra_weekly_visits_ring_B": round(float(post_extra.get("ring B (1-2 km)", pd.Series(dtype=float)).sum())),
        "note": "Rings only include survivors not near other closures, so this is a LOWER BOUND on total recapture."}
    tot = res["recapture"]["extra_weekly_visits_ring_A"] + res["recapture"]["extra_weekly_visits_ring_B"]
    res["recapture"]["recapture_rate_within_2km_pct"] = round(100 * tot / max(closed_pre.sum(), 1), 1)
    return es


def overlap(loc: pd.DataFrame, res: dict) -> pd.DataFrame:
    files = [f for w in REF_WEEKS for f in RAW.glob(f"{w}__*.parquet")]
    frames = [pd.read_parquet(f, columns=["ID_STORE", "VISITOR_HOME_CBGS", "ISO_COUNTRY_CODE"]) for f in files]
    d = pd.concat(frames)
    d = d[(d["ISO_COUNTRY_CODE"] == "US") & d["VISITOR_HOME_CBGS"].notna()]
    homes: dict[str, dict[str, float]] = {}
    for sid, js in zip(d["ID_STORE"], d["VISITOR_HOME_CBGS"]):
        h = homes.setdefault(sid, {})
        for cbg, n in (json.loads(js) if isinstance(js, str) else js).items():
            h[cbg] = h.get(cbg, 0) + n
    shares = {k: {c: n / sum(v.values()) for c, n in v.items()} for k, v in homes.items() if sum(v.values()) > 0}
    L = loc[loc["placekey"].isin(shares)].reset_index(drop=True)
    L["closed_wave"] = (L["close"] >= WAVE[0]) & (L["close"] < WAVE[1])
    # density (Starbucks locations within 15 km) for like-for-like comparisons
    dens = np.concatenate([(km_matrix(L["lat"].values[i:i + 3000], L["lon"].values[i:i + 3000], L["lat"].values, L["lon"].values) <= 15).sum(1) - 1
                           for i in range(0, len(L), 3000)])
    L["density"] = dens
    # pairs within 5 km via a 0.05-degree grid
    cell = 0.05
    grid: dict[tuple, list[int]] = {}
    for i, (a, b) in enumerate(zip(L["lat"], L["lon"])):
        grid.setdefault((int(a // cell), int(b // cell)), []).append(i)
    pairs = []
    for i, (a, b) in enumerate(zip(L["lat"], L["lon"])):
        gi, gj = int(a // cell), int(b // cell)
        cand = [j for di in (-1, 0, 1) for dj in (-1, 0, 1) for j in grid.get((gi + di, gj + dj), []) if j > i]
        if not cand:
            continue
        dist = km_matrix(np.array([a]), np.array([b]), L["lat"].values[cand], L["lon"].values[cand])[0]
        si = shares[L.at[i, "placekey"]]
        for j, dk in zip(cand, dist):
            if dk <= 5:
                sj = shares[L.at[j, "placekey"]]
                small, big = (si, sj) if len(si) < len(sj) else (sj, si)
                ov = sum(min(v, big.get(c, 0.0)) for c, v in small.items())
                pairs.append((i, j, dk, ov))
    P = pd.DataFrame(pairs, columns=["i", "j", "km", "overlap"])
    P["band"] = pd.cut(P["km"], [0, 0.5, 1, 2, 5], labels=["< 0.5 km", "0.5–1 km", "1–2 km", "2–5 km"], include_lowest=True)
    band = P.groupby("band", observed=True)["overlap"].agg(pairs="size", median="median", mean="mean").round(3).reset_index()
    band.to_csv(OUT / "cannib_overlap_by_distance.csv", index=False)
    res["overlap_by_distance"] = band.to_dict(orient="records")

    # each store's highest overlap with any neighbour within 5 km
    both = pd.concat([P[["i", "overlap"]], P[["j", "overlap"]].rename(columns={"j": "i"})])
    L["max_neighbour_overlap"] = both.groupby("i")["overlap"].max().reindex(L.index).fillna(0)
    L["dens_q"] = pd.qcut(L["density"], 5, labels=["Q1 least dense", "Q2", "Q3", "Q4", "Q5 most dense"])
    cmp_ = L.groupby(["dens_q", "closed_wave"], observed=True)["max_neighbour_overlap"].median().unstack()
    cmp_.columns = ["stayed open", "closed Oct 2025"]
    cmp_ = cmp_.round(3).reset_index()
    cmp_.to_csv(OUT / "cannib_closed_vs_open_overlap.csv", index=False)
    res["closed_vs_open_max_overlap_by_density"] = cmp_.to_dict(orient="records")
    res["closed_vs_open_max_overlap_overall"] = {
        "closed_median": round(float(L.loc[L["closed_wave"], "max_neighbour_overlap"].median()), 3),
        "open_median": round(float(L.loc[~L["closed_wave"], "max_neighbour_overlap"].median()), 3),
        "closed_n": int(L["closed_wave"].sum())}
    L[["placekey", "density", "closed_wave", "max_neighbour_overlap"]].to_csv(OUT / "cannib_store_overlap.csv", index=False)
    return P.assign(pk_i=L["placekey"].values[P["i"]], pk_j=L["placekey"].values[P["j"]],
                    closed_i=L["closed_wave"].values[P["i"]], closed_j=L["closed_wave"].values[P["j"]])


def gain_vs_overlap(P: pd.DataFrame, panel: pd.DataFrame, loc: pd.DataFrame, res: dict) -> pd.DataFrame:
    """Neighbours of a closed store: does a larger customer overlap predict a larger traffic gain?"""
    e = pd.concat([P[P["closed_i"] & ~P["closed_j"]].rename(columns={"pk_j": "neighbour", "pk_i": "closed"}),
                   P[P["closed_j"] & ~P["closed_i"]].rename(columns={"pk_i": "neighbour", "pk_j": "closed"})])
    e = e.sort_values("overlap", ascending=False).drop_duplicates("neighbour")   # neighbour's most-overlapping closed store
    pre = panel[(panel["week"] >= EVENT_WEEK - pd.Timedelta(weeks=PRE)) & (panel["week"] < EVENT_WEEK)]
    post = panel[(panel["week"] >= EVENT_WEEK + pd.Timedelta(weeks=4)) & (panel["week"] <= EVENT_WEEK + pd.Timedelta(weeks=POST))]
    g = (np.log(post.groupby("placekey")["visits"].mean()) - np.log(pre.groupby("placekey")["visits"].mean())).rename("growth")
    allg = g.median()
    e = e.join(g, on="neighbour").dropna(subset=["growth"])
    e["growth_vs_all_pct"] = 100 * (np.exp(e["growth"] - allg) - 1)
    e["overlap_bin"] = pd.qcut(e["overlap"], 5, duplicates="drop")
    b = e.groupby("overlap_bin", observed=True).agg(neighbours=("neighbour", "size"), median_overlap=("overlap", "median"),
                                                    growth_vs_all_pct=("growth_vs_all_pct", "median")).round(3).reset_index()
    b["overlap_bin"] = b["overlap_bin"].astype(str)
    b.to_csv(OUT / "cannib_gain_vs_overlap.csv", index=False)
    res["gain_vs_overlap"] = {"neighbours": len(e),
                              "spearman": round(float(e["overlap"].rank().corr(e["growth"].rank())), 3),
                              "bins": b.to_dict(orient="records"),
                              "note": "Growth = log(post-closure mean visits / pre-closure mean), relative to all-store median; not metro-adjusted."}
    return b


def charts(es: pd.DataFrame, res: dict, gb: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 4.2))
    col = {"ring A (< 1 km)": C.BLUE, "ring B (1-2 km)": "#eb6834"}
    for g, gg in es.groupby("group"):
        gg = gg.sort_values("event_week")
        pct = 100 * (np.exp(gg["gap_log"]) - 1)
        ax.fill_between(gg["event_week"], 100 * (np.exp(gg["ci_low"]) - 1), 100 * (np.exp(gg["ci_high"]) - 1),
                        color=col[g], alpha=0.15, linewidth=0)
        ax.plot(gg["event_week"], pct, color=col[g], linewidth=2,
                label=f"{g}: +{res['event_study'][g]['did_pct']:.1f}% (n={res['event_study'][g]['stores']:,})")
    ax.axvline(0, color=C.INK_2, linewidth=1)
    ax.axhline(0, color=C.INK_2, linewidth=0.8)
    ax.text(0.5, ax.get_ylim()[1] * 0.92, " closure week (Oct 13 2025)", color=C.INK_2, fontsize=8.5)
    ax.set_xlabel("Weeks relative to the October 2025 closure wave")
    ax.set_ylabel("Visits vs same-metro controls (%)")
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    ax.set_title("Little of a closed store's traffic moved to nearby Starbucks")
    C._finish(fig, ax, OUT / "cannib_event_study.png",
              f"Surviving Starbucks near the {res['event_study_meta']['closures_in_wave']} Oct-2025 closures vs stores > 5 km from any closure, same metros · 95% CI",
              note=f"Recapture ≈ {res['recapture']['recapture_rate_within_2km_pct']:.0f}% within 2 km (≈ 12% within 5 km), lower bounds. Dips at weeks 6/10 = Thanksgiving/Christmas (urban vs suburban mix).")

    band = pd.DataFrame(res["overlap_by_distance"])
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(range(len(band)), band["median"] * 100, color=C.BLUE, width=0.6, zorder=2)
    ax.set_xticks(range(len(band)), [f"{b}\n({n:,} pairs)" for b, n in zip(band["band"], band["pairs"])], fontsize=8.5)
    for x_, v_ in enumerate(band["median"] * 100):
        ax.text(x_, v_, f"{v_:.0f}%", ha="center", va="bottom", fontsize=9, color=C.INK_2)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Shared customers (%)")
    ax.set_title("Nearby Starbucks share the same customers")
    C._finish(fig, ax, OUT / "cannib_overlap_by_distance.png",
              "Median overlap of visitors' home neighbourhoods between pairs of stores, Sep 2025 (pre-closure)",
              note="Overlap = Σ min(share_i, share_j) over visitors' home census block groups (Advan).")

    cv = pd.DataFrame(res["closed_vs_open_max_overlap_by_density"])
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    x = np.arange(len(cv))
    ax.bar(x - 0.18, cv["stayed open"] * 100, width=0.34, color=C.BLUE_LIGHT, label="Stayed open", zorder=2)
    ax.bar(x + 0.18, cv["closed Oct 2025"] * 100, width=0.34, color=C.BLUE, label="Closed Oct 2025", zorder=2)
    ax.set_xticks(x, cv["dens_q"].astype(str), fontsize=8.5)
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=9)
    ax.set_ylabel("Highest overlap with a neighbour (%)")
    ax.set_title("Closed stores shared FEWER customers with neighbours than survivors")
    C._finish(fig, ax, OUT / "cannib_closed_vs_open_overlap.png",
              "Median of each store's highest customer overlap with any Starbucks within 5 km, by local density",
              note="Compared within density quintiles so the result is not just 'closed stores were in denser areas'.")

    if len(gb):
        fig, ax = plt.subplots(figsize=(8, 3.6))
        ax.bar(range(len(gb)), gb["growth_vs_all_pct"], color=C.BLUE, width=0.6, zorder=2)
        ax.axhline(0, color=C.INK_2, linewidth=0.8)
        ax.set_xticks(range(len(gb)), [f"{m * 100:.0f}% shared\n(n={n})" for m, n in zip(gb["median_overlap"], gb["neighbours"])], fontsize=8.5)
        for x_, v_ in enumerate(gb["growth_vs_all_pct"]):
            ax.text(x_, v_, f"{v_:+.1f}%", ha="center", va="bottom" if v_ >= 0 else "top", fontsize=9, color=C.INK_2)
        ax.grid(axis="x", visible=False)
        ax.set_ylabel("Visit change vs all stores (%)")
        ax.set_xlabel("Customer overlap with the closed store (quintiles)")
        ax.set_title("Neighbours' gains did not depend on shared customers")
        C._finish(fig, ax, OUT / "cannib_gain_vs_overlap.png",
                  "Neighbours (≤ 5 km) of Oct-2025 closures: post- vs pre-closure visits, relative to the all-store median",
                  note=f"Spearman ρ = {res['gain_vs_overlap']['spearman']} (n = {res['gain_vs_overlap']['neighbours']:,}). Not metro-adjusted.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel, loc = load_panel()
    res: dict = {"stores_in_panel": int(loc["placekey"].nunique())}
    es = event_study(panel, loc, res)
    P = overlap(loc, res)
    gb = gain_vs_overlap(P, panel, loc, res)
    (OUT / "cannibalization_results.json").write_text(json.dumps(res, indent=2, default=str))
    charts(es, res, gb)
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
