"""One-off re-check: were expired frontline requisitions replaced?

    python src/recheck_batch.py --snapshot-date 2026-10-01 --batch-date 2026-07-04 --label recheck_0402

The frontline batch posted 2026-07-04 expired at 00:00 ET on 2026-10-02 (fixed 90-day
expiry), part-way through the national scrape. For every store that had a posting
from that batch in the national snapshot, run ONE small coordinate search (2 km
around the store, up to 3 pages) and record whether the store now shows a posting for
the same role, and whether it is a new requisition.

Uses the same Searcher (pacing, retries, raw-page storage). Raw pages go to
data/raw/<label>/searches/. Not a recurring job.
Output: data/processed/<snapshot>/batch_recheck_<label>.csv
"""

from __future__ import annotations

import argparse
import re

import pandas as pd

from common import SearchUnit, load_config, processed_dir, setup_logging
from scrape_jobs import Searcher, positions_of


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snapshot-date", default="2026-10-01")
    ap.add_argument("--batch-date", default="2026-07-04")
    ap.add_argument("--label", required=True, help="folder label for this re-check, e.g. recheck_0402")
    ap.add_argument("--max-stores", type=int, default=400)
    args = ap.parse_args()
    cfg = load_config()
    log = setup_logging(cfg, f"recheck_{args.label}")

    jobs = pd.read_csv(processed_dir(cfg, args.snapshot_date) / "starbucks_jobs_US.csv",
                       dtype={"store_number": str, "job_id": str})
    batch = jobs[(jobs["posted_date"] == args.batch_date) & jobs["role_bucket"].isin(["BARISTA", "SHIFT_SUPERVISOR"])
                 & jobs["store_number"].notna() & jobs["latitude"].notna()]
    stores = batch.groupby("store_number").agg(lat=("latitude", "first"), lon=("longitude", "first"),
                                                roles=("role_bucket", lambda x: sorted(set(x))),
                                                expired_job_ids=("job_id", lambda x: sorted(set(x)))).reset_index()
    stores = stores.head(args.max_stores)
    log.info("Re-checking %d stores with %d postings from the %s batch", len(stores), len(batch), args.batch_date)

    s = Searcher(cfg, args.label, log)          # writes under data/raw/<label>/searches/
    rows = []
    for st in stores.itertuples():
        unit = SearchUnit.point(f"store_{st.store_number}", st.lat, st.lon, 2)
        found = []
        for start in (0, 10, 20):
            rec = s.fetch_page(unit, start)
            pos = positions_of(rec)
            found += [p for p in pos if re.search(rf"store\s*#\s*{st.store_number}\b", p["name"], re.I)]
            count = (rec["response"].get("data") or {}).get("count") or 0
            if start + 10 >= count:
                break
        for role in st.roles:
            pat = "barista" if role == "BARISTA" else r"shift (supervisor|manager)"
            same = [p for p in found if re.match(pat, p["name"], re.I)]
            rows.append({
                "store_number": st.store_number, "role": role,
                "expired_job_ids": ";".join(st.expired_job_ids),
                "expired_still_listed": any(str(p["displayJobId"]) in st.expired_job_ids for p in same),
                "same_role_postings_now": len(same),
                "replacement_job_ids": ";".join(str(p["displayJobId"]) for p in same
                                                if str(p["displayJobId"]) not in st.expired_job_ids),
                "replacement_posted_ts": ";".join(str(p["postedTs"]) for p in same
                                                  if str(p["displayJobId"]) not in st.expired_job_ids),
                "replacement_created_ts": ";".join(str(p["creationTs"]) for p in same
                                                   if str(p["displayJobId"]) not in st.expired_job_ids),
            })
    out = pd.DataFrame(rows)
    path = processed_dir(cfg, args.snapshot_date) / f"batch_recheck_{args.label}.csv"
    out.to_csv(path, index=False)
    log.info("requests: %d | rows: %d | still listed: %d | same-role posting present: %d -> %s",
             s.requests_made, len(out), out["expired_still_listed"].sum(), (out["same_role_postings_now"] > 0).sum(), path)


if __name__ == "__main__":
    main()
