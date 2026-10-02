"""Workstream 6 (+ light closure-risk model): were the Oct-2025 closures the low-productivity tail, and how much tail is left?

    python src/closure_productivity.py

Sample: company-operated stores in the Aug-2025 store-locator snapshot (pre-closure) matched to Advan.
  closed  = Advan close date Sep-Nov 2025 (the Oct-2025 restructuring wave, confirmed in filings)
  survivor = still open in the latest Advan week
Pre-closure features are measured on the 13 weeks ending 2025-08-25 (before the announcement):
  visits/week, YoY visits (vs same weeks 2024), Aug-2025 weekly hours, visits per operating hour, traffic percentile in metro,
  Starbucks within 1/2/5 km (open at the time), Dunkin' within 2 km, weekend-hours share.

Outputs (06_closure_productivity/):
  closed_vs_survivors.csv   medians, closed vs all survivors and vs survivors in the same metros (metro-demeaned)
  closure_risk_model.csv    logistic coefficients (standardized) + cross-validated AUC
  at_risk_open_stores.csv   currently open company-operated stores ranked by the model's closure-likeness (Sep-2026 features)
  results.json, charts/06_closure_productivity.png
Descriptive. The risk model shows which stores *resemble* the Oct-2025 closures; it is not a forecast of closures.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from lab import LAB, count_within, load_advan, locations, save_json

OUT = LAB / "06_closure_productivity"
PRE_END = pd.Timestamp("2025-08-25")
FEATS = ["log_visits", "visits_yoy_pct", "weekly_hours", "visits_per_op_hour", "traffic_pctile_in_metro",
         "log_sb2", "log_dk2", "weekend_share"]


def window(p: pd.DataFrame, end: pd.Timestamp, n: int = 13) -> pd.Series:
    weeks = pd.date_range(end=end, periods=n, freq="7D")
    x = p[p["week"].isin(weeks)].groupby("ID_STORE")["visits"].agg(["mean", "size"])
    return x[x["size"] >= 11]["mean"]


def features(base: pd.DataFrame, p: pd.DataFrame, end: pd.Timestamp, sb_open: pd.DataFrame, dk_open: pd.DataFrame,
             hours_col: str, weekend_col: str) -> pd.DataFrame:
    d = base.copy()
    cur, ly = window(p, end), window(p, end - pd.Timedelta(weeks=52))
    d = d.join(cur.rename("visits_per_week"), on="store_id").join(ly.rename("visits_ly"), on="store_id")
    d["visits_yoy_pct"] = 100 * (d["visits_per_week"] / d["visits_ly"] - 1)
    d["log_visits"] = np.log(d["visits_per_week"])
    d["weekly_hours"] = d[hours_col]
    d["visits_per_op_hour"] = d["visits_per_week"] / d["weekly_hours"]
    d["weekend_share"] = d[weekend_col] / d["weekly_hours"]
    c_sb, _ = count_within(d["lat"].values, d["lon"].values, sb_open["lat"].values, sb_open["lon"].values, exclude_self=True)
    c_dk, _ = count_within(d["lat"].values, d["lon"].values, dk_open["lat"].values, dk_open["lon"].values)
    for r in (1, 2, 5):
        d[f"starbucks_within_{r}km"] = c_sb[r]
    d["dunkin_within_2km"] = c_dk[2]
    d["log_sb2"] = np.log1p(d["starbucks_within_2km"])
    d["log_dk2"] = np.log1p(d["dunkin_within_2km"])
    d["traffic_pctile_in_metro"] = d.groupby("msa")["visits_per_week"].rank(pct=True)
    return d


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hp = pd.read_csv(LAB / "04_operating_hours/store_hours_panel.csv", dtype={"locator_id": str, "store_id": str, "msa": str})
    panel = pd.read_csv(LAB / "01_store_panel/store_panel.csv", dtype={"store_id": str, "msa": str})
    hp = hp[hp["store_id"].notna() & hp["weekly_hours_2025-08"].notna()].drop_duplicates("store_id")
    hp = hp.drop(columns=["status", "close_date", "msa"]).merge(
        panel[["store_id", "lat", "lon", "msa", "status", "close_date", "urbanicity"]], on="store_id")
    hp["close_date"] = pd.to_datetime(hp["close_date"])
    hp["closed_oct25"] = hp["close_date"].between("2025-09-01", "2025-11-30")
    hp = hp[hp["closed_oct25"] | hp["status"].eq("open")].copy()

    sb = load_advan("Starbucks")
    dk = load_advan("Dunkin")
    p = sb[["ID_STORE", "week", "visits"]]
    sl, dl = locations(sb), locations(dk)
    open_at = lambda L, t: L[(L["first_week"] <= t) & (L["last_week"] >= t - pd.Timedelta(weeks=2))  # noqa: E731
                             & (L["close_date"].isna() | (L["close_date"] > t))]
    pre = features(hp, p, PRE_END, open_at(sl, PRE_END), open_at(dl, PRE_END), "weekly_hours_2025-08", "weekend_hours_2025-08")
    pre = pre.dropna(subset=FEATS + ["msa"])
    pre = pre[pre["visits_yoy_pct"].between(-60, 100)]
    y = pre["closed_oct25"].astype(int)

    # 1. Closed vs survivors (raw and metro-demeaned)
    cols = FEATS[:5] + ["starbucks_within_1km", "starbucks_within_2km", "starbucks_within_5km", "dunkin_within_2km", "visits_per_week"]
    dm = pre[cols] - pre.groupby("msa")[cols].transform("mean")
    rows = []
    for c in cols:
        rows.append({"metric": c, "closed_median": pre.loc[y == 1, c].median(), "survivor_median": pre.loc[y == 0, c].median(),
                     "closed_mean_vs_metro": dm.loc[y == 1, c].mean(), "survivor_mean_vs_metro": dm.loc[y == 0, c].mean()})
    cmp_ = pd.DataFrame(rows).round(3)
    cmp_.to_csv(OUT / "closed_vs_survivors.csv", index=False)
    urb = pd.crosstab(pre["urbanicity"], pre["closed_oct25"], normalize="columns").round(3)

    # 2. Mechanical productivity gain from removing the closed stores (Aug-2025 measurement)
    vph_all, vph_surv = pre["visits_per_op_hour"], pre.loc[y == 0, "visits_per_op_hour"]
    tot_all = pre["visits_per_week"].sum() / pre["weekly_hours"].sum()
    tot_surv = pre.loc[y == 0, "visits_per_week"].sum() / pre.loc[y == 0, "weekly_hours"].sum()
    closed_med = float(pre.loc[y == 1, "visits_per_op_hour"].median())
    composition = {"aggregate_visits_per_op_hour_all": round(tot_all, 3), "aggregate_visits_per_op_hour_survivors": round(tot_surv, 3),
                   "composition_gain_pct": round(100 * (tot_surv / tot_all - 1), 2),
                   "closed_share_of_stores_pct": round(100 * y.mean(), 2),
                   "closed_share_of_hours_pct": round(100 * pre.loc[y == 1, "weekly_hours"].sum() / pre["weekly_hours"].sum(), 2),
                   "closed_share_of_visits_pct": round(100 * pre.loc[y == 1, "visits_per_week"].sum() / pre["visits_per_week"].sum(), 2),
                   "closed_median_visits_per_op_hour": round(closed_med, 2),
                   "median_all": round(float(vph_all.median()), 2), "median_survivors": round(float(vph_surv.median()), 2)}

    # 3. Closure-risk model (logistic, standardized features, 5-fold CV AUC)
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced"))
    X = pre[FEATS].to_numpy(float)
    cv = cross_val_predict(model, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
    auc = roc_auc_score(y, cv)
    auc_simple = roc_auc_score(y, -pre["visits_per_op_hour"])
    model.fit(X, y)
    coef = pd.DataFrame({"feature": FEATS, "std_coef": model[-1].coef_[0].round(3)})
    coef["odds_ratio_per_1sd"] = np.exp(coef["std_coef"]).round(3)
    coef.to_csv(OUT / "closure_risk_model.csv", index=False)
    pre["closure_score_cv"] = cv
    thr = float(np.quantile(cv[y == 1], 0.5))  # median score among actual closures

    # 4. Score currently open company-operated stores on Sep-2026 features
    last = sb["week"].max()
    now_base = hp[hp["status"].eq("open") & hp["weekly_hours_2026-09"].notna()].copy()
    now = features(now_base, p, last, open_at(sl, last), open_at(dl, last), "weekly_hours_2026-09", "weekend_hours_2026-09")
    now = now.dropna(subset=FEATS)
    now = now[now["visits_yoy_pct"].between(-60, 100)]
    now["closure_likeness"] = model.predict_proba(now[FEATS].to_numpy(float))[:, 1]
    now["resembles_oct25_closures"] = now["closure_likeness"] >= thr
    now["below_closed_median_vph"] = now["visits_per_op_hour"] < closed_med
    keep = ["store_id", "locator_id", "msa", "state_2026-09", "lat", "lon", "visits_per_week", "visits_yoy_pct", "weekly_hours",
            "visits_per_op_hour", "traffic_pctile_in_metro", "starbucks_within_2km", "dunkin_within_2km", "closure_likeness",
            "resembles_oct25_closures", "below_closed_median_vph"]
    now.sort_values("closure_likeness", ascending=False)[keep].round(4).to_csv(OUT / "at_risk_open_stores.csv", index=False)
    # Same Aug-2025 survivors: share below the closed-store median VPOH then vs now (season-matched windows Jun-Aug / Jun-Sep)
    tail = {"aug25_survivors_below_closed_median_vph_pct": round(100 * float((vph_surv < closed_med).mean()), 1),
            "sep26_open_below_closed_median_vph_pct": round(100 * float(now["below_closed_median_vph"].mean()), 1),
            "sep26_open_resembling_closures_n": int(now["resembles_oct25_closures"].sum()),
            "sep26_open_resembling_closures_pct": round(100 * float(now["resembles_oct25_closures"].mean()), 1),
            "sep26_scored_stores": len(now),
            "sep26_resembling_median_yoy": round(float(now.loc[now["resembles_oct25_closures"], "visits_yoy_pct"].median()), 2),
            "sep26_others_median_yoy": round(float(now.loc[~now["resembles_oct25_closures"], "visits_yoy_pct"].median()), 2)}

    res = {"sample": {"stores": len(pre), "closed_oct25": int(y.sum()), "survivors": int((y == 0).sum())},
           "closed_vs_survivors": cmp_.to_dict(orient="records"), "urbanicity_mix": urb.to_dict(),
           "composition_effect_aug25": composition,
           "risk_model": {"cv_auc": round(auc, 3), "auc_visits_per_op_hour_alone": round(auc_simple, 3),
                          "coefficients": coef.to_dict(orient="records"), "threshold_median_closed_score": round(thr, 3)},
           "remaining_tail": tail}
    save_json(res, OUT / "results.json")
    print(cmp_.to_string(index=False))
    print(urb)
    print(composition)
    print(coef.to_string(index=False), "\nAUC", round(auc, 3), "VPH-only AUC", round(auc_simple, 3))
    print(tail)
    chart(pre, y, now, closed_med, tail, composition, auc)


def chart(pre, y, now, closed_med, tail, comp, auc) -> None:
    import sys
    sys.path.insert(0, str(LAB.parent / "_research_archive/starbucks_hiring/src"))
    import charts as C
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2))
    ax = axes[0]
    bins = np.arange(0, 61, 2)
    ax.hist(pre.loc[y == 0, "visits_per_op_hour"].clip(0, 60), bins=bins, density=True, color=C.GRAY, label=f"Survivors (n={int((y == 0).sum()):,})")
    ax.hist(pre.loc[y == 1, "visits_per_op_hour"].clip(0, 60), bins=bins, density=True, histtype="step", linewidth=2, color=C.BLUE,
            label=f"Closed Oct 2025 (n={int(y.sum()):,})")
    ax.axvline(closed_med, color=C.INK_2, linewidth=1, linestyle="--")
    ax.text(closed_med + 0.8, ax.get_ylim()[1] * 0.92, f"closed median {closed_med:.1f}", fontsize=8, color=C.INK_2)
    ax.set_title("Pre-closure visits per operating hour (Jun–Aug 2025)", fontsize=10)
    ax.set_xlabel("Advan visits per operating hour")
    ax.set_yticks([])
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax = axes[1]
    labels = ["Aug 2025 survivors\nbelow closed median", "Sep 2026 open stores\nbelow closed median", "Sep 2026 open stores\nresembling closures (model)"]
    vals = [tail["aug25_survivors_below_closed_median_vph_pct"], tail["sep26_open_below_closed_median_vph_pct"], tail["sep26_open_resembling_closures_pct"]]
    ax.barh(range(3), vals, color=[C.GRAY, C.BLUE, C.BLUE], height=0.55)
    for i, v in enumerate(vals):
        ax.text(v + 0.3, i, f"{v:.1f}%", va="center", fontsize=9, color=C.INK_2)
    ax.set_yticks(range(3), labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("% of company-operated stores")
    ax.grid(axis="y", visible=False)
    ax.set_title(f"How much low-productivity tail is left (model CV AUC {auc:.2f})", fontsize=10)
    fig.suptitle(f"Closures removed the low-productivity tail: +{comp['composition_gain_pct']:.1f}% aggregate visits per operating hour, one time",
                 x=0.01, y=0.99, ha="left", fontsize=12, fontweight="semibold")
    fig.text(0.01, 0.01, "Company-operated stores · Advan visits (panel sample, relative only) · hours from Starbucks store locator snapshots",
             fontsize=8, color=C.INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    fig.savefig(LAB / "charts/06_closure_productivity.png", dpi=200)


if __name__ == "__main__":
    main()
