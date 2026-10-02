"""Test E: do staffing-pressure signals line up with weaker foot traffic? (Advan via Dewey)

    python src/advan_analysis.py [--input data/processed/advan_starbucks.csv.gz] [--months 3] [--zone-km 15]

Inputs (read only):
  data/processed/advan_starbucks.csv.gz                       Starbucks rows from advan_pull.py
  ../starbucks_store_universe/data/processed/starbucks_store_universe.csv   company-operated (CO) stores
  ../starbucks_store_universe/data/processed/hiring_store_join.csv          hiring store_key -> locator_id
  ../starbucks_thesis_tests/outputs/tables/store_pattern_classes.csv        hiring pattern per store_key
  ../starbucks_hiring/data/processed/2026-10-01/starbucks_jobs_US.csv       leadership postings (area coords)

Method
  1. Advan POIs -> nearest CO store within 75 m (address similarity reported). Licensed stores excluded.
  2. Per store: mean weekly visits over the latest N weeks vs the same weeks 52 weeks earlier (YoY %),
     and the change in median dwell time. Visits = normalized_visits_by_state_scaling when present,
     else raw_visit_counts (panel changes partly cancel in a same-store YoY).
  3. Groups: stores within ZONE_KM of an open store/district-manager requisition ("leadership zone"),
     and within ZONE_KM of a re-posted or > 60-day leadership requisition ("persistent zone");
     hiring pattern classes from the national snapshot.
  4. Compare groups on YoY *relative to the store's state median* (removes regional trends),
     with bootstrap 95% intervals. Descriptive only; no causal claim.
Outputs: outputs/advan/*.csv, outputs/advan/*.png, outputs/advan/advan_results.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT.parent
OUT = ROOT / "outputs/advan"
sys.path.insert(0, str(PROJ / "starbucks_hiring/src"))


def nearest(src: pd.DataFrame, dst: pd.DataFrame, max_m: float) -> pd.DataFrame:
    """For each src row (lat/lon) the nearest dst row within max_m metres (grid index)."""
    cell = 0.01
    grid: dict[tuple, list[int]] = {}
    dl, dn = dst["latitude"].to_numpy(), dst["longitude"].to_numpy()
    for i, (a, b) in enumerate(zip(dl, dn)):
        grid.setdefault((int(a // cell), int(b // cell)), []).append(i)
    idx, dist = [], []
    for a, b in zip(src["latitude"].to_numpy(), src["longitude"].to_numpy()):
        best, bd = -1, float("inf")
        gi, gj = int(a // cell), int(b // cell)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for i in grid.get((gi + di, gj + dj), []):
                    dy = (dl[i] - a) * 111_195
                    dx = (dn[i] - b) * 111_195 * math.cos(math.radians(a))
                    d = math.hypot(dx, dy)
                    if d < bd:
                        best, bd = i, d
        idx.append(best if bd <= max_m else -1)
        dist.append(bd if bd <= max_m else None)
    return pd.DataFrame({"dst_idx": idx, "dist_m": dist}, index=src.index)


def within_km(stores: pd.DataFrame, points: pd.DataFrame, km: float) -> pd.Series:
    """True for stores within km of any point (haversine, brute force on small point sets)."""
    if points.empty:
        return pd.Series(False, index=stores.index)
    la, lo = np.radians(stores["latitude"].to_numpy())[:, None], np.radians(stores["longitude"].to_numpy())[:, None]
    pa, po = np.radians(points["latitude"].to_numpy())[None, :], np.radians(points["longitude"].to_numpy())[None, :]
    h = np.sin((pa - la) / 2) ** 2 + np.cos(la) * np.cos(pa) * np.sin((po - lo) / 2) ** 2
    d = 2 * 6371 * np.arcsin(np.sqrt(h))
    return pd.Series((d <= km).any(axis=1), index=stores.index)


def boot_ci(x: pd.Series, n: int = 2000, seed: int = 0) -> tuple[float, float]:
    x = x.dropna().to_numpy()
    if len(x) < 10:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    m = [np.median(rng.choice(x, len(x))) for _ in range(n)]
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", default=str(ROOT / "data/processed/advan_starbucks.csv.gz"))
    ap.add_argument("--weeks", type=int, default=13, help="latest weeks compared with the same weeks 52 weeks earlier")
    ap.add_argument("--zone-km", type=float, default=15)
    ap.add_argument("--snapshot-date", default="2026-10-01")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    adv = pd.read_csv(args.input, dtype=str, low_memory=False)
    adv.columns = [c.lower() for c in adv.columns]
    for c in ("latitude", "longitude", "raw_visit_counts", "raw_visitor_counts", "median_dwell",
              "normalized_visits_by_state_scaling"):
        if c in adv:
            adv[c] = pd.to_numeric(adv[c], errors="coerce")
    adv["week"] = pd.to_datetime(adv["date_range_start"].str[:10], errors="coerce")
    vcol = "normalized_visits_by_state_scaling" if adv.get("normalized_visits_by_state_scaling", pd.Series(dtype=float)).notna().any() \
        else "raw_visit_counts"
    adv["raw_visit_counts"] = pd.to_numeric(adv["raw_visit_counts"], errors="coerce")
    panel = adv.groupby(["placekey", "week"]).agg(visits=(vcol, "sum"), dwell=("median_dwell", "median")).reset_index()
    pois = adv.sort_values("week").groupby("placekey").agg(
        latitude=("latitude", "last"), longitude=("longitude", "last"), street_address=("street_address", "last"),
        city=("city", "last"), region=("region", "last")).reset_index().dropna(subset=["latitude", "longitude"])

    # 1. POI -> company-operated store
    uni = pd.read_csv(PROJ / "starbucks_store_universe/data/processed/starbucks_store_universe.csv", dtype={"locator_id": str})
    co = uni[uni["ownership_type"] == "CO"].reset_index(drop=True)
    m = nearest(pois, co, 75)
    pois["locator_id"] = [co.at[i, "locator_id"] if i >= 0 else None for i in m["dst_idx"]]
    pois["state"] = [co.at[i, "state"] if i >= 0 else None for i in m["dst_idx"]]
    pois["match_m"] = m["dist_m"]
    matched = pois.dropna(subset=["locator_id"]).drop_duplicates("locator_id")
    res = {"advan_rows": len(adv), "advan_pois": len(pois), "visits_column": vcol,
           "pois_matched_to_co_stores": len(matched), "co_stores": len(co),
           "weeks_available": [str(panel["week"].min().date()), str(panel["week"].max().date())]}

    # 2. Same-store YoY: mean weekly visits over the latest N weeks vs the same weeks 52 weeks earlier
    #    (52-week offset keeps the same weekdays/season; avoids 4-vs-5-week months).
    weeks = sorted(panel["week"].dropna().unique())
    cur = weeks[-args.weeks:]
    prev = [w - pd.Timedelta(weeks=52) for w in cur]
    need = int(round(args.weeks * 0.85))
    agg = lambda ws: panel[panel["week"].isin(ws)].groupby("placekey").agg(  # noqa: E731
        v=("visits", "mean"), n=("visits", "size"), dwell=("dwell", "median"))
    a, b = agg(cur), agg(prev)
    yoy = a.join(b, lsuffix="_cur", rsuffix="_prev", how="inner")
    yoy = yoy[(yoy["n_cur"] >= need) & (yoy["n_prev"] >= need) & (yoy["v_prev"] > 0)]
    yoy["visits_yoy_pct"] = 100 * (yoy["v_cur"] / yoy["v_prev"] - 1)
    yoy["dwell_change_min"] = yoy["dwell_cur"] - yoy["dwell_prev"]
    st = matched.merge(yoy.reset_index(), on="placekey")
    lo_, hi_ = st["visits_yoy_pct"].quantile([0.01, 0.99])
    st = st[st["visits_yoy_pct"].between(lo_, hi_)]          # trim extreme panel artefacts
    st["yoy_vs_state"] = st["visits_yoy_pct"] - st.groupby("state")["visits_yoy_pct"].transform("median")
    st["dwell_vs_state"] = st["dwell_change_min"] - st.groupby("state")["dwell_change_min"].transform("median")
    res["window"] = {"current": [str(pd.Timestamp(cur[0]).date()), str(pd.Timestamp(cur[-1]).date())],
                     "prior": [str(pd.Timestamp(prev[0]).date()), str(pd.Timestamp(prev[-1]).date())],
                     "weeks": args.weeks, "min_weeks_required": need}
    res["stores_with_yoy"] = len(st)
    res["national_median_visits_yoy_pct"] = round(float(st["visits_yoy_pct"].median()), 2)

    # 3. Groups
    jobs = pd.read_csv(PROJ / f"starbucks_hiring/data/processed/{args.snapshot_date}/starbucks_jobs_US.csv",
                       dtype={"store_number": str})
    lead = jobs[jobs["role_bucket"].isin(["STORE_MANAGER", "DISTRICT_MANAGER"]) & jobs["latitude"].notna()]
    persistent = lead[(lead["reposted_requisition"].astype(str) == "True") | (lead["req_age_days"].astype(float) > 60)]
    coords = st.merge(co[["locator_id", "latitude", "longitude"]], on="locator_id", suffixes=("_poi", ""))
    st["leadership_zone"] = within_km(coords, lead, args.zone_km).to_numpy()
    st["persistent_leadership_zone"] = within_km(coords, persistent, args.zone_km).to_numpy()
    join = pd.read_csv(PROJ / "starbucks_store_universe/data/processed/hiring_store_join.csv", dtype={"locator_id": str})
    cls = pd.read_csv(PROJ / "starbucks_thesis_tests/outputs/tables/store_pattern_classes.csv")
    lk = join[join["matched"] == True][["locator_id", "store_key"]].merge(cls[["store_key", "pattern_class"]], on="store_key")  # noqa: E712
    st = st.merge(lk[["locator_id", "pattern_class"]], on="locator_id", how="left")
    st["pattern_class"] = st["pattern_class"].fillna("no active posting")
    st.to_csv(OUT / "store_visits_yoy.csv", index=False)

    # 4. Comparisons (state-relative)
    rows = []
    def add(label, mask):
        g = st[mask]
        lo, hi = boot_ci(g["yoy_vs_state"])
        rows.append({"group": label, "stores": int(mask.sum()),
                     "median_visits_yoy_pct": round(float(g["visits_yoy_pct"].median()), 2) if len(g) else None,
                     "median_yoy_vs_state_pp": round(float(g["yoy_vs_state"].median()), 2) if len(g) else None,
                     "ci95_low": round(lo, 2), "ci95_high": round(hi, 2),
                     "median_dwell_change_vs_state_min": round(float(g["dwell_vs_state"].median()), 2) if len(g) else None})
    add("All matched company-operated stores", st.index == st.index)
    add(f"Within {args.zone_km:.0f} km of an open manager requisition", st["leadership_zone"])
    add(f"Within {args.zone_km:.0f} km of a persistent manager requisition", st["persistent_leadership_zone"])
    add("Not near any open manager requisition", ~st["leadership_zone"])
    for c in st["pattern_class"].unique():
        add(f"Hiring pattern: {c}", st["pattern_class"] == c)
    comp = pd.DataFrame(rows)
    comp.to_csv(OUT / "visits_by_group.csv", index=False)
    res["comparison"] = comp.to_dict(orient="records")
    (OUT / "advan_results.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))

    # 5. Robustness: within-metro comparison and a density control
    msa = adv.drop_duplicates("placekey")[["placekey", "msa_code"]] if "msa_code" in adv else None
    co_xy = co[["locator_id", "latitude", "longitude"]]
    sx = st.merge(co_xy, on="locator_id", suffixes=("_poi", ""))
    cla, clo = np.radians(co_xy["latitude"].to_numpy()), np.radians(co_xy["longitude"].to_numpy())
    dens = []
    for a_, b_ in zip(np.radians(sx["latitude"].to_numpy()), np.radians(sx["longitude"].to_numpy())):
        h = np.sin((cla - a_) / 2) ** 2 + np.cos(a_) * np.cos(cla) * np.sin((clo - b_) / 2) ** 2
        dens.append(int((2 * 6371 * np.arcsin(np.sqrt(h)) <= args.zone_km).sum()))
    sx["co_stores_within_zone_km"] = dens
    rob = {}
    if msa is not None:
        sx = sx.merge(msa, on="placekey", how="left")
        m_ = sx[sx["msa_code"].notna()].copy()
        m_["yoy_vs_msa"] = m_["visits_yoy_pct"] - m_.groupby("msa_code")["visits_yoy_pct"].transform("median")
        for z in ("leadership_zone", "persistent_leadership_zone"):
            rob[f"within_msa_median_pp_{z}"] = round(float(m_.loc[m_[z], "yoy_vs_msa"].median()), 2)
            rob[f"within_msa_median_pp_not_{z}"] = round(float(m_.loc[~m_[z], "yoy_vs_msa"].median()), 2)

    def ols(df, xcols):
        X = pd.get_dummies(df[xcols + ["state"]], columns=["state"], drop_first=True).astype(float)
        X.insert(0, "const", 1.0)
        y = df["visits_yoy_pct"].to_numpy()
        bta = np.linalg.lstsq(X.to_numpy(), y, rcond=None)[0]
        e = y - X.to_numpy() @ bta
        cov = (e @ e / (len(y) - X.shape[1])) * np.linalg.inv(X.to_numpy().T @ X.to_numpy())
        return {c: [round(float(bta[i]), 3), round(float(np.sqrt(cov[i, i])), 3)]
                for i, c in enumerate(X.columns) if c in xcols}
    sx["log_density"] = np.log1p(sx["co_stores_within_zone_km"])
    for z in ("leadership_zone", "persistent_leadership_zone"):
        sx[z + "_f"] = sx[z].astype(float)
        rob[f"ols_state_fe_{z}"] = ols(sx, [z + "_f"])
        rob[f"ols_state_fe_density_{z}"] = ols(sx, [z + "_f", "log_density"])
    rob["median_density_in_zone_vs_not"] = sx.groupby("leadership_zone")["co_stores_within_zone_km"].median().to_dict()
    res["robustness"] = rob

    # 6. Store openings / closures recorded by Advan (validated against the store locator)
    last = adv.sort_values("week").drop_duplicates("placekey", keep="last")
    closures = None
    if "close_date" in last:
        cd = pd.to_datetime(last["close_date"].str[:10], errors="coerce")
        od = pd.to_datetime(last["open_date"].str[:10], errors="coerce")
        cl = last[(cd >= "2024-01-01") & (cd < "2030-01-01")].copy()   # 2038-01-01 = still open
        cl["close_month"] = cd[cl.index].dt.to_period("M").astype(str)
        loc = nearest(cl.astype({"latitude": float, "longitude": float}), uni.reset_index(drop=True), 75)
        cl["still_in_store_locator"] = loc["dst_idx"] >= 0
        closures = cl.groupby("close_month").agg(closed_locations=("placekey", "size"),
                                                 share_still_in_locator=("still_in_store_locator", "mean")).reset_index()
        closures.to_csv(OUT / "advan_closures_by_month.csv", index=False)
        res["closures"] = {"closed_2024_onward": int(len(cl)),
                           "share_absent_from_store_locator": round(1 - float(cl["still_in_store_locator"].mean()), 3),
                           "opened_by_year": od[od >= "2024-01-01"].dt.year.value_counts().sort_index().to_dict(),
                           "note": "All Starbucks-branded locations incl. licensed; Advan does not flag ownership."}
    (OUT / "advan_results.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))

    # 7. Charts
    import charts as C
    import matplotlib.pyplot as plt
    short = {f"Within {args.zone_km:.0f} km of a persistent manager requisition": "Near a persistent manager vacancy",
             f"Within {args.zone_km:.0f} km of an open manager requisition": "Near any manager vacancy",
             "Not near any open manager requisition": "Not near a manager vacancy"}
    d = comp[comp["stores"] >= 30].iloc[1:].copy()
    d["label"] = d["group"].map(short).fillna(d["group"].str.replace("Hiring pattern: ", "Pattern: ")
                                              .str.replace("ordinary store: ", "").str.replace(" (Reserve, campus, airport…)", ""))
    d = d.sort_values("median_yoy_vs_state_pp")
    fig, ax = plt.subplots(figsize=(9, 0.48 * len(d) + 1.9))
    y = range(len(d))
    ax.hlines(list(y), d["ci95_low"], d["ci95_high"], color=C.BLUE_LIGHT, linewidth=6, zorder=2)
    ax.scatter(d["median_yoy_vs_state_pp"], list(y), color=C.INK, s=40, zorder=3)
    ax.axvline(0, color=C.INK_2, linewidth=1)
    ax.set_yticks(list(y), [f"{g}  (n={n:,})" for g, n in zip(d["label"], d["stores"])])
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Visits YoY minus the store's state median (percentage points)")
    ax.set_title("Foot traffic vs. staffing-pressure signals")
    C._finish(fig, ax, OUT / "visits_yoy_by_group.png",
              f"Advan weekly visits {res['window']['current'][0]} to {res['window']['current'][1]} vs a year earlier · dot = median, bar = 95% CI",
              note="The vacancy-area gap is closure transfer: excluding stores within 2 km of a recent closure, it disappears (advan_overcrowding.py).")
    if closures is not None:
        c2 = closures[closures["close_month"] >= "2024-07"]
        fig, ax = plt.subplots(figsize=(9, 3.6))
        ax.bar(range(len(c2)), c2["closed_locations"], color=C.BLUE, width=0.7, zorder=2)
        ax.set_xticks(range(len(c2)), [pd.Period(m).strftime("%b\n%y") for m in c2["close_month"]], fontsize=8)
        ax.grid(axis="x", visible=False)
        for x_, v_ in enumerate(c2["closed_locations"]):
            if v_ >= 50:
                ax.text(x_, v_, f"{v_}", ha="center", va="bottom", fontsize=8.5, color=C.INK_2)
        ax.set_ylabel("Locations closed")
        ax.set_title("U.S. Starbucks locations closed per month (Advan)")
        C._finish(fig, ax, OUT / "closures_by_month.png",
                  f"{res['closures']['share_absent_from_store_locator']:.0%} of these are absent from Starbucks' store locator (2026-09-26), i.e. genuine closures",
                  note="Includes licensed locations (Advan does not flag ownership). Months with no closures are omitted.")


if __name__ == "__main__":
    main()
