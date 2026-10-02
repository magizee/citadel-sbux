# START HERE: Starbucks staffing research (overnight run, 2026-10-01 → 10-02)

Everything to review is in **`REVIEW/`**: copies of the outputs, organized for reading. The working projects are untouched.
Rebuild it after any rerun with `./build_review.sh`.

## 60-second summary

1. **National scrape: complete and clean.** 19,831 unique U.S. postings (100.8% of Starbucks' own U.S. count),
   10,224 hiring stores, 395 searches, 4,455 requests, 0 incomplete searches, 0 rate-limit errors.
2. **Frontline hiring is a standing, batch-refreshed pipeline at ~every store** (99.3% of company-operated stores; 86.9% show
   exactly 1 barista + 1 supervisor posting; 0% of frontline requisitions older than 90 days or re-posted). Raw posting counts
   and posting age are therefore weak signals.
3. **Requisition creation is DOWN year-over-year:** about −20% vs 2025 for Jan–early Jul (requisition numbers are
   sequential, so they count every requisition created). Consistent with lower turnover, which **cuts against** a "can't hire" short.
4. **Leadership is the one pressure pocket:** 42% of the 195 open store/district-manager requisitions are re-posted, 18 are
   older than 90 days, clustered in the Philadelphia and Chicago suburbs, Michigan, the Pacific NW and Baltimore/DC.
   Management says leader stability drives store performance.
5. **July 4 batch re-check:** all 145 frontline requisitions that hit their 90-day expiry at midnight disappeared, and **none was
   replaced** ~3 hours later (122 of 137 stores still showed their other-role posting). Requisitions are not auto-renewed;
   replacements, if any, come in later batches. A re-check from Oct 3 onward tells whether they come back.
6. **Foot traffic (Advan via Dewey, added Oct 2):** no staffing → traffic link. Stores near manager vacancies only looked
   faster-growing because of closure transfer; removing that, there is no difference.
7. **The stronger short angle is unit economics, not staffing:** dense markets are cannibalized (visits per store ≈ half of rural),
   Starbucks is closing stores there (9.2% vs 2.6%; 481 in Oct 2025 + ~300 in spring 2026), and survivors within 2 km of a
   closure grow ~2× faster, flattering same-store growth by ≈ 0.3 pp. See the memo's "overbuilt network" section.
8. **Verdict:** the data supports a *monitoring* angle and a narrow leadership/labor-productivity risk, **not** a claim that
   Starbucks is failing to hire. See `REVIEW/1_read_first/1_short_case_memo.md`.

## Folder guide

| Folder | What's inside |
|---|---|
| `REVIEW/1_read_first/` | Short-case memo → analysis summary → thesis tests → prioritization |
| `REVIEW/2_key_charts/` | 7–8 pitch-ready charts (PNG + CSV), numbered in suggested pitch order |
| `REVIEW/3_supporting_charts/` | Additional national charts |
| `REVIEW/4_caveated_charts/` | Posting-age charts that mostly reflect batch timing (do not use as persistence evidence) |
| `REVIEW/5_pilot_preview/` | NYC pilot preview (not nationally representative) |
| `REVIEW/6_tables/` | National postings CSV, store and market summaries, leadership requisitions, review lists |
| `REVIEW/7_data_quality/` | QA report, merge report, scraper README |
| `REVIEW/8_background_research/` | Management statements, store universe, pay pilot, operating-data and historical-data source reviews, archive validation, labor controls |

## Working projects (source code + raw data)

`starbucks_hiring/` (scraper + national analysis) · `starbucks_thesis_tests/` (tests A–F, requisition trend, memo) ·
`starbucks_archive/` (Wayback index + requisition sequence) · `starbucks_store_universe/` · `starbucks_management_research/` ·
`starbucks_pay_analysis/` · `starbucks_operating_data/` · `starbucks_labor_market/` · `starbucks_historical_hiring/`

## What I did overnight beyond the original plan (your instruction: maximize research)

- Pulled the full Wayback CDX index (46 requests) and 231 archived job pages, which established that requisition numbers are a
  sequential count, turning the archive into a year-over-year measure.
- Ran a one-off re-check of the 137 stores whose July 4 requisitions expired at midnight (~150–250 small requests, same pacing).
- No recurring jobs, no national pay pull, nothing committed or pushed to git.

## Decisions waiting for you

1. **Commit / push?** New folders are uncommitted. Raw data (archive pages, store-universe GeoJSON, national pages) should
   be git-ignored. Code, docs and `REVIEW/` are small.
2. **Repeat snapshot** in 1–2 weeks (one command) to turn leadership re-posting and requisition pace into trends.
3. **Data access:** check WRDS (Revelio postings) and Dewey (Advan foot traffic) for the operating-outcome link.
