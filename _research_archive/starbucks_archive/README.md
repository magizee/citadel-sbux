# starbucks_archive

Can the Internet Archive provide historical evidence on Starbucks job postings? (PILOT / VALIDATION)

- **Source:** Wayback Machine CDX API (`web.archive.org/cdx/search/cdx`) and raw playback (`/web/<ts>id_/<url>`). Tested 2026-10-01.
- **Scripts:**
  - `src/archive_lookup.py --build-candidates`: picks 10–20 NYC-pilot postings (reads `../starbucks_hiring`, never writes there)
  - `src/archive_lookup.py`: CDX prefix lookups → `data/raw/cdx/`, `data/processed/archive_index.csv`
  - `src/parse_archived_jobs.py [--index …]`: fetches archived HTML → `data/raw/pages/`, parses JSON-LD → `data/processed/archive_history.csv`
- **Results:** `outputs/archive_validation.md`. Current postings are rarely captured (1/16), but the job-URL index is large
  (~55k captures in 6 of 46 index pages, mostly 2025–2026) and archived pages often carry JSON-LD with datePosted.
- **Limitations:** bursty, crawler-driven coverage; not representative; captures ≠ existence; Wayback availability varies.
- **Investment suitability:** indicative historical context only (e.g. was the standing pattern the same in earlier bursts?), not a trend series.
- **Requirements:** `requests`, `pandas`.
