# Historical Starbucks frontline job-posting data: candidate sources

Requirement: **retail / frontline posting history** (barista, shift supervisor, store manager, district manager) with
dates and locations. Corporate headcount or employee-profile data does not qualify.
Assessed 2026-10-01. Vendor and library descriptions were checked by web search; access depends on your institution
and is **unconfirmed**.

| Source | Starbucks coverage | Barista | Shift supv. | Store mgr. | District mgr. | History | Posting date | Removal date | Location | Store-level ID | Cost / access | Usable today? | Likely coverage bias |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **LinkUp** (RAW / job-level data) | Yes. Indexes employer career sites directly | Yes | Yes | Yes | Yes | Since 2007, daily | Yes | **Yes** (de-listing date) | Yes | Title text includes "Store# NNNNN", so parseable | Paid (direct, FactSet, Datarade); some academic deals | Only if you already have access | Low: scrapes the same careers site we scrape, so it has the same standing-requisition artefact |
| **Revelio Labs – Job Postings** (COSMOS) | Yes. 350k+ company sites + job boards | Yes | Yes | Yes | Yes | ~2021+ | Yes | **Yes** (removed postings) | Yes | Title text | Paid; **WRDS** at some universities (one library notes its WRDS Revelio access expires June 2026) | Only if your institution has it | Moderate: board duplicates are de-duplicated; frontline coverage should be checked |
| Revelio Labs – Workforce dynamics | Employee profiles | **Weak** for frontline (baristas are rarely on LinkedIn) | Weak | Partial | Partial | 2008+ | n/a | n/a | Yes | No | WRDS / paid | — | **Do not use** for frontline staffing |
| **Lightcast** (Burning Glass) | Yes, aggregated postings | Yes | Yes | Yes | Yes | 2010+ | Yes | Approx. (expiry) | Yes (county / MSA) | Title text | Paid; university licenses are common | Only with existing access | Moderate: board aggregation, de-duplicated |
| Thinknum (Alternative Data) | Yes. Company job-listing counts | Yes (by title) | Yes | Yes | Yes | ~2017+ | Yes (first seen) | Yes (last seen) | City / state | Title text | Paid; some academic access | Only with access | Low; built from the careers site |
| Dewey (marketplace) | Hosts job-posting vendors (varies) | Varies | Varies | Varies | Varies | Varies | Varies | Varies | Varies | — | Academic subscription | Check catalog | Depends on vendor |
| **Internet Archive (Wayback)** | Some captures of `apply.starbucks.com/careers/job/*` (CDX index reported 46 index pages) | Sparse | Sparse | Sparse | Sparse | Since the site moved to Eightfold | Sometimes (JSON-LD) | No (only capture dates) | Sometimes | Title text | Free | **Tested today, inconclusive:** Wayback was degraded during the test | **High**: captures are opportunistic, not representative |
| Indeed Hiring Lab / Job Postings Index | Aggregate (sector), no employer detail | No | No | No | No | 2020+ | — | — | Country / state | No | Free | Yes, but for **sector context** only | n/a |
| BLS JOLTS (accommodation & food services) | Industry openings / hires / quits | No | No | No | No | 2000+ | — | — | National (state estimates exist) | No | Free | Yes, as context | n/a |

## Assessment

- **Best fit:** LinkUp or Revelio Postings. Both record posting **and removal** dates for the same careers-site
  requisitions, so they would show how long requisitions stay open and how often they are reposted (standing vs.
  replacement) over time. That is exactly what a one-day snapshot cannot show.
- **Caution:** because the frontline requisitions are batch-created with a fixed 90-day expiry (see
  `starbucks_pay_analysis/outputs/pay_validation.md`), historical "time-to-fill" from any of these vendors would mostly
  measure the refresh cycle. The more useful historical metrics are **counts of distinct requisitions per store per
  quarter**, **leadership-posting counts by market**, and **changes in the batch cadence**.
- **Next action (no big extraction without approval):** check your institution's WRDS subscription list for
  "Revelio Labs – Job Postings" and your library for Lightcast / LinkUp. If available, pull Starbucks (RCID / ticker SBUX)
  U.S. postings for 2023–2026 filtered to the four retail titles: one query, not a scrape.
