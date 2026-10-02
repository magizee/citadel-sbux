"""Build state-level labor-market controls from public BLS / DOL data.

    python src/build_controls.py

Sources (all in data/raw/):
  BLS LAUS   state unemployment rate, seasonally adjusted (series LASST{fips}0000000000003), via BLS API v1
  BLS QCEW   NAICS 722513 limited-service restaurants, private ownership, state level, 2026 Q1
             (avg weekly wage, employment, and over-the-year % changes)
  DOL WHD    state minimum wage table, effective 2026-07-01 (extracted from the DOL web page; verify)
Output: data/processed/labor_market_controls.csv (join key: two-letter state code)
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FIPS = {'AL': 1, 'AK': 2, 'AZ': 4, 'AR': 5, 'CA': 6, 'CO': 8, 'CT': 9, 'DE': 10, 'DC': 11, 'FL': 12, 'GA': 13, 'HI': 15,
        'ID': 16, 'IL': 17, 'IN': 18, 'IA': 19, 'KS': 20, 'KY': 21, 'LA': 22, 'ME': 23, 'MD': 24, 'MA': 25, 'MI': 26,
        'MN': 27, 'MS': 28, 'MO': 29, 'MT': 30, 'NE': 31, 'NV': 32, 'NH': 33, 'NJ': 34, 'NM': 35, 'NY': 36, 'NC': 37,
        'ND': 38, 'OH': 39, 'OK': 40, 'OR': 41, 'PA': 42, 'RI': 44, 'SC': 45, 'SD': 46, 'TN': 47, 'TX': 48, 'UT': 49,
        'VT': 50, 'VA': 51, 'WA': 53, 'WV': 54, 'WI': 55, 'WY': 56}
BY_FIPS = {f"{v:02d}": k for k, v in FIPS.items()}


def laus() -> pd.DataFrame:
    rows = []
    for block in json.loads((ROOT / "data/raw/bls_laus_state_unemployment_2025_2026.json").read_text()):
        for s in block["Results"]["series"]:
            st = BY_FIPS[s["seriesID"][5:7]]
            obs = sorted(((int(d["year"]), int(d["period"][1:]), float(d["value"])) for d in s["data"]
                          if d["period"].startswith("M") and d["period"] != "M13" and d["value"] not in ("-", "")), reverse=True)
            if not obs:
                continue
            y, m, v = obs[0]
            prior = next((x[2] for x in obs if x[0] == y - 1 and x[1] == m), None)
            rows.append({"state": st, "unemployment_rate": v, "unemployment_rate_period": f"{y}-{m:02d}",
                         "unemployment_rate_12m_change_pp": round(v - prior, 2) if prior is not None else None})
    return pd.DataFrame(rows)


def qcew() -> pd.DataFrame:
    q = pd.read_csv(ROOT / "data/raw/qcew_2026_q1_naics722513.csv", dtype={"area_fips": str})
    q = q[(q["own_code"] == 5) & q["area_fips"].str.endswith("000") & q["area_fips"].str[:2].isin(BY_FIPS)]
    q = q[q["area_fips"].str.len() == 5]
    q["state"] = q["area_fips"].str[:2].map(BY_FIPS)
    q["lsr_employment_q1_2026"] = q["month3_emplvl"]
    return q.rename(columns={"avg_wkly_wage": "lsr_avg_weekly_wage_q1_2026",
                             "oty_avg_wkly_wage_pct_chg": "lsr_avg_weekly_wage_yoy_pct",
                             "oty_month3_emplvl_pct_chg": "lsr_employment_yoy_pct",
                             "disclosure_code": "qcew_disclosure_code"})[
        ["state", "lsr_employment_q1_2026", "lsr_employment_yoy_pct", "lsr_avg_weekly_wage_q1_2026",
         "lsr_avg_weekly_wage_yoy_pct", "qcew_disclosure_code"]]


def main():
    mw = pd.read_csv(ROOT / "data/raw/dol_state_minimum_wage_2026-07-01.csv")
    mw["binding_statewide_minimum_wage"] = mw["state_minimum_wage"].clip(lower=7.25)
    df = laus().merge(qcew(), on="state", how="outer").merge(mw, on="state", how="outer")
    df["source_date"] = "LAUS latest month; QCEW 2026Q1 (NAICS 722513, private); DOL min wage eff. 2026-07-01"
    df = df.sort_values("state")
    df.to_csv(ROOT / "data/processed/labor_market_controls.csv", index=False)
    print(df.describe().round(2).to_string())
    print(df.head(8).to_string())
    print("missing:", df.isna().sum()[lambda s: s > 0].to_dict())


if __name__ == "__main__":
    main()
