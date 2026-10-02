# QA report: data/processed/2026-10-01/pilot/pilot_jobs_clean.csv

250 postings

| Status | Check | Detail |
|---|---|---|
| PASS | duplicate job_ids | 0 duplicates |
| PASS | retail rows missing store_key | 1 of 243 (0.4%); examples: store manager |
| PASS | retail rows using address fallback store_key | 12 (4.9%) |
| PASS | retail rows missing coordinates | 0 (0.0%) |
| PASS | retail rows missing street address | 1 (0.4%) |
| PASS | impossible / missing posting ages (<0, >730 days, null) | 0; range 1..89 days |
| PASS | OTHER_RETAIL title variety (review for mis-bucketing) | 11 postings, 6 distinct role texts; top: operations lead (5); baker (2); mixologist (bartender) (1); porter (dishwasher) (1); baker lead (1); mixologist (1) |
| PASS | store_number with >1 street address | 0 store numbers; e.g. [] |
| PASS | store_number with >1 coordinate | 0 store numbers; e.g. [] |
| PASS | non-U.S. rows | 0 |
| PASS | rows without a parsed state | 0 |
| PASS | state codes not two-letter | [] |
| WARN | states represented | 2 (smallest: NY=233, NJ=17) |
| PASS | manager titles classified NON_RETAIL | 0;  |
| PASS | corporate-looking titles classified retail (no store number) | 0;  |
