# 08 · Peak load: did the recovery land in the hours that need more staff?

**Question:** a store is staffed to its rush. Extra visits in slack hours (midday, afternoon) are absorbed by partners already on the floor.
Extra visits in the morning rush need more partners on that shift. So, where did Starbucks' traffic growth land?

## Method
- **Data:** Advan `VISITS_BY_EACH_HOUR` (168 hour-of-week values, local time).
  - Per store-week the field is sparse (one device ≈ one step), so it is pooled over 13-week windows.
  - **Its levels are not consistent over time:** hourly totals fell YoY while true visit counts rose. So only its **time-of-day shares** are used.
  - Growth always comes from `VISIT_COUNTS`.
- **Sample:** 7,497 open company-operated Starbucks and 6,816 Dunkin' with hourly data in both windows (Jun 29 – Sep 21 2026 vs the same weeks of 2025).
- **Implied day-part growth** = (1 + total visit growth) × share now ÷ share a year ago − 1.

## Result
**1. Starbucks' growth is concentrated in the morning.** Same-store visits grew +2.1% (Dunkin' +1.2%).

| Day-part | Share of visits | Implied YoY growth | Share of Starbucks' growth |
|---|---|---|---|
| Early 4–7 am | 8.9% | +4.7% | 20% |
| Morning peak 7–10 am | 21.2% | +3.2% | 33% |
| Midday 10 am–2 pm | 30.5% | +0.9% | 13% |
| Afternoon 2–5 pm | 19.5% | +0.7% | 6% |
| Evening 5–10 pm | 17.0% | +2.5% | 20% |

**The 4–10 am window holds 30% of visits but produced 52% of the growth.** Dunkin's 7–10 am share *fell* (−0.11 pp) over the same period.

**2. This has been building for two years.** Share of visits before 10 am, same fiscal quarter:

| | FY24 Q3 | FY25 Q3 | FY26 Q3 | Two-year change |
|---|---|---|---|---|
| Starbucks | 28.4% | 29.9% | 30.3% | **+1.9 pp** |
| Dunkin' | 33.3% | 34.2% | 34.2% | +1.0 pp |

**3. Faster-growing stores shifted more toward the rush:**

| Store traffic growth | Change in 7–10 am share |
|---|---|
| > 10% | +0.51 pp |
| 5–10% | +0.50 pp |
| 0–5% | +0.14 pp |
| < 0% | +0.03 pp |

With metro fixed effects this is not statistically significant (t 1.4): store-level hourly shares are noisy.

Chart: `../charts/08_peak_load.png`.

## Supports / weakens the short
- **Supports.** The recovery is landing in the least labor-efficient hours: the morning rush, where stores already run at capacity and extra customers
  need extra partners on shift. Slack hours (midday, afternoon) lost share.
- This fits flat posted hours (04) together with a store-opex ratio that stays high (filings): **more labor per peak hour, not more open hours.**
- It also fits the strategy of mobile order, drive-thru and a morning focus.

**Confidence:** medium. The shift is consistent across two years and against Dunkin'. But the hourly field is an Advan derivative with
changing coverage, and its hour attribution (it peaks around 10 am–noon) may differ from till data. Treat it as relative only.

**Limitations:**
- No transaction-level timing.
- Phone dwell can spill across hour boundaries.
- Store-level shares are noisy.
- It can't see how many partners are on a shift.

**Files:**
- `daypart_growth.csv`
- `profiles_by_fq.csv`: national hour-of-day profiles by fiscal quarter.
- `store_peak.csv`
- `peak_by_growth_cohort.csv`
- `results.json`

**Code:** `src/peak_load.py`.
