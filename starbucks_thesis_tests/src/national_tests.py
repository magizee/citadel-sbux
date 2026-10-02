"""Run the staffing-thesis tests (A, B, C, E, F + requisition-volume trend) on the national snapshot.

    python src/national_tests.py --snapshot-date 2026-10-01

Reads (never writes) sibling projects:
  ../starbucks_hiring/data/processed/<date>/starbucks_jobs_US.csv      cleaned national postings
  ../starbucks_hiring/outputs/tables/store_role_patterns.csv            per-store role patterns
  ../starbucks_store_universe/data/processed/starbucks_store_universe.csv + hiring_store_join.csv
  ../starbucks_labor_market/data/processed/labor_market_controls.csv
  ../starbucks_operating_data/data/processed/store_hours.csv
  ../starbucks_archive/data/processed/req_sequence_points.csv, archived_postings.csv
Writes: outputs/tables/*.csv, outputs/charts/*.png (+ .csv), outputs/national_tests_results.json

Every metric is descriptive (one cross-section) unless it is explicitly built from
requisition creation dates or archive data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT.parent
sys.path.insert(0, str(PROJ / "starbucks_hiring/src"))
import charts as C  # noqa: E402  (reuse the shared chart style)

OUT_T = ROOT / "outputs/tables"
OUT_C = ROOT / "outputs/charts"
FRONTLINE = ["BARISTA", "SHIFT_SUPERVISOR"]
LEAD = ["STORE_MANAGER", "DISTRICT_MANAGER"]
MIN_CO_STORES_STATE = 50
BATCH_EXPIRED = "2026-07-04"   # frontline batch that expired at 00:00 ET on 2026-10-02, mid-scrape


def load(date: str):
    jobs = pd.read_csv(PROJ / f"starbucks_hiring/data/processed/{date}/starbucks_jobs_US.csv",
                       dtype={"store_number": str, "job_id": str, "postal_code": str})
    jobs["days_open"] = jobs["days_since_posted"].astype(float)
    jobs["req_age"] = jobs["req_age_days"].astype(float)
    retail = jobs[jobs["role_bucket"] != "NON_RETAIL"].copy()
    # Frontline postings from the batch that expired during the scrape exist only in regions
    # fetched before midnight ET; exclude them from age / count comparisons across regions.
    retail["expired_batch"] = retail["role_bucket"].isin(FRONTLINE) & (retail["posted_date"] <= BATCH_EXPIRED)
    pat = pd.read_csv(PROJ / "starbucks_hiring/outputs/tables/store_role_patterns.csv", dtype={"store_number": str})
    uni = pd.read_csv(PROJ / "starbucks_store_universe/data/processed/starbucks_store_universe.csv", dtype={"locator_id": str})
    join = pd.read_csv(PROJ / "starbucks_store_universe/data/processed/hiring_store_join.csv", dtype={"locator_id": str})
    lab = pd.read_csv(PROJ / "starbucks_labor_market/data/processed/labor_market_controls.csv")
    hours = pd.read_csv(PROJ / "starbucks_operating_data/data/processed/store_hours.csv", dtype={"locator_id": str})
    return jobs, retail, pat, uni, join, lab, hours


def spearman(a: pd.Series, b: pd.Series) -> float | None:
    m = a.notna() & b.notna()
    return round(float(a[m].rank().corr(b[m].rank())), 3) if m.sum() >= 8 else None


# --------------------------------------------------------------------------- #

def penetration(retail, pat, uni, join):
    """Test F: share of company-operated stores with postings, by state."""
    co = uni[uni["ownership_type"] == "CO"]
    j = join[join["matched"] == True].merge(pat[["store_key", "BARISTA", "SHIFT_SUPERVISOR", "STORE_MANAGER", "role_set"]],  # noqa: E712
                                            on="store_key", how="left")
    co_n = co.groupby("state").size().rename("co_stores")
    h = j.groupby("state").agg(hiring_co_stores=("locator_id", "nunique"),
                               with_supervisor=("SHIFT_SUPERVISOR", lambda x: int((x > 0).sum())),
                               with_barista=("BARISTA", lambda x: int((x > 0).sum())))
    lead = retail[retail["role_bucket"].isin(LEAD)].groupby("state").size().rename("leadership_postings")
    sm = retail[retail["role_bucket"] == "STORE_MANAGER"].groupby("state").size().rename("store_manager_postings")
    t = pd.concat([co_n, h, lead, sm], axis=1).fillna(0)
    t["pct_co_stores_hiring"] = (100 * t["hiring_co_stores"] / t["co_stores"]).round(1)
    t["pct_co_stores_supervisor_posting"] = (100 * t["with_supervisor"] / t["co_stores"]).round(1)
    t["leadership_postings_per_100_co_stores"] = (100 * t["leadership_postings"] / t["co_stores"]).round(2)
    t["store_manager_postings_per_100_co_stores"] = (100 * t["store_manager_postings"] / t["co_stores"]).round(2)
    t = t.reset_index().rename(columns={"index": "state"})
    nat = {"co_stores": int(co_n.sum()), "hiring_co_stores_matched": int(j["locator_id"].nunique()),
           "pct_co_stores_hiring": round(100 * j["locator_id"].nunique() / co_n.sum(), 1),
           "pct_co_stores_supervisor_posting": round(100 * (j["SHIFT_SUPERVISOR"] > 0).sum() / co_n.sum(), 1),
           "pct_co_stores_barista_posting": round(100 * (j["BARISTA"] > 0).sum() / co_n.sum(), 1),
           "leadership_postings_per_100_co_stores": round(100 * retail["role_bucket"].isin(LEAD).sum() / co_n.sum(), 2),
           "hiring_stores_not_in_locator": int((join["matched"] == False).sum()),  # noqa: E712
           "join_match_rate_pct": round(100 * join["matched"].mean(), 1)}
    return t, nat


def persistence(retail):
    """Test C: requisition age (creation date, not reset by reposting) and reposting, by role."""
    r = retail.copy()
    g = r.groupby("role_bucket")
    t = pd.DataFrame({
        "postings": g.size(),
        "median_posting_age_days": g["days_open"].median(),
        "median_requisition_age_days": g["req_age"].median(),
        "pct_requisitions_over_60d": g["req_age"].apply(lambda x: round(100 * (x > 60).mean(), 1)),
        "pct_requisitions_over_90d": g["req_age"].apply(lambda x: round(100 * (x > 90).mean(), 1)),
        "pct_requisitions_over_180d": g["req_age"].apply(lambda x: round(100 * (x > 180).mean(), 1)),
        "pct_reposted": g["reposted_requisition"].apply(lambda x: round(100 * x.astype(bool).mean(), 1)),
        "pct_in_expired_jul4_batch": g["expired_batch"].apply(lambda x: round(100 * x.mean(), 1)),
    }).reset_index()
    return t


def nonstandard(pat, join):
    """Test A: stores off the standard 1 barista + 1 supervisor pair, split by likely explanation."""
    p = pat.merge(join[["store_key", "matched"]], on="store_key", how="left")
    std = (p["role_set"] == "BARISTA + SHIFT_SUPERVISOR") & (p["BARISTA"] == 1) & (p["SHIFT_SUPERVISOR"] == 1)
    special = p["store_name"].fillna("").str.contains(r"RESERVE|ROASTERY|MACY|AIRPORT|AIRPT|TERMINAL|STADIUM|UNIVERSITY|CAMPUS|HOSPITAL",
                                                     case=False) | p["store_key"].str.startswith("addr:")
    p["pattern_class"] = np.select(
        [std, ~p["matched"].fillna(False).astype(bool), special,
         p["flag_same_role_duplicate"] | p["flag_3plus_role_types"],
         p["role_set"].isin(["SHIFT_SUPERVISOR", "BARISTA"])],
        ["standard pair", "not in store locator (new/closed/temporarily closed?)", "special format (Reserve, campus, airport…)",
         "ordinary store: duplicates or 3+ roles", "ordinary store: only one frontline role"],
        default="ordinary store: other combination")
    return p


def requisition_volume(jobs):
    """2026 requisition creation curve from live data + 2024/2025 points from the archive."""
    j = jobs[jobs["job_id"].astype(str).str.fullmatch(r"\d{9}")].copy()
    j["yy"] = j["job_id"].str[:2].astype(int)
    j["seq"] = j["job_id"].str[2:].astype(int)
    j = j[j["yy"] == 26].dropna(subset=["req_created_date"])
    cur = j.groupby("req_created_date")["seq"].max().cummax().reset_index()
    cur["year"] = 2026
    cur = cur.rename(columns={"req_created_date": "date"})
    pts_path = PROJ / "starbucks_archive/data/processed/req_sequence_points.csv"
    hist = pd.DataFrame(columns=["date", "seq", "year"])
    if pts_path.exists():
        p = pd.read_csv(pts_path)
        p = p[p["yy"].isin([24, 25])]
        hist = p.rename(columns={"created": "date"}).assign(year=2000 + p["yy"])[["date", "seq", "year"]]
    out = pd.concat([cur[["date", "seq", "year"]], hist], ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    out["doy"] = out["date"].dt.dayofyear
    return out


def ytd_at(curve: pd.DataFrame, year: int, doy: int) -> float | None:
    """Requisitions created by day-of-year `doy` (upper envelope, linear interpolation)."""
    c = curve[curve["year"] == year].sort_values("doy")
    if len(c) < 3 or doy < c["doy"].min() or doy > c["doy"].max():
        return None
    env = c.groupby("doy")["seq"].max().cummax()
    return float(np.interp(doy, env.index.values, env.values))


# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot-date", default="2026-10-01")
    args = ap.parse_args()
    OUT_T.mkdir(parents=True, exist_ok=True)
    OUT_C.mkdir(parents=True, exist_ok=True)
    C.BANNER, C.TABLE_DIR = "", OUT_T
    jobs, retail, pat, uni, join, lab, hours = load(args.snapshot_date)
    res: dict = {"snapshot_date": args.snapshot_date}

    # ---- F: penetration ----------------------------------------------------
    pen, res["penetration"] = penetration(retail, pat, uni, join)
    pen = pen.merge(lab, on="state", how="left")
    pen.to_csv(OUT_T / "state_penetration_leadership_controls.csv", index=False)
    big = pen[pen["co_stores"] >= MIN_CO_STORES_STATE]

    # ---- B: leadership ------------------------------------------------------
    res["leadership"] = {
        "store_manager_postings": int((retail["role_bucket"] == "STORE_MANAGER").sum()),
        "district_manager_postings": int((retail["role_bucket"] == "DISTRICT_MANAGER").sum()),
        "states_min_co_stores": MIN_CO_STORES_STATE,
        "spearman_leadership_intensity_vs_unemployment": spearman(big["leadership_postings_per_100_co_stores"], big["unemployment_rate"]),
        "spearman_leadership_intensity_vs_lsr_employment_growth": spearman(big["leadership_postings_per_100_co_stores"], big["lsr_employment_yoy_pct"]),
        "spearman_leadership_intensity_vs_min_wage": spearman(big["leadership_postings_per_100_co_stores"], big["binding_statewide_minimum_wage"]),
        "spearman_penetration_vs_unemployment": spearman(big["pct_co_stores_hiring"], big["unemployment_rate"]),
    }
    d = big.nlargest(15, "leadership_postings_per_100_co_stores")[
        ["state", "co_stores", "leadership_postings", "leadership_postings_per_100_co_stores", "unemployment_rate"]].copy()
    d["text"] = d.apply(lambda r: f"{r.leadership_postings_per_100_co_stores:.2f}  ({int(r.leadership_postings)} of {int(r.co_stores)} stores)", axis=1)
    C._hbar(d, "state", "leadership_postings_per_100_co_stores",
            "Store- and district-manager postings per 100 company-operated stores",
            f"Top 15 states with ≥ {MIN_CO_STORES_STATE} company-operated stores · denominator: Starbucks store locator (2026-09-26)",
            OUT_C / "T1_leadership_postings_per_100_stores_by_state.png", "{:.2f}",
            ref=res["penetration"]["leadership_postings_per_100_co_stores"],
            ref_label=f"U.S. {res['penetration']['leadership_postings_per_100_co_stores']:.2f}", text_col="text",
            note="Small counts: a state with ~150 stores moves ~0.7 per 100 for each additional posting.")
    C._table(d, OUT_C, "T1_leadership_postings_per_100_stores_by_state.csv")

    # ---- C: persistence -----------------------------------------------------
    per = persistence(retail)
    per.to_csv(OUT_T / "persistence_by_role.csv", index=False)
    res["persistence_by_role"] = per.set_index("role_bucket").to_dict(orient="index")
    sm = retail[retail["role_bucket"] == "STORE_MANAGER"]
    res["store_manager_requisition_age"] = {
        "median": float(sm["req_age"].median()) if len(sm) else None,
        "pct_over_90d": round(100 * (sm["req_age"] > 90).mean(), 1) if len(sm) else None,
        "pct_reposted": round(100 * sm["reposted_requisition"].astype(bool).mean(), 1) if len(sm) else None}
    d = per[["role_bucket", "pct_requisitions_over_90d", "postings"]].copy()
    d["role"] = d["role_bucket"].str.replace("_", " ").str.title().str.replace("Other Retail", "Other in-store (Reserve)")
    d["text"] = d.apply(lambda r: f"{r.pct_requisitions_over_90d:.1f}%  ({round(r.pct_requisitions_over_90d * r.postings / 100):,.0f} of {r.postings:,})", axis=1)
    C._hbar(d, "role", "pct_requisitions_over_90d", "Share of open requisitions created more than 90 days ago",
            "Requisition age = fetch date − requisition creation date (not reset by re-posting)",
            OUT_C / "T2_requisitions_over_90_days_by_role.png", "{:.1f}%", text_col="text",
            note="Barista and shift-supervisor requisitions expire 90 days after posting and are never re-posted, hence 0%.")
    C._table(d, OUT_C, "T2_requisitions_over_90_days_by_role.csv")

    # Requisition-age histogram for store managers
    if len(sm):
        import matplotlib.pyplot as plt
        bins = list(range(0, int(sm["req_age"].max()) + 15, 14))
        cnt = pd.cut(sm["req_age"], bins=bins, right=False).value_counts().sort_index()
        dd = pd.DataFrame({"req_age_from": bins[:-1], "store_manager_postings": cnt.values})
        C._table(dd, OUT_C, "T3_store_manager_requisition_age.csv")
        fig, ax = plt.subplots(figsize=(8, 3.6))
        ax.bar(dd["req_age_from"] + 7, dd["store_manager_postings"], width=12.5, color=C.BLUE, zorder=2)
        ax.grid(axis="x", visible=False)
        ax.set_xlabel("Days since the requisition was created")
        ax.set_ylabel("Store-manager postings")
        ax.set_title("How long open store-manager requisitions have existed")
        C._finish(fig, ax, OUT_C / "T3_store_manager_requisition_age.png",
                  f"n = {len(sm)} · median {sm['req_age'].median():.0f} days · {res['store_manager_requisition_age']['pct_reposted']}% re-posted")

    # ---- A: non-standard stores ----------------------------------------------
    p = nonstandard(pat, join)
    p.to_csv(OUT_T / "store_pattern_classes.csv", index=False)
    cls = p["pattern_class"].value_counts().rename_axis("pattern_class").reset_index(name="stores")
    cls["pct_of_hiring_stores"] = (100 * cls["stores"] / cls["stores"].sum()).round(1)
    cls.to_csv(OUT_T / "pattern_class_counts.csv", index=False)
    res["pattern_classes"] = cls.set_index("pattern_class")["pct_of_hiring_stores"].to_dict()
    cls["label"] = cls["pattern_class"].map({
        "standard pair": "Standard pair (1 barista + 1 supervisor)",
        "ordinary store: only one frontline role": "Only one frontline role",
        "ordinary store: duplicates or 3+ roles": "Same-role duplicates",
        "not in store locator (new/closed/temporarily closed?)": "Not in store locator",
        "special format (Reserve, campus, airport…)": "Special format (Reserve, campus…)",
        "ordinary store: other combination": "Other combination"}).fillna(cls["pattern_class"])
    cls["text"] = cls.apply(lambda r: f"{r.stores:,}  ({r.pct_of_hiring_stores:.1f}%)", axis=1)
    C._hbar(cls, "label", "stores", "Hiring stores by posting pattern",
            f"n = {len(p):,} stores with at least one retail posting",
            OUT_C / "T4_store_pattern_classes.png", "{:,.0f}", text_col="text",
            note="Classes are assigned in order: standard pair first, so 'not in store locator' counts only non-standard stores.")
    C._table(cls, OUT_C, "T4_store_pattern_classes.csv")
    ord_dev = p["pattern_class"] == "ordinary store: duplicates or 3+ roles"
    st = p.groupby("state").agg(hiring_stores=("store_key", "size"), ordinary_deviation=("pattern_class", lambda x: int((x == "ordinary store: duplicates or 3+ roles").sum())))
    st["pct_ordinary_deviation"] = (100 * st["ordinary_deviation"] / st["hiring_stores"]).round(2)
    st = st[st["hiring_stores"] >= 40].reset_index().merge(lab, on="state", how="left")
    st.to_csv(OUT_T / "state_nonstandard_rates.csv", index=False)
    res["nonstandard"] = {"ordinary_store_deviation_pct": round(100 * ord_dev.mean(), 2),
                          "spearman_state_deviation_vs_unemployment": spearman(st["pct_ordinary_deviation"], st["unemployment_rate"])}

    # ---- E: posted hours vs hiring pattern -----------------------------------
    hh = hours.merge(join[join["matched"] == True][["locator_id", "store_key"]], on="locator_id", how="left")  # noqa: E712
    hh = hh.merge(p[["store_key", "pattern_class"]], on="store_key", how="left")
    hh["group"] = hh["pattern_class"].fillna("company-operated, no active posting")
    e = hh.groupby("group")["weekly_hours"].agg(["count", "median", "mean"]).round(1).reset_index()
    e.to_csv(OUT_T / "hours_by_hiring_pattern.csv", index=False)
    res["hours_by_pattern"] = e.set_index("group").to_dict(orient="index")

    # ---- Requisition volume trend ---------------------------------------------
    # 2026 curve comes from requisitions still open on the snapshot date. It is exact only
    # where nearly all requisitions created are still open: from DENSE_FROM onward (weekly
    # sequence ranges are contiguous there). Earlier 2026 values are lower bounds.
    # 2024/2025 values come from sampled archived pages, so their envelope is a lower bound too.
    DENSE_FROM = 187   # 2026-07-06
    curve = requisition_volume(jobs)
    curve.to_csv(OUT_T / "requisition_sequence_curve.csv", index=False)
    cmp_days = {"Jul 19": 200, "Jul 30": 211, "Sep 30": 273}
    rv = {"note": "2026 exact from day 187 (Jul 6); 2024/2025 archive-sample envelopes are lower bounds",
          "dense_from_doy_2026": DENSE_FROM}
    for lab_, doy in cmp_days.items():
        v = {y: ytd_at(curve, y, doy) for y in (2024, 2025, 2026)}
        rv[lab_] = {"doy": doy, **{f"ytd_{y}": (round(x) if x else None) for y, x in v.items()},
                    "pct_2026_vs_2025": round(100 * (v[2026] / v[2025] - 1), 1) if v[2026] and v[2025] else None,
                    "pct_2026_vs_2024": round(100 * (v[2026] / v[2024] - 1), 1) if v[2026] and v[2024] else None}
    c26 = curve[curve["year"] == 2026].groupby("doy")["seq"].max().cummax()
    c24 = curve[curve["year"] == 2024].groupby("doy")["seq"].max().cummax()
    q3_26 = float(np.interp(273, c26.index, c26.values) - np.interp(DENSE_FROM, c26.index, c26.values))
    q3_24 = float(np.interp(273, c24.index, c24.values) - np.interp(DENSE_FROM, c24.index, c24.values))
    rv["created_jul6_to_sep30"] = {"2026": round(q3_26), "2024": round(q3_24), "pct_2026_vs_2024": round(100 * (q3_26 / q3_24 - 1), 1)}
    res["requisition_volume"] = rv
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for y, col in ((2024, C.GRAY), (2025, C.BLUE_LIGHT)):
        g = curve[curve["year"] == y]
        env = g.groupby("doy")["seq"].max().cummax()
        ax.plot(env.index, env.values, color=col, linewidth=1.5, zorder=2, label=f"{y} (archived pages, n={len(g)})")
        ax.scatter(g["doy"], g["seq"], s=10, color=col, zorder=2, edgecolor=C.SURFACE, linewidth=0.5)
    dense = c26[c26.index >= DENSE_FROM]
    ax.plot(dense.index, dense.values, color=C.BLUE, linewidth=2.4, zorder=3, label="2026 (live data, exact from Jul 6)")
    for doy, txt in ((211, "Jul 30"), (273, "Sep 30")):
        ax.axvline(doy, color=C.GRID, linewidth=1, zorder=1)
        ax.text(doy, ax.get_ylim()[1] * 0.02, f" {txt}", color=C.INK_2, fontsize=8)
    ax.set_xlabel("Day of year the requisition was created")
    ax.set_ylabel("Requisitions created year-to-date")
    ax.legend(frameon=False, loc="upper left", fontsize=8.5)
    ax.set_title("Starbucks requisitions created year-to-date")
    j30 = rv["Jul 30"]
    _finish_sub = (f"By Jul 30: 2026 {j30['ytd_2026']:,} vs 2025 ≥ {j30['ytd_2025']:,} ({j30['pct_2026_vs_2025']}%) "
                   f"vs 2024 {j30['ytd_2024']:,}") if j30.get("ytd_2025") and j30.get("ytd_2026") else ""
    C._finish(fig, ax, OUT_C / "T5_requisitions_created_ytd.png", _finish_sub,
              note="Requisition number = YY + sequence; sequence rises monotonically with creation date (Spearman 1.0). All Starbucks requisitions incl. corporate.")
    C._table(curve, OUT_C, "T5_requisitions_created_ytd.csv")

    # ---- Archive: store-manager share of postings by crawl burst ---------------
    ap_ = PROJ / "starbucks_archive/data/processed/archived_postings.csv"
    if ap_.exists():
        a = pd.read_csv(ap_, dtype=str)
        a["month"] = a["first_capture"].str[:6]
        b = a.groupby("month").agg(postings=("position_id", "size"),
                                   store_manager=("role", lambda r: int((r == "STORE_MANAGER").sum())))
        # 2024-era URLs do not carry role slugs for manager postings, so start in 2025.
        b = b[(b["postings"] >= 5000) & (b.index >= "202501")].reset_index()
        b["store_manager_share_pct"] = (100 * b["store_manager"] / b["postings"]).round(2)
        now_share = round(100 * (retail["role_bucket"] == "STORE_MANAGER").sum() / len(retail), 2)
        b = pd.concat([b, pd.DataFrame([{"month": "Snapshot\nOct 1 2026", "postings": len(retail),
                                         "store_manager": int((retail["role_bucket"] == "STORE_MANAGER").sum()),
                                         "store_manager_share_pct": now_share}])], ignore_index=True)
        b["label"] = b["month"].map(lambda m: m if not m[:6].isdigit() else pd.to_datetime(m, format="%Y%m").strftime("%b %Y"))
        C._table(b, OUT_C, "T6_store_manager_share_by_crawl_burst.csv")
        res["archive_store_manager_share"] = b.set_index("label")["store_manager_share_pct"].to_dict()
        fig, ax = plt.subplots(figsize=(9, 3.8))
        ax.bar(range(len(b)), b["store_manager_share_pct"], color=[C.BLUE_LIGHT] * (len(b) - 1) + [C.BLUE], width=0.6, zorder=2)
        ax.set_xticks(range(len(b)), b["label"], rotation=0, fontsize=8.5)
        ax.grid(axis="x", visible=False)
        for x, v in enumerate(b["store_manager_share_pct"]):
            ax.text(x, v, f"{v:.1f}%", ha="center", va="bottom", fontsize=8.5, color=C.INK_2)
        ax.set_ylabel("% of postings")
        ax.set_title("Store-manager share of postings over time")
        C._finish(fig, ax, OUT_C / "T6_store_manager_share_by_crawl_burst.png",
                  "Wayback crawl bursts with ≥ 5,000 newly captured postings vs. today's snapshot",
                  note="Archive coverage depends on crawler schedules; shares are more comparable than counts. Indicative only.")

    (ROOT / "outputs/national_tests_results.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
