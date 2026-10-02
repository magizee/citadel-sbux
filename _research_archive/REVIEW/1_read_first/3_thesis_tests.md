# Empirical tests of the staffing thesis

**Thesis:** hiring difficulty → staffing / labor-cost pressure → weaker store execution → weaker traffic, service, sales or margin.

## What we learned today that constrains every test

1. **Standing requisitions.** In the NYC pilot, 89% of hiring stores carry exactly one barista and one shift-supervisor
   posting. Posting *volume* mostly counts stores with an open pipeline, not vacancies.
2. **Batch creation with a fixed 90-day expiry.** Frontline postings are created in batches at midnight ET and all expire
   90 days later (`starbucks_pay_analysis`). Frontline posting age is capped at 89 days and mostly reflects the refresh calendar.
3. **Store-manager postings are area-level** ("store manager – Tulsa") with individual timestamps and 28–60 day lifetimes.
   They are the closest thing to individual vacancies in the data.
4. **Pay is a zone ladder** (max = 1.135 × min); there is no posting-level wage variation.
5. **Reported outcomes are strong:** Q3 FY26 U.S. comps +7.9%, transactions +4.2%, margins expanding, guidance raised
   (SEC 8-K, 2026-07-29). Management reports record-low hourly turnover and improving leader tenure.

Implication: tests must use **deviations from the standing pattern**, **leadership postings**, and **repeat snapshots**,
not raw counts or raw posting age.

---

### TEST A: Non-standard hiring intensity
- **Question:** Do some stores or markets have materially more active requisitions than the standing pattern?
- **Dependent variable:** share of hiring stores off the standard pair (same-role duplicates, 3+ role types); same-role postings per store.
- **Independent variable:** market (state / city); store format (Reserve, mall, airport, drive-thru); new-store status (hiring but not in the locator).
- **Dataset:** national postings + `store_patterns.py` + store universe (format, new / closed stores) + labor controls.
- **Expected sign if thesis is correct:** deviations concentrated in specific markets, beyond what format, new stores and local unemployment explain.
- **Alternative explanations:** store openings (pre-opening hiring), seasonal hiring, large or special formats (pilot: every duplicate was a Reserve or department-store format), high-volume stores.
- **Would contradict the thesis:** deviations that are rare (< ~5% of stores) and explained by format or new stores.
- **Today?** **Yes** (cross-section) once the national scrape finishes.

### TEST B: Leadership vacancies
- **Question:** Are store-manager / coffeehouse-coach / district-manager postings unusually concentrated?
- **Dependent variable:** leadership postings ÷ company-operated stores in the market (store-universe denominator); share of areas with an open store-manager posting.
- **Independent variable:** market; local unemployment; limited-service-restaurant employment growth.
- **Dataset:** national postings, store universe, labor controls.
- **Expected sign if thesis is correct:** high leadership intensity in large or important markets, not explained by labor-market tightness.
- **Alternative explanations:** planned promotions and pipeline building (management: internal leadership hiring is *up*), new-store openings (coffeehouse coaches as an opening pipeline), normal turnover.
- **Would contradict the thesis:** low and evenly spread leadership intensity, or concentration only where new stores open.
- **Today?** **Yes** (cross-section). Trend needs repeat snapshots.

### TEST C: Vacancy persistence
- **Question:** Are some roles or markets much older than the national baseline?
- **Dependent variable:** for **store managers only**, days open relative to the posting's own expiry window. For frontline roles, share of requisitions from older batches.
- **Independent variable:** market, role.
- **Dataset:** national postings (+ detail expiry dates for a sample).
- **Expected sign if thesis is correct:** leadership postings in some markets reposted or extended repeatedly.
- **Alternative explanations:** **evergreen / batch requisitions** (frontline age is mechanically ≤ 89 days); reposting resets age.
- **Would contradict the thesis:** age patterns that are uniform across markets and match batch dates.
- **Today?** **Only partly.** A one-day frontline age analysis mostly measures the batch calendar. The real test needs **a
  repeat snapshot after 2026-10-02** (when the July 4 batch expires): are those requisitions reposted, and are leadership postings re-listed?

### TEST D: Labor-cost pressure
- **Question:** Are older or non-standard requisitions associated with higher pay?
- **Dependent variable:** posted pay midpoint (by role).
- **Independent variable:** posting age, duplicate status, market intensity.
- **Dataset:** pay sample (40); a city-level zone map (~1–2k requests) if needed.
- **Expected sign if thesis is correct:** higher pay for persistent openings or high-intensity markets, beyond zone and minimum wage.
- **Alternative explanations:** pay zones and local wage law (e.g. California's $20 fast-food minimum wage); cost of living.
- **Would contradict the thesis:** identical pay within zones regardless of age or intensity. **This is what the pilot shows.**
- **Today?** Pilot done: **no support.** A meaningful test needs zone levels over time.

### TEST E: Operating relationship
- **Question:** Do staffing-pressure signals correspond to weaker store outcomes?
- **Dependent variable:** visits / visit growth (Advan / pass_by), posted hours (short-hours tail), store closures (past locator runs).
- **Independent variable:** store- or market-level hiring deviations and leadership postings.
- **Dataset:** national postings + store universe + store hours (built) + foot traffic (needs access).
- **Expected sign if thesis is correct:** higher pressure ↔ fewer posted hours, lower visit growth, more closures.
- **Alternative explanations:** high-volume stores both hire more and have longer waits (reverse causality); urban formats.
- **Would contradict the thesis:** no relationship, or a positive one (busy, growing stores hire more). Aggregate comps are already strong.
- **Today?** **Hours only** (weak; hours are standardized). Traffic needs data access.

### TEST F: Store-universe penetration (context only)
- **Question:** How widespread is hiring across the company-operated store base?
- **Variables:** hiring stores ÷ 9,979 CO stores; supervisor-hiring and manager-hiring shares; multi-role shares.
- **Dataset:** national postings + store universe.
- **Interpretation:** context and denominator only. Under standing requisitions, high penetration is expected and is **not** evidence of hiring failure.
- **Today?** **Yes.**

---

## Summary

| Test | Possible today | Needs future data | Current evidence |
|---|---|---|---|
| A Non-standard intensity | Yes | Repeats for trend | Pilot: deviations rare and format-driven |
| B Leadership vacancies | Yes | Repeats for trend | Pending national |
| C Persistence | **Done** (requisition age) | Re-check from Oct 3 for replacement batches | Frontline: 0% > 90 days, 0% re-posted; July 4 batch expired with 0 replacements after 3 h. Leadership: 42% re-posted, 9.5% > 90 days |
| D Labor cost | Pilot only | Zone levels over time | Pilot: no age-pay relationship |
| E Operating link | **Done** (Advan via Dewey) | Repeat after more weeks | No staffing → traffic link once closure transfer is removed; hiring patterns: no difference. Found instead: cannibalization + closure transfer (+1.6 pp < 1 km) |
| F Penetration | Yes | — | Context only |
