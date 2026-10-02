# starbucks_labor_market

State-level labor-market controls, to check whether Starbucks hiring signals simply reflect local labor conditions.

- **Build:** `python src/build_controls.py` → `data/processed/labor_market_controls.csv` (51 rows, join key `state`).

| Variable | Source | Date | Notes |
|---|---|---|---|
| unemployment_rate, 12-month change (pp) | BLS LAUS, seasonally adjusted (series `LASST{fips}0000000000003`), BLS API v1 | Latest month: 2026-08 | Raw JSON in `data/raw/` |
| lsr_employment, YoY % | BLS QCEW, NAICS 722513 limited-service restaurants, private, state | 2026 Q1 (month 3) | Raw CSVs for 2026Q1 and 2025Q1 in `data/raw/` |
| lsr_avg_weekly_wage, YoY % | BLS QCEW, same | 2026 Q1 | Weekly wage, not hourly; mixes hours and rates |
| state_minimum_wage, binding_statewide_minimum_wage | U.S. DOL WHD state minimum wage table | Effective 2026-07-01 | **Extracted from the DOL page by an automated reader (direct download was blocked with 403); spot-check before use.** Ignores local (city/county) and industry-specific minimums, e.g. California's $20 fast-food minimum wage and NYC's rate |

- **Interpretation:** use these as controls in market comparisons (e.g. are states with high leadership-posting
  intensity simply tight labor markets?). They do not measure Starbucks-specific difficulty.
- **Granularity:** state. QCEW also has county and MSA rows (in the raw CSVs) if a city / metro proxy is needed later.
- **Limitations:** state averages hide metro variation; QCEW lags about 6 months; minimum-wage table needs verification.
- **Investment suitability:** good as controls; not evidence on their own.
