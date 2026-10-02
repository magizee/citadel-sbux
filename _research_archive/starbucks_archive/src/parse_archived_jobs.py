"""Fetch and parse archived job pages listed in data/processed/archive_index.csv.

    python src/parse_archived_jobs.py --max-pages 40

For each capture with HTTP 200 and an HTML mime type, fetches the raw archived
bytes (Wayback "id_" mode, no toolbar rewriting), saves them under
data/raw/pages/, and extracts what the page exposes:

* schema.org JobPosting JSON-LD (title, datePosted, validThrough, jobLocation) if present
* <title> / og:title / og:description meta tags
* store number from the title ("Store# 09230")

Eightfold job pages are JavaScript applications, so an archived capture may contain
only a shell with meta tags. `parse_quality` records what was recoverable.

Writes data/processed/archive_history.csv. Missing or empty captures say nothing
about whether a job existed.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
UA = "starbucks-hiring-research/0.1 (small archive validation)"
STORE_RE = re.compile(r"store\s*#\s*(\d+)", re.IGNORECASE)


def parse_page(text: str) -> dict:
    out = {}
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', text, re.S | re.I):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for d in data if isinstance(data, list) else [data]:
            if isinstance(d, dict) and d.get("@type") == "JobPosting":
                loc = d.get("jobLocation") or {}
                loc = loc[0] if isinstance(loc, list) and loc else loc
                addr = (loc or {}).get("address") or {}
                out.update({"job_title": d.get("title"), "posting_date": d.get("datePosted"),
                            "valid_through": d.get("validThrough"),
                            "location": ", ".join(str(addr.get(k)) for k in ("streetAddress", "addressLocality", "addressRegion")
                                                  if addr.get(k)),
                            "parse_quality": "jsonld_jobposting"})
    if "job_title" not in out:
        m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', text, re.I) or \
            re.search(r"<title>(.*?)</title>", text, re.S | re.I)
        if m:
            out.update({"job_title": html.unescape(m.group(1)).strip(), "parse_quality": "title_only"})
    title = out.get("job_title") or ""
    m = STORE_RE.search(title)
    out["store_number"] = m.group(1) if m else None
    m = re.search(r"store\s*#\s*\d+\s*,\s*(.+?)(?:\s*\||$)", title, re.I)
    out["store_name"] = m.group(1).strip() if m else None
    out["role"] = title.split(" - ")[0].strip().lower() if title else None
    # A page offering "apply" with a job title is treated as an active posting at capture time.
    out["appeared_active"] = bool(title) and not re.search(r"no longer (available|accepting)|position (has been )?filled|job not found",
                                                         text, re.I)
    out.setdefault("parse_quality", "no_job_fields")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--index", default=str(ROOT / "data/processed/archive_index.csv"),
                    help="capture list with archived_timestamp, archived_url, original_url, job_id, capture_status, http_status, mime_type, digest")
    args = ap.parse_args()
    idx = pd.read_csv(args.index, dtype=str)
    caps = idx[(idx["capture_status"] == "captured") & (idx["http_status"] == "200")
               & idx["mime_type"].str.contains("html", na=False)].drop_duplicates("digest").head(args.max_pages)
    pages = ROOT / "data/raw/pages"
    pages.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = UA
    rows = []
    for _, c in caps.iterrows():
        ts, orig = c["archived_timestamp"], c["archived_url"].split("/", 5)[-1]
        path = pages / f"{ts}_{re.sub(r'[^A-Za-z0-9]+', '_', orig)[:120]}.html"
        if not path.exists():
            r = s.get(f"https://web.archive.org/web/{ts}id_/{orig}", timeout=90)
            if r.status_code != 200:
                rows.append({**c.to_dict(), "fetch_status": f"HTTP {r.status_code}"})
                continue
            path.write_bytes(r.content)
            time.sleep(2)
        parsed = parse_page(path.read_text(errors="ignore"))
        rows.append({"original_url": c["original_url"], "job_id": c["job_id"], "archived_timestamp": ts,
                     "archived_url": c["archived_url"], "fetch_status": "ok", **parsed})
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data/processed/archive_history.csv", index=False)
    print(f"{len(caps)} HTML captures considered; {len(out)} rows written")


if __name__ == "__main__":
    main()
