# 05 · Service quality (wait-time proxies)

**Question:** is the traffic recovery straining service, e.g. longer waits at fast-growing stores?

## What's available
| Source | Usable? | Notes |
|---|---|---|
| **Advan `MEDIAN_DWELL` / `BUCKETED_DWELL_TIMES`** | **Yes, used here** | Already downloaded. Dwell mixes order-to-pickup wait with sit-down time. Buckets are coarse (<5, 5–20, 21–60 min). |
| Advan `VISITS_BY_EACH_HOUR` | Possible next step | Peak-hour concentration (crowding) by store; not built. |
| Google Maps reviews / "popular times" | Not used | Scraping is against Google's terms of service. Paid vendors (Outscraper, SerpApi) cost money and time; review text would allow a wait-time keyword index. |
| Yelp Fusion API | Limited | 3 reviews per business via the API; too thin. |
| App-store reviews (Starbucks app) | Possible | National only (no store detail); mobile-order complaints. |
| Reddit r/starbucks, r/starbucksbaristas | Possible | Qualitative / sentiment on staffing; not store-level. |
| Customer Connection / drive-thru timing (SeeLevel HX, QSR Drive-Thru Study) | Paid / annual | Best direct measure of drive-thru speed; one data point a year. |

## Result (Advan dwell, `src/service_quality.py`)
- **Share of visits ≥ 5 minutes**, company-operated Starbucks vs Dunkin':

  | Period | Starbucks | Dunkin' |
  |---|---|---|
  | FY24 Q2 | 16.7% | 13.8% |
  | FY25 Q2–Q4 | 13.1–13.3% | 12.2–12.4% |
  | FY26 | 13.8–14.2% | 12.7–13.0% |

  Starbucks' premium over Dunkin' shrank from +2.9 pp to about +1 pp during FY25 and has stayed there. The drop coincides with mobile-order and
  drive-thru growth and with the Advan panel change (Dunkin' fell too).
- **Store-level YoY:** the share of visits ≥ 5 min rose more at faster-growing stores.

  | Traffic growth cohort | Change in share ≥ 5 min |
  |---|---|
  | > 10% | +1.0 pp |
  | 5–10% | +0.7 pp |
  | 0–5% and < 0% | +0.4 pp |

  With metro FE that is +0.57 pp per 10 pp of growth (t 3.5). Median dwell is unchanged at 4 min; a panel-wide −1 min shift hit both brands.
- Chart: `../charts/05_service_quality.png`.

## Supports / weakens the short
- **Ambiguous, slightly supportive.** Fast-growing stores do see more long visits, which fits congestion (longer waits). It also fits
  management's push for customers to stay in the café. Dwell can't separate the two.
- No evidence of a broad service breakdown: Starbucks' long-visit share is stable relative to Dunkin' through FY26.

**Confidence:** low. The proxy is indirect and the buckets are coarse.

**Limitations:**
- Dwell is phone presence, not wait time.
- Drive-thru visits may register as short or be missed.
- The Advan panel changed over 2024–25.

**Files:** `weekly_dwell.csv`, `store_dwell_change.csv`, `dwell_by_growth_cohort.csv`, `results.json`.
