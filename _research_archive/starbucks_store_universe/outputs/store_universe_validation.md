# Store-universe validation

## Source

| | |
|---|---|
| Source | All the Places (alltheplaces.xyz), spider `starbucks_us`, which collects **Starbucks' own store-locator API** (`starbucks.com/apiproxy/v1/locations`) |
| Run / data date | Run 2026-09-26 → 2026-09-29 (file modified 2026-09-29); hiring snapshot is 2026-10-01 |
| Raw file | `data/raw/starbucks_us_alltheplaces_2026-09-26.geojson` (13 MB, 16,707 features) |
| Cleaned | `data/processed/starbucks_store_universe.csv` |
| Fields | locator_id (locator's internal ID), store_name (branch), address, city, state, **postal_code**, lat/long, **ownership_type (CO / LS)**, located_in (host retailer for licensed stores), opening_hours, phone |
| License | All the Places data is published under CC0 |

## Coverage

| | Locations |
|---|---|
| All U.S. locations | 16,707 (51 state codes incl. DC; no missing coordinates or ZIPs) |
| **Company-operated (CO)** | **9,979** |
| Licensed (LS) | 6,728 (4,153 tagged with a host: Target 1,831, Safeway 629, Kroger 478, Albertsons 225, …) |

**Cross-check:** the Q3 FY26 8-K reports **11,149 North America company-operated stores**, which includes Canada (roughly
1,100 company-operated stores; approximate, not verified here). 9,979 U.S. CO locations is consistent with that, and with
management's "10,000-plus Starbucks-owned U.S. stores" (2025). Likely completeness: high (95%+ of open CO stores), with
gaps for very new stores, temporarily closed stores, and anything the spider's location-grid queries miss.

## Do not mix store types

Licensed stores (Target, grocery, airports) are staffed by the host company's employees and **do not hire through
Starbucks careers**. Every hiring store matched in the pilot is company-operated (109 of 109). **Use only CO stores
(9,979) as the denominator.**

## Join to hiring data

The locator's `locator_id` is an internal ID, **not** the 5-digit store number in job titles, so there is no direct
store-number join. `src/build_universe.py` joins on:
1. **Address:** state + house number + first street word (unique match required).
2. **Coordinates:** nearest CO/LS location within 75 m, accepted only if name or address similarity ≥ 0.6.

NYC pilot result (120 hiring stores):

| | Stores |
|---|---|
| Matched by address | 102 |
| Matched by coordinates | 7 |
| **Matched total** | **109 (90.8%), all company-operated**; median distance 0 m, median address similarity 1.0 |
| Unmatched | 11: the Reserve Kitchen (28 Summit St) and 10 numbered stores absent from the locator snapshot (e.g. 125 Chambers St, 100 William St, 99 Wall St, 11 Penn Plz) |

**Unmatched hiring stores are a finding, not just noise.** A store that hires but isn't in the locator is most likely
(a) a new store hiring ahead of opening, (b) temporarily closed or remodelling, (c) recently closed, or (d) a spider
coverage gap. (a) is one of the main alternative explanations for non-standard hiring (store openings), so these stores
should be flagged and excluded from "pressure" metrics, or analyzed separately, nationally.

## What the denominator enables (context only)

- Share of the 9,979 CO stores with ≥ 1 active retail posting
- Share with a shift-supervisor posting / a store-manager posting / multiple role types
- Market-level hiring penetration (hiring CO stores ÷ CO stores in the market)

These shares are context. A store with an open standing requisition is not a store with a staffing problem.

## Suitable for investment analysis?

**Yes, as a denominator, with caveats.** It is current (5 days before the hiring snapshot), sourced from Starbucks' own
locator, and separates company-operated from licensed. It is a third-party scrape, a single point in time, and not an
audited count.
