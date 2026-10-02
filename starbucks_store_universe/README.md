# starbucks_store_universe

Current U.S. Starbucks location universe, used as the denominator for hiring metrics.

- **Source:** All the Places spider `starbucks_us` (Starbucks store-locator API), run 2026-09-26..29, CC0.
- **Build:** `python src/build_universe.py [--hiring <cleaned postings csv>]`
- **Outputs:** `data/processed/starbucks_store_universe.csv` (16,707 locations, 9,979 company-operated),
  `data/processed/hiring_store_join.csv` (hiring store → locator location), `outputs/store_universe_validation.md`.
- **Method:** address match (house number + street), then coordinates within 75 m with a name/address-similarity check.
  There is no store-number join, because the locator ID ≠ job-title store number.
- **Limitations:** single point in time; third-party scrape; locator may omit new or temporarily closed stores.
  Licensed stores must be excluded from hiring denominators.
- **Investment suitability:** good as a denominator for company-operated store shares; not evidence on its own.
- Reads `../starbucks_hiring` outputs; never writes there.
