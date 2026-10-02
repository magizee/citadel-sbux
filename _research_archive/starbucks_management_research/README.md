# starbucks_management_research

What Starbucks management says about staffing and why it matters to the turnaround.

- **Sources:** Q1, Q2 and Q3 FY2026 earnings-call transcripts (FactSet CallStreet PDFs posted on Starbucks IR,
  `s203.q4cdn.com`), the Q3 FY2026 earnings release (SEC 8-K, 2026-07-29), and a Fortune interview with the COO (2026-04-29).
- **Files:** `data/raw/*.pdf` + extracted `*.txt`; `data/management_staffing_evidence.csv` (16 statements, with a
  `quote_verified` column); `outputs/management_thesis.md`.
- **Method:** transcripts were searched for staffing, labor, turnover, coffeehouse-leader, throughput and margin
  language. Every transcript quote is checked verbatim against the local text. Non-transcript quotes are flagged unverified.
- **Limitations:** company-reported claims; the Q4 FY25 transcript and investor-day (2026-01-29) materials were not retrieved.
- **Investment suitability:** high for establishing why staffing matters; the claims themselves need external testing.
