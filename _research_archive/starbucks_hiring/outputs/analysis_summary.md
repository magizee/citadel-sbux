# Starbucks U.S. retail hiring: national snapshot analysis

*Snapshot: 2026-10-01 (collected 22:14 Oct 1 → 03:07 Oct 2 ET). One-day cross-section, plus requisition-history
evidence from requisition numbers and the Internet Archive. Charts: `outputs/charts/` and
`../starbucks_thesis_tests/outputs/charts/`.*

**How to read this document.** Each claim is tagged **[Observed]** (measured directly), **[Inferred]** (reasonable
interpretation), or **[Cannot establish]**. This is a one-day cross-sectional snapshot. It cannot show whether hiring is
improving or deteriorating except where requisition numbers or archived pages give history. Active postings are not the
same as unfilled positions, and posting age is a proxy for persistence, not proof of hiring failure.

---

## 1. What the dataset is

- **19,831 unique U.S. job postings** from Starbucks' public careers search (onsite only, remote excluded), deduplicated by
  requisition ID across 395 overlapping geographic searches. **100.8%** of the server's own U.S. count (19,674); the excess
  is the July 4 batch, captured before it expired at midnight.
- **19,687 retail postings** at **10,224 hiring stores** (10,212 store numbers), plus 144 corporate / non-retail postings.
- Joined to a **store universe**: 9,979 company-operated U.S. stores from Starbucks' store locator (via All the Places,
  2026-09-26); 97.1% of hiring stores matched.
- Context: state labor-market controls (BLS LAUS / QCEW, DOL minimum wage), management statements (Q1–Q3 FY26 calls,
  Q3 8-K), a 40-posting pay sample, and **155,626 archived postings** (Wayback index, 2024–2026).

## 2. Methodology (short)

- Public JSON endpoint behind the careers page; adaptive lat/long grid (400 → 100 → 25 km circles), every page retrieved,
  per-search completeness check (0 incomplete searches, 0 retries), 4,455 requests at ~2.5 s pacing, no rate-limit errors.
- Role buckets from titles (coffeehouse coach = assistant store manager → STORE_MANAGER), with a department fallback.
- **Two age measures:** *posting age* (since the current posting went live; reset by reposting and capped by a 90-day
  expiry) and **requisition age** (since the requisition was created; not reset). Requisition age is the persistence measure.
- Full QA: `outputs/qa_report.md` (all checks pass; 3 explained warnings).

## 3. National snapshot

| Metric | Value |
|---|---|
| Total unique postings / retail / non-retail | 19,831 / 19,687 / 144 |
| Hiring stores (≥ 1 retail posting) | 10,224 |
| **Company-operated stores with ≥ 1 posting** | **99.3%** (9,913 of 9,979) |
| Retail postings per hiring store | 1.93 |
| Median retail posting age | 27 days |
| Retail postings open > 30 / > 60 days | 35.0% / 14.3% (batch-driven, see §4) |
| Role mix | Shift supervisor 9,995 (50.8%) · Barista 9,484 (48.2%) · Store manager 190 (1.0%) · District manager 5 · Other in-store 13 |
| Stores with a barista / supervisor / store-manager posting | 91.4% / 97.1% / 0.1% of hiring stores |
| Stores with 2+ role types | 88.7% (almost all the barista + supervisor pair) |

## 4. Role-level findings

- **[Observed] Frontline postings are standing, batch-refreshed requisitions.** 86.9% of hiring stores show exactly one
  barista + one shift-supervisor posting. Frontline requisitions are created in rolling batches and expire 90 days after
  posting: **0.0% of barista and supervisor requisitions are older than 90 days, and 0.0% are re-postings of an older requisition.**
- **[Inferred]** Frontline posting volume measures "stores with an open pipeline" (≈ every store), not vacancies, and
  frontline posting age mostly reflects batch timing. City rankings by "% open > 30 days" (Boston 60%, Reno 50%, …) are
  **not** persistence evidence.
- **[Observed] Leadership postings behave like real individual vacancies:** 190 store-manager + 5 district-manager postings,
  listed by **area** ("store manager – Tulsa"), with individual timestamps. **42% (82 of 195) are re-posted older requisitions**,
  and **18 have been open > 90 days** (oldest: Olympia/Tumwater WA 170 days, Cambridge MA 169, Annapolis/Glen Burnie MD 160).
- **[Observed] Expired requisitions are not auto-renewed.** All 145 frontline requisitions from the July 4 batch expired at
  00:00 ET Oct 2. Re-checked ~3 h later: 0 still listed, **0 replaced** by a same-role posting, while 122 of 137 stores still
  showed their other-role posting. **[Inferred]** Stores cycle between batches, which also explains much of the 10.6% of stores
  showing only one frontline role. **[Cannot establish yet]** whether replacements arrive in a later batch (re-check from Oct 3).
- **[Observed] Pay is a standardized zone ladder** (hourly max = 1.135 × min; 40/40 sampled postings). There is no
  posting-age premium (an 89-day Arizona barista posting pays the same as a 1-day one).

## 5. Geographic findings

- **[Observed]** Hiring penetration is near-universal everywhere (99.3% of company-operated stores), so geography shows up
  in *deviations*, not in volume.
- **[Observed]** Ordinary stores with same-role duplicates or 3+ roles: **1.7%** of hiring stores. A further 10.6% show only one
  frontline role (8.5% supervisor-only: Indiana 13.8%, Connecticut 13.0%, South Carolina 12.7% vs. Massachusetts 4.3%).
  Meaning ambiguous.
- **[Observed]** The state deviation rate is *higher where unemployment is lower* (Spearman −0.39). **[Inferred]** this is consistent
  with ordinary local labor-market tightness rather than a Starbucks-specific problem.
- **[Observed]** Posted store hours are the same for every hiring pattern (median 112 h/week). No operating link is visible in hours.

## 6. Leadership hiring findings

- **[Observed]** 1.95 leadership postings per 100 company-operated stores nationally. Above-average states (small counts):
  WI 5.3 (8 postings), MI 4.5 (8), PA 4.4 (12), OR 4.3 (7), WA 4.1 (14), OH 3.5 (9), IL 3.1 (14).
- **[Observed] Persistent clusters:** four Philadelphia-area store-manager requisitions created 2026-06-16 still open
  (Fishtown, Willow Grove/Fort Washington, King of Prussia, Haverford/Ardmore); Chicago suburbs (Joliet, Aurora/Oswego,
  created 06-11); Michigan (Rochester/Clarkston, Plymouth); Pacific Northwest (Olympia, Greater Portland, Bend/Redmond,
  Redmond WA); Baltimore/Annapolis/DC. Re-posted leadership requisitions by state: FL 10, PA 8, WA 8, IL 7, CA 6, WI 6.
- **[Observed, indicative]** These pockets recur in archived postings: store-manager postings in the same areas were captured
  repeatedly in 2024–2026 (Chicago suburbs 23, Philadelphia suburbs 12, Greater Portland 12, Olympia area 10, Michigan 7;
  `../starbucks_thesis_tests/outputs/tables/leadership_pockets_in_archive.csv`). Larger markets naturally post more.
- **[Observed]** Leadership intensity is **not** correlated with unemployment (ρ −0.02), restaurant employment growth (0.12)
  or minimum wage (−0.01) across states with ≥ 50 stores, nor with new-store openings proxied by hiring stores not yet in the
  store locator (ρ −0.18). **[Inferred]** The pockets look like replacement hiring, not expansion.
- **[Observed, indicative]** Store-manager share of postings in Wayback crawl bursts: 1.4–5.7% across 2025 bursts,
  0.8–2.2% in 2026, **1.0% today**.
- **[Inferred]** Leadership hiring looks *lower* than in 2025, consistent with management's claim that coffeehouse-leader
  tenure is up (~7 pts YoY) and internal promotion is rising. But a minority of leadership requisitions in specific markets
  are hard to close (re-posted, 3–6 months old).

## 7. Requisition volume over time (the one real trend measure)

- **[Observed]** Starbucks requisition numbers are `YY` + a sequence that rises perfectly with creation date (Spearman 1.0 in
  2024, 2025 and 2026). The sequence reached by a date = requisitions created that year so far (all Starbucks, incl. corporate).
- **[Observed]** Requisitions created Jan 1 → Jul 5: **2026 ≈ 53,200 vs 2025 ≥ 66,900 (≈ −20%) vs 2024 ≈ 57,600 (−8%)**.
  By Jul 30: 2026 58,992 vs 2025 ≥ 70,875 (≈ −17%). The 2025 figures are lower bounds (sampled archive pages), so the decline is at least this large.
- **[Observed]** Jul 6 → Sep 29: 2026 ≈ 27,200 vs 2024 ≈ 25,800 (+5%), concentrated in an early-September refresh batch.
- **[Inferred]** Fewer requisitions created in 2026 is consistent with **lower churn** (management: "record-low" hourly
  turnover), not with a hiring problem. Q3 creation back near 2024 levels is worth watching but not decisive.

## 8. Potential implications for Starbucks' operating execution

- Management makes staffing, roster size and coffeehouse-leader stability central to the turnaround and to margins (labor
  investment was the main FY26 margin headwind; the Green Apron investment anniversaries in Q4 FY26).
- **The snapshot does not show broad hiring difficulty.** Frontline hiring is a uniform standing pipeline. Leadership hiring is
  lower than in 2025, and requisition creation is down year-over-year.
- **Where execution risk could sit:** (i) a small set of markets with persistent, re-posted store-manager requisitions
  (management itself links leader stability to store performance); (ii) labor cost: hourly pay zones are well above
  statutory minimums, and management says more hours must be "earned" as transactions grow, so margin leverage after the
  Q4 anniversary depends on transactions per labor hour; (iii) a re-acceleration of requisition creation would signal
  rising churn. This is now measurable on any future date.

## 9. Limitations

- One-day cross-section; a disappearing posting can't be told apart from a hire, cancellation or repost.
- Requisition IDs cover all Starbucks requisitions (incl. corporate, possibly Canada); the 2024/2025 curves come from 185 sampled
  archive pages (lower-bound envelopes); 2025 history ends Jul 30.
- Archive coverage is crawler-driven and not representative; shares are indicative only.
- City = city as written in the address (no metro definitions); state rankings rest on small counts.
- Store universe is a third-party scrape (5 days older than the snapshot); 300 hiring stores (2.9%) are not in it.
- The 90-day frontline expiry and batch timing make posting age a weak persistence proxy; requisition age is used instead.
- **[Cannot establish]** time-to-fill, whether vacancies are rising or falling *within* stores, causal links to sales or
  margin, or anything about licensed stores (they do not hire through Starbucks careers).
