# 04 · Operating hours

**Question:** are hours changing? Do growing stores extend hours, did closed stores have short or shrinking hours, and do hiring-pressure stores cut hours?

## Method
- **Data:** Starbucks store-locator snapshots (All the Places, CC0) from Jul 2024 (partial, 937 company-operated stores), Aug 2025, Jan 2026, Apr 2026 and Sep 2026.
  Stores are linked across snapshots by locator ID. Hours are parsed from OSM `opening_hours`.
- The Aug-2025 download was cut off before its closing bracket; it is parsed line by line (9,628 company-operated stores recovered).

## Result
| | Aug 2025 | Jan 2026 | Apr 2026 | Sep 2026 |
|---|---|---|---|---|
| Median weekly hours (company-operated) | 112 | 112 | 112 | 112 |
| Mean weekly hours | 111.0 | 112.9 | 112.3 | 112.2 |
| % open by 5 am on weekdays | 91.8 | 97.9 | 98.3 | 98.0 |
| Median visits per operating hour (same 8,400 survivors) | 22.1 | 21.7 | 23.6 | 22.5 |

- **Same-store change, Aug 2025 to Sep 2026:** mean +0.6 h/week, median 0.
  - 45% of stores added hours and 33% cut them, mostly by about an hour. Weekday open and close times are unchanged at the median.
- **Growth vs hours:** stores growing > 10% added +2.0 h/week on average; 5–10% growth added +1.6 h; shrinking stores cut 0.6 h (Spearman 0.13).
  Hours respond to traffic, but only slightly: about 2% more hours for 10%+ more visits.
- **Closed stores already had shorter hours before closure:**
  - Weekly hours in Aug 2025: median 101.5 h for stores closed in Oct 2025 (n = 382) vs 112 h for survivors.
  - 44% of closed stores were under 100 h, vs 10% of survivors.
  - Change Jul 2024 to Aug 2025 (partial snapshot): −0.4 h for closed stores (n = 65) vs +1.7 h for survivors (n = 843). This is suggestive that hours were trimmed ahead of closure.
- **Hiring pressure vs hours:** no relationship (Spearman −0.02 with level, −0.01 with change). Only the rare HPI 3–4 stores have shorter hours (106–110 h).
- **Visits per operating hour** in Sep 2026 is +1.5% vs Aug 2025 on the same stores; the windows are near-matched by season. Most of that gain is visits, not hours: hours are standardized.

## Supports / weakens the short
- **Weakens "growth needs more hours":** the recovery is being absorbed inside existing hours, so visits per open hour rise.
- **Neutral on margins:** posted hours are nearly fixed, so they can't explain the ~5 pp rise in the store-opex ratio vs FY24 (`../tables/operating_leverage.csv`).
  That cost sits in staffing per open hour and in wages, which posted hours don't measure.
- **Useful for closure risk:** short hours were the strongest single marker of the Oct-2025 closures (see 06).

**Confidence:** high for hours levels and changes. Medium for visits per operating hour (Advan sample, seasonality).

**Limitations:**
- Posted hours are not labor hours.
- Snapshots are about 4 months apart.
- The Jul-2024 snapshot is partial and skews toward a subset of states.
- Temporary hour cuts between snapshots are missed.

**Code:** `src/operating_hours.py`. Snapshots are downloaded by `src/fetch_alltheplaces_history.py`; the 2024-01 and 2025-01 runs returned 404.

**Files:** `store_hours_panel.csv` (store × snapshot hours, linked to Advan / HPI), `results.json`. Chart: `../charts/04_operating_hours.png`.
