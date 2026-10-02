"""Small pay-range pilot: fetch ~40 Starbucks job detail pages and extract posted pay.

    python src/pay_sample.py --n 40

Candidates are read (never written) from raw search pages the national scrape has
already saved in ../starbucks_hiring/data/raw/<date>/searches/, chosen to cover:
oldest retail postings, leadership postings, stores with same-role duplicates,
and a spread of states. Each detail page is one request to the public endpoint
https://apply.starbucks.com/api/pcsx/position_details?position_id=<id>&domain=starbucks.com

Outputs:
    data/raw/details/<position_id>.json        untouched responses
    data/processed/pay_candidates.csv
    data/processed/pay_sample.csv
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
HIRING = ROOT.parent / "starbucks_hiring"
DETAILS_URL = "https://apply.starbucks.com/api/pcsx/position_details"
UA = "Mozilla/5.0 (compatible; starbucks-hiring-research/0.1; pay-range pilot)"
DELAY = 3.0
SNAPSHOT = dt.date(2026, 10, 1)

ROLE_RE = [("DISTRICT_MANAGER", r"district manager"), ("STORE_MANAGER", r"store manager|coffeehouse leader"),
           ("SHIFT_SUPERVISOR", r"shift supervisor|shift manager"), ("BARISTA", r"barista")]
PAY_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)\s*(?:to|-|–)\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(USD|CAD)?\s*(annually|hourly|per hour|/hr)?",
                    re.IGNORECASE)


def role_of(title: str) -> str | None:
    t = title.lower()
    for role, pat in ROLE_RE:
        if re.search(pat, t):
            return role
    return None


def load_saved_positions(snapshot_date: str) -> pd.DataFrame:
    rows, seen = [], set()
    for p in (HIRING / "data/raw" / snapshot_date / "searches").glob("*/page_*.json"):
        try:
            rec = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue  # a page being written right now
        for pos in (rec["response"].get("data") or {}).get("positions") or []:
            if pos["id"] in seen or not pos.get("standardizedLocations"):
                continue
            seen.add(pos["id"])
            std = pos["standardizedLocations"][0].split(",")
            if std[-1].strip() != "US":
                continue
            m = re.search(r"store\s*#\s*(\d+)", pos["name"], re.IGNORECASE)
            rows.append({"position_id": str(pos["id"]), "job_id": pos.get("displayJobId"), "title": pos["name"],
                         "role": role_of(pos["name"]), "store_number": m.group(1) if m else None,
                         "state": std[-2].strip() if len(std) >= 2 else None, "location": pos["locations"][0],
                         "posted_ts": pos.get("postedTs")})
    df = pd.DataFrame(rows)
    df["days_open"] = df["posted_ts"].apply(lambda t: (SNAPSHOT - dt.datetime.fromtimestamp(t, dt.timezone.utc).date()).days)
    return df[df["role"].notna()]


def choose(df: pd.DataFrame, n: int) -> pd.DataFrame:
    picks = []

    def take(sub, reason, k):
        for _, r in sub.iterrows():
            if k <= 0:
                break
            if r["position_id"] not in {p["position_id"] for p in picks}:
                picks.append({**r.to_dict(), "reason": reason})
                k -= 1

    take(df[df["role"].isin(["STORE_MANAGER", "DISTRICT_MANAGER"])].sort_values("days_open", ascending=False), "leadership", 8)
    dup_stores = df[df["store_number"].notna()].groupby(["store_number", "role"]).filter(lambda g: len(g) > 1)
    take(dup_stores.sort_values(["store_number", "role"]), "same-role duplicate at a store", 6)
    take(df.sort_values("days_open", ascending=False), "oldest posting", 6)
    # Geographic spread for the frontline roles: one barista + one supervisor per state, newest-first.
    for st in sorted(df["state"].dropna().unique()):
        for role in ["BARISTA", "SHIFT_SUPERVISOR"]:
            take(df[(df["state"] == st) & (df["role"] == role)].sort_values("days_open"), f"geographic spread ({st})", 1)
            if len(picks) >= n:
                break
        if len(picks) >= n:
            break
    out = pd.DataFrame(picks).head(n)
    out.to_csv(ROOT / "data/processed/pay_candidates.csv", index=False)
    return out


def parse_pay(d: dict) -> dict:
    """Pick the populated pay field and split it into min / max / basis."""
    fields = ["efcustomTextPayRange", "efcustomTextPayRangenonretail", "efcustomTextPayRateRangeUs"]
    for f in fields:
        v = d.get(f)
        text = v[0] if isinstance(v, list) and v else (v if isinstance(v, str) else None)
        if not text:
            continue
        m = PAY_RE.search(text)
        if not m:
            return {"pay_field": f, "pay_text": text}
        lo, hi = (float(x.replace(",", "")) for x in m.group(1, 2))
        basis = "salary" if (m.group(4) or "").lower().startswith("annual") or lo > 1000 else "hourly"
        return {"pay_field": f, "pay_text": text, "minimum_pay": lo, "maximum_pay": hi,
                "pay_midpoint": round((lo + hi) / 2, 2), "hourly_or_salary": basis, "currency": m.group(3) or "USD"}
    return {"pay_field": None, "pay_text": None}


def fetch(cands: pd.DataFrame) -> pd.DataFrame:
    raw = ROOT / "data/raw/details"
    raw.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    rows = []
    for _, c in cands.iterrows():
        path = raw / f"{c['position_id']}.json"
        if path.exists():
            payload = json.loads(path.read_text())
        else:
            r = s.get(DETAILS_URL, params={"position_id": c["position_id"], "domain": "starbucks.com", "hl": "en"}, timeout=30)
            if r.status_code != 200:
                print(f"{c['position_id']}: HTTP {r.status_code}; stopping (no retries in a pilot)")
                break
            payload = r.json()
            path.write_text(json.dumps(payload))
            time.sleep(DELAY)
        d = payload.get("data") or {}
        rows.append({"job_id": c["job_id"], "position_id": c["position_id"], "store_number": c["store_number"],
                     "role": c["role"], "title": c["title"], "location": c["location"], "state": c["state"],
                     "posted_ts": c["posted_ts"], "days_open": c["days_open"], "reason": c["reason"],
                     "hiring_band": (d.get("efcustomTextPositionHiringBand") or [None])[0],
                     "bonus": (d.get("efcustomTextPositionBonus") or [None])[0],
                     "post_expiry_ts": (d.get("efcustomIntExtPostExpDate") or [None])[0],
                     **parse_pay(d), "source_url": d.get("publicUrl")})
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data/processed/pay_sample.csv", index=False)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--snapshot-date", default="2026-10-01")
    args = ap.parse_args()
    saved = load_saved_positions(args.snapshot_date)
    print(f"{len(saved)} retail-titled US positions in saved national pages so far; "
          f"{saved['state'].nunique()} states")
    cands = choose(saved, args.n)
    print(cands["reason"].str.split(" \\(").str[0].value_counts().to_dict())
    out = fetch(cands)
    print(f"fetched {len(out)}; with parsed pay: {out['minimum_pay'].notna().sum() if 'minimum_pay' in out else 0}")


if __name__ == "__main__":
    main()
