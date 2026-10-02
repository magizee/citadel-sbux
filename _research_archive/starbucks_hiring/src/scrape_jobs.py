"""Collect Starbucks job postings from the public careers search API.

Data collection only. Every API response is saved untouched; parsing and
cleaning live in clean_jobs.py.

How the site is accessed
------------------------
The careers page https://apply.starbucks.com/careers (Eightfold) loads results
from a public JSON endpoint:

    GET https://apply.starbucks.com/api/pcsx/search
        ?domain=starbucks.com
        &location=<"lat,lon" or free text>
        &filter_distance=<radius in KM>
        &filter_include_remote=0
        &start=<offset>

* 10 rows per page (fixed), paginated by `start`; `data.count` = total.
* No result cap: offsets up to 21,670 were served; past the end -> 0 rows.
* `location` accepts "lat,lon" directly (same results as the city name).
* Free-text locations are geocoded: cities -> point + radius; most state
  names -> region match. "New York"/"DC" are geocoded as cities, so text
  state searches are a cross-check only, not the collection method.

Collection model
----------------
A *search unit* is one query (coordinates + radius, or free text). Each unit
gets data/raw/<date>/searches/<search_id>/page_*.json (raw responses) and a
manifest data/raw/<date>/searches/<search_id>.json recording its status.
A *run* (pilot, a state cross-check, the national grid) is a list of search
units, recorded in data/raw/<date>/runs/<run_name>.json. One posting can be
discovered by many searches; build_run_outputs() writes a discovery table
(job x search) next to the raw rows.

Usage
-----
    python src/scrape_jobs.py --pilot
    python src/scrape_jobs.py --point 40.7128,-74.006 --radius-km 40 --max-results 250
    python src/scrape_jobs.py --location "New York, NY" --max-results 250
    python src/scrape_jobs.py --state CA                     # cross-check only
    python src/scrape_jobs.py --national --plan-only --confirm   # page-0 probes
    python src/scrape_jobs.py --national --confirm               # full grid

Re-running the same command with the same --snapshot-date resumes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import time
from pathlib import Path

import pandas as pd
import requests

import geo_grid
from common import (SearchUnit, load_config, raw_dir, searches_dir,
                    setup_logging, slug, today_str)


class FatalHTTPError(RuntimeError):
    """Non-retryable response (e.g. 401/403). We stop rather than work around it."""


# --------------------------------------------------------------------------- #
# HTTP with retries
# --------------------------------------------------------------------------- #

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def get_json(session: requests.Session, url: str, params: dict, req_cfg: dict, log) -> dict:
    """GET a JSON document, retrying transient failures with exponential backoff.

    Retries: connection errors, timeouts, HTTP 429 and 5xx (honouring
    Retry-After when present). Any other 4xx is fatal: access controls are
    respected, never bypassed.
    """
    max_retries = req_cfg["max_retries"]
    for attempt in range(max_retries + 1):
        reason = None
        retry_after = None
        try:
            resp = session.get(url, params=params, timeout=req_cfg["timeout_seconds"])
            if resp.status_code == 200:
                payload = resp.json()
                # The API also reports a status inside the body.
                body_status = payload.get("status", 200)
                if body_status == 200:
                    return payload
                if body_status in RETRYABLE_STATUS:
                    reason = f"body status {body_status}"
                else:
                    raise FatalHTTPError(f"API body status {body_status}: {payload.get('error')}")
            elif resp.status_code in RETRYABLE_STATUS:
                reason = f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("Retry-After")
            else:
                raise FatalHTTPError(f"HTTP {resp.status_code} for {resp.url}: {resp.text[:200]}")
        except (requests.ConnectionError, requests.Timeout, ValueError) as e:
            # ValueError covers truncated / non-JSON bodies.
            reason = f"{type(e).__name__}: {e}"

        if attempt == max_retries:
            raise RuntimeError(f"Giving up after {max_retries} retries ({reason}) params={params}")

        wait = min(req_cfg["backoff_base_seconds"] * (2 ** attempt), req_cfg["backoff_max_seconds"])
        if retry_after and str(retry_after).isdigit():
            wait = max(wait, int(retry_after))
        wait += random.uniform(0, 1)
        log.warning("Transient failure (%s); retry %d/%d in %.1fs", reason, attempt + 1, max_retries, wait)
        time.sleep(wait)
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------- #
# Storage helpers
# --------------------------------------------------------------------------- #

def write_json_atomic(path: Path, obj) -> None:
    """Write to a temp file then rename, so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=None), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def positions_of(page_rec: dict) -> list[dict]:
    return (page_rec["response"].get("data") or {}).get("positions") or []


def facet_addresses(page_rec: dict) -> dict[str, str]:
    """Address -> "lat,lon" pairs from the response's map facet (all results, max 1,500)."""
    out = {}
    data = page_rec["response"].get("data") or {}
    for f in (data.get("filterDef") or {}).get("allFilters") or []:
        if f.get("filterName") == "latlong_non_remote":
            for opt in f.get("options") or []:
                val = opt.get("value") if isinstance(opt, dict) else opt
                if isinstance(val, str) and ":::" in val:
                    key, coords = val.rsplit(":::", 1)
                    out[key] = coords
    return out


# --------------------------------------------------------------------------- #
# One search unit
# --------------------------------------------------------------------------- #

class Searcher:
    """Runs search units, saving every page and a manifest per unit."""

    def __init__(self, cfg: dict, snapshot_date: str, log):
        self.cfg, self.snapshot_date, self.log = cfg, snapshot_date, log
        self.sdir = searches_dir(cfg, snapshot_date)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": cfg["request"]["user_agent"], "Accept": "application/json"})
        self.requests_made = 0

    def page_dir(self, unit: SearchUnit) -> Path:
        return self.sdir / unit.search_id

    def manifest_path(self, unit: SearchUnit) -> Path:
        return self.sdir / f"{unit.search_id}.json"

    def _query(self, unit: SearchUnit) -> dict:
        return {"domain": self.cfg["api"]["domain"], **unit.params(self.cfg["search"]["include_remote"])}

    def fetch_page(self, unit: SearchUnit, start: int) -> dict:
        """Return the saved page if present, else fetch and save it."""
        path = self.page_dir(unit) / f"page_{start:06d}.json"
        query = self._query(unit)
        if path.exists():
            rec = read_json(path)
            saved = {k: v for k, v in rec["request"].items() if k != "start"}
            if saved != query:
                raise SystemExit(f"{path} was saved for a different query ({saved} vs {query}). "
                                 "Use --fresh or a different snapshot date.")
            return rec
        params = {**query, "start": start}
        payload = get_json(self.session, self.cfg["api"]["search_url"], params, self.cfg["request"], self.log)
        self.requests_made += 1
        rec = {"request": params,
               "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "response": payload}
        write_json_atomic(path, rec)
        time.sleep(self.cfg["request"]["delay_seconds"])
        return rec

    def write_manifest(self, unit: SearchUnit, **fields) -> dict:
        m = {"search_unit": unit.to_dict(), "snapshot_date": self.snapshot_date,
             "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), **fields}
        write_json_atomic(self.manifest_path(unit), m)
        return m

    def probe(self, unit: SearchUnit) -> dict:
        """Fetch page 0 only and summarise it (used to decide whether to split)."""
        rec = self.fetch_page(unit, 0)
        data = rec["response"].get("data") or {}
        addrs = facet_addresses(rec)
        return {
            "count": data.get("count") or 0,
            "applied_filters": data.get("appliedFilters"),
            "facet_addresses": len(addrs),
            "facet_us_addresses": sum(a.lower().endswith("united states") for a in addrs),
        }

    def paginate(self, unit: SearchUnit, max_results: int | None = None, already_seen: set | None = None) -> dict:
        """Fetch every page of a unit (or until max_results unique IDs) and record completeness.

        A search is COMPLETE when the last page has been reached, the
        server-reported count stayed the same on every page, and the number
        of unique postings collected equals that count.
        """
        page_size = self.cfg["request"]["page_size"]
        seen: set[str] = set()
        run_seen = already_seen if already_seen is not None else set()
        counts, start, pages, rows, reached_end = [], 0, 0, 0, False
        info = self.probe(unit)
        if info["applied_filters"] and unit.query_radius_km is None and "distance" in info["applied_filters"]:
            self.log.warning("Search %s (%r) was treated as a RADIUS search (distance=%s), not a region.",
                             unit.search_id, unit.query_location, info["applied_filters"]["distance"])
        while True:
            rec = self.fetch_page(unit, start)
            data = rec["response"].get("data") or {}
            pos = positions_of(rec)
            count = data.get("count") or 0
            counts.append(count)
            new = [str(p["id"]) for p in pos if str(p["id"]) not in seen]
            seen.update(new)
            run_seen.update(new)
            pages += 1
            rows += len(pos)
            self.log.info("%s page %d (start=%d): rows=%d new=%d cumulative=%d / %d",
                          unit.search_id, pages, start, len(pos), len(new), len(seen), count)
            start += page_size
            if len(pos) == 0 or start >= count:
                reached_end = True
                break
            if max_results is not None and len(run_seen) >= max_results:
                break

        if not reached_end:
            status = "capped"
        elif len(set(counts)) == 1 and len(seen) == counts[-1]:
            status = "complete"
        else:
            status = "incomplete"   # count changed mid-run, or unique != count: re-run
        self.log.info("%s: %s (unique=%d, reported=%s, pages=%d)", unit.search_id, status, len(seen),
                      sorted(set(counts)), pages)
        return self.write_manifest(
            unit, status=status, reported_count_first=counts[0], reported_count_last=counts[-1],
            reported_counts_changed=len(set(counts)) > 1, pages=pages, rows=rows, unique_postings=len(seen),
            applied_filters=info["applied_filters"], facet_addresses=info["facet_addresses"],
            facet_truncated=info["facet_addresses"] >= self.cfg["national"]["facet_address_cap"],
            max_results=max_results)


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #

def run_manifest_path(cfg: dict, snapshot_date: str, run_name: str) -> Path:
    return raw_dir(cfg, snapshot_date) / "runs" / f"{run_name}.json"


def run_simple(cfg, snapshot_date, run_name, units: list[SearchUnit], max_results, fresh, log) -> None:
    """Run a fixed list of search units (pilot, single location, state cross-check)."""
    s = Searcher(cfg, snapshot_date, log)
    if fresh:
        for u in units:
            for p in list(s.page_dir(u).glob("*.json")) + [s.manifest_path(u)]:
                p.unlink(missing_ok=True)
    seen: set[str] = set()
    for u in units:
        log.info("Search %s | location=%r radius_km=%s", u.search_id, u.query_location, u.query_radius_km)
        s.paginate(u, max_results=max_results, already_seen=seen)
    write_json_atomic(run_manifest_path(cfg, snapshot_date, run_name),
                      {"run_name": run_name, "kind": "simple", "max_results": max_results,
                       "search_ids": [u.search_id for u in units]})
    log.info("Requests made this invocation: %d", s.requests_made)
    build_run_outputs(cfg, snapshot_date, run_name, log)


def paginate_with_retry(s: "Searcher", u: SearchUnit, log, max_retries: int = 2) -> dict:
    """Paginate a unit; if it fails the completeness check, re-fetch ONLY that unit.

    A unit still incomplete after max_retries keeps status "incomplete" (it is
    reported by the merge step, never silently accepted).
    """
    m = s.paginate(u)
    attempt = 0
    while m["status"] == "incomplete" and attempt < max_retries:
        attempt += 1
        log.warning("%s INCOMPLETE (reported %s->%s, counts changed=%s, unique=%s); retry %d/%d",
                    u.search_id, m["reported_count_first"], m["reported_count_last"],
                    m["reported_counts_changed"], m["unique_postings"], attempt, max_retries)
        for p in s.page_dir(u).glob("page_*.json"):
            p.unlink()
        m = s.paginate(u)
    if attempt:
        m = s.write_manifest(u, **{k: v for k, v in m.items()
                                   if k not in ("search_unit", "snapshot_date", "updated_at")},
                             retries=attempt)
        log.info("%s after %d retr%s: %s", u.search_id, attempt, "y" if attempt == 1 else "ies", m["status"])
    return m


def run_national(cfg, snapshot_date, plan_only: bool, log) -> None:
    """Adaptive grid: probe each circle, split dense ones, paginate the rest.

    Deterministic: the same counts produce the same plan. Resumable: saved
    pages are reused, so a re-run walks the same tree without re-fetching.
    """
    nat = cfg["national"]
    s = Searcher(cfg, snapshot_date, log)
    queue = geo_grid.root_units(cfg)
    visited: dict[str, dict] = {}
    log.info("National grid: %d root circles; plan_only=%s", len(queue), plan_only)
    while queue:
        u = queue.pop(0)
        if u.search_id in visited:
            continue
        info = s.probe(u)
        kids = geo_grid.children(cfg, u)
        too_big = info["count"] > nat["split_if_count_over"] or info["facet_addresses"] >= nat["facet_address_cap"]
        if info["count"] == 0:
            visited[u.search_id] = s.write_manifest(u, status="empty", **info)
        elif info["facet_us_addresses"] == 0 and info["facet_addresses"] < nat["facet_address_cap"]:
            # Every result is outside the U.S. (Canada/Mexico/ocean edge).
            visited[u.search_id] = s.write_manifest(u, status="no_us_results", **info)
        elif too_big and kids:
            visited[u.search_id] = s.write_manifest(u, status="split", children=[k.search_id for k in kids], **info)
            queue.extend(k for k in kids if k.search_id not in visited)
        elif plan_only:
            visited[u.search_id] = {**info, "status": "planned_leaf"}
        else:
            visited[u.search_id] = paginate_with_retry(s, u, log)
        log.info("%s r=%skm count=%s addr=%s -> %s (queue %d, requests %d)", u.search_id, u.query_radius_km,
                 info["count"], info["facet_addresses"], visited[u.search_id]["status"], len(queue), s.requests_made)

    # Completeness cross-check: server total for the whole U.S. (1 request).
    national = s.probe(SearchUnit("national_count", nat.get("count_query", "United States")))
    log.info("Server-reported national count (location='United States', onsite): %s", national["count"])

    run_name = nat["run_name"] if not plan_only else nat["run_name"] + "_plan"
    retried = {k: v.get("retries", 0) for k, v in visited.items() if v.get("retries")}
    write_json_atomic(run_manifest_path(cfg, snapshot_date, run_name),
                      {"run_name": run_name, "kind": "national_grid", "plan_only": plan_only,
                       "national_count": national["count"], "retried_searches": retried,
                       "requests_this_invocation": s.requests_made,
                       "search_ids": list(visited),
                       "status_counts": pd.Series([v["status"] for v in visited.values()]).value_counts().to_dict()})
    leaves = [v for v in visited.values() if v["status"] in ("planned_leaf", "complete", "incomplete")]
    est_pages = sum(max(1, -(-v.get("count", v.get("reported_count_first", 0)) // 10)) for v in leaves)
    log.info("Searches visited: %d | leaves: %d | estimated leaf pages: %d | requests this invocation: %d",
             len(visited), len(leaves), est_pages, s.requests_made)
    if not plan_only:
        build_run_outputs(cfg, snapshot_date, run_name, log)


# --------------------------------------------------------------------------- #
# Run outputs: raw rows, discovery table, coordinates
# --------------------------------------------------------------------------- #

def build_run_outputs(cfg: dict, snapshot_date: str, run_name: str, log) -> Path:
    """Flatten a run's saved pages into raw tables (no parsing, no cleaning).

    data/raw/<date>/<run>.csv              one row per (search, posting) discovery,
                                           with the full original record in raw_json
    data/raw/<date>/<run>_discoveries.csv  job_id, position_id, search_id, snapshot_date
    data/raw/<date>/<run>_latlong.csv      address -> lat/long from the map facet
    """
    rm = read_json(run_manifest_path(cfg, snapshot_date, run_name))
    max_results = rm.get("max_results")
    sdir = searches_dir(cfg, snapshot_date)
    rows, latlong, seen = [], {}, set()
    for sid in rm["search_ids"]:
        man_path = sdir / f"{sid}.json"
        unit = read_json(man_path)["search_unit"] if man_path.exists() else {"search_id": sid}
        seen_here = set()
        for p in sorted((sdir / sid).glob("page_*.json")):
            rec = read_json(p)
            latlong.update(facet_addresses(rec))
            for pos in positions_of(rec):
                pid = str(pos.get("id"))
                if pid in seen_here:
                    continue                      # same posting twice in one search (drift)
                if pid not in seen and max_results is not None and len(seen) >= max_results:
                    continue                      # pilot cap
                seen_here.add(pid)
                seen.add(pid)
                rows.append({
                    "snapshot_date": snapshot_date,
                    "run_name": run_name,
                    "search_id": sid,
                    "query_location": unit.get("query_location"),
                    "query_latitude": unit.get("query_latitude"),
                    "query_longitude": unit.get("query_longitude"),
                    "query_radius_km": unit.get("query_radius_km"),
                    "page_start": rec["request"]["start"],
                    "fetched_at": rec["fetched_at"],
                    "position_id": pid,
                    "display_job_id": pos.get("displayJobId"),
                    "ats_job_id": pos.get("atsJobId"),
                    "name": pos.get("name"),
                    "department": pos.get("department"),
                    "locations": json.dumps(pos.get("locations"), ensure_ascii=False),
                    "standardized_locations": json.dumps(pos.get("standardizedLocations"), ensure_ascii=False),
                    "posted_ts": pos.get("postedTs"),
                    "creation_ts": pos.get("creationTs"),
                    "work_location_option": pos.get("workLocationOption"),
                    "position_url": pos.get("positionUrl"),
                    "raw_json": json.dumps(pos, ensure_ascii=False),
                })

    out_dir = raw_dir(cfg, snapshot_date)
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / f"{run_name}.csv", index=False)
    if len(df):
        df[["display_job_id", "position_id", "search_id", "snapshot_date", "page_start"]].rename(
            columns={"display_job_id": "job_id"}).to_csv(out_dir / f"{run_name}_discoveries.csv", index=False)
    pd.DataFrame([{"location_key": k, "latlong": v} for k, v in sorted(latlong.items())]).to_csv(
        out_dir / f"{run_name}_latlong.csv", index=False)
    log.info("Wrote %d discovery rows (%d unique postings, %d searches) -> %s",
             len(df), len(seen), len(rm["search_ids"]), out_dir / f"{run_name}.csv")
    log.info("Wrote %d address->lat/long pairs", len(latlong))
    return out_dir / f"{run_name}.csv"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--pilot", action="store_true", help="the `pilot` search unit in config.yaml")
    target.add_argument("--point", help="coordinate search 'LAT,LON' (use with --radius-km)")
    target.add_argument("--location", help='free-text location, e.g. "New York, NY"')
    target.add_argument("--state", help="free-text state search from config `states` (cross-check only)")
    target.add_argument("--national", action="store_true", help="adaptive national grid (requires --confirm)")
    ap.add_argument("--radius-km", type=float, help="search radius in km (default: search.default_radius_km)")
    ap.add_argument("--max-results", type=int, help="stop after this many unique postings")
    ap.add_argument("--run-name", help="output file stem")
    ap.add_argument("--plan-only", action="store_true", help="national: probe page 0 of each circle only")
    ap.add_argument("--confirm", action="store_true", help="required for --national")
    ap.add_argument("--snapshot-date", default=today_str(), help="YYYY-MM-DD (pass the original date to resume)")
    ap.add_argument("--delay", type=float, help="override request.delay_seconds")
    ap.add_argument("--config", help="path to config.yaml")
    ap.add_argument("--fresh", action="store_true", help="discard saved pages for these searches first")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.delay is not None:
        cfg["request"]["delay_seconds"] = args.delay
    radius = args.radius_km or cfg["search"]["default_radius_km"]

    if args.national:
        if not args.confirm:
            raise SystemExit("--national needs --confirm (it issues thousands of requests; see README).")
        log = setup_logging(cfg, f"scrape_{args.snapshot_date}_national")
        run_national(cfg, args.snapshot_date, args.plan_only, log)
        return

    max_results = args.max_results
    if args.pilot:
        pc = cfg["pilot"]
        units = [SearchUnit.point(pc["search_id"], pc["latitude"], pc["longitude"], pc["radius_km"])]
        run_name = args.run_name or pc["run_name"]
        max_results = max_results or pc["max_results"]
    elif args.point:
        lat, lon = (float(x) for x in args.point.split(","))
        sid = f"point_{lat:.4f}_{lon:.4f}_{int(radius)}km".replace("-", "m").replace(".", "p")
        units = [SearchUnit.point(sid, lat, lon, radius)]
        run_name = args.run_name or sid
    elif args.location:
        units = [SearchUnit(f"text_{slug(args.location)}_{int(radius)}km", args.location, None, None, radius)]
        run_name = args.run_name or units[0].search_id
    else:
        st = args.state.upper()
        if st not in cfg["states"]:
            raise SystemExit(f"Unknown state code {args.state!r}; see `states` in config.yaml")
        units = [SearchUnit(f"state_{st}", cfg["states"][st])]   # no radius: region match
        run_name = args.run_name or f"state_{st}"

    log = setup_logging(cfg, f"scrape_{args.snapshot_date}_{run_name}")
    run_simple(cfg, args.snapshot_date, run_name, units, max_results, args.fresh, log)


if __name__ == "__main__":
    main()
