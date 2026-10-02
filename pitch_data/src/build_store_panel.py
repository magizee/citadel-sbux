"""Workstream 1: store-level panel combining traffic, hours, hiring, density and closure status.

    python src/build_store_panel.py

Outputs (01_store_panel/):
  store_panel.csv          one row per U.S. Starbucks location in Advan (open and closed)
  store_month_visits.parquet  store x month visits (sum of weekly visits by week-start month, with week counts)
  panel_summary.json

Key fields: store_id (Advan ID_STORE), locator_id / ownership (company-operated vs licensed, from the Starbucks
store locator), visits (latest 13 weeks, YoY, 2-year), traffic percentile within metro, weekly operating hours,
visits per operating hour, careers-snapshot hiring fields (2026-10-01), nearby manager vacancies, Starbucks and
Dunkin' density within 1/2/5 km, open/close dates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from lab import HIRE, LAB, OPS, SNAPSHOT, UNIV, count_within, load_advan, locations, nearest_match, save_json, weekly_hours

OUT = LAB / "01_store_panel"


def window_mean(panel: pd.DataFrame, end_week: pd.Timestamp, n: int = 13, lag_weeks: int = 0) -> pd.DataFrame:
    weeks = pd.date_range(end=end_week - pd.Timedelta(weeks=lag_weeks), periods=n, freq="7D")
    x = panel[panel["week"].isin(weeks)].groupby("ID_STORE")["visits"].agg(["mean", "size"])
    return x[x["size"] >= int(round(n * 0.85))]["mean"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sb = load_advan("Starbucks")
    dk = load_advan("Dunkin")
    loc = locations(sb)
    last_week = sb["week"].max()

    # Store x month visits
    sb["month"] = sb["week"].dt.to_period("M").astype(str)
    sm = sb.groupby(["ID_STORE", "month"]).agg(visits=("visits", "sum"), weeks=("visits", "size")).reset_index()
    sm["visits_per_week"] = sm["visits"] / sm["weeks"]
    sm.to_parquet(OUT / "store_month_visits.parquet", index=False)

    # Traffic: latest 13 weeks vs 52 and 104 weeks earlier
    p = sb[["ID_STORE", "week", "visits"]]
    cur, y1, y2 = window_mean(p, last_week), window_mean(p, last_week, lag_weeks=52), window_mean(p, last_week, lag_weeks=104)
    loc = loc.join(cur.rename("visits_per_week_13w"), on="ID_STORE").join(y1.rename("visits_per_week_13w_ly"), on="ID_STORE") \
             .join(y2.rename("visits_per_week_13w_2y"), on="ID_STORE")
    loc["visits_yoy_pct"] = 100 * (loc["visits_per_week_13w"] / loc["visits_per_week_13w_ly"] - 1)
    loc["visits_2y_pct"] = 100 * (loc["visits_per_week_13w"] / loc["visits_per_week_13w_2y"] - 1)
    loc["traffic_pctile_in_metro"] = loc.groupby("msa")["visits_per_week_13w"].rank(pct=True).round(3)

    # Status
    loc["status"] = np.where(loc["close_date"].notna() & (loc["close_date"] <= last_week), "closed",
                             np.where(loc["last_week"] >= last_week - pd.Timedelta(weeks=2), "open", "dropped_from_panel"))

    # Ownership + current hours from the Starbucks store locator (2026-09-26)
    uni = pd.read_csv(UNIV / "data/processed/starbucks_store_universe.csv", dtype={"locator_id": str})
    idx = nearest_match(loc["lat"].values, loc["lon"].values, uni, 75)
    for c in ("locator_id", "ownership_type", "store_name", "opening_hours", "located_in"):
        loc[c] = [uni.at[i, c] if i >= 0 else None for i in idx]
    loc["company_operated"] = loc["ownership_type"].eq("CO")
    loc["weekly_hours_2026_09"] = loc["opening_hours"].map(weekly_hours)
    loc["visits_per_operating_hour"] = (loc["visits_per_week_13w"] / loc["weekly_hours_2026_09"]).round(2)

    # Careers snapshot (2026-10-01): store-level hiring fields via locator_id -> store_key
    join = pd.read_csv(UNIV / "data/processed/hiring_store_join.csv", dtype={"locator_id": str})
    join = join[join["matched"] == True][["locator_id", "store_key"]].drop_duplicates("locator_id")  # noqa: E712
    jobs = pd.read_csv(HIRE / f"data/processed/{SNAPSHOT}/starbucks_jobs_US.csv", dtype={"store_number": str, "job_id": str})
    retail = jobs[jobs["role_bucket"] != "NON_RETAIL"].copy()
    retail["reposted_requisition"] = retail["reposted_requisition"].astype(str).eq("True")
    per = retail[retail["store_key"].notna()].groupby("store_key").agg(
        active_postings=("job_id", "nunique"),
        barista_postings=("role_bucket", lambda r: int((r == "BARISTA").sum())),
        supervisor_postings=("role_bucket", lambda r: int((r == "SHIFT_SUPERVISOR").sum())),
        store_manager_postings=("role_bucket", lambda r: int((r == "STORE_MANAGER").sum())),
        distinct_roles_open=("role_bucket", "nunique"),
        oldest_posting_age_days=("days_since_posted", "max"),
        oldest_requisition_age_days=("req_age_days", "max"),
        reposted_requisitions=("reposted_requisition", "sum")).reset_index()
    loc = loc.merge(join, on="locator_id", how="left").merge(per, on="store_key", how="left")
    for c in ("active_postings", "barista_postings", "supervisor_postings", "store_manager_postings",
              "distinct_roles_open", "reposted_requisitions"):
        loc[c] = loc[c].fillna(0).astype(int)
    loc["postings_per_1000_weekly_visits"] = (1000 * loc["active_postings"] / loc["visits_per_week_13w"]).round(3)

    # Nearby store/district-manager requisitions (area-level postings), any and persistent
    lead = retail[retail["role_bucket"].isin(["STORE_MANAGER", "DISTRICT_MANAGER"]) & retail["latitude"].notna()]
    pers = lead[lead["reposted_requisition"] | (lead["req_age_days"] > 60)]
    for name, pts in (("mgr_vacancy", lead), ("persistent_mgr_vacancy", pers)):
        cnt, nearest = count_within(loc["lat"].values, loc["lon"].values, pts["latitude"].values, pts["longitude"].values, radii=(5, 15))
        loc[f"{name}_within_5km"] = cnt[5]
        loc[f"{name}_within_15km"] = cnt[15]
        loc[f"km_to_nearest_{name}"] = np.round(nearest, 2)

    # Density: currently open Starbucks and Dunkin' within 1/2/5 km
    sb_open = loc[loc["status"] == "open"]
    dloc = locations(dk)
    dk_open = dloc[dloc["last_week"] >= last_week - pd.Timedelta(weeks=2)]
    c_sb, _ = count_within(loc["lat"].values, loc["lon"].values, sb_open["lat"].values, sb_open["lon"].values, exclude_self=True)
    c_dk, near_dk = count_within(loc["lat"].values, loc["lon"].values, dk_open["lat"].values, dk_open["lon"].values)
    for r in (1, 2, 5):
        loc[f"starbucks_within_{r}km"] = c_sb[r]
        loc[f"dunkin_within_{r}km"] = c_dk[r]
    loc["km_to_nearest_dunkin"] = np.round(near_dk, 2)
    loc["urbanicity"] = pd.cut(loc["starbucks_within_5km"], [-1, 2, 9, 1e9], labels=["low density", "suburban", "urban core"])

    loc = loc.rename(columns={"ID_STORE": "store_id"})
    loc.to_csv(OUT / "store_panel.csv", index=False)
    co_open = loc[(loc["status"] == "open") & loc["company_operated"]]
    summary = {
        "locations": len(loc), "status": loc["status"].value_counts().to_dict(),
        "ownership_matched": loc["ownership_type"].value_counts(dropna=False).to_dict(),
        "company_operated_open": len(co_open),
        "co_open_with_hours": int(co_open["weekly_hours_2026_09"].notna().sum()),
        "co_open_with_any_posting": int((co_open["active_postings"] > 0).sum()),
        "co_open_with_yoy": int(co_open["visits_yoy_pct"].notna().sum()),
        "median_visits_per_operating_hour_co": float(co_open["visits_per_operating_hour"].median()),
        "median_weekly_hours_co": float(co_open["weekly_hours_2026_09"].median()),
        "panel_last_week": str(last_week.date()), "careers_snapshot": SNAPSHOT,
    }
    save_json(summary, OUT / "panel_summary.json")
    print(summary)


if __name__ == "__main__":
    main()
