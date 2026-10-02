# Starbucks U.S. retail job postings: data collection

Collects public Starbucks job postings (barista, shift supervisor, store manager, etc.)
from the Starbucks careers site for retail staffing research.

**Status: national snapshot collected 2026-10-01 (run started 22:14 ET); see `outputs/analysis_summary.md`.**

---

## How the site is accessed

`careers.starbucks.com` links to an Eightfold-hosted search at `https://apply.starbucks.com/careers`,
which loads results from a public JSON endpoint. This project calls that endpoint directly:

```
GET https://apply.starbucks.com/api/pcsx/search
    ?domain=starbucks.com
    &location=<"lat,lon"  or free text>
    &filter_distance=<radius in KILOMETRES>
    &filter_include_remote=0
    &start=<offset>
```

### Backend behaviour (verified with targeted single-page probes)

| Question | Finding |
|---|---|
| Page size | Fixed at 10; `num` is ignored |
| Pagination | `start` offset. NYC (799 results): offsets 0, 240, 490, 740 each gave 10 unique rows, 790 gave the final 9 (= 799), 800+ gave 0. No repeated IDs |
| Result cap | None. A 21,675-result query served its last page at `start=21670` |
| Filter syntax | Filters need a `filter_` prefix. `include_remote=0` and `distance=…` are silently ignored; `filter_include_remote=0` and `filter_distance=…` work (echoed in `appliedFilters`) |
| Remote jobs | `filter_include_remote=0` is applied; the NYC count stays 799 (no remote jobs near NYC). The Seattle rows in pilot v1 were **not** remote: they are onsite corporate jobs listed in both NYC and Seattle |
| Radius unit | **Kilometres.** 95–100% of results fall within the radius read as km. The UI's "40" means 40 km ≈ 25 mi |
| Max radius | No cap observed. 8, 40, 160, 500 and 3,000 km were all honoured (3,000 km from Kansas City → 21,675 jobs) |
| Coordinates as input | **Yes.** `location=39.0997,-94.5786` gives the same 117 results as `Kansas City, MO`. `lat=`/`lng=`/`latitude=` parameters are ignored |
| Explicit state filter | **None.** No `state`/`region` parameter or state facet. Facets are job_category, job_function, job_level, remote, and an address-level lat/long facet |
| State names as text | Geocoded. Most state names are region-matched (no radius; OK, NV, TX, CT, NJ, WA, GA, CA checked by address list). **But "New York, United States" and "NY, United States" geocode to NYC with a 40 km radius**, "District of Columbia" is treated as a city radius, and RI includes four MA border towns. So text state search is not trustworthy as a collection method |
| Coordinates in output | Not on each job. Each response carries an address → lat/long list (`latlong_non_remote` facet) for **all** results of the query, **capped at 1,500 addresses** |
| Posting date | `postedTs` (Unix seconds) on every job. The "x days ago" text is rendered in the browser, not sent |
| Postal code | Not exposed anywhere (search or detail). Left null |
| Store numbers | Only in titles. The detail endpoint has no store field |
| Blocked endpoint | Legacy `/api/apply/v2/jobs` → 403. Not used; no workaround attempted |
| Rate limiting | None seen at ~1 request / 2.5–3 s (≈110 requests total so far) |

---

## Collection model

**Collection geography is separate from output geography.**

* A **search unit** is one query: `search_id, query_location, query_latitude, query_longitude, query_radius_km`.
* A **run** is a list of search units (pilot = 1; national = adaptive grid).
* A posting can be **discovered** by many searches. `<run>_discoveries.csv` records `job_id, position_id, search_id, snapshot_date, page_start`.
* After collection, postings are deduplicated by `job_id`. Each posting's **state comes from its own address**.
  State files are derived outputs (`by_state/<ST>.csv`), not search partitions.

### National method: adaptive coordinate grid (designed, not run)

1. Level-0 circles on a fixed hex lattice cover CONUS (88 × 400 km), Alaska (20 × 1,200 km) and Hawaii (1 × 400 km).
2. For each circle, fetch page 0 (count + address list):
   * count 0 → `empty`; only non-US addresses → `no_us_results`;
   * count > 1,500 or address list truncated (1,500) → `split` into next-level circles (100 km, then 25 km),
     taken from a fixed global lattice so neighbouring parents share children (each queried once);
   * otherwise paginate to the end.
3. Geometry is verified by `python src/geo_grid.py`: 100% coverage of every region bounding box at every level,
   and children cover 100% of their parent.
4. Deterministic (same counts → same plan) and resumable (saved pages are reused, never re-fetched).

**Completeness of each search:** a search is `complete` only if the last page was reached (a short page, or
`start ≥ count`), the server-reported count was identical on every page, **and** unique postings
collected = that count. Otherwise it is `incomplete` and should be re-run (`--fresh` for that search).
**National check:** the US-only unique total is compared with the server count for
`location="United States"` (19,919 on 2026-10-01).

---

## Setup

```bash
cd starbucks_hiring
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Commands (run from `starbucks_hiring/`)

```bash
# Pilot: Manhattan, 40 km, remote off, <=250 postings
python src/scrape_jobs.py --pilot
python src/clean_jobs.py
python src/validate.py

# Ad-hoc searches
python src/scrape_jobs.py --point 40.7128,-74.006 --radius-km 40 --max-results 250
python src/scrape_jobs.py --location "New York, NY" --max-results 250
python src/scrape_jobs.py --state CA        # text state search: CROSS-CHECK ONLY

# National (NOT YET RUN; needs approval)
python src/scrape_jobs.py --national --plan-only --confirm   # page-0 probes only; pages are reused later
python src/scrape_jobs.py --national --confirm
python src/merge_states.py --national-count <count for "United States">
python src/analyze.py        # store_summary.csv, market_summary.csv, outputs/ (charts, national summary)
```

Incomplete searches are retried automatically, that search only, up to 2 times, with the reason logged. A search still
incomplete after that keeps status `incomplete` and is listed in `merge_report.txt`.

## Resume behaviour

* Every response is saved immediately (atomic write) to `data/raw/<date>/searches/<search_id>/page_<start>.json`.
* Re-running the same command with the same `--snapshot-date` reuses saved pages and continues, with no repeat requests.
* Saved pages store their query parameters; reusing a search_id with different parameters is refused.
* `--fresh` discards saved pages for the searches in that command.
* Transient errors (timeouts, 429, 5xx) are retried with exponential backoff (4 s·2^n + jitter, ≤120 s, 5 tries, `Retry-After` honoured). 401/403 stop the run.

## Output files

| Path | Content |
|---|---|
| `data/raw/<date>/searches/<search_id>/page_*.json` | Untouched API responses |
| `data/raw/<date>/searches/<search_id>.json` | Search manifest: unit, status, counts, pages, applied filters |
| `data/raw/<date>/runs/<run>.json` | Search units belonging to a run |
| `data/raw/<date>/<run>.csv` | One row per (search, posting) discovery; full original record in `raw_json` |
| `data/raw/<date>/<run>_discoveries.csv` | job_id × search_id discovery table |
| `data/raw/<date>/<run>_latlong.csv` | Address → lat/long pairs |
| `data/processed/<date>/<run>_clean.csv` | One row per posting (pilot: `pilot_jobs_clean.csv`) |
| `data/processed/<date>/store_summary.csv` | Pilot store summary (`<run>_store_summary.csv` for other runs) |
| `data/processed/<date>/<run>_validation.txt` | Validation report |
| `data/processed/<date>/starbucks_jobs_US.csv`, `by_state/<ST>.csv`, `merge_report.txt` | National postings (one row per job_id, US only) |
| `data/processed/<date>/store_summary.csv` | National: one row per store_key (retail postings) |
| `data/processed/<date>/market_summary.csv` | State, city/state, role and national rows (`geography_level`) |
| `outputs/charts/*.png` + `.csv` | Pitch charts and their data |
| `outputs/national_summary.json`, `outputs/oldest_*.csv`, `outputs/analysis_summary.md` | Headline metrics and write-up |
| `data/processed/<date>/pilot/` | Pilot outputs (moved here so national files do not overwrite them) |
| `data/*/2026-10-01/_superseded_v1/` | First pilot (remote included, v1 parser), kept for reference |

### Cleaned columns and rules

`snapshot_date, job_id, job_url, job_title_raw, role_bucket, store_number, store_name, street_address,
city, state, postal_code, country, posted_text, posted_ts_raw, posted_date, days_since_posted, latitude,
longitude` + `position_id, dedup_key, store_key, department, work_location_option, location_raw,
n_locations, all_states, search_ids, n_searches`.

* **Dates:** `posted_ts_raw` is the backend timestamp; `posted_date` is its UTC date; `days_since_posted` = snapshot − posted_date.
  `posted_text` stays null (not sent by the API). `parse_relative_age()` exists only to validate such text if it is ever captured.
* **Store number:** from titles `role - Store# 09230, NAME` or `… - NAME, Store# 57845, City`. Kept as text (leading zeros).
  Never invented. `store_key` = `store:<number>`, else `addr:<street>|<city>|<state>` (e.g. Reserve Roasteries).
* **Location:** parsed from the raw address (`street…, city, state name, country`). Multi-location jobs use the
  location nearest the centre of a search that found them (first listed on ties). `all_states` lists every state.
* **role_bucket:** DISTRICT_MANAGER > STORE_MANAGER (incl. assistant store manager, coffeehouse leader) >
  SHIFT_SUPERVISOR (incl. "shift manager") > BARISTA > OTHER_RETAIL (store number or in-store roles such as
  mixologist, operations lead, baker, porter) > NON_RETAIL.

## Pilot validation (2026-10-01, Manhattan 40 km, remote off)

| Check | Result |
|---|---|
| Server count | 799 (same as the text query "New York, NY") |
| Rows / unique postings / duplicates | 250 / 250 / 0 |
| Remote filter | `includeRemote=0` applied; all 250 `onsite`. Seattle rows now resolve to their NYC location |
| States (primary location) | NY 233, NJ 17 |
| Unique store numbers | 118 (122 store_keys) |
| Retail missing store number | 13 (5.3%): 11 at NY Roastery / Reserve Kitchen (no store number published anywhere), 1 multi-store manager role (Hoboken + Jersey City) |
| Store-number consistency | 109 stores with 2+ postings: all share one name, address and lat/long |
| Missing lat/long / address / postal | 0% / 0.8% / 100% (not exposed) |
| posted_ts present | 250 / 250; dates 2026-07-04 → 2026-09-30 |

## National estimate (not run)

| Item | Estimate |
|---|---|
| Expected unique US postings | ≈19,500–20,000 (server: 19,919) |
| Expected unique stores | ≈8,500–9,000 (pilot: ~2 postings/store, ~92% of retail postings carry store numbers) |
| Search units | 109 roots → ≈450–800 leaf searches after splitting (≈25–40 splits) |
| Pages per leaf | median ≈2–5; dense metro leaves up to ~150 |
| Raw duplicate rate | ≈25–40% of discovery rows (hex overlap ≈1.34× plus split probes) |
| HTTP requests | ≈3,100–3,800 |
| Runtime | ≈2.5–3 h at 2.5 s delay; ≈4 h at 4 s |

Estimates use known counts and grid geometry. `--plan-only` replaces them with exact numbers; its pages are reused by the full run.

### Risks
* **Pagination drift:** postings added or removed mid-search shift pages. Searches are kept small, and any change is detected (`incomplete`) so that search can be re-run.
* **Multi-location jobs:** counted once and assigned to one state. `all_states` keeps the rest.
* **Canada:** the same site serves Canadian jobs. These are filtered by country, but border circles fetch some of them.
* **Undocumented API:** it may change. Raw responses are kept so parsing can be redone offline.

**Recurring / scheduled scraping is intentionally not set up.**
