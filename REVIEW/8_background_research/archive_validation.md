# Internet Archive (Wayback Machine): small validation

> PILOT / VALIDATION ONLY. Run 2026-10-01, 22:55–23:15 ET. No large archive scrape was launched.

## What was tested

1. **Candidate lookup** (`src/archive_lookup.py`): 16 postings from the NYC pilot (6 oldest, 1 leadership, 5 at stores with
   unusual role sets / same-role duplicates, 2 standard-pattern controls, 2 non-retail controls). Each was queried in the
   CDX index as a URL **prefix** on both careers hosts (32 queries). Raw responses: `data/raw/cdx/`. Index: `data/processed/archive_index.csv`.
2. **Index sample** (`data/raw/cdx_prefix_page*.txt`): 6 of 46 CDX index pages for `apply.starbucks.com/careers/job/*`,
   parsed into `data/processed/archive_prefix_sample.csv` (role and store number parsed from the URL slug).
3. **Page parse test** (`src/parse_archived_jobs.py`): 10 archived job pages (3 barista, 3 shift supervisor, 3 store manager,
   1 district manager), saved under `data/raw/pages/`. Results: `data/processed/archive_history.csv`.

**Operational note:** Wayback was degraded at the start of the test. CDX returned empty results even for `example.com`,
and playback returned HTTP 500. The first lookup pass was discarded and rerun after the service recovered (~23:10 ET).
A first design flaw was also fixed: archived job URLs carry a title slug
(`/careers/job/481052354323-barista-store-71315-…`), so exact-URL lookups miss them; prefix queries are required.

## Results

| Metric | Result |
|---|---|
| Current pilot postings tested | 16 |
| With any capture | **1** (the corporate "Influencers" posting, captured 2026-05-16) |
| Index sample: captures / distinct postings / distinct store numbers | **54,983 / 36,566 / 11,543** (from 6 of 46 index pages) |
| Earliest / latest capture in sample | 2023-05-30 / 2026-09-16 |
| Role mix of archived postings (first capture) | Mostly barista and shift supervisor; store manager ~2–3%; district manager rare |
| Usable archived job pages | **7 of 10** carry schema.org JobPosting JSON-LD (title, store number, city/state, **datePosted**). 3 of 10 are generic shells (likely expired or redirected postings) |

**Example reconstructed postings**

| Captured | Title | datePosted | Location |
|---|---|---|---|
| 2026-04-18 | barista - Store# 00702, DUPONT CIRCLE | 2026-03-15 | Washington, DC |
| 2026-04-15 | barista - Store# 02588, OXFORD - MIAMI UNIVERSITY | 2026-03-19 | Oxford, OH |
| 2026-04-17 | shift supervisor - Store# 13674, WESTCHESTER COMMONS | 2026-03-05 | Midlothian, VA |
| 2026-05-11 | store manager | 2026-04-28 | South Orange, NJ |
| 2026-06-11 | store manager | 2026-05-28 | Seagoville, TX |

## Coverage pattern

Captures come in **crawl bursts**, not continuously. First captures of distinct postings by month (sample):
large bursts in Mar 2025, Jun 2025, Oct 2025, and Mar–Jul 2026 (Apr 2026: ~14,000 postings in the sample alone),
with near-zero months in between. A burst approximates a cross-section of postings live at that time.

## Cautions

- Missing captures do **not** mean a job did not exist. Coverage depends on crawler schedules and is **not representative**.
- Archived JSON-LD `validThrough` is always datePosted + 180 days (including store managers). It looks like a generic SEO field
  and should **not** be compared with the live API's 90-day requisition expiry.
- Index pages are ordered by URL, so a sample of pages covers ranges of posting IDs, not a random sample of time or stores.
  Per-store statistics need the full index.

## Is it worth expanding after the national analysis?

**Yes, as a targeted second step.** It is the only free source found that can show:
- whether the standing pattern (one barista + one supervisor requisition per store) held in earlier crawl bursts;
- how many distinct requisitions a store cycled through over 2025–2026 (store-level requisition churn);
- whether leadership postings were more or less common in, say, Apr 2026 than today.

Suggested expansion (needs approval): pull all 46 CDX index pages (~46 small requests, URL slugs give role + store number
+ first-seen date with no page fetches), then fetch JSON-LD for a stratified sample of a few hundred pages for posting dates.
Treat burst-to-burst comparisons as indicative only.

---

## Update (2026-10-02 ~02:45 ET): full index + requisition-sequence test

Following the validation, two small extensions were run (user asked for maximum research overnight):

1. **Full CDX index** (`src/archive_index_pull.py`, 46 index requests, no page fetches): **314,856 captures of 155,626
   distinct archived postings at 12,005 store numbers**, 2024–2026 (`data/processed/archived_postings.csv`).
   By first-capture year: 2024 ≈ 19k, 2025 ≈ 89k, 2026 ≈ 47k postings (crawl-dependent, not hiring volume).
2. **Requisition-sequence sample** (`src/archive_req_sequence.py`, 231 archived pages, about 10 per month for 2024–2025):
   the 2024–2025 page template embeds the position record (`t_create`, `ats_job_id`), giving 186 usable
   (creation date, requisition number) pairs (`data/processed/req_sequence_points.csv`).

**Finding:** requisition numbers are `YY` + a 7-digit sequence that rises **perfectly** with creation date within each year
(Spearman 1.0 in both 2024 and 2025; also 1.0 for the 2026 live data). The sequence reached by a date therefore counts
**all requisitions Starbucks created that year so far**, including ones already filled or closed. Pages from Aug 2025 onward
use a new template without the embedded record, so 2025 points stop at Jul 30.

This turns the archive into a real year-over-year measure of requisition creation. Analysis and chart:
`../starbucks_thesis_tests/outputs/charts/T5_requisitions_created_ytd.png`.
