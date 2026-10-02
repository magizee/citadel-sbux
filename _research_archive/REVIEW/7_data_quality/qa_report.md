# QA report: national postings

19831 postings

| Status | Check | Detail |
|---|---|---|
| PASS | duplicate job_ids | 0 duplicates |
| PASS | retail rows missing store_key | 187 of 19687 (0.9%); examples: store manager - Anchorage, AK; store manager - Fairbanks, AK; store manager - Mount Vernon/Burlington, WA; store manager - Marysville/Arlington, WA; store manager - Lynnwood, WA |
| PASS | retail rows using address fallback store_key | 25 (0.1%) |
| PASS | retail rows missing coordinates | 0 (0.0%) |
| PASS | retail rows missing street address | 187 (0.9%) |
| PASS | impossible / missing posting ages (<0, >730 days, null) | 0; range 0..149 days |
| PASS | OTHER_RETAIL title variety (review for mis-bucketing) | 13 postings, 7 distinct role texts; top: operations lead (5); mixologist (bartender) (2); baker (2); assembler (receiver) (1); porter (dishwasher) (1); baker lead (1); mixologist (1) |
| WARN | store_number with >1 street address | 2 store numbers; e.g. ['02914', '07293'] |
| WARN | store_number with >1 coordinate | 2 store numbers; e.g. ['02914', '07293'] |
| PASS | non-U.S. rows | 0 |
| WARN | rows without a parsed state | 2 |
| PASS | state codes not two-letter | [] |
| PASS | states represented | 51 (smallest: SD=45, ND=35, AK=24, VT=22, WY=21) |
| PASS | unique postings vs server 'United States' count | 19831 / 19674 = 100.8% |
| PASS | manager titles classified NON_RETAIL | 0;  |
| PASS | corporate-looking titles classified retail (no store number) | 0;  |
