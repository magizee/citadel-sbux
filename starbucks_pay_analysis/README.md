# starbucks_pay_analysis

PILOT: is posted pay on Starbucks job postings usable as evidence of labor-cost pressure?

- **Source:** public job-detail endpoint `https://apply.starbucks.com/api/pcsx/position_details?position_id=<id>&domain=starbucks.com`
  (same Eightfold API as the hiring scrape). Collected 2026-10-01.
- **Run:** `python src/pay_sample.py --n 40` (reads saved search pages from `../starbucks_hiring`, never writes there).
- **Outputs:** `data/raw/details/*.json`, `data/processed/pay_candidates.csv`, `data/processed/pay_sample.csv`,
  `outputs/pay_validation.md`.
- **Result:** pay present on 40/40, but set by a standardized zone ladder (max = 1.135 × min for hourly roles).
  No age-pay relationship. The detail payload's **90-day posting expiry** is the more important finding.
- **Limitations:** 40 hand-picked postings, one day, posted ranges only.
- **Investment suitability:** low as a one-day cross-section; potentially useful as a time series of zone levels.
