# SBUX short: what the staffing evidence can and cannot carry

*Prepared from the 2026-10-01 national hiring snapshot and supporting research. Market and valuation data were not
part of this work. Pair this with your own valuation and positioning view.*

## Bottom line (read this first)

**The hiring data does not support a "Starbucks can't hire" short.** Frontline hiring is a uniform standing pipeline
at ~99% of company-operated stores. Requisition creation is **down ~17–20% year-over-year** through July. Leadership hiring
is a smaller share of postings than in 2025. Q3 FY26 reported U.S. comps of +7.9% with transactions +4.2%.

A staffing-based short has to be a **narrower, forward-looking argument**: the turnaround's margin recovery depends on labor
productivity and leadership stability that are already priced as "fixed". This data can **monitor** that risk cheaply, and
it shows a few early pressure points to watch. It does not show a current failure.

## Arguments that the data can support (strength-rated)

| # | Argument | Evidence | Strength |
|---|---|---|---|
| 1 | **Store-leader hiring is hard in specific markets**, and management says leader stability drives store performance | 42% of open store-manager requisitions are re-posted; 18 open > 90 days (max 170); clusters in Philadelphia suburbs (4 requisitions open since Jun 16), Chicago suburbs, Michigan, Pacific NW, Baltimore/DC; leadership intensity 2–2.7× the national rate in WI, MI, PA, OR, WA; the same areas recur in archived store-manager postings 2024–26 (Chicago suburbs 23, Philadelphia 12, Portland 12, Olympia 10) | **Moderate as a pocket signal; weak as a national signal.** Not explained by local unemployment (ρ −0.02) or new-store openings (ρ −0.18), so it looks like replacement hiring. Only 195 leadership postings in total (≈ 2 per 100 stores) |
| 2 | **Labor productivity must keep rising to deliver margin expansion after the Q4 FY26 anniversary** | Management: "We don't see our way forward with cutting" labor; hours to be "earned" as growth continues; labor investment was the main FY26 margin headwind (Q1 NA margin −420 bps). Pay zones sit far above statutory minimums (e.g. barista $15.25+ where the state minimum is $7.25) | **Moderate (management's own framing).** A forward risk, not a current observation |
| 3 | **Churn may be re-accelerating in Q3** | Requisitions created Jul 6–Sep 29 2026 ≈ 27.2k vs ≈ 25.8k in 2024 (+5%), with a large early-September batch | **Weak.** 2025 comparison unavailable for Q3; driven by batch timing; H1 2026 was well below both prior years |
| 4 | **The labor model is fragile to local tightness** | Off-pattern stores are more common where unemployment is lower (ρ −0.39) | **Weak.** Off-pattern stores are only 1.7%; this is ordinary labor-market sensitivity |

## Evidence that contradicts or weakens a staffing short

1. **Reported outcomes are strong** (SEC 8-K, Jul 29 2026): U.S. comps +7.9%, transactions +4.2%, NA operating margin up, FY26
   guidance raised. Management reports record-low hourly turnover, ~98% shift fill (COO, Fortune; unverified), leader tenure up ~7 pts.
2. **Requisition creation fell YoY:** Jan 1–Jul 5: 2026 ≈ 53.2k vs 2025 ≥ 66.9k (≈ −20%); by Jul 30 ≈ −17%. Fewer
   requisitions is what lower turnover looks like.
3. **Frontline persistence is zero:** 0% of barista and supervisor requisitions are older than 90 days, and none are re-posted.
4. **Leadership share of postings is down vs 2025** (Wayback bursts: 1.4–5.7% in 2025 → ~1% today; indicative).
5. **No pay pressure is visible:** pay is a fixed zone ladder; old postings pay the same as new ones.
6. **Expired frontline requisitions were not immediately replaced** (0 of 145 within ~3 h). That fits periodic batch
   refresh (or filled needs), not stores scrambling to re-post open roles. Neutral-to-contradicting until a later re-check.
7. **Foot traffic shows no staffing → traffic link (Advan, 9,419 stores):** stores near manager vacancies first looked faster-growing,
   but that was closure transfer. With closure-adjacent stores removed, there is no difference (0.0 / +0.1 pp within metro). Hiring-pattern groups
   show no difference either.
8. **No operating link is visible:** posted store hours are identical across hiring patterns.

## The stronger angle the data surfaced: an overbuilt network, with comps flattered by closure transfer

| Evidence (Advan via Dewey, verified against the store locator) | Reading |
|---|---|
| Visits per store: 3,442/week in the least-dense quintile vs **1,755** in the densest; within metro, +10% nearby stores ≈ −1.9% visits per store | **Cannibalization** in dense markets |
| Closures since Oct 2025: **9.2%** of densest-quintile locations vs 2.6% of least dense; waves of **481 (Oct 2025)** and **~300 (Mar–Jun 2026)** | Starbucks is **pruning** where it is overbuilt |
| Stores < 1 km from a closure: **+1.6 pp** visit growth vs metro; 1–2 km **+1.1 pp**; > 2 km ≈ 0 | **Transfer** from closed stores |
| Transfer adds ≈ **+0.3 pp** to mean same-store visit growth (2.85% vs 2.51% excluding closure-adjacent stores) | Part of the comp recovery is **moved, not new**, demand (management cited ~0.5 pt) |
| Openings slowing: 653 (2024) → 510 (2025) → 135 (2026 YTD) | Unit growth is slowing while the network is pruned |

**Pitch framing:** the turnaround's comps are partly flattered by consolidating an overbuilt network. Organic same-store visit
growth is closer to ~2% than the headline. When the closure waves lap (Oct 2026 for the 2025 wave), the transfer tailwind fades.
Caveats: Advan includes licensed locations and may understate dense urban visits; one 13-week window; verify closures against
10-Q store counts.

## What would have to become true for the staffing short to work (and how to see it early)

| Signal | Current reading | Bearish trigger | How to measure (built) |
|---|---|---|---|
| Requisitions created YTD vs prior year | 2026 ≈ 17–20% below 2025 (to July) | 2026 pace exceeds 2025 / 2024 for a sustained window | Requisition number on any live posting (`starbucks_hiring`, one run); archive for prior years |
| Re-posted store-manager requisitions | 82 of 195 (42%); 18 > 90 days | Count or share rising over repeated snapshots; spreading beyond the current clusters | `outputs/tables/leadership_postings_by_requisition_age.csv` |
| Leadership postings per 100 stores | 1.95 | Sustained rise, especially in top-volume states (CA, TX, FL) | `national_tests.py` |
| Stores off the standard pair | 1.7% duplicates; 10.6% single-role | Duplicates rising, i.e. multiple open requisitions per role per store | `store_patterns.py` |
| Pay zones | Fixed ladder | Zone levels stepping up between snapshots | Detail endpoint (sample of ~1–2k postings) |
| Comps / transactions vs labor | +7.9% / +4.2% | Transactions slowing while labor $ per store keeps rising after the Q4 anniversary | Q4 FY26 results (late Oct / early Nov) |

## Suggested positioning of this work in a pitch

- Present the staffing data as a **monitoring edge** (a cheap, repeatable, store-level read on Starbucks' labor pipeline that
  most investors don't have), not as proof of current failure.
- Lead with what management says matters (leader stability → store performance; labor investment → margin) and show
  where the data is **already stretched** (re-posted leadership requisitions in named markets).
- Be explicit that frontline hiring looks healthy and requisition creation is down YoY. Pre-empting that is more credible
  than omitting it.

## Not established

Time-to-fill; actual staffing levels or labor hours per store; whether leadership vacancies hurt those stores' sales;
anything about licensed stores; any causal link from hiring to comps or margin.
