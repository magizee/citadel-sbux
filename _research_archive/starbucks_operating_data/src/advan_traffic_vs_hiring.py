"""Do the busiest stores show more hiring strain? (Advan traffic x national job snapshot)

    python src/advan_traffic_vs_hiring.py

Traffic: median weekly visits Jun 29 - Sep 21 2026 (Advan), expressed RELATIVE TO THE STORE'S METRO
(log visits minus the MSA median), then split into quintiles, so the comparison is busy-vs-quiet
stores within the same metro rather than city-vs-suburb.

Hiring strain per store (national snapshot 2026-10-01): same-role duplicate postings, missing a
barista or supervisor posting, number of open postings, and an open / persistent store-manager
requisition within 15 km. Special formats (Reserve, campus, airport...) are excluded.

Inputs : outputs/advan/store_visits_yoy.csv, outputs/advan/store_density_msa.csv (or Advan msa codes),
         ../starbucks_hiring/outputs/tables/store_role_patterns.csv,
         ../starbucks_store_universe/data/processed/hiring_store_join.csv,
         ../starbucks_thesis_tests/outputs/tables/store_pattern_classes.csv
Outputs: outputs/advan/traffic_vs_hiring.csv, traffic_vs_hiring_results.json, traffic_vs_hiring.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT.parent
OUT = ROOT / "outputs/advan"
sys.path.insert(0, str(PROJ / "starbucks_hiring/src"))
import charts as C  # noqa: E402

QL = ["Q1 quietest", "Q2", "Q3", "Q4", "Q5 busiest"]


def main() -> None:
    st = pd.read_csv(OUT / "store_visits_yoy.csv", dtype={"locator_id": str, "placekey": str})
    adv = pd.read_csv(ROOT / "data/processed/advan_starbucks.csv.gz", usecols=["placekey", "msa_code"], dtype=str) \
        .drop_duplicates("placekey")
    st = st.merge(adv, on="placekey", how="left")
    join = pd.read_csv(PROJ / "starbucks_store_universe/data/processed/hiring_store_join.csv", dtype={"locator_id": str})
    join = join[join["matched"] == True][["locator_id", "store_key"]]  # noqa: E712
    pat = pd.read_csv(PROJ / "starbucks_hiring/outputs/tables/store_role_patterns.csv")
    cls = pd.read_csv(PROJ / "starbucks_thesis_tests/outputs/tables/store_pattern_classes.csv")[["store_key", "pattern_class"]]
    pat = pat.merge(cls, on="store_key", how="left").rename(columns={"pattern_class": "pclass"})
    s = st.merge(join, on="locator_id", how="left").merge(
        pat[["store_key", "BARISTA", "SHIFT_SUPERVISOR", "active_postings", "flag_same_role_duplicate", "pclass"]],
        on="store_key", how="left")
    s = s[~s["pclass"].fillna("").str.startswith("special format")]
    for c in ("BARISTA", "SHIFT_SUPERVISOR", "active_postings"):
        s[c] = s[c].fillna(0)
    s["has_any_posting"] = s["store_key"].notna()
    s["same_role_duplicate"] = s["flag_same_role_duplicate"].fillna(False).astype(bool)
    s["no_barista_posting"] = s["has_any_posting"] & (s["BARISTA"] == 0)
    s["no_supervisor_posting"] = s["has_any_posting"] & (s["SHIFT_SUPERVISOR"] == 0)

    s = s[s["msa_code"].notna() & (s["v_cur"] > 0)].copy()
    s["log_v"] = np.log(s["v_cur"])
    s["traffic_vs_metro"] = s["log_v"] - s.groupby("msa_code")["log_v"].transform("median")
    s["traffic_q"] = pd.qcut(s["traffic_vs_metro"], 5, labels=QL)

    metrics = {"same_role_duplicate": "Same-role duplicate postings",
               "no_barista_posting": "No barista posting",
               "no_supervisor_posting": "No supervisor posting",
               "leadership_zone": "Manager vacancy within 15 km",
               "persistent_leadership_zone": "Persistent manager vacancy within 15 km"}
    g = s.groupby("traffic_q", observed=True)
    tab = pd.DataFrame({"stores": g.size(),
                        "median_weekly_visits": g["v_cur"].median().round(0),
                        "mean_open_postings": g["active_postings"].mean().round(3),
                        **{f"pct_{k}": g[k].mean().mul(100).round(2) for k in metrics}}).reset_index()
    tab.to_csv(OUT / "traffic_vs_hiring.csv", index=False)

    rng = np.random.default_rng(0)
    q1, q5 = s[s["traffic_q"] == QL[0]], s[s["traffic_q"] == QL[-1]]
    diffs = {}
    for k, lab in list(metrics.items()) + [("active_postings", "Open postings per store")]:
        a, b = q1[k].astype(float).to_numpy(), q5[k].astype(float).to_numpy()
        boot = [rng.choice(b, len(b)).mean() - rng.choice(a, len(a)).mean() for _ in range(2000)]
        scale = 1 if k == "active_postings" else 100
        diffs[lab] = {"busiest_minus_quietest": round(scale * (b.mean() - a.mean()), 3),
                      "ci95": [round(scale * np.percentile(boot, 2.5), 3), round(scale * np.percentile(boot, 97.5), 3)],
                      "unit": "postings" if k == "active_postings" else "percentage points",
                      "spearman_with_traffic": round(float(s["traffic_vs_metro"].rank().corr(s[k].astype(float).rank())), 3)}
    res = {"stores": len(s), "quintiles": tab.to_dict(orient="records"), "busiest_vs_quietest": diffs,
           "note": "Traffic relative to metro median. Special formats excluded. Descriptive."}
    (OUT / "traffic_vs_hiring_results.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))

    import matplotlib.pyplot as plt
    show = [("pct_same_role_duplicate", "Same-role duplicate postings"),
            ("pct_no_supervisor_posting", "No supervisor posting"),
            ("pct_no_barista_posting", "No barista posting"),
            ("pct_persistent_leadership_zone", "Persistent manager vacancy nearby")]
    fig, axes = plt.subplots(1, len(show), figsize=(11, 3.6), sharey=False)
    for ax, (col, title) in zip(axes, show):
        ax.bar(range(5), tab[col], color=[C.BLUE_LIGHT] * 4 + [C.BLUE], width=0.65, zorder=2)
        ax.set_xticks(range(5), ["Q1", "Q2", "Q3", "Q4", "Q5"], fontsize=8.5)
        ax.grid(axis="x", visible=False)
        for x_, v_ in enumerate(tab[col]):
            ax.text(x_, v_, f"{v_:.1f}", ha="center", va="bottom", fontsize=8, color=C.INK_2)
        ax.set_title(title, fontsize=10, pad=6)
        ax.set_ylabel("% of stores" if col == show[0][0] else "")
    fig.suptitle("Hiring-strain signals by store traffic (Q1 = quietest to Q5 = busiest, within metro)",
                 x=0.01, y=0.98, ha="left", fontsize=12.5, fontweight="semibold")
    fig.text(0.01, 0.01, f"n = {len(s):,} company-operated stores · traffic = Advan weekly visits Jun–Sep 2026 relative to the metro median "
             "· hiring = national job snapshot Oct 1 2026 · each panel has its own scale", fontsize=8, color=C.INK_2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.94))
    fig.savefig(OUT / "traffic_vs_hiring.png", dpi=200)


if __name__ == "__main__":
    main()
