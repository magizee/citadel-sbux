# Pay-range pilot: validation

> PILOT: 40 job detail pages, chosen on purpose (not a random sample). Collected 2026-10-01 ~22:50–23:00 ET.

## Method

- Candidates were read from search pages the national scrape had already saved (read-only), covering 33 states:
  8 leadership postings, 6 same-role duplicates at a store, 6 of the oldest postings, and 20 for geographic spread
  (one barista + one shift supervisor per state).
- One request per job to the public detail endpoint `apply.starbucks.com/api/pcsx/position_details`, spaced 3 s apart. No errors.
- Raw responses: `data/raw/details/*.json`. Parsed: `data/processed/pay_sample.csv`.

## Findings

| Question | Answer |
|---|---|
| Are pay ranges available? | **Yes: 40 of 40.** Hourly roles: `efcustomTextPayRange` ("15.25 to 17.31 USD"). Store managers: `efcustomTextPayRangenonretail` ("$63,400-$88,800 annually") |
| Role-specific? | Yes. Barista min $15.25–21.75/h (9 distinct ranges); shift supervisor $19.37–25.72/h (7); store manager $58.8k–67.6k min salary (5) |
| Standardized? | **Highly.** Each range is a step on a fixed pay-zone ladder: max = min × 1.135 for every hourly posting. The same barista range ($15.25–17.31) appears in AL, AR, AZ, GA, IL and NM, and the same supervisor range ($19.37–21.99) in AR, AZ, FL, IL, KS and TX. Store-manager ranges are max = min × 1.40 |
| Comparable across markets? | Yes, as **zone levels** (cost-of-labor tiers), not as market-specific bids |
| Do older postings show higher pay than newer same-role postings? | **No evidence.** An 89-day Arizona barista posting shows $15.25–17.31, identical to a 1-day Arizona barista posting. Median barista minimum: 16.25 (> 60 days) vs. 16.75 (≤ 60 days), a difference that comes from which zones the old postings were in, not their age |
| Same-role duplicates at one store | Identical pay (FL store 08732 ×2, FL 09516 ×2, WA Southcenter ×2) |
| Are high-pressure markets paying more? | Can't tell from 40 postings. Pay follows zones and local wage law (e.g. California barista $20.25 ≈ the state's $20 fast-food minimum wage) |

## Also found in the detail payload (more useful than pay)

- **Posting expiry date** (`efcustomIntExtPostExpDate`): **every barista and shift-supervisor posting expires exactly 90 days
  after it was posted**, and they are posted in batches at midnight ET (2026-07-04, 09-02, 09-17, 09-22, 09-27/28, 09-30).
  Frontline posting age is therefore capped at 89 days and mostly reflects the requisition refresh calendar.
- Store-manager postings have individual timestamps and 28–60 day lifetimes, and are **area-level** ("store manager –
  Tulsa"), not store-level.
- Hiring band, bonus eligibility and full description are also available.

## Is a national pay pull worth it today?

**No.**
- **Cost:** about 20,000 retail postings means about 20,000 requests, roughly 15–17 hours at a 2.5–3 s delay.
- **Payoff:** pay is a standardized zone table, so a national pull would mostly map Starbucks' pay zones. It wouldn't
  reveal posting-level wage pressure in a single snapshot.
- **Cheaper alternative:** one barista + one supervisor posting per city (about 1–2k requests, 1–1.5 hours) would map the
  zone ladder if needed.
- **What would make pay useful:** repeated snapshots showing **zone levels rising between snapshots** (labor-cost pressure),
  compared with local minimum-wage changes.

## Limitations

40 hand-picked postings; one day; posted ranges, not actual wages; no causal inference possible.
