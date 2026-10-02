"""Historical store-level hiring from Internet Archive captures of Starbucks careers job pages.

    python _research_archive/starbucks_hiring_archive/src/archive_hiring.py

Input (read only): ../_research_archive/starbucks_archive/data/processed/archived_postings.csv
  155,626 distinct job postings (position IDs) seen in Wayback captures of apply.starbucks.com/careers/job/...,
  with role, store number and first/last capture time parsed from the URL slug.
Linking: store number -> Starbucks store-locator ID (store number is in the locator `website` URL, all snapshots)
  -> Advan store (04_operating_hours/store_hours_panel.csv: locator -> Advan store_id, closure status, metro).

Key issue: capture volume is driven by the crawler (bursts), not by Starbucks' hiring. So every measure is
*relative within a period*:
  role mix        share of each role among postings first captured in the fiscal quarter
  store intensity store's share of the period's captured postings x number of linked stores (1.0 = average store)
Tests:
  A. Role mix over time (is the store-manager share rising?)
  B. Do stores whose traffic grew FY26 vs FY25 show rising relative hiring intensity? (metro FE OLS)
  C. Did the Oct-2025 closed stores hire differently before closure?
  D. Repeat store-manager postings at the same store (manager turnover) vs traffic growth
Outputs: _research_archive/starbucks_hiring_archive/{data,outputs}/ and pitch_data/03_archive_hiring/
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
HERE = ROOT / "_research_archive/starbucks_hiring_archive"
LAB = ROOT / "pitch_data"
sys.path.insert(0, str(LAB / "src"))
from hiring_pressure import ols_fe  # noqa: E402
from lab import save_json  # noqa: E402

ARCHIVE = ROOT / "_research_archive/starbucks_archive/data/processed/archived_postings.csv"
STORE_ROLES = ["BARISTA", "SHIFT_SUPERVISOR", "STORE_MANAGER"]
# Fiscal years with usable crawl coverage (captures from Feb 2024 on are dense enough; FY24 = partial)
FY_KEEP = ["FY25", "FY26"]


def fiscal(ts: pd.Series) -> pd.DataFrame:
    t = pd.to_datetime(ts.astype(str).str[:8])
    fy = t.dt.year + (t.dt.month >= 10).astype(int)
    q = ((t.dt.month - 10) % 12) // 3 + 1
    return pd.DataFrame({"date": t, "fy": "FY" + (fy % 100).astype(str), "fq": "FY" + (fy % 100).astype(str) + " Q" + q.astype(str)})


def store_number_map() -> pd.DataFrame:
    """store_number -> locator_id from every store-locator snapshot (website URL /store/<number>-<id>/)."""
    rx = re.compile(r"/store/(\d+)-(\d+)/")
    rows = []
    for f in sorted((LAB / "data/raw/alltheplaces").glob("*.geojson")):
        for line in f.read_text().splitlines():
            line = line.strip().rstrip(",")
            if not line.startswith('{"type": "Feature"'):
                continue
            try:
                p = json.loads(line)["properties"]
            except json.JSONDecodeError:
                continue
            m = rx.search(p.get("website") or "")
            if m:
                rows.append({"store_number": int(m.group(1)), "locator_id": str(p.get("ref")), "snapshot": f.stem[-19:-9]})
    m = pd.DataFrame(rows).sort_values("snapshot").drop_duplicates("store_number", keep="last")
    return m[["store_number", "locator_id"]]


def main() -> None:
    (HERE / "data").mkdir(parents=True, exist_ok=True)
    (HERE / "outputs").mkdir(parents=True, exist_ok=True)
    out3 = LAB / "03_archive_hiring"
    out3.mkdir(parents=True, exist_ok=True)

    a = pd.read_csv(ARCHIVE, low_memory=False)
    a = a.join(fiscal(a["first_capture"]))
    a = a[a["role"].isin(STORE_ROLES + ["DISTRICT_MANAGER"])]

    # A. role mix by fiscal quarter (all postings, linked or not)
    mix = a.groupby(["fq", "role"]).size().unstack(fill_value=0)
    mix["total"] = mix.sum(axis=1)
    mix = mix[mix["total"] >= 1000]
    for r in STORE_ROLES + ["DISTRICT_MANAGER"]:
        mix[f"{r.lower()}_share_pct"] = (100 * mix[r] / mix["total"]).round(2)
    mix.reset_index().to_csv(HERE / "outputs/role_mix_by_fiscal_quarter.csv", index=False)

    # Link to locator -> Advan
    smap = store_number_map()
    hp = pd.read_csv(LAB / "04_operating_hours/store_hours_panel.csv", dtype={"locator_id": str, "store_id": str, "msa": str})
    hp = hp[hp["store_id"].notna()][["locator_id", "store_id", "msa", "status", "close_date", "weekly_hours_2025-08"]]
    s = a[a["store_number"].notna()].copy()
    s["store_number"] = s["store_number"].astype(int)
    s = s.merge(smap, on="store_number", how="left").merge(hp, on="locator_id", how="left")
    link = {"postings_with_store_number": len(s), "linked_to_locator": int(s["locator_id"].notna().sum()),
            "linked_to_advan": int(s["store_id"].notna().sum()),
            "distinct_store_numbers": int(s["store_number"].nunique()),
            "distinct_advan_stores": int(s["store_id"].nunique())}
    s.to_csv(HERE / "data/archived_postings_linked.csv", index=False)

    # Store x fiscal year relative intensity (company-operated stores known to Advan via the Aug-2025 locator)
    base = hp.drop_duplicates("store_id").copy()
    base["closed_oct25"] = pd.to_datetime(base["close_date"]).between("2025-09-01", "2025-11-30")
    ls = s[s["store_id"].notna()]
    cnt = ls.groupby(["store_id", "fy"]).size().unstack(fill_value=0)
    mgr = ls[ls["role"] == "STORE_MANAGER"].groupby(["store_id", "fy"]).size().unstack(fill_value=0)
    fq_cnt = ls.groupby(["store_id", "fq"]).size().unstack(fill_value=0)
    st = base.set_index("store_id")
    for fy in ["FY24", "FY25", "FY26"]:
        st[f"postings_{fy}"] = cnt[fy].reindex(st.index).fillna(0) if fy in cnt else 0
        st[f"mgr_postings_{fy}"] = mgr[fy].reindex(st.index).fillna(0) if fy in mgr else 0
    # FY26 universe excludes closed stores; FY25 universe = all in Aug-2025 locator
    for fy in ["FY24", "FY25", "FY26"]:
        alive = st.index if fy != "FY26" else st.index[st["status"].eq("open")]
        st.loc[alive, f"intensity_{fy}"] = st.loc[alive, f"postings_{fy}"] / st.loc[alive, f"postings_{fy}"].mean()
    good_q = mix.index[mix["total"] >= 3000]
    st["quarters_with_postings"] = (fq_cnt.reindex(columns=[q for q in good_q if q in fq_cnt.columns]) > 0).sum(axis=1).reindex(st.index).fillna(0)
    st["quarters_observed"] = len([q for q in good_q if q in fq_cnt.columns])

    # Traffic by fiscal year from the Advan store-month panel (Oct-Sep; FY26 through latest week)
    sm = pd.read_parquet(LAB / "01_store_panel/store_month_visits.parquet")
    sm["m"] = pd.PeriodIndex(sm["month"], freq="M")
    sm["fy"] = "FY" + ((sm["m"].dt.year + (sm["m"].dt.month >= 10).astype(int)) % 100).astype(str)
    sm = sm[sm["fy"].isin(["FY25", "FY26"])]
    # match months: FY26 has data through Sep-2026; use the same months in FY25
    months26 = sorted(sm.loc[sm["fy"] == "FY26", "m"].dt.month.unique())
    sm = sm[sm["m"].dt.month.isin(months26)]
    v = sm.groupby(["ID_STORE", "fy"]).apply(lambda g: g["visits"].sum() / g["weeks"].sum(), include_groups=False).unstack()
    st = st.join(v.rename(columns={"FY25": "visits_pw_FY25", "FY26": "visits_pw_FY26"}))
    st["traffic_growth_fy26_pct"] = 100 * (st["visits_pw_FY26"] / st["visits_pw_FY25"] - 1)
    st["postings_per_1000_visits_FY25"] = 1000 * st["postings_FY25"] / st["visits_pw_FY25"]
    st["postings_per_1000_visits_FY26"] = 1000 * st["postings_FY26"] / st["visits_pw_FY26"]
    st["d_log_intensity"] = np.log((st["intensity_FY26"] + 0.25) / (st["intensity_FY25"] + 0.25))
    st["d_log_postings_per_visit"] = np.log((st["postings_FY26"] + 1) / st["visits_pw_FY26"]) - np.log((st["postings_FY25"] + 1) / st["visits_pw_FY25"])
    st = st.reset_index()
    st.to_csv(HERE / "data/store_fiscal_year_hiring.csv", index=False)

    # B. traffic growth vs change in hiring intensity (surviving stores, metro FE)
    sv = st[st["status"].eq("open")].dropna(subset=["traffic_growth_fy26_pct", "msa"]).copy()
    sv = sv[sv["traffic_growth_fy26_pct"].between(*sv["traffic_growth_fy26_pct"].quantile([0.01, 0.99]))]
    sv["growth"] = sv["traffic_growth_fy26_pct"]
    sv["log_visits"] = np.log(sv["visits_pw_FY25"])
    xs = ["growth", "log_visits"]
    reg = pd.DataFrame([ols_fe(sv, y, xs) for y in ["d_log_intensity", "d_log_postings_per_visit", "intensity_FY26",
                                                     "quarters_with_postings"]])
    reg.to_csv(HERE / "outputs/traffic_growth_vs_archive_hiring.csv", index=False)
    sv["cohort"] = pd.cut(sv["growth"], [-1e9, 0, 5, 10, 1e9], labels=["< 0%", "0–5%", "5–10%", "> 10%"])
    coh = sv.groupby("cohort", observed=True).agg(stores=("store_id", "size"), median_growth=("growth", "median"),
                                                  intensity_FY25=("intensity_FY25", "mean"), intensity_FY26=("intensity_FY26", "mean"),
                                                  postings_per_1000_visits_FY25=("postings_per_1000_visits_FY25", "mean"),
                                                  postings_per_1000_visits_FY26=("postings_per_1000_visits_FY26", "mean")).round(3).reset_index()
    coh["intensity_change"] = (coh["intensity_FY26"] - coh["intensity_FY25"]).round(3)
    coh.to_csv(HERE / "outputs/archive_hiring_by_growth_cohort.csv", index=False)

    # C. closed vs survivors before closure (FY24 + FY25 relative intensity, manager postings)
    pre = st[st["closed_oct25"] | st["status"].eq("open")]
    cl = pre.groupby("closed_oct25").agg(stores=("store_id", "size"), intensity_FY24=("intensity_FY24", "mean"),
                                         intensity_FY25=("intensity_FY25", "mean"),
                                         quarters_with_postings=("quarters_with_postings", "mean")).round(3)
    # How uniform is the frontline pipeline? postings per store-quarter, and role mix per store-quarter
    sq = ls[ls["role"].isin(["BARISTA", "SHIFT_SUPERVISOR"])].groupby(["store_id", "fq"])["role"].agg(["size", "nunique"])
    uniform = {"store_quarters": len(sq), "mean_postings_per_store_quarter": round(float(sq["size"].mean()), 2),
               "pct_exactly_one_barista_and_one_supervisor": round(100 * float(((sq["size"] == 2) & (sq["nunique"] == 2)).mean()), 1),
               "pct_more_than_2": round(100 * float((sq["size"] > 2).mean()), 1),
               "store_fy_postings_sd_FY25": round(float(st["postings_FY25"].std()), 2),
               "store_fy_postings_mean_FY25": round(float(st["postings_FY25"].mean()), 2)}
    city = manager_by_city(a, sv)

    # Aggregate: postings per 1,000 weekly visits, FY25 vs FY26, same surviving stores
    agg = {"same_store_postings_FY25": int(sv["postings_FY25"].sum()), "same_store_postings_FY26": int(sv["postings_FY26"].sum()),
           "note": "Totals depend on crawl volume; compare only relative measures."}

    res = {"linking": link, "role_mix_by_fq": mix[[c for c in mix.columns if c.endswith("_pct")] + ["total"]].reset_index().to_dict(orient="records"),
           "traffic_growth_regressions": {r["outcome"]: {"b_per_1pp_growth": r["b_growth"], "se": r["se_growth"], "t": r["t_growth"],
                                                         "n": r["n"], "outcome_mean": r["outcome_mean"]} for r in reg.to_dict(orient="records")},
           "cohorts": coh.to_dict(orient="records"), "closed_vs_survivors_pre": cl.reset_index().to_dict(orient="records"),
           "aggregate": agg, "frontline_uniformity": uniform, "manager_by_city": city, "spearman_growth_vs_d_intensity": round(float(sv["growth"].rank().corr(sv["d_log_intensity"].rank())), 3)}
    save_json(res, HERE / "outputs/results.json")
    save_json(res, out3 / "results.json")
    print(json.dumps(link, indent=1))
    print(mix[[c for c in mix.columns if c.endswith("_pct")] + ["total"]].to_string())
    print(reg[["outcome", "n", "b_growth", "se_growth", "t_growth", "outcome_mean"]].to_string(index=False))
    print(coh.to_string(index=False))
    print(cl.to_string())
    print(json.dumps(uniform, indent=1))
    print(json.dumps(city, indent=1))
    chart(mix, coh)


STATES = {"AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas", "CA": "california", "CO": "colorado",
          "CT": "connecticut", "DE": "delaware", "DC": "district-of-columbia", "FL": "florida", "GA": "georgia", "HI": "hawaii",
          "ID": "idaho", "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas", "KY": "kentucky", "LA": "louisiana",
          "ME": "maine", "MD": "maryland", "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
          "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada", "NH": "new-hampshire", "NJ": "new-jersey",
          "NM": "new-mexico", "NY": "new-york", "NC": "north-carolina", "ND": "north-dakota", "OH": "ohio", "OK": "oklahoma",
          "OR": "oregon", "PA": "pennsylvania", "RI": "rhode-island", "SC": "south-carolina", "SD": "south-dakota",
          "TN": "tennessee", "TX": "texas", "UT": "utah", "VT": "vermont", "VA": "virginia", "WA": "washington",
          "WV": "west-virginia", "WI": "wisconsin", "WY": "wyoming"}


def slugify(x: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(x).lower()).strip("-")


def manager_by_city(a: pd.DataFrame, sv: pd.DataFrame) -> dict:
    """Store-manager postings carry a city, not a store number: test them at city level.
    Outcome: city's share of the fiscal year's manager postings relative to its share of stores (1 = proportional),
    which nets out crawl volume. Change FY25 -> FY26 vs the city's FY26 traffic growth (state FE)."""
    m = a[a["role"] == "STORE_MANAGER"].copy()
    m = m[m["fy"].isin(["FY25", "FY26"])]
    m["tail"] = m["slug"].str.replace(r"-united-states$", "", regex=True)
    panel = pd.read_csv(LAB / "01_store_panel/store_panel.csv", dtype={"store_id": str})[["store_id", "city", "state"]]
    g = sv.merge(panel, on="store_id")
    g["city_key"] = g["city"].map(slugify) + "-" + g["state"].map(STATES).fillna("?")
    keys = set(g["city_key"])
    def match(t: str):
        parts = t.split("-")
        for i in range(len(parts) - 1):
            k = "-".join(parts[i:])
            if k in keys:
                return k
        return None
    m["city_key"] = m["tail"].map(match)
    matched_pct = round(100 * float(m["city_key"].notna().mean()), 1)
    c = g.groupby("city_key").agg(stores=("store_id", "size"), state=("state", "first"),
                                  v25=("visits_pw_FY25", "sum"), v26=("visits_pw_FY26", "sum")).reset_index()
    c["growth"] = 100 * (c["v26"] / c["v25"] - 1)
    cnt = m.groupby(["city_key", "fy"]).size().unstack(fill_value=0).reindex(columns=["FY25", "FY26"], fill_value=0)
    c = c.join(cnt, on="city_key").fillna({"FY25": 0, "FY26": 0})
    for fy in ["FY25", "FY26"]:
        c[f"rel_{fy}"] = (c[fy] / c[fy].sum()) / (c["stores"] / c["stores"].sum())
    c = c[c["stores"] >= 5].copy()
    c["d_rel"] = c["rel_FY26"] - c["rel_FY25"]
    c["log_stores"] = np.log(c["stores"])
    c.to_csv(HERE / "outputs/manager_postings_by_city.csv", index=False)
    r = ols_fe(c.rename(columns={"state": "msa"}), "d_rel", ["growth", "log_stores"])
    c["cohort"] = pd.cut(c["growth"], [-1e9, 0, 5, 10, 1e9], labels=["< 0%", "0–5%", "5–10%", "> 10%"])
    coh = c.groupby("cohort", observed=True).agg(cities=("city_key", "size"), stores=("stores", "sum"),
                                                rel_FY25=("rel_FY25", "mean"), rel_FY26=("rel_FY26", "mean")).round(3).reset_index()
    return {"manager_postings_FY25_FY26": len(m), "matched_to_city_pct": matched_pct, "cities_with_5plus_stores": len(c),
            "regression_d_rel_on_growth_stateFE": {"b_per_1pp": r["b_growth"], "se": r["se_growth"], "t": r["t_growth"], "n": r["n"]},
            "spearman_growth_vs_rel_FY26": round(float(c["growth"].rank().corr(c["rel_FY26"].rank())), 3),
            "spearman_growth_vs_d_rel": round(float(c["growth"].rank().corr(c["d_rel"].rank())), 3),
            "cohorts": coh.to_dict(orient="records")}


def chart(mix: pd.DataFrame, coh: pd.DataFrame) -> None:
    sys.path.insert(0, str(ROOT / "_research_archive/starbucks_hiring/src"))
    import charts as C
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4))
    ax = axes[0]
    m = mix.reset_index()
    ax.plot(range(len(m)), m["store_manager_share_pct"], color=C.BLUE, linewidth=2, zorder=2)
    thin = m["total"] < 10000
    ax.scatter(np.where(~thin)[0], m.loc[~thin, "store_manager_share_pct"], s=40, color=C.BLUE, zorder=3, label="≥ 10k captured postings")
    ax.scatter(np.where(thin)[0], m.loc[thin, "store_manager_share_pct"], s=40, facecolor=C.SURFACE, edgecolor=C.BLUE, linewidth=1.5,
               zorder=3, label="thin crawl (< 10k)")
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax.set_xticks(range(len(m)), m["fq"].str.replace(" ", "\n"), fontsize=7)
    ax.set_ylabel("% of captured store postings")
    ax.set_ylim(0, max(m["store_manager_share_pct"]) * 1.4)
    ax.set_title("Store-manager share of archived store postings", fontsize=10)
    ax = axes[1]
    x = np.arange(len(coh))
    ax.bar(x - 0.18, coh["intensity_FY25"], width=0.34, color=C.GRAY, label="FY25")
    ax.bar(x + 0.18, coh["intensity_FY26"], width=0.34, color=C.BLUE, label="FY26")
    ax.axhline(1, color=C.INK_2, linewidth=0.8, linestyle="--")
    ax.set_xticks(x, [f"{c}\n(n={n:,})" for c, n in zip(coh["cohort"], coh["stores"])], fontsize=8)
    ax.set_ylabel("relative hiring intensity (1 = avg store)")
    ax.set_title("Frontline postings per store: same at every growth rate\n(by FY26 traffic growth vs FY25)", fontsize=10)
    ax.legend(fontsize=8, frameon=False)
    ax.grid(axis="x", visible=False)
    fig.suptitle("Internet Archive hiring history (relative measures; crawl-driven coverage)", x=0.01, y=0.99, ha="left",
                 fontsize=12, fontweight="semibold")
    fig.text(0.01, 0.01, "Wayback captures of apply.starbucks.com job pages, first-capture date · company-operated stores linked via store number · Advan visits",
             fontsize=8, color=C.INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    for p in (HERE / "outputs/archive_hiring.png", LAB / "charts/03_archive_hiring.png"):
        fig.savefig(p, dpi=200)


if __name__ == "__main__":
    main()
