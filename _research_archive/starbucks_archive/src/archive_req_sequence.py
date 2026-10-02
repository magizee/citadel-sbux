"""Recover (creation date, requisition number) pairs from archived 2024-2025 job pages.

    python src/archive_req_sequence.py --per-month 10

Starbucks requisition numbers look like YY + 7-digit sequence (e.g. 250048523). If the
sequence is assigned in order through the year, the sequence reached by a given date
counts all requisitions created that year so far, including filled / closed ones.
The 2024-2025 Eightfold page template embeds the position record (t_create, ats_job_id),
so archived pages give (date, sequence) points for past years to compare with 2026.

Input : data/processed/archived_postings.csv (from archive_index_pull.py)
Output: data/raw/req_pages/*.html.gz, data/processed/req_sequence_points.csv
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import html
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
UA = "starbucks-hiring-research/0.1 (archive requisition-sequence sample)"


def parse(text: str) -> dict:
    t = html.unescape(text)
    out = {}
    for k in ("t_create", "t_update"):
        m = re.search(rf'"{k}":\s*(\d{{9,10}})', t)
        out[k] = int(m.group(1)) if m else None
    m = re.search(r'"(?:ats_job_id|display_job_id)":\s*"(\d{9})"', t)
    out["req"] = m.group(1) if m else None
    m = re.search(r'"business_unit":\s*"([^"]*)"', t)
    out["business_unit"] = m.group(1) if m else None
    m = re.search(r'"department":\s*"([^"]*)"', t)
    out["department"] = m.group(1) if m else None
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-month", type=int, default=10)
    ap.add_argument("--start", default="202401")
    ap.add_argument("--end", default="202512")
    args = ap.parse_args()

    a = pd.read_csv(ROOT / "data/processed/archived_postings.csv", dtype=str).dropna(subset=["example_ok_url"])
    a["m"] = a["example_ok_timestamp"].str[:6]
    a = a[(a["m"] >= args.start) & (a["m"] <= args.end)]
    # Spread the sample across months and across roles (frontline + leadership).
    sample = a.groupby("m", group_keys=False).apply(
        lambda g: g.sample(min(len(g), args.per_month), random_state=0))
    raw = ROOT / "data/raw/req_pages"
    raw.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = UA
    rows = []
    for i, r in enumerate(sample.itertuples(), 1):
        f = raw / f"{r.example_ok_timestamp}_{r.position_id}.html.gz"
        if not f.exists():
            try:
                resp = s.get(f"https://web.archive.org/web/{r.example_ok_timestamp}id_/{r.example_ok_url}", timeout=90)
            except requests.RequestException as e:
                rows.append({"position_id": r.position_id, "fetch": type(e).__name__})
                continue
            if resp.status_code != 200:
                rows.append({"position_id": r.position_id, "fetch": f"HTTP {resp.status_code}"})
                time.sleep(3)
                continue
            f.write_bytes(gzip.compress(resp.content))
            time.sleep(2)
        p = parse(gzip.decompress(f.read_bytes()).decode(errors="ignore"))
        rows.append({"position_id": r.position_id, "capture": r.example_ok_timestamp, "role_slug": r.role,
                     "store_number": r.store_number, "fetch": "ok", **p})
        if i % 25 == 0:
            print(f"{i}/{len(sample)}", flush=True)
    d = pd.DataFrame(rows)
    ok = d[d["req"].notna() & d["t_create"].notna()].copy()
    ok["yy"] = ok["req"].str[:2].astype(int)
    ok["seq"] = ok["req"].str[2:].astype(int)
    ok["created"] = ok["t_create"].map(lambda x: dt.datetime.fromtimestamp(x, dt.timezone.utc).date().isoformat())
    d.to_csv(ROOT / "data/processed/req_sequence_fetch_log.csv", index=False)
    ok.to_csv(ROOT / "data/processed/req_sequence_points.csv", index=False)
    print(f"fetched {len(d)}; usable (req + t_create) {len(ok)}")
    print(ok.groupby("yy")["seq"].describe().to_string())


if __name__ == "__main__":
    main()
