"""Look up Wayback Machine captures for candidate Starbucks job URLs (small validation only).

    python src/archive_lookup.py --build-candidates     # 10-20 candidates from the NYC pilot
    python src/archive_lookup.py                        # query the CDX index for each candidate

Reads (never writes) ../starbucks_hiring outputs. Writes:
    data/processed/archive_candidates.csv   chosen URLs and why
    data/raw/cdx/<key>.json                 raw CDX responses (one per query)
    data/processed/archive_index.csv        one row per capture (or one 'no_captures' row per URL)

Each candidate is queried as a URL PREFIX on both hosts the careers site has used
(apply.starbucks.com and starbucks.eightfold.ai), which also matches slugged and
query-string variants of the job URL.

Missing captures do NOT mean a job did not exist; Wayback coverage is sparse and not representative.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
HIRING = ROOT.parent / "starbucks_hiring"
CDX = "https://web.archive.org/cdx/search/cdx"
UA = "starbucks-hiring-research/0.1 (small archive validation)"
DELAY = 2.0


def build_candidates(snapshot_date: str, n_max: int = 20) -> pd.DataFrame:
    """Pick 10-20 pilot postings: oldest, leadership, unusual role sets, multi-posting stores."""
    clean = pd.read_csv(HIRING / "data/processed" / snapshot_date / "pilot/pilot_jobs_clean.csv",
                        dtype={"job_id": str, "store_number": str, "position_id": str})
    pat = pd.read_csv(HIRING / "outputs/tables/pilot/store_role_patterns.csv", dtype={"store_number": str})
    retail = clean[clean["role_bucket"] != "NON_RETAIL"].copy()
    picks = []

    def take(df, reason, k):
        for _, r in df.head(k).iterrows():
            if r["job_id"] not in {p["job_id"] for p in picks}:
                picks.append({**r[["job_id", "position_id", "job_url", "job_title_raw", "role_bucket",
                                   "store_number", "store_key", "city", "state", "posted_date",
                                   "days_since_posted"]].to_dict(), "reason": reason})

    take(retail.sort_values("days_since_posted", ascending=False), "oldest active retail posting", 6)
    take(retail[retail["role_bucket"].isin(["STORE_MANAGER", "DISTRICT_MANAGER"])], "leadership posting", 3)
    unusual = pat[pat["flag_unusual_role_set"] | pat["flag_same_role_duplicate"]]["store_key"]
    take(retail[retail["store_key"].isin(unusual)].sort_values("days_since_posted", ascending=False),
         "store with unusual role set / same-role duplicates", 5)
    multi = pat[(pat["role_set"] == "BARISTA + SHIFT_SUPERVISOR") & (pat["active_postings"] == 2)]["store_key"].head(2)
    take(retail[retail["store_key"].isin(multi)], "standard multi-posting store (control)", 4)
    take(clean[clean["role_bucket"] == "NON_RETAIL"], "non-retail control", 2)
    out = pd.DataFrame(picks).head(n_max)
    out.to_csv(ROOT / "data/processed/archive_candidates.csv", index=False)
    return out


def url_variants(position_id: str) -> list[str]:
    """Prefix queries: archived URLs usually carry a title slug and/or query string
    (/careers/job/<id>-barista-store-71315-...?domain=starbucks.com), so exact-URL lookups miss them."""
    return [f"apply.starbucks.com/careers/job/{position_id}", f"starbucks.eightfold.ai/careers/job/{position_id}"]


def cdx_query(session: requests.Session, url: str, retries: int = 4) -> tuple[list, str]:
    """Return (rows, status). status: ok | empty | error:<reason>. Retries with backoff."""
    params = {"url": url, "matchType": "prefix", "output": "json",
              "fl": "timestamp,original,statuscode,mimetype,digest,length"}
    for attempt in range(retries + 1):
        try:
            r = session.get(CDX, params=params, timeout=90)
            if r.status_code == 200:
                if not r.text.strip():
                    return [], "empty"
                rows = r.json()
                return rows[1:] if rows and rows[0][0] == "timestamp" else rows, "ok"
            reason = f"HTTP {r.status_code}"
        except (requests.RequestException, ValueError) as e:
            reason = type(e).__name__
        if attempt < retries:
            time.sleep(5 * 2 ** attempt)
    return [], f"error:{reason}"


def lookup(candidates: pd.DataFrame) -> pd.DataFrame:
    raw = ROOT / "data/raw/cdx"
    raw.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = UA
    out = []
    for _, c in candidates.iterrows():
        for v in url_variants(str(c["position_id"])):
            rows, status = cdx_query(s, v)
            key = v.replace("/", "_").replace("?", "_").replace("=", "_")
            (raw / f"{key}.json").write_text(json.dumps({"query": v, "status": status, "rows": rows,
                                                          "queried_at": pd.Timestamp.utcnow().isoformat()}))
            base = {"original_url": c["job_url"], "queried_url": v, "job_id": c["job_id"],
                    "store_number": c["store_number"], "reason": c["reason"], "query_status": status}
            if not rows:
                out.append({**base, "capture_status": "no_captures" if status in ("ok", "empty") else "query_failed"})
            for ts, orig, code, mime, digest, length in rows:
                out.append({**base, "archived_timestamp": ts, "archived_url": f"https://web.archive.org/web/{ts}/{orig}",
                            "capture_status": "captured", "http_status": code, "mime_type": mime,
                            "digest": digest, "length": length})
            print(f"{v}: {status} {len(rows)} captures", flush=True)
            time.sleep(DELAY)
    df = pd.DataFrame(out)
    df.to_csv(ROOT / "data/processed/archive_index.csv", index=False)
    return df


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot-date", default="2026-10-01")
    ap.add_argument("--build-candidates", action="store_true")
    args = ap.parse_args()
    if args.build_candidates:
        print(build_candidates(args.snapshot_date)[["job_id", "job_title_raw", "days_since_posted", "reason"]].to_string())
        return
    lookup(pd.read_csv(ROOT / "data/processed/archive_candidates.csv", dtype=str))


if __name__ == "__main__":
    main()
