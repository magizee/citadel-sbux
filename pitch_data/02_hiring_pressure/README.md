# 02 · Hiring Pressure Index and traffic growth vs hiring (workstreams 2 + 3)

**Question:** do stores with faster traffic growth need more hiring, i.e. is the recovery labor-hungry at the store level?

## Method
Sample: 9,128 open company-operated stores that have YoY traffic. Careers snapshot taken Oct 1 2026.

The Hiring Pressure Index (HPI) has three specifications, each summing 0/1 components:

| Index | Components |
|---|---|
| `HPI_full` | manager vacancy ≤ 5 km + oldest posting > 30 d + > 60 d + re-posted requisition + same-role duplicate |
| `HPI_persistence` | re-posted requisition + requisition > 60 d + persistent manager vacancy ≤ 5 km |
| `HPI_gap` | missing a barista *or* supervisor posting + manager vacancy ≤ 5 km |

**Regression:** OLS with metro fixed effects and robust SEs.
`outcome ~ YoY traffic growth + log traffic level + weekly hours + log(Starbucks ≤ 2 km) + log(Dunkin' ≤ 2 km)`

## Result
| Outcome | per +10 pp traffic growth | t | mean |
|---|---|---|---|
| Active postings | −0.003 | −0.4 | 1.89 |
| Postings per 1,000 weekly visits | +0.014 | 0.7 | 1.05 |
| Same-role duplicate postings | −0.1 pp | −0.4 | 1.9% |
| Oldest requisition age | +0.4 days | 0.9 | 40 d |
| HPI_full | +0.019 | 1.3 | 0.86 |
| HPI_persistence | +0.019 | 2.3 | 0.27 |
| Manager vacancy ≤ 5 km | +1.3 pp | 2.9 | 9.1% |
| Persistent manager vacancy ≤ 5 km | +1.3 pp | 3.4 | 4.4% |

- **Frontline hiring does not scale with traffic.** Postings, duplicates, posting age and re-posts are flat across growth
  cohorts. Each store carries a standing barista + supervisor requisition whatever its traffic, so a store growing +13% posts the same as a
  store shrinking −2%. The archive history in 03 confirms this has held since FY24.
- **Manager vacancies cluster at both extremes.** Stores growing > 10% (n = 1,029) are near a persistent manager vacancy 8.8% of the time vs 3.3–4.4% for
  the other cohorts (+3.8 pp vs metro). The quietest fifth of stores also sit near vacancies more often (7.6% vs 2.4% for the busiest fifth).
- Chart: `../charts/02_hiring_pressure_by_traffic_growth.png`.

## Supports / weakens the short
- **Neutral to slightly weakening on frontline labor:** there is no sign that growth forces extra frontline hiring.
- **Mildly supportive on management:** manager instability sits near the fastest-growing stores and the weakest ones.
  The effect is small, about 1–4 pp of a low base.
- The cost of the recovery isn't visible as hiring. If it exists, it is in **labor hours per open hour and wages**, which postings can't measure.

**Confidence:** medium for "frontline postings do not respond to traffic" (a large n, a robust null, consistent with history). Low–medium for the
manager pattern: manager requisitions are area-level (city), so "within 5 km" is a proxy.

**Limitations:**
- This is a one-day snapshot.
- Postings measure vacancies, not staffing levels or turnover.
- Requisitions are batch-created (90-day expiry), which mechanically flattens differences between stores.

**Code:** `src/hiring_pressure.py`.

**Files:**
- `store_hpi.csv`: one row per store.
- `regressions.csv`.
- `cohorts.csv`: growth cohorts, raw and demeaned by metro.
- `by_traffic_level.csv`.
- `results.json`.
