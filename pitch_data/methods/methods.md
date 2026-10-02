# Methods and reproducibility

## Run order (from the repo root, Python 3.12 with pandas, numpy, pyarrow, scikit-learn, matplotlib)
```
python3 pitch_data/src/fetch_alltheplaces_history.py   # store-locator snapshots (~40 MB, git-ignored)
python3 pitch_data/src/build_store_panel.py            # 01
python3 pitch_data/src/hiring_pressure.py              # 02 (+ workstream 3 tests)
python3 pitch_data/src/operating_hours.py              # 04
python3 _research_archive/starbucks_hiring_archive/src/archive_hiring.py  # 03 (needs 04's store_hours_panel)
python3 pitch_data/src/closure_productivity.py         # 06 (needs 04)
python3 pitch_data/src/service_quality.py              # 05
python3 pitch_data/src/new_store_productivity.py       # 07 (needs 06)
python3 pitch_data/src/peak_load.py                    # 08 (~3 min, parses hourly arrays)
python3 pitch_data/src/qcew_wages.py                   # 09 (downloads BLS QCEW, needs 04)
python3 pitch_data/src/operating_leverage_chart.py     # chart 00
```
Run the scripts from `pitch_data/src/` or the repo root; they resolve paths themselves. Raw Advan parquet files must already exist in
`_research_archive/starbucks_operating_data/data/raw/` (downloaded by `advan_pull.py` with the Dewey key in `.dewey_env`).

## Data sources
| Source | Coverage | Used for |
|---|---|---|
| Advan Weekly Patterns Plus (Dewey) | Starbucks + Dunkin', U.S., weekly, Jan 2024 – Sep 2026 | visits, dwell time, open/close dates, metro |
| Starbucks store locator via All the Places (CC0) | Jul 2024 (partial), Aug 2025, Jan 2026, Apr 2026, Sep 2026 | ownership (company-operated vs licensed), posted hours, store number |
| Starbucks careers API snapshot | Oct 1 2026, 19,831 U.S. postings | current hiring fields, manager vacancies |
| Internet Archive (Wayback) | Feb 2024 – Aug 2026, 155,626 postings | historical role mix, store-level posting intensity |
| BLS QCEW (open API) | Calendar 2023 Q1 – 2026 Q1, county × NAICS 722515 / 722513, private | Market wage growth weighted to Starbucks' footprint |
| Starbucks 8-K releases | FY24 Q2 – FY26 Q3 | North America store revenue and store operating expenses (`tables/filings_store_opex.csv`) |

## Definitions
- **Visits per operating hour** = Advan visits per week (13-week mean) ÷ posted weekly hours. Advan is a sample, so the level is not the true
  number of customers. Compare across stores and over time only.
- **Traffic growth** = 13-week mean visits ÷ the same 13 weeks a year earlier − 1 (trimmed at the 1st/99th percentiles).
- **Metro fixed effects:** outcome and regressors demeaned within Advan MSA (metros with ≥ 3 stores). SEs are HC1 robust with a degrees-of-freedom
  correction for the absorbed fixed effects.
- **Oct-2025 closure wave** = Advan close date Sep 1 – Nov 30 2025, company-operated. Filings confirm 627 closures (520 U.S.).
- **Operating leverage** (`tables/operating_leverage.csv`) = incremental North America store opex ÷ incremental company-operated revenue, YoY.

## Known biases
- Advan panel composition changed during 2024–25: national dwell and visit levels shift for both brands. Prefer Starbucks-vs-Dunkin' or within-store comparisons.
- Posted hours ≠ labor hours. None of these sources observe partners per shift, wages or scheduled labor hours, which is where store
  labor cost is decided.
- Careers postings are batch-created standing requisitions (90-day expiry), so they measure pipeline, not staffing.
- Advan `VISITS_BY_EACH_HOUR` levels drift over time (hourly totals fell YoY while visit counts rose), so only its time-of-day shares are used.
- QCEW average weekly wage mixes hourly rates with hours per worker; some county cells are suppressed.
- Wayback coverage is crawler-driven; only within-period relative measures are used.
- The closure-risk model is fit on one closure wave and describes similarity to it; it is not a forecast.
