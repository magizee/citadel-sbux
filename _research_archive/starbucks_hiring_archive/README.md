# starbucks_hiring_archive

Store-level hiring history built from Internet Archive (Wayback) captures of Starbucks careers job pages.
Results and their interpretation: [`pitch_data/03_archive_hiring/README.md`](../../pitch_data/03_archive_hiring/README.md).

**Run:** `python3 _research_archive/starbucks_hiring_archive/src/archive_hiring.py` from the repo root. It takes about 5 s and needs the outputs of the `pitch_data` panel and hours steps.

**Inputs (read only):**
- `_research_archive/starbucks_archive/data/processed/archived_postings.csv`: 155,626 postings, built by the CDX / slug parser in
  `_research_archive/starbucks_archive/src/`.
- The store-locator snapshots in `pitch_data/data/raw/alltheplaces/`. The store number is taken from the `website` URL: `/store/<number>-<id>/`.
- `pitch_data/04_operating_hours/store_hours_panel.csv`: locator to Advan store, closure status, metro.

**Outputs:**

| File | Contents |
|---|---|
| `data/archived_postings_linked.csv` | postings with store number → locator → Advan store, fiscal quarter |
| `data/store_fiscal_year_hiring.csv` | store × FY postings, relative intensity, quarters with postings, Advan visits FY25/FY26 |
| `outputs/role_mix_by_fiscal_quarter.csv` | role shares by fiscal quarter |
| `outputs/traffic_growth_vs_archive_hiring.csv` | OLS with metro FE |
| `outputs/archive_hiring_by_growth_cohort.csv` | relative intensity by traffic-growth cohort |
| `outputs/manager_postings_by_city.csv` | city-level store-manager postings vs traffic growth |
| `outputs/results.json`, `outputs/archive_hiring.png` | summary and chart |

**Coverage and caveats:**
- Crawl volume per fiscal quarter ranges from about 1.3k (FY26 Q4, partial) to 25k (FY25 Q3). Quarters under 10k are thin.
- A Wayback capture proves a posting existed at that time, not when it was created or how long it stayed open.
- Store-manager postings have no store number (city slug only), so they are analyzed at city level.
- Only measures that are relative within a period are interpretable. Totals mostly reflect crawler activity.
