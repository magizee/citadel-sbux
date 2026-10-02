# Prioritization (updated 2026-10-02 03:20 ET, after the national run)

Ranking criteria, in order: (1) can it distinguish standing requisitions from genuine staffing pressure;
(2) does it link staffing to operating outcomes; (3) does it establish that the turnaround depends on staffing;
(4) can it be completed today.

| Rank | Data / analysis | Folder | Why it matters | Status | Available today? | Time to complete | Value to thesis | Supports / falsifies / context | Next action |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **National snapshot: deviation metrics** (off-pattern stores, same-role duplicates, 3+ roles) and **leadership postings per CO store by market** (Tests A, B) | starbucks_hiring (+ store_universe, labor_market) | The only cross-sectional measures that can separate pressure from standing requisitions | **Done** (national run complete 03:07 ET; tests run) | Yes | Done | **High** | Can support or falsify | Wait for the scrape; then `merge_states.py` → `analyze.py` → join store universe + labor controls |
| 2 | **Repeat snapshot after the July 4 batch expires (2026-10-02)** | starbucks_hiring | Tests whether frontline requisitions are standing (reposted at the same stores) or real vacancies (disappear). Also re-checks leadership postings | **Done (first pass):** 137 stores / 145 requisitions re-checked 3 h after expiry; 0 replaced. Second pass from Oct 3 still useful | Partly: a targeted re-check (detail lookups for ~200–500 July-4 postings + searches around their stores) can run tomorrow morning | 0.5–1.5 h runtime | **High** | Falsifies or supports the standing interpretation | Approve a one-off targeted re-check (not a recurring scraper) |
| 3 | **Wayback full CDX index** (46 index requests) → postings by store, role and crawl burst for 2025–2026 | starbucks_archive | Was the 1 barista + 1 supervisor pattern the same in earlier bursts? Were leadership postings more or fewer per store in Apr 2026 vs. today? | **Done**: full index (155,626 postings) + 231 pages → requisition-sequence YoY | Yes | ~15 min pull + 1 h analysis | Medium–high (indicative, biased coverage) | Context, with some falsifying power | Approve the 46-page index pull; no page scraping needed |
| 4 | Management evidence | starbucks_management_research | Establishes that staffing and leader stability are central to the turnaround, and that management reports improving inputs and outputs | **Done** (16 statements, verified quotes) | Yes | — | High (premise) | Supports the *premise*; reported outcomes **contradict** the outcome leg | Optional: add Q4 FY25 and Investor Day (2026-01-29) |
| 5 | Store-universe penetration + new-store flag (Test F) | starbucks_store_universe | Denominator; flags hiring at stores not in the locator (likely openings, an alternative explanation) | **Done**: national join 97.1%; 99.3% of CO stores hiring | Yes | 15 min after national | Medium | Context | Run `build_universe.py --hiring <national csv>` |
| 6 | Foot traffic (Advan / pass_by via Dewey) | starbucks_operating_data | The only realistic store-level outcome measure (Test E) | Identified; access unknown | Only if your institution has Dewey | Hours to days | **High** if accessible | Can support or falsify | Check Dewey access |
| 7 | Historical postings (LinkUp / Revelio Postings via WRDS) | starbucks_historical_hiring | Real time series of requisitions incl. removal dates | Identified; access unknown | Only with access | Hours | **High** if accessible | Can support or falsify | Check the WRDS subscription list |
| 8 | Labor-market controls | starbucks_labor_market | Separates local labor tightness from Starbucks-specific pressure | **Done** (state level) | Yes | — | Medium | Context / control | Join to market summary after the national run |
| 9 | Store hours cross-section | starbucks_operating_data | Weak outcome proxy (hours are standardized) | **Built** | Yes | 15 min | Low | Weak support or falsification | Join after the national run |
| 10 | National pay pull | starbucks_pay_analysis | Pay is a zone ladder with no posting-level variation | Pilot done | Possible, but 15+ h | — | Low | Pilot: no support | **Skip** (or map zones with 1–2k requests only if needed) |

## Already-established findings that shape the thesis

- Frontline postings are **batch-created standing requisitions with a fixed 90-day expiry**. Raw volume and frontline age are weak signals.
- Store-manager postings are **area-level and individually timed**. Leadership is the most informative posting signal.
- **Reported outcomes are strong** (Q3 FY26: U.S. comps +7.9%, transactions +4.2%, margin expanding; management reports
  record-low hourly turnover and improving leader tenure). To support a short, the data would need to show concentrated,
  non-standard pressure that these aggregates hide, or a forward risk (labor hours lagging growth; margins after the Q4
  anniversary). Neither is established yet.
