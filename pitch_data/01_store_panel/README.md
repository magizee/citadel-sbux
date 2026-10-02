# 01 · Store panel

**Question:** can traffic, operating hours, hiring, density and closure status be joined at the store level?

**Result:** yes. `store_panel.csv` has one row per U.S. Starbucks location in Advan (17,856 rows: 16,521 open, 1,323 closed, 12 dropped from the panel).
- 9,719 are open and company-operated. Of those, 9,705 have operating hours, 9,632 have careers postings and 9,395 have YoY traffic.
- Median company-operated store: **112 operating hours/week** and **21.8 Advan visits per operating hour**.

| File | Contents |
|---|---|
| `store_panel.csv` | one row per location; fields below |
| `store_month_visits.parquet` | store × month Advan visits (sum, weeks, visits/week) |
| `panel_summary.json` | counts and coverage |

**Fields:**
- **Traffic (Advan):** `visits_per_week_13w` (latest 13 weeks), `visits_yoy_pct`, `visits_2y_pct`, `traffic_pctile_in_metro`.
- **Locator (Sep 2026):** `ownership_type` / `company_operated`, `weekly_hours_2026_09`, `visits_per_operating_hour`.
- **Careers snapshot (Oct 1 2026):** `active_postings`, postings by role, `oldest_posting_age_days`, `oldest_requisition_age_days`, `reposted_requisitions`.
- **Area-level manager vacancies within 5/15 km:** `mgr_vacancy_*` and `persistent_mgr_vacancy_*`.
- **Density:** Starbucks and Dunkin' within 1/2/5 km, `urbanicity`.
- **Dates:** open and close dates.

**How stores are linked:**
- Advan store to Starbucks store locator: nearest point within 75 m.
- Locator to careers postings: via `store_key` from `_research_archive/starbucks_store_universe`.
- Store numbers: the locator's `website` URL contains the Starbucks store number. Workstream 03 uses this.

**Supports/weakens the short:** infrastructure only.

**Confidence:** high for the joins. 3,184 Advan locations have no locator match within 75 m; these are mostly licensed stores, moved pins or closed stores.

**Limitations:**
- Advan is a phone-panel sample, so use relative measures only.
- Hours are posted store hours, **not labor hours**: they say nothing about how many partners are on shift.
- Hiring is a one-day snapshot.

**Code:** `src/build_store_panel.py` (helpers in `src/lab.py`).
