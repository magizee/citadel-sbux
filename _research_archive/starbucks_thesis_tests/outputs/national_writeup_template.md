# Starbucks staffing: national snapshot analysis (TEMPLATE, no conclusions yet)

> Fill each `[[…]]` from the national outputs. Leave conclusions empty until the data is in.
> Main sources: `starbucks_hiring/outputs/national_summary.json`, `…/data/processed/<date>/{store_summary,market_summary}.csv`,
> `…/outputs/tables/*.csv`, `…/outputs/qa_report.md`, and the sibling folders.

## 1. Thesis question
Does current Starbucks store-level hiring look unusually difficult, persistent or costly enough to create execution risk
for the turnaround? (Chain: hiring difficulty → staffing / labor-cost pressure → weaker execution → weaker traffic / sales / margin.)

## 2. Why staffing matters to Starbucks
From `starbucks_management_research/outputs/management_thesis.md`: rosters, low turnover, leader stability ("highly correlated
to store performance"), labor investment as the main FY26 margin headwind, Green Apron anniversary in Q4 FY26.

## 3. Dataset and methodology
- Snapshot [[date]], public careers API, adaptive coordinate grid ([[n]] searches, [[n]] requests), deduplicated by job_id; [[n]] U.S. postings ([[x]]% of the server's national count).
- QA: [[link qa_report.md; key WARNs]].
- Store universe: 9,979 company-operated stores (store locator, 2026-09-26); join coverage [[x]]%.

## 4. Important caveat: standing / evergreen requisitions
- Share of hiring stores with exactly 1 barista + 1 supervisor: [[x]]% (pilot: 89%).
- Frontline postings: batch-created, fixed 90-day expiry → age ≤ 89 days, set by the refresh calendar. Batch dates: [[list]].
- Store-manager postings: area-level, individual timestamps, 28–60 day lifetimes.

## 5. National retail hiring snapshot
[[total, retail, non-retail, hiring stores, share of CO stores hiring, role mix, median age, % > 30 / > 60 days]]

## 6. Store-level hiring patterns
[[role-combination table; share of CO stores with supervisor / manager postings]]

## 7. Non-standard requisition intensity (Test A)
[[share off-pattern; same-role duplicate rate; by format / new-store status; top markets with ≥ N stores]]

## 8. Posting persistence (Test C)
[[frontline: share by batch; leadership: age distribution; caveats]]

## 9. Leadership hiring (Test B)
[[store-manager / coffeehouse-coach / district-manager counts; per 100 CO stores by market; vs. labor controls]]

## 10. Geographic concentration
[[maps / rankings with minimum-store thresholds; vs. unemployment and limited-service-restaurant employment growth]]

## 11. Store-universe denominator (Test F)
[[penetration metrics; unmatched hiring stores (possible new stores)]]

## 12. Pay evidence
Pilot: zone ladder, no age-pay relationship (`starbucks_pay_analysis`). [[any national follow-up]]

## 13. Operating-data evidence (Test E)
[[posted-hours cross-section vs. hiring intensity; foot-traffic status]]

## 14. Historical evidence
[[archive result; LinkUp / Revelio access status]]

## 15. What supports the thesis
[[only items backed by data above]]

## 16. What contradicts or weakens the thesis
[[e.g. strong reported comps and transactions; standing-requisition structure; pay standardization; management turnover and tenure claims]]

## 17. What the data cannot establish
One-day snapshot: no trend; active postings ≠ unfilled positions; posting age ≠ time-to-fill; disappearance ≠ hire.

## 18. Investment implications
[[neutral; what would need to be true for the short thesis; what to monitor (repeat snapshots, Q4 FY26 margin as the Green Apron investment anniversaries)]]

## 19. Limitations
[[collection, classification, denominator, external-source caveats]]
