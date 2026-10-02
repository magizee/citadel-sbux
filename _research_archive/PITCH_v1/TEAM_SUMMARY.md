# SBUX: alternative-data summary

*Data as of Oct 1–2, 2026. One page for the team; the full thesis and Q&A prep are in [`PITCH/`](PITCH/README.md).*

## Bottom line

The alternative data **does not show Starbucks' operations deteriorating nationally**. Foot traffic tracks reported transactions
closely, traffic is accelerating, and Starbucks is outgrowing Dunkin' per store. **Near-term momentum is strong: our early read on
the unreported FY26 Q4 is U.S. comparable transactions of roughly +5–6%.** The bearish evidence is **structural and local**:
Starbucks' Oct-2025 closures (627 stores, 520 in the U.S.) lost most of those stores' customers, and the metros hit hardest
have been losing ground to Dunkin' every quarter since. This supports a **valuation / expectations** short ("traffic has only recovered to 2024 levels
and still trails Dunkin' over two years, comparisons get tougher from FY27 (by arithmetic, not observed), growth now relies on a smaller store base, and closures leak
customers to competitors"), not an "execution is breaking" short, and argues against
being short into the Q4 print.

## 1. The foot-traffic data is trustworthy

![Advan vs reported transactions](PITCH/charts/16_advan_vs_reported_transactions.png)

- Advan same-store visits at company-operated stores track reported U.S. comparable transactions with **r = 0.98 over six quarters**
  (FY25 Q2 → FY26 Q3), including the swing from −4% to +4%. Advan understates the size of moves (~2.4×) but matches direction and turns.
- **FY26 Q4 (not yet reported):** Advan same-store visits +2.2% → implied U.S. comparable transactions **≈ +5–6%** (indicative,
  6-point fit). Management guided U.S. comps ≥ 6.5%.

## 2. The turnaround is real at the store level, and widening vs Dunkin'

![Starbucks vs Dunkin' by quarter](PITCH/charts/18_starbucks_vs_dunkin_by_quarter.png)

- Starbucks went from **trailing Dunkin' by ~2 pp** in same-store visit growth (FY25) to **leading in every FY26 quarter**
  (+0.2 → +1.2 pp). Its share of Starbucks + Dunkin' visits is flat YoY. **Expect this as the first pushback.**

**…but on a two-year view it is a recovery, not growth, and Starbucks is still behind Dunkin'.**

![Two-year view vs 2024 and Dunkin'](PITCH/charts/19_two_year_vs_2024_and_dunkin.png)

- Reported U.S. transactions over two years: **+0.1% (FY26 Q2) and +0.0% (Q3)**, i.e. back to 2024 levels, not above them.
- Advan agrees: Starbucks same-store visits vs two years earlier −0.7% / +0.4% / +1.2% (Q2/Q3/Q4) while **Dunkin' grew +0.8% / +2.3% / +1.8%**.
  Starbucks still **trails Dunkin' by −1.5 / −1.9 / −0.6 pp** since 2024; the FY26 "outperformance" is winning back FY25 losses.
- *Inference, not data:* from FY27 Q1 (Oct 2026 on) Starbucks will be compared with its own +3–4% transaction quarters, so the
  bar for YoY growth rises. No FY27 data exists yet; this is comparison arithmetic, not a forecast.

## 3. The Oct-2025 closures shrank the store base, and the customers mostly left

![Closure event study](PITCH/charts/07_closure_event_study_low_recapture.png)

- Company filings: **627 stores closed in the Sep-2025 restructuring (520 U.S.)**; North America company-operated stores fell 435 in
  FY25 Q4 and are **−2.7% YoY** (Jun 2025 → Jun 2026) even after ~130 net openings since.
- Before/after model of that wave: nearby Starbucks recaptured only **~4% of the closed stores' visits within 2 km (~12% within 5 km)**.
  The closed stores were low-traffic (30–45% below survivors at the same density). Comparable-store sales exclude closed stores,
  so this lost traffic never shows up in comps.

## 4. Where Starbucks closed stores, Dunkin' gained ground, every quarter since

![Closure share loss with placebo test](PITCH/charts/17_closure_share_loss_placebo_test.png)

- Across 112 metros (controlling for metro size and starting share), each closure per 100 Starbucks stores is associated with
  **≈ −0.10 pp of share vs Dunkin'** in FY26 Q1–Q3 (−0.07 pp in Q4). **Placebo:** before the closures, the same metros showed no
  meaningful share loss (≈ −0.02 pp, not significant), so this is not a pre-existing trend. It holds within small, mid and large metros.

![Dunkin' growth by distance to a Starbucks closure](PITCH/charts/14_dunkin_growth_by_distance_to_closure.png)

- At the store level, **Dunkin' within 1 km of a closed Starbucks grew visits +2.0% vs ~+1.0% elsewhere** (+0.8 pp vs same-metro
  Dunkin', 95% CI +0.2 to +1.3). In volume terms Dunkin' captured only ~0.8% of the closed stores' visits, so the leakage is
  broad (other chains, independents, or gone), not mainly to Dunkin'.

## 5. Store-manager vacancies sit next to the weaker stores

![Hiring strain by store traffic](PITCH/charts/10_hiring_strain_by_store_traffic.png)

- 195 open store/district-manager requisitions; **42% re-posted**, 18 open > 90 days (Philadelphia and Chicago suburbs, Michigan,
  Pacific NW, Baltimore/DC). Stores in the quietest fifth for their metro are near a persistent manager vacancy **twice as often**
  as the busiest fifth (22% vs 11%; holds after density control).
- **Not supported:** frontline hiring difficulty. Barista/supervisor hiring is a routine standing pipeline at 99% of stores;
  requisitions created in 2026 are ~17–20% below 2025.

## What this means for valuation

| Input for the model | What the data says |
|---|---|
| Near-term comps | Advan implies FY26 Q4 U.S. transactions ≈ +5–6% and still accelerating, so **no near-term miss signal** |
| Comps from FY27 (inference) | Two-year transactions ≈ flat (back to 2024 levels). FY27 quarters are compared with +3–4% FY26 quarters, so **sustaining +4% requires growth on top of growth**. No FY27 data yet |
| Unit growth | North America company-operated stores −2.7% YoY after the Oct-2025 restructuring; modest net openings since (+131 in FY26 YTD) |
| Competitive position | Gaining vs Dunkin' nationally; **losing ~0.1 pp of share per closure per 100 stores in closure-hit metros** |
| Lost demand | Closed stores' traffic mostly not recaptured (~4–12% nearby), so system traffic lags comps |
| Margin / labor | Manager instability concentrated near weaker stores; labor investment anniversaries in Q4 FY26 |

## Caveats

- Advan is a phone-panel sample: use *relative* growth (vs reported, vs Dunkin', near vs far), not raw levels.
- **Advan's spring-2026 "closure wave" (~300 locations) is NOT confirmed by company filings** (company-operated counts rose then);
  it likely mixes licensed closures and Advan data clean-up. All closure findings above use the **Oct-2025 wave**, which filings confirm.
- The FY26 Q4 read is a 6-point linear fit; treat it as directional.
- The job data is a one-day snapshot (Oct 1, 2026); it cannot measure staffing levels.

## Sources

Starbucks careers API (19,831 U.S. postings) · Advan Weekly Patterns via Dewey (Starbucks + Dunkin', Jan 2024 – Sep 2026) ·
Starbucks 8-K earnings releases (FY25 Q2 – FY26 Q3: comps, transactions, store data) · Starbucks store locator via All the Places ·
Internet Archive · Starbucks Q1–Q3 FY26 calls · BLS. Methods: [`PITCH/3_sources_and_methods.md`](PITCH/3_sources_and_methods.md).

---

**Repo layout:** [`PITCH/`](PITCH/README.md) holds the thesis, Q&A prep, all charts and data. [`_research_archive/`](_research_archive/START_HERE.md)
holds every scraper, raw dataset and full analysis (nothing deleted).
