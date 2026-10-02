# 03 · Historical hiring from the Internet Archive

Pipeline and data: [`_research_archive/starbucks_hiring_archive/`](../../_research_archive/starbucks_hiring_archive/README.md). This folder holds the summary (`results.json`).

**Question:** has store-level hiring intensity changed over time, and did stores whose traffic grew in FY26 hire relatively more than in FY25?

## Method
- **Data:** 155,626 distinct job postings seen in Wayback captures of `apply.starbucks.com/careers/job/…` (Feb 2024 – Aug 2026). Role and store
  number come from the URL slug.
- **Linking:** 154k postings carry a store number. 130k of these link to the store locator (via the store number in the locator's URL) and 122k link to Advan
  (9,486 stores).
- **Crawl adjustment:** capture volume is set by the crawler, not by Starbucks. So all measures are **within-period relative**: the role mix, and a
  store's share of the period's postings × number of stores (1.0 = average).

## Result
1. **Frontline postings are a uniform standing pipeline, historically too.**
   - The average store-quarter has 1.8 captured frontline postings. 63% are exactly one barista + one supervisor; only 7% have more than 2.
   - Per-store postings per year: mean 5.7, SD 1.0.
2. **They don't respond to traffic growth.**
   - Relative intensity is about 1.00 in every FY26 traffic-growth cohort, in both FY25 and FY26.
   - The FY26-vs-FY25 change is +0.01 log points per 10 pp growth. That is statistically non-zero (t 2.4) but economically nil.
   - Postings per visit therefore *fall* as traffic rises. This is mechanical: postings are fixed.
3. **The store-manager share of postings fell in FY26.**

   | Period | Store-manager share |
   |---|---|
   | FY25 Q3–Q4 (well-sampled quarters) | 3.9–4.2% |
   | FY26 Q1 | 3.5% |
   | FY26 Q2–Q3 | 1.7% |

   This is consistent with management's push to stabilize store leadership. It runs against a "manager churn is rising" story. Caveat: crawl mix could differ by role.
4. **Manager postings by city** (81.5% of 4,266 FY25–26 manager postings matched to a city; 382 cities with ≥ 5 stores): a city's
   manager-posting share relative to its store share is unrelated to the city's traffic growth (t −0.2, Spearman ≈ 0).
5. **Closed stores before closure:** FY25 relative intensity was 1.00, the same as survivors. Closed stores were not hiring differently in the year
   before the Oct-2025 closures. Their FY24 figure (0.93) is a thin crawl.

## Supports / weakens the short
- **Weakens a "labor strain" narrative:** frontline hiring never scaled with traffic, and manager posting share fell in FY26.
- **Neutral for the margin thesis:** postings are not where labor cost shows up. Labor cost is set by hours staffed per shift and wages, which this data can't see.

**Confidence:**
- Medium for the uniformity result (large n, consistent with the 2026 snapshot).
- Low–medium for the manager-share trend (crawl composition).

**Limitations:**
- Captures are not postings: coverage is bursty and FY24 is thin.
- The first-capture date is not the posting date.
- Manager postings are area-level.
- Licensed stores are not included.

Chart: `../charts/03_archive_hiring.png`.
