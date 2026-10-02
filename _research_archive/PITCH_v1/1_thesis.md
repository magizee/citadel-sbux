# SBUX short: an overbuilt, weakening network whose closures shed demand

*Data snapshot: Oct 1–2, 2026. Sources: Starbucks careers API (national scrape), Advan foot traffic via Dewey, Starbucks store
locator, Internet Archive, Starbucks filings and earnings calls. Details in `3_sources_and_methods.md`.*

## Thesis in one paragraph

Starbucks' U.S. company-operated network is **overbuilt in dense markets**: stores there capture roughly half the weekly
visits of stores in sparse markets. Starbucks is now **closing stores disproportionately in those markets**: its Sep-2025 restructuring
closed **627 stores (520 U.S.)**, and North America company-operated stores are −2.7% YoY. The closed stores were its **weakest** locations, and a before/after model shows **most of
their customers did not move to a nearby Starbucks** (~12% recaptured within 5 km). Closures shrink the system's traffic while
comparable-store sales, which exclude closed stores, look healthier. Meanwhile, store-manager hiring (the role management
itself ties most closely to store performance) shows **persistent vacancies in specific markets**.

## Pillar 1: Cannibalization in dense markets

| Local Starbucks density (locations within 15 km) | Median weekly visits per store |
|---|---|
| Least dense quintile (~3 nearby) | **3,442** |
| Middle (~30 nearby) | 2,541 |
| Densest quintile (~128 nearby) | **1,755** |

- Within the *same metro*, 10% more nearby Starbucks locations ≈ **1.9% fewer visits per store**.
- Chart: `charts/02_visits_per_store_by_density.png`.

## Pillar 2: Starbucks is pruning exactly those markets

- **Closures since Oct 2025: 9.2% of densest-quintile locations vs 2.6% of the least dense.** Chart: `charts/03_closures_by_density.png`.
- **Company filings:** 627 stores closed in the Sep-2025 restructuring (520 U.S.); North America company-operated stores fell 435
  in FY25 Q4 (licensed +12), then rose +131 net in FY26 Q1–Q3. NA company-operated: **−2.7% YoY** (Jun 2025 → Jun 2026).
- Advan records the same wave as **481 U.S. locations closed in Oct 2025** (`charts/01_store_closures_by_month.png`); 92% are absent
  from Starbucks' store locator.
- **Correction:** Advan's later bars (Mar / May / Jun 2026, ~300) are **not** confirmed by company filings (company-operated counts
  rose; restructuring closures were 3 in Q1 and 62 in Q2). Treat them as licensed closures and/or Advan data clean-up. All closure
  analysis in this pitch uses the confirmed Oct-2025 wave.

## Pillar 2b: Advan is a valid read on Starbucks traffic, and says near-term momentum is strong

- Advan same-store visits (company-operated stores) track reported U.S. comparable transactions with **r = 0.98** over six quarters
  (FY25 Q2 → FY26 Q3). Chart: `charts/16_advan_vs_reported_transactions.png`.
- **Early read for FY26 Q4 (not yet reported): implied U.S. transactions ≈ +5–6%**, still accelerating. Starbucks' same-store edge
  over Dunkin' widened every FY26 quarter (+0.2 → +1.2 pp; `charts/18`). **Implication: no near-term miss signal; the bear case is structural.**
- **But it is a recovery, not growth:** reported U.S. transactions over two years are ≈ flat (+0.1% FY26 Q2, +0.0% Q3), and on Advan
  Starbucks still **trails Dunkin' by 0.6–1.9 pp vs 2024** (Starbucks −0.7% / +0.4% / +1.2% vs Dunkin' +0.8% / +2.3% / +1.8%, Q2–Q4).
  *Inference (no FY27 data yet):* from FY27 Q1 Starbucks is compared with its own +3–4% transaction quarters, a tougher bar than FY26. Chart: `charts/19_two_year_vs_2024_and_dunkin.png`.

## Pillar 3: Closures shed demand. Most of a closed store's customers do not move to a nearby Starbucks

*Updated after a before/after model of the Oct-2025 wave (481 closures, 953 nearby survivors vs 6,240 same-metro controls,
26 weeks before to 48 weeks after). Chart: `charts/07_closure_event_study_low_recapture.png`.*

| Test | Result |
|---|---|
| Survivors < 1 km from a closure | **+0.6%** visits vs controls (95% CI −0.5% to +1.7%, not significant) |
| Survivors 1–2 km away | **+1.8%** (CI +0.9% to +2.6%) |
| **Recapture**: neighbours' extra visits ÷ closed stores' pre-closure visits | **≈ 4% within 2 km, ≈ 12% within 5 km** (lower bounds) |
| Closed stores' pre-closure traffic vs survivors at the same density | **30–45% lower** (median 1,341 vs 2,251 weekly visits) |
| Customer overlap with neighbours (where visitors live) | Closed stores shared **fewer** customers (19% vs 27%); `charts/08`. Overlap is high only < 0.5 km (24%); `charts/09` |

- **Reading:** Starbucks closed **low-traffic** stores, not redundant ones, and roughly **85–90% of those visits did not reappear at
  Starbucks within 5 km**. Closures therefore **shrink system traffic**. Because comparable-store sales exclude closed stores,
  comps do not show that lost demand.
- **Where closures were heaviest, Dunkin' gained ground.** Across 112 metros with ≥ 20 Starbucks, more closures per 100
  stores goes with a weaker change in Starbucks' share of Starbucks + Dunkin' visits (Spearman −0.42): metros with no
  closures +0.70 pp, 6+ per 100 −0.03 pp (Jun–Sep 2026 vs 2025). Chart: `charts/11_share_vs_dunkin_by_closure_intensity.png`.
  **Robustness (`charts/17_closure_share_loss_placebo_test.png`):** using only the confirmed Oct-2025 closures and controlling for
  metro size and starting share, each closure per 100 stores ≈ **−0.10 pp share vs Dunkin'** in FY26 Q1–Q3 (−0.07 in Q4), significant
  in every quarter, and holds within small/mid/large metros. **Placebo:** the same metros showed no significant share loss in the
  three quarters *before* the closures (≈ −0.02 pp), so the effect starts with the closures.
- **Dunkin' stores right next to a closure gained:** within 1 km, +2.0% visits vs ~+1.0% for Dunkin' elsewhere (+0.8 pp vs
  same-metro Dunkin', 95% CI +0.2 to +1.3; nothing beyond 1 km). Chart: `charts/14_dunkin_growth_by_distance_to_closure.png`.
  A before/after version (`charts/15`) also shows +1.5–2.2%, but Dunkin' near closures was already trending up beforehand,
  so treat it as supportive, not causal. In volume terms Dunkin' captured only ~0.8% of the closed stores' visits within 2 km.
- **Earlier cross-sectional result (`charts/04`) is superseded:** the +1.6 pp "transfer" gradient across all 2025–26 closures was
  not confirmed by the before/after model for the stores closest to closures. Transfer is at most a small (~+0.3 pp) effect.
  Don't present `charts/04` as evidence of comp inflation.

## Pillar 4: Store-manager vacancies persist in specific markets

Management: *"coffeehouse leader stability is highly correlated to store performance"* (Q3 FY26 call, Jul 29 2026).

- **195** open store/district-manager requisitions nationally. **42% are re-posted** older requisitions; **18 have been open more
  than 90 days** (longest: Olympia/Tumwater WA 170 days, Cambridge MA 169, Annapolis/Glen Burnie MD 160).
- Clusters: Philadelphia suburbs (4 requisitions open since Jun 16), Chicago suburbs (Joliet, Aurora/Oswego since Jun 11),
  Michigan, Pacific NW, Baltimore/DC. The same areas recur in archived manager postings 2024–26 (Chicago suburbs 23,
  Philadelphia 12, Portland 12, Olympia 10).
- Not explained by local unemployment (ρ −0.02) or new-store openings (ρ −0.18).
- **Manager vacancies cluster near under-performing stores.** Ranking stores by traffic *within their own metro* (Advan),
  the quietest fifth is near an open manager requisition 40% of the time vs 23% for the busiest fifth (persistent vacancies:
  22% vs 11%). The pattern holds within the same metro after controlling for store density (−3 pp per log-unit of traffic,
  SE 0.7) and is strongest in dense markets (62% vs 44%). That fits management's own claim that leader stability and store performance
  go together. Direction is not established (weak stores may lose managers, or missing managers may weaken stores).
  Chart: `charts/10_hiring_strain_by_store_traffic.png`.
- Charts: `charts/05_manager_vacancies_per_100_stores_by_state.png`, `charts/06_store_manager_requisition_age.png`.
  List: `data/manager_vacancies_by_requisition_age.csv`.

## Pillar 5: Labor productivity has to carry the margin story

- Labor investment was the main FY26 margin headwind (Q1 FY26 North America margin −420 bps, "primarily as our investments in
  support of Back to Starbucks continue to annualize").
- Management will not cut labor ("We don't see our way forward with cutting", Q2 FY26) and says additional hours must be
  "earned" as the business grows (Q3 FY26). Margin expansion after the Green Apron anniversary (Q4 FY26) depends on transactions
  per labor hour. If closures keep removing traffic while the per-store labor standard stays fixed, that leverage is harder to get.
- Source quotes: `data/management_statements.csv` (verified against the transcripts).

## What to monitor (catalysts / falsifiers)

| Signal | Bearish if | How |
|---|---|---|
| Same-store visits at stores **not** near closures | Organic growth decelerates below ~2% | Re-run Advan pull monthly (pipeline built) |
| System traffic incl. closed stores | Total U.S. visits (all locations) fall even as comps rise | Advan, all locations (pipeline built) |
| New closure waves | Continue in dense markets | Advan close dates + store locator |
| Store-manager vacancies | Re-posted share or > 90-day count rising | Re-run the careers scrape (one command) |
| Q4 FY26 / Q1 FY27 | U.S. transactions slow while labor $ per store keeps rising | Earnings |

See `2_anticipated_pushback.md` before presenting.
