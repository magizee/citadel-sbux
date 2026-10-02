# Sources and methods (short)

| Data | Source | Date | Used for |
|---|---|---|---|
| Starbucks U.S. job postings (19,831) | Public careers API behind apply.starbucks.com, adaptive geographic grid, deduplicated by requisition | Oct 1–2, 2026 | Manager vacancies, requisition age, re-posting |
| Foot traffic | Advan Weekly Patterns Plus via Dewey (project dataset), 143 weeks Jan 2024 – Sep 2026, U.S. Starbucks locations | Downloaded Oct 2, 2026 | Visits per store, same-store visit growth, closures |
| Store universe | Starbucks store locator via All the Places (9,979 company-operated U.S. stores) | Sep 26, 2026 | Denominators; closure validation; ownership filter |
| Archived job postings | Internet Archive CDX index (155,626 postings, 2024–26) | Oct 2, 2026 | Recurrence of manager-vacancy pockets |
| Management statements | Q1–Q3 FY26 earnings-call transcripts (Starbucks IR), Q3 FY26 8-K | Jan–Jul 2026 | Premise; labor/margin framing |
| Reported comps, transactions, store counts | Starbucks 8-K earnings releases FY25 Q2 – FY26 Q3 | Apr 2025 – Jul 2026 | Validating Advan; confirming closures were company-operated |
| Labor-market controls | BLS LAUS, BLS QCEW (NAICS 722513) | Aug 2026 / Q1 2026 | Ruling out local unemployment as the driver |

**Key definitions**
- *Density*: Starbucks-branded locations within 15 km (Advan).
- *Same-store visit growth*: mean weekly visits Jun 29 – Sep 21 2026 vs the same weeks 52 weeks earlier, stores with ≥ 11 of 13 weeks in both.
- *Vs metro / vs state*: store growth minus the median of its MSA / state.
- *Requisition age*: days since the requisition was created (not reset by re-posting). *Re-posted*: posting date > 7 days after creation.

**Reproduce:** scripts are in `_research_archive/starbucks_operating_data/src/` (`advan_pull.py`, `advan_analysis.py`,
`advan_overcrowding.py`) and `_research_archive/starbucks_hiring/src/`. Credentials go in `.dewey_env` (git-ignored).
