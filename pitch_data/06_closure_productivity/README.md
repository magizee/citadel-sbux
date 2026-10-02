# 06 · Closed-store productivity and closure-risk model

**Question:** were the Oct-2025 closures the low-productivity tail? How much did removing them lift productivity, and how much tail is left?

## Method
- **Sample:** company-operated stores in the Aug-2025 locator (pre-announcement) linked to Advan. 349 closed Sep–Nov 2025 and 8,348 survivors
  had complete features. 382 closed stores have Aug-2025 hours; filings say 520 U.S. stores closed in total, so some aren't linked.
- **Pre-closure features** (13 weeks to Aug 25 2025): visits, YoY visits, Aug-2025 weekly hours, visits per operating hour, traffic
  percentile in metro, Starbucks within 1/2/5 km, Dunkin' within 2 km, weekend share of hours.
- **Risk model:** logistic regression on standardized features (balanced classes), evaluated with 5-fold cross-validated AUC. It is then applied to
  Sep-2026 features of open company-operated stores.

## Result
**Closed stores were the low-productivity tail.**

| Pre-closure (Jun–Aug 2025) | Closed | Survivors |
|---|---|---|
| Visits / week (Advan) | 1,392 | 2,438 |
| Weekly operating hours | 101.5 | 112 |
| **Visits per operating hour** | **14.1** | **21.7** |
| Traffic percentile in own metro | 27th | 55th |
| Starbucks within 2 km | 3 | 1 |
| Urban core share | 63% | 26% |
| YoY visits | −2.0% | −1.7% |

- **The productivity gain from closing them was small and one-time.**
  - The closed stores were 4.0% of stores, 3.7% of operating hours and 2.5% of visits.
  - Removing them raises aggregate visits per operating hour by **+1.2%**, once.
  - Closed stores' traffic mostly wasn't recaptured (earlier event study in `_research_archive/PITCH_v1/`: about 4–12% nearby), so the network gave up visits to get this ratio.
- **Risk model:** cross-validated AUC 0.84 (visits per operating hour alone: 0.69).
  - Strongest markers: **short hours** (odds ratio 0.37 per SD), **dense Starbucks clustering** (1.95 per SD), and a low traffic rank in the metro (0.75).
  - Prior traffic growth did not predict closure.
- **The low-productivity tail is not used up.**
  - 21.0% of open company-operated stores in Sep 2026 sit below the closed stores' median visits per operating hour, vs 21.9% of survivors in Aug 2025.
  - **418 open stores (4.9%)** score above the median closed store on the model (`at_risk_open_stores.csv`).
  - Those look-alikes grew **+4.2% YoY vs +2.1%** for the rest. Many sit next to Oct-2025 closures and absorbed some of their traffic, which
    lowers their near-term closure risk.

Chart: `../charts/06_closure_productivity.png`.

## Supports / weakens the short
- **Supports:** the restructuring's productivity boost was small (+1.2%) and doesn't repeat. Most margin recovery has to come from same-store
  operating leverage, not mix.
- **Cuts both ways:** about 400–1,800 stores still look like the closed tail. That is optionality for management (another optimization round:
  bullish for margins, bearish for unit count and system traffic) rather than a clean short signal.

**Confidence:** medium–high that closures were the low-productivity tail. Medium for the risk model: it is in-sample to one wave, and short
hours could partly reflect pre-closure decisions.

**Limitations:**
- Advan close dates are estimates.
- Some closures are not linked to locator hours.
- The model describes similarity to past closures; it is not a forecast.

**Files:** `closed_vs_survivors.csv`, `closure_risk_model.csv`, `at_risk_open_stores.csv`, `results.json`. Code: `src/closure_productivity.py`.
