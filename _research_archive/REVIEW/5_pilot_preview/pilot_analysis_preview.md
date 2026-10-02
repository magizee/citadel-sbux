# Pilot analysis preview

> **NYC PILOT — NOT NATIONALLY REPRESENTATIVE.** 250 postings nearest Manhattan City Hall (40 km radius, remote jobs excluded),
> collected 2026-10-01. The server reported 799 matches for this radius; the pilot intentionally stopped at 250, which are the
> postings closest to the centre (mostly Manhattan and Brooklyn). Its purpose is to exercise the analysis pipeline and
> surface patterns to test nationally, not to describe Starbucks' hiring.

Charts: `outputs/charts/pilot/` · tables: `outputs/tables/pilot/` · code: `src/pilot_preview.py`, `src/store_patterns.py`, `src/qa.py`

## Metrics

| Metric | Pilot value |
|---|---|
| Total postings | 250 |
| Retail / non-retail | 243 / 7 |
| Unique hiring stores (store_key) | 120 (118 store numbers + 2 address-keyed Reserve locations) |
| Role counts | Barista 116 · Shift supervisor 115 · Store manager 1 · District manager 0 · Other in-store 11 |
| Median retail posting age | 28 days |
| Retail postings open > 30 / > 60 days | 31.3% / 12.3% |
| Stores with 2+ role types open | 110 (91.7%), almost all of it the standard barista + supervisor pair (see below) |
| Stores with a same-role duplicate | 4 (3.3%) |
| Leadership postings | 1 store manager (covers Hoboken and Jersey City; no single store) |
| Stores with a manager posting tied to a specific store | 0 |
| QA | All checks pass (`qa_report_pilot.md`) |

## The dominant store-level pattern

| Pattern | Stores | % of hiring stores |
|---|---|---|
| **Exactly 1 barista + 1 shift supervisor, nothing else** | **107** | **89.2%** |
| Barista + shift supervisor (any count) | 108 | 90.0% |
| Shift supervisor only | 7 | 5.8% |
| Barista only | 2 | 1.7% |
| Barista + other in-store (Reserve formats) | 2 | 1.7% |
| Other in-store only (Reserve Kitchen) | 1 | 0.8% |
| Barista + supervisor + store manager | 0 | 0% |
| Store manager only | 0 | 0% |
| Multiple barista postings | 2 | 1.7% |
| Multiple supervisor / store-manager postings | 0 | 0% |

## What the pilot appears to show

1. **Most postings look like standing, store-level requisitions, not counts of individual vacancies.** Nine in ten
   hiring stores carry exactly one barista and one shift-supervisor posting. A store with three open barista shifts
   and a store with none would likely look the same here. So **raw posting volume is close to "number of stores with an
   open pipeline", and "postings per hiring store" (≈2.0) carries almost no information by itself.**
2. **"Multiple roles open" is the norm, not a signal.** 92% of hiring stores have 2+ role types, because the standard
   pattern is itself two roles. The informative version is *deviation* from the standard pair.
3. **Posting age differs by role in a way that fits requisition refresh cycles.** Shift-supervisor postings fall in a
   tight 20–35 day band (median 26). Barista postings are spread wider (median 28, 10th–90th percentile ≈15–80 days).
   A tight, capped age band is what you would expect if requisitions are reposted on a schedule. If so, posting age
   partly reflects the refresh calendar, not how long a role has gone unfilled. **This needs checking nationally before
   any age-based claim.**
4. **Every same-role duplicate is at a large or special format:** the Reserve Roastery (61 9th Ave: 4 barista + 6
   other postings), the Empire State Building Reserve store, Macy's Herald Square, and the Reserve Kitchen. In the pilot,
   duplicates track store size and format, not stress.
5. **Leadership hiring is nearly invisible** in this sample: one store-manager posting, covering two cities.
   Store-manager hiring may run through internal promotion or a different channel. The national data will show whether
   this holds.

## Deviations that might still be informative (test nationally)

- **Same-role duplicates at ordinary stores** (not Reserve, not flagship/department-store formats).
- **Stores missing the standard pair** (supervisor-only or barista-only), which could mean one role was just filled or is not being recruited.
- **Store-manager or district-manager postings**, especially at stores that also have frontline openings
  (`flag_manager_plus_multiple_frontline`).
- **Postings much older than their role's norm** (above the role's 90th percentile), especially shift-supervisor postings
  beyond the usual ~35-day band, which would break the apparent refresh cycle.
- **Geographic concentration** of any of the above, compared against market size (store-universe denominator).

## What a one-day snapshot cannot establish

- Whether hiring is getting easier or harder (no time dimension).
- Whether an active posting is an unfilled position, a standing pipeline, or a refreshed duplicate of a filled role.
- Time-to-fill. Posting age is how long the current posting has been active, and is reset by reposting.
- Whether a posting that disappears was filled, cancelled or reposted.
- Anything about stores with no posting (no denominator in this dataset alone).

## Re-run nationally

`store_patterns.py` (role combinations, duplicates, review lists), `charts.age_by_role` (does the supervisor
refresh band hold everywhere?), `qa.py`, and `analyze.py` (store and market summaries). Market rankings should use
deviation metrics (share of stores off the standard pair, same-role duplicate rate, leadership postings per store,
share of postings older than their role's 90th percentile) rather than raw postings per store.
