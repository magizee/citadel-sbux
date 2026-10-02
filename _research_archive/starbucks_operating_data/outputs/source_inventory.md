# Operating-outcome data: source inventory

Goal: find data that can link staffing-pressure signals to store performance or customer experience (Test E).
Assessed 2026-10-01. Access claims for paid sources come from vendor and library pages and should be confirmed with your institution.

| Source | Metric available | Geographic granularity | Historical coverage | Cost / access | Join key to Starbucks | How strongly it tests the thesis | Time to use today |
|---|---|---|---|---|---|---|---|
| **Store-locator hours** (All the Places `starbucks_us`, built here) | Posted weekly hours, weekday open/close | Store (9,979 CO stores) | Single snapshot (2026-09-26); ATP keeps past runs, so a history is possible | Free (CC0) | Address / coordinates → hiring store_key (91% match in pilot) | **Weak to moderate.** Hours are very standardized (99% open by 6 am; median 112 h/week), so only the short-hours tail varies. A store-level cross-section is possible today | **Done**: `data/processed/store_hours.csv` |
| Past ATP runs (weekly archives) | Same hours, store openings and closures over time | Store | Weeks to ~2+ years of runs (depends on archive retention) | Free | locator_id / address | **Moderate:** store openings and closures, and hours changes over time, could separate expansion hiring from replacement hiring | 1–2 h to pull 3–6 past runs (not done) |
| **Advan Research** (via **Dewey**) | Weekly / monthly visits, dwell time, visitor home areas | POI (store) | Since ~2019 (Dewey: often ~2 years) | Paid; academic access via Dewey subscriptions (many universities) | Address / coordinates (Advan verifies Starbucks POIs) | **Strong:** visits are the closest observable to transactions; dwell time could proxy wait times | Hours to days, depending on institutional access |
| pass_by (via Dewey) | Foot traffic | POI | ~2–3 years | Paid / Dewey | Address / coordinates | Strong (same logic as Advan) | Same as Advan |
| Placer.ai | Visits, dwell time, trade areas | POI, market | 2017+ | Paid; free tier is limited and has no export | Address | Strong, but no bulk export without a license | Not today |
| Google Maps reviews / popular times | Review text (waits, "understaffed", lobby closed), rating, busyness | Store | Reviews accumulate over years (dated) | Scraping is against Google's ToS; Places API is paid and limited to 5 reviews per place | Address | Moderate. Text is noisy, and review volume tracks traffic (the "high-volume stores" confound) | Not recommended |
| Yelp Fusion API | Rating, review count, 3 review excerpts | Store | Limited | Free tier, rate-limited; ToS restricts storage | Address | Weak (3 excerpts per store) | Not worth it |
| Starbucks 10-K / 10-Q / 8-K | Comps, transactions, ticket, margins, store counts | Segment (NA / U.S.) | Quarterly, many years | Free (SEC) | Not store-level | Strong for the **aggregate** outcome; cannot be linked to store-level staffing | **Done** (see `starbucks_management_research`) |
| Health-inspection / local closure notices | Closures, violations | Store (some cities) | Years | Free, fragmented by city | Address | Weak, and only a few cities | Not today |
| Card-spend panels (Bloomberg Second Measure, Consumer Edge, Earnest) | Sales and transactions by brand / market | Brand × market (DMA / state) | Years | Paid | Market | Strong at market level | Not today |

## Recommendation

1. **Today:** use store-locator hours as a weak cross-sectional check (are hiring-intensive stores on shorter posted hours?).
   It is built and ready to join to the national hiring data. Expect little signal, because hours are standardized.
2. **Highest value next:** Advan or pass_by weekly visits via Dewey, if your institution has Dewey. It allows
   market- and store-level visit trends to be compared against hiring-intensity metrics, controlling for store volume.
3. **Cheap and useful:** pull 3–6 past All the Places runs to build store open / close / hours-change histories. This separates
   new-store hiring from replacement hiring and shows whether stores with persistent leadership postings cut hours.
4. Skip review scraping (ToS and noise).

## Hours snapshot (company-operated stores)

| Metric | Value |
|---|---|
| Stores / hours parsed | 9,979 / 9,964 |
| Weekly hours: median (IQR) | 112 (107.5–115.5) |
| Weekday opening time | 5:00 (44%), 4:30 (42%), 4:00 (9%), 3:30 (3%) |
| Open after 6 am / close before 6 pm on weekdays | 0.9% / 0.9% |
| Lowest median weekly hours by state | AK 101.5; NH, RI, DC, MN 105 |
