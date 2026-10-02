# starbucks_operating_data

Sources that could connect staffing-pressure signals to store outcomes (traffic, hours, closures, service).

- **Inventory:** `outputs/source_inventory.md` (metric, granularity, history, access, join key, strength, time to use).
- **Built today:** `src/store_hours.py` → `data/processed/store_hours.csv`. Posted weekly hours for 9,979 company-operated
  stores from Starbucks' store locator (via All the Places, 2026-09-26), read from `../starbucks_store_universe`.
  Join it to hiring data with `../starbucks_store_universe/data/processed/hiring_store_join.csv`.
- **Limitations:** posted hours (not actual), one snapshot, highly standardized hours; there is no traffic or service data without paid access.
- **Investment suitability:** hours are weak context only. Foot traffic (Advan / pass_by via Dewey) is the strongest candidate but needs institutional access.

## Advan foot traffic via Dewey (Test E), DONE 2026-10-02

1. In Dewey: open **Advan → Monthly Patterns** (or Weekly). Copy the dataset's **API endpoint** and create an **API key**.
   If the site lets you filter to brand = Starbucks before export, that is the easiest route (see step 3b).
2. In your terminal (do not commit keys):
   `pip install deweydatapy@git+https://github.com/Dewey-Data/deweydatapy` · `export DEWEY_API_KEY='…'` · `export DEWEY_ADVAN_PATH='…/files'`
3. a) API: `python src/advan_pull.py --check`, then `--start 2026-01-01 --end 2026-03-31` (test), then the full window
      (Jan 2024 →). Each file is filtered to Starbucks rows and the unfiltered file is deleted.
   b) Manual: put Starbucks-filtered exports in `data/raw/advan/` and run `python src/advan_pull.py --local`.
4. `python src/advan_analysis.py` → `outputs/advan/` (store-level YoY visits and dwell; leadership-zone and hiring-pattern
   comparisons relative to state medians, with bootstrap CIs; chart).

Tested end-to-end on synthetic data (since deleted). Needs ≥ 15 months of data for the year-over-year window.

### Results (2026-10-02)
Source: Dewey project dataset `prj_…__cdst_…` (Advan Weekly Patterns Plus, Starbucks-filtered), downloaded with the v1 API
(`advan_pull.py` detects `prj_` IDs). 143 weekly files, Jan 2024 → Sep 21 2026; U.S. rows only; store ID = `ID_STORE`.
Outputs in `outputs/advan/`: `advan_results.json`, `visits_by_group.csv`, `store_visits_yoy.csv`,
`visits_yoy_by_group.png`, `advan_closures_by_month.csv`, `closures_by_month.png`.
Headline: manager-vacancy areas grow visits faster (+0.5 to +0.8 pp vs state; robust within metro + density); closure waves
in Oct 2025 (481) and spring 2026 (~300).

### Overcrowding / closure transfer (`src/advan_overcrowding.py`)
Cannibalization (visits per store ≈ half in the densest quintile; within-metro elasticity −0.19), pruning (9.2% vs 2.6% closed
since Oct 2025), and transfer (+1.6 pp < 1 km from a closure, +1.1 pp at 1–2 km, ~0 beyond). Removing closure-adjacent stores
eliminates the apparent "manager-vacancy areas grow faster" effect. Outputs: `outputs/advan/overcrowding_results.json`,
`density_quintiles.csv`, `yoy_by_closure_distance.csv` and three charts.
