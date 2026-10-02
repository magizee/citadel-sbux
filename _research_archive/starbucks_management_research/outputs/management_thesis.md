# What Starbucks management says about staffing, and how to test it

Sources: Starbucks' own earnings-call transcripts (Q1, Q2, Q3 FY2026; FactSet CallStreet copies posted on
Starbucks IR), the Q3 FY2026 earnings release (SEC 8-K, 2026-07-29), and one Fortune interview with the COO.
The table of statements is in `../data/management_staffing_evidence.csv`. Transcript quotes are checked verbatim against
the local text (`data/raw/*.txt`). The two non-transcript quotes are flagged as unverified.

## 1. What management says matters operationally

Management's turnaround ("Back to Starbucks") puts store labor at the centre of the operating model:

| Lever | What management says | When |
|---|---|---|
| **Roster size and labor hours** | "bigger rosters", "healthy rosters"; Green Apron Service came with added labor hours, and "We don't see our way forward with cutting." | Q1, Q2 FY26 |
| **Hourly turnover** | "continued low hourly partner turnover" | Q1 FY26 |
| **Store-leader stability** | "leadership continuity strongly correlates to a better culture and improved coffeehouse performance"; leaders expected to stay in role 3+ years; 80% of top-rated (5-shot) stores had a leader enrolled > 1 year; leaders enrolled 2+ years up ~7 pts YoY | Q1, Q2, Q3 FY26 |
| **Internal leadership pipeline** | "coffeehouse coaches, which are our assistant store managers" as the pipeline for new stores; internal hiring for retail leadership up YoY | Q1, Q3 FY26 |
| **Throughput / service speed** | Café and drive-thru service times below the 4-minute target; "target service times across every access point in Q3" | Q1, Q3 FY26 |
| **Labor hours vs. growth** | Hours are managed to demand; "we'll earn our way into having the additional hours necessary to match the growth of the business" | Q3 FY26 |

## 2. Which parts relate to revenue

Management's causal story is the same chain as the thesis: staffing → service speed and consistency → transactions → comps.
- Green Apron pilot stores reportedly outperformed the fleet by about 200 bps in comps, mostly via transactions (Q1 FY26 call, secondary summary).
- **Reported outcomes are currently strong:** U.S. comps +7.9% with transactions +4.2% in Q3 FY26 (8-K), the fourth straight quarter of comp growth, and guidance raised (Q4 U.S. comps ≥ 6.5%).

## 3. Which parts relate to margin

- Labor is the main margin headwind of the turnaround: Q1 FY26 North America margin fell ~420 bps, "primarily as our investments in support of Back to Starbucks, continue to annualize."
- Margin recovery depends on (a) **lapping the Green Apron labor investment in Q4 FY26** (Aug 2026) and (b) sales leverage. Q3 FY26 North America margin rose ~280 bps (>100 bps excluding tariff refunds); FY26 margin guidance was raised to >11%.
- **Where the thesis could still bite:** if transaction growth requires *more* hours ("earn our way into" hours) faster than sales leverage, or if pay and incentives (weekly pay, quarterly rewards of up to $300) keep raising labor cost per hour, margin expansion after the anniversary could disappoint even with good comps.

## 4. What external data could test each statement

| Management claim | External test | Status |
|---|---|---|
| Rosters are healthy; hourly turnover is low | Frontline postings per store over **repeated** snapshots (stable standing requisitions vs. growing duplicates); share of stores off the standard 1 barista + 1 supervisor pattern | One snapshot today. Needs repeats |
| Leader stability is improving; internal promotion is up | Store-manager / coffeehouse-coach postings per store by market, and their persistence across snapshots | Measurable today (cross-section). Trend needs repeats |
| Service times on target | Review text mentioning waits / understaffing; foot-traffic dwell time | No accessible source today (see `starbucks_operating_data`) |
| Transactions growing | Foot-traffic panels (Placer.ai / Advan) by market | Paid; not accessible today |
| Labor cost pressure | Posted pay ranges by role and zone over time | Pay is posted on every requisition but set by a standardized zone table (see `starbucks_pay_analysis`); trend needs repeats |

## Bottom line

Management explicitly makes staffing and store-leader stability central to the turnaround. That supports the *premise*
of the thesis (staffing execution matters). But management also reports that the inputs (rosters, turnover, leader
tenure, fill rate) and the outputs (service times, transactions, comps) are improving, and Q3 FY26 reported results agree
on the outputs. These are company-reported figures. The live job data can test parts of the input claims cross-sectionally
today, and the trend only with repeated snapshots.
