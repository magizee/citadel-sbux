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
  2. Per store: visits over the latest N complete months vs the same months a year earlier (YoY %),
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
    ap.add_argument("--months", type=int, default=3, help="latest complete months compared YoY")
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
    adv["month"] = pd.to_datetime(adv["date_range_start"].str[:10], errors="coerce").dt.to_period("M")
    vcol = "normalized_visits_by_state_scaling" if adv.get("normalized_visits_by_state_scaling", pd.Series(dtype=float)).notna().any() \
        else "raw_visit_counts"
    # Weekly files -> monthly sums (monthly files pass through unchanged)
    panel = adv.groupby(["placekey", "month"]).agg(visits=(vcol, "sum"), dwell=("median_dwell", "median")).reset_index()
    pois = adv.sort_values("month").groupby("placekey").agg(
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
           "months_available": [str(panel["month"].min()), str(panel["month"].max())]}

    # 2. Same-store YoY over the latest N complete months
    last = panel["month"].max() - 1   # treat the latest month as possibly incomplete
    cur = [last - i for i in range(args.months)]
    prev = [p - 12 for p in cur]
    agg = lambda months: panel[panel["month"].isin(months)].groupby("placekey").agg(  # noqa: E731
        v=("visits", "sum"), n=("visits", "size"), dwell=("dwell", "median"))
    a, b = agg(cur), agg(prev)
    yoy = a.join(b, lsuffix="_cur", rsuffix="_prev", how="inner")
    yoy = yoy[(yoy["n_cur"] == args.months) & (yoy["n_prev"] == args.months) & (yoy["v_prev"] > 0)]
    yoy["visits_yoy_pct"] = 100 * (yoy["v_cur"] / yoy["v_prev"] - 1)
    yoy["dwell_change_min"] = yoy["dwell_cur"] - yoy["dwell_prev"]
    st = matched.merge(yoy.reset_index(), on="placekey")
    lo_, hi_ = st["visits_yoy_pct"].quantile([0.01, 0.99])
    st = st[st["visits_yoy_pct"].between(lo_, hi_)]          # trim extreme panel artefacts
    st["yoy_vs_state"] = st["visits_yoy_pct"] - st.groupby("state")["visits_yoy_pct"].transform("median")
    st["dwell_vs_state"] = st["dwell_change_min"] - st.groupby("state")["dwell_change_min"].transform("median")
    res["window"] = {"current": [str(p) for p in sorted(cur)], "prior": [str(p) for p in sorted(prev)]}
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

    # 5. Chart: state-relative YoY visits by group with 95% CI
    import charts as C
    import matplotlib.pyplot as plt
    d = comp[comp["stores"] >= 30].iloc[1:].copy()
    d = d.sort_values("median_yoy_vs_state_pp")
    fig, ax = plt.subplots(figsize=(8.5, 0.5 * len(d) + 1.8))
    y = range(len(d))
    ax.hlines(list(y), d["ci95_low"], d["ci95_high"], color=C.BLUE_LIGHT, linewidth=6, zorder=2)
    ax.scatter(d["median_yoy_vs_state_pp"], list(y), color=C.INK, s=40, zorder=3)
    ax.axvline(0, color=C.INK_2, linewidth=1)
    ax.set_yticks(list(y), [f"{g}  (n={n:,})" for g, n in zip(d["group"], d["stores"])])
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Visits YoY vs. the store's state median (percentage points)")
    ax.set_title("Foot traffic at stores near staffing-pressure signals")
    C._finish(fig, ax, OUT / "visits_yoy_by_group.png",
              f"Advan visits, {res['window']['current'][0]}–{res['window']['current'][-1]} vs prior year · dot = median, bar = 95% bootstrap CI",
              note="Descriptive only. Busy stores can both hire more and post higher traffic (reverse causality).")


if __name__ == "__main__":
    main()
