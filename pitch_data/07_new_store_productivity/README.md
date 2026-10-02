# 07 · New-store productivity (light)

**Question:** are new stores less productive than the stores being closed, or than the mature base?

**Method:**
- **Sample:** 769 company-operated stores with an Advan open date between Mar 2024 and Jun 2026, still open.
- **Productivity:** latest 13-week visits per week and visits per operating hour (Sep-2026 hours), relative to mature stores (opened before 2024) in the same metro.
- **Ramp:** weekly visits since opening ÷ the metro's mature median that week.

**Result:**
- **New stores are about as productive per operating hour as the mature base:** median **21.7 visits per operating hour vs 21.7** for mature
  stores, and far above the closed stores' 14.1 before closure.
- New stores run at 94% of their metro's mature-store visits.

  | Opening cohort | Visits vs metro mature | Visits per operating hour vs metro mature |
  |---|---|---|
  | Mar–Dec 2024 | 0.92× | 0.92× |
  | Jan–Sep 2025 | 1.00× | 1.01× |
  | Oct 2025 – Jun 2026 | 0.91× | 0.90× |

- **Ramp:** 0.85× at 4 weeks, 0.90× at 26 weeks, 0.92× at 1 year, 0.96× at 2 years.
- New stores skew low-density (43% vs 28% for mature stores; urban core 17% vs 27%), so the footprint is moving toward suburban and drive-thru sites.

Chart: `../charts/07_new_store_productivity.png`.

**Supports / weakens the short:** **weakens** it modestly. Replacing closed urban-core stores (14 visits per operating hour) with new suburban ones (about 22)
improves network productivity over time. The effect is small: about 130 net openings a year against roughly 9,800 stores.

**Confidence:** medium. Advan open dates are estimates. Build costs, pre-opening labor and occupancy (rent) aren't visible.

**Limitations:** this measures traffic per open hour only. New stores could still carry higher rent or depreciation.

**Code:** `src/new_store_productivity.py`.
