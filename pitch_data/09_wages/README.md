# 09 · Wage-rate pressure where Starbucks operates (BLS QCEW)

**Question:** how much of Starbucks' store-cost growth is explained by market wage growth, and is wage pressure rising or easing?

## Method
- **Data:** BLS QCEW open data API (no key), calendar 2023 Q1 – 2026 Q1. Private sector, two industries:
  - **722515** coffee & snack bars: Starbucks' own industry.
  - **722513** limited-service restaurants: the wider labor pool.
- **Starbucks weighting:** county-level average weekly wage YoY, weighted by the number of open company-operated Starbucks in each county
  (county from Advan `POI_CBG`).
- **Coverage:** 722513 county data is disclosed for 98% of stores. 722515 is disclosed for about 74%; the rest is suppressed by BLS.
- **Fiscal mapping:** calendar Q1 = Starbucks FY Q2, Q2 = FY Q3, Q3 = FY Q4, Q4 = next FY Q1.
- **Caveat:** average weekly wage = wages ÷ employees, so it mixes hourly rates with hours per worker.

## Result
**1. Market wage growth is slowing.**

| Fiscal quarter | Coffee & snack bars (Starbucks counties) | Fast food (Starbucks counties) |
|---|---|---|
| FY25 Q2 | 7.3% | 2.3% |
| FY25 Q3 | 3.6% | 3.5% |
| FY25 Q4 | 4.0% | 3.0% |
| FY26 Q1 | 4.3% | 1.7% |
| FY26 Q2 | 2.0% | 4.0% |

FY24 ran at 5–8% for coffee & snack bars. The California $20 fast-food wage (AB 1228, Apr 2024) shows clearly: California coffee-bar wages were +12–13% YoY from
2024 Q2 through 2025 Q1, then +2.6–4.4%.

**2. Starbucks' store costs grew far faster than market wages.**

| Fiscal quarter | Store opex growth | Market wage growth (coffee bars) | Gap |
|---|---|---|---|
| FY25 Q2 | +13.0% | +7.3% | +5.7 pp |
| FY25 Q3 | +13.5% | +3.6% | +9.9 pp |
| FY25 Q4 | +12.1% | +4.0% | +8.1 pp |
| FY26 Q1 | +9.4% | +4.3% | +5.1 pp |
| FY26 Q2 | +7.6% | +2.0% | +5.6 pp |

This happened while company-operated store count *fell*. **The excess is Starbucks-specific:** more labor hours per store, benefits, and
non-labor items (occupancy, depreciation, technology). Market wage rates explain less than half.

**3. Competition for workers:** coffee & snack bar employment is growing +5–6% YoY nationally (2025 Q2 – 2026 Q1) while fast-food
employment is flat. Other coffee chains are expanding into the same labor pool.

**4. Closures hit high-wage counties.** Oct-2025 closure rate by county fast-food wage level (2025 Q2):

| County wage quintile | Closure rate | Traffic growth of remaining stores |
|---|---|---|
| Lowest | 1.7% | +1.4% |
| Q2 | 2.6% | +1.4% |
| Q3 | 2.0% | +1.8% |
| Q4 | 3.6% | +2.0% |
| Highest | **5.5%** | **+3.1%** |

Wage level is tied up with urban density (see 06). Surviving stores in those counties grew faster, partly by absorbing closed stores' customers.

Chart: `../charts/09_wages.png`.

## Supports / weakens the short
- **Weakens the "wage inflation squeeze" version.** Market wage growth has slowed to about 2–4%, a tailwind for margins from here.
- **Supports the "structural cost layer" version.** Store opex outgrew market wages by 5–10 pp every quarter. Starbucks chose to add cost
  (staffing and service investment) beyond wage inflation. Margin recovery depends on revenue growing into that layer or management cutting it back,
  not on wage rates easing.
- **Labor-cost economics probably shaped the closures:** the highest-wage counties had 3× the closure rate. If wage pressure re-accelerates, that is
  where further closures would come from.

**Confidence:** high for the QCEW figures. Medium for the decomposition: store opex includes non-labor items, and average weekly wage mixes rates and hours.

**Limitations:**
- QCEW lags about 5–6 months; it runs through calendar 2026 Q1 (FY26 Q2), so it can't yet be compared with the FY26 Q3 inflection.
- Industry wages are not Starbucks' own wages.
- County suppression removes about 26% of Starbucks stores from the coffee-bar series.

**Files:**
- `qcew_national.csv`
- `starbucks_weighted_wages.csv`
- `wages_vs_store_opex.csv`
- `county_panel.csv`
- `closures_by_county_wage_level.csv`
- `results.json`

Raw API files are in `../data/raw/qcew/` (git-ignored). **Code:** `src/qcew_wages.py`.
