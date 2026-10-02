"""Automated data-quality checks for a cleaned postings file (national or pilot).

    python src/qa.py --input data/processed/2026-10-01/starbucks_jobs_US.csv \
        --national-count 19919 --out outputs/qa_report.md

Each check prints PASS / WARN / FAIL with counts and examples. WARN means
"look at it before relying on the affected metric", not "broken".
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

# Title words that suggest a store/field leadership role (should not be NON_RETAIL)
MANAGER_RE = re.compile(r"store manager|coffeehouse leader|district manager|assistant store manager|store leader",
                        re.IGNORECASE)
# Title words that suggest a corporate/support-centre role (should not be retail)
CORPORATE_RE = re.compile(r"\b(?:analyst|engineer|director|specialist|coordinator|counsel|scientist|developer|"
                          r"product manager|program manager|accountant|recruiter|architect|vice president|"
                          r"support center|corporate)\b", re.IGNORECASE)


def run_checks(df: pd.DataFrame, national_count: int | None) -> list[tuple[str, str, str]]:
    out = []
    n = len(df)
    retail = df[df["role_bucket"] != "NON_RETAIL"]

    def add(name, status, detail):
        out.append((status, name, detail))

    d = df["job_id"].duplicated().sum()
    add("duplicate job_ids", "PASS" if d == 0 else "FAIL", f"{d} duplicates")

    m = retail["store_key"].isna().sum()
    add("retail rows missing store_key", "PASS" if m / max(len(retail), 1) < 0.02 else "WARN",
        f"{m} of {len(retail)} ({100 * m / max(len(retail), 1):.1f}%); examples: "
        + "; ".join(retail[retail['store_key'].isna()]['job_title_raw'].head(5)))

    fb = retail["store_key"].str.startswith("addr:", na=False).sum()
    add("retail rows using address fallback store_key", "PASS" if fb / max(len(retail), 1) < 0.1 else "WARN",
        f"{fb} ({100 * fb / max(len(retail), 1):.1f}%)")

    mc = retail["latitude"].isna().sum()
    add("retail rows missing coordinates", "PASS" if mc / max(len(retail), 1) < 0.02 else "WARN",
        f"{mc} ({100 * mc / max(len(retail), 1):.1f}%)")

    ma = retail["street_address"].isna().sum()
    add("retail rows missing street address", "PASS" if ma / max(len(retail), 1) < 0.02 else "WARN",
        f"{ma} ({100 * ma / max(len(retail), 1):.1f}%)")

    age = df["days_since_posted"].astype(float)
    bad = ((age < 0) | (age > 730) | age.isna()).sum()
    add("impossible / missing posting ages (<0, >730 days, null)", "PASS" if bad == 0 else "WARN",
        f"{bad}; range {age.min():.0f}..{age.max():.0f} days")

    other = df[df["role_bucket"] == "OTHER_RETAIL"]["job_title_raw"].str.split(r" - |,").str[0].str.strip().str.lower()
    add("OTHER_RETAIL title variety (review for mis-bucketing)", "WARN" if other.nunique() > 15 else "PASS",
        f"{len(other)} postings, {other.nunique()} distinct role texts; top: "
        + "; ".join(f"{k} ({v})" for k, v in other.value_counts().head(12).items()))

    sn = df[df["store_number"].notna()]
    multi_addr = sn.groupby("store_number")["street_address"].nunique()
    multi_ll = sn.assign(ll=sn["latitude"].round(4).astype(str) + "," + sn["longitude"].round(4).astype(str)) \
                 .groupby("store_number")["ll"].nunique()
    add("store_number with >1 street address", "PASS" if (multi_addr > 1).sum() == 0 else "WARN",
        f"{(multi_addr > 1).sum()} store numbers; e.g. {list(multi_addr[multi_addr > 1].index[:8])}")
    add("store_number with >1 coordinate", "PASS" if (multi_ll > 1).sum() == 0 else "WARN",
        f"{(multi_ll > 1).sum()} store numbers; e.g. {list(multi_ll[multi_ll > 1].index[:8])}")

    nonus = (df["country"] != "US").sum()
    add("non-U.S. rows", "PASS" if nonus == 0 else "FAIL", f"{nonus}")

    st = df["state"].value_counts()
    add("rows without a parsed state", "PASS" if df["state"].isna().sum() == 0 else "WARN", f"{df['state'].isna().sum()}")
    odd = [s for s in st.index if not re.fullmatch(r"[A-Z]{2}", str(s))]
    add("state codes not two-letter", "PASS" if not odd else "WARN", f"{odd}")
    add("states represented", "PASS" if st.size >= 50 else "WARN", f"{st.size} (smallest: "
        + ", ".join(f"{k}={v}" for k, v in st.tail(5).items()) + ")")

    if national_count:
        ratio = n / national_count
        add("unique postings vs server 'United States' count", "PASS" if ratio >= 0.97 else "WARN" if ratio >= 0.9 else "FAIL",
            f"{n} / {national_count} = {100 * ratio:.1f}%")

    nr = df[df["role_bucket"] == "NON_RETAIL"]
    mgr_nr = nr[nr["job_title_raw"].str.contains(MANAGER_RE, na=False)]
    add("manager titles classified NON_RETAIL", "PASS" if len(mgr_nr) == 0 else "WARN",
        f"{len(mgr_nr)}; " + "; ".join(mgr_nr["job_title_raw"].head(8)))
    corp_r = retail[retail["job_title_raw"].str.contains(CORPORATE_RE, na=False) & retail["store_number"].isna()]
    add("corporate-looking titles classified retail (no store number)", "PASS" if len(corp_r) == 0 else "WARN",
        f"{len(corp_r)}; " + "; ".join(corp_r["job_title_raw"].head(8)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--national-count", type=int)
    ap.add_argument("--out", help="write the report as markdown here too")
    args = ap.parse_args()
    df = pd.read_csv(args.input, dtype={"store_number": str, "job_id": str, "postal_code": str})
    res = run_checks(df, args.national_count)
    lines = [f"# QA report: {args.input}", "", f"{len(df)} postings", "", "| Status | Check | Detail |", "|---|---|---|"]
    lines += [f"| {s} | {n} | {d.replace('|', '/')} |" for s, n, d in res]
    text = "\n".join(lines)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n")


if __name__ == "__main__":
    main()
