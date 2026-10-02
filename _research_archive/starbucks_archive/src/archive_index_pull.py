"""Pull the full Wayback CDX index for Starbucks job URLs and build a postings table.

    python src/archive_index_pull.py

Fetches every index page (46 on 2026-10-01) for the prefix apply.starbucks.com/careers/job/
(~46 small requests to archive.org, no page fetches). Raw pages are stored gzipped
under data/raw/cdx_index/. Output:

    data/processed/archived_postings.csv   one row per archived posting (position_id):
        first/last capture, n_captures, role and store number parsed from the URL slug,
        location slug, and one example 200/HTML capture for later page fetches

Coverage is crawler-driven and bursty; this is NOT a representative sample of postings.
"""

from __future__ import annotations

import gzip
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
CDX = "https://web.archive.org/cdx/search/cdx"
PREFIX = "apply.starbucks.com/careers/job/"
UA = "starbucks-hiring-research/0.1 (archive index pull)"
ROLE_PATTERNS = [("DISTRICT_MANAGER", r"district-manager"),
                 ("STORE_MANAGER", r"store-manager|coffeehouse-leader|coffeehouse-coach|assistant-store-manager"),
                 ("SHIFT_SUPERVISOR", r"shift-supervisor|shift-manager"), ("BARISTA", r"barista")]


def get(session, params, tries=5):
    for i in range(tries):
        try:
            r = session.get(CDX, params=params, timeout=180)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(10 * 2 ** i)
    raise RuntimeError(f"CDX failed: {params}")


def main() -> None:
    out = ROOT / "data/raw/cdx_index"
    out.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = UA
    n_pages = int(get(s, {"url": PREFIX, "matchType": "prefix", "showNumPages": "true"}).strip())
    print("index pages:", n_pages)
    for p in range(n_pages):
        f = out / f"page_{p:03d}.txt.gz"
        if f.exists():
            continue
        txt = get(s, {"url": PREFIX, "matchType": "prefix", "fl": "timestamp,original,statuscode,mimetype", "page": p})
        f.write_bytes(gzip.compress(txt.encode()))
        print(f"page {p}: {txt.count(chr(10))} lines", flush=True)
        time.sleep(2)

    rows = []
    for f in sorted(out.glob("page_*.txt.gz")):
        for line in gzip.decompress(f.read_bytes()).decode().splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            ts, url, code, mime = parts[:4]
            m = re.search(r"/careers/job/(\d{9,})(?:-([a-z0-9-]+))?", url)
            if m:
                rows.append((m.group(1), m.group(2) or "", ts, url, code, mime))
    d = pd.DataFrame(rows, columns=["position_id", "slug", "timestamp", "url", "status", "mime"])
    ok = d[(d["status"] == "200") & d["mime"].str.contains("html")]
    agg = d.groupby("position_id").agg(first_capture=("timestamp", "min"), last_capture=("timestamp", "max"),
                                       n_captures=("timestamp", "size"), slug=("slug", "max")).reset_index()
    ex = ok.sort_values("timestamp").drop_duplicates("position_id")[["position_id", "timestamp", "url"]] \
        .rename(columns={"timestamp": "example_ok_timestamp", "url": "example_ok_url"})
    agg = agg.merge(ex, on="position_id", how="left")
    agg["role"] = agg["slug"].map(lambda s: next((r for r, p in ROLE_PATTERNS if re.search(p, s)), "OTHER" if s else "NO_SLUG"))
    agg["store_number"] = agg["slug"].str.extract(r"store-(\d{5})")[0]
    agg["location_slug"] = agg["slug"].str.extract(r"-([a-z-]+)-united-states$")[0]
    agg.to_csv(ROOT / "data/processed/archived_postings.csv", index=False)
    print(f"captures {len(d)}; archived postings {len(agg)}; with store number {agg['store_number'].notna().sum()}; "
          f"stores {agg['store_number'].nunique()}")
    print(agg.assign(y=agg["first_capture"].str[:4]).pivot_table(index="y", columns="role", values="position_id",
                                                                  aggfunc="count", fill_value=0).to_string())


if __name__ == "__main__":
    main()
