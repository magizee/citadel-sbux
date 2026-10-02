"""Turn a run's raw discovery rows into cleaned, deduplicated postings.

Reads only what scrape_jobs.py saved (no network access), so parsing rules can
be changed and re-run at any time.

    python src/clean_jobs.py                                  # pilot
    python src/clean_jobs.py --run-name state_CA --snapshot-date 2026-10-01

Input : data/raw/<date>/<run>.csv (one row per search x posting discovery)
Output: data/processed/<date>/<run>_clean.csv (one row per posting)
        data/processed/<date>/store_summary.csv (pilot) or <run>_store_summary.csv

A posting found by several searches becomes one row, keyed by job_id, with
`search_ids` listing every search that found it. Its state comes from its own
address, never from the search that found it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re

import pandas as pd

from common import haversine_km, load_config, processed_dir, raw_dir, today_str

CLEAN_COLUMNS = [
    "snapshot_date", "job_id", "job_url", "job_title_raw", "role_bucket",
    "store_number", "store_name", "street_address", "city", "state",
    "postal_code", "country", "posted_text", "posted_ts_raw", "posted_date",
    "days_since_posted", "latitude", "longitude",
    # Provenance / helper columns
    "position_id", "dedup_key", "store_key", "department", "work_location_option",
    "location_raw", "n_locations", "all_states", "search_ids", "n_searches",
]

# --------------------------------------------------------------------------- #
# Title parsing
# --------------------------------------------------------------------------- #

# Standard form: "barista - Store# 09230, DTLA GRAND PARK" -> role="barista",
# number="09230", name="DTLA GRAND PARK". Tolerates "Store #", "Store#09230"
# and a missing comma.
STORE_RE = re.compile(
    r"^(?P<role>.*?)\s*[-–]\s*store\s*#\s*(?P<num>\d+)\s*,?\s*(?P<name>.*)$",
    re.IGNORECASE,
)
# Variant with the store number mid-title (Reserve / Roastery formats):
# "barista, Main Bar - Empire State Building, Store# 57845, New York"
STORE_ANYWHERE_RE = re.compile(r"store\s*#\s*(?P<num>\d+)", re.IGNORECASE)


def parse_title(title: str) -> tuple[str, str | None, str | None]:
    """Return (role_text, store_number, store_name). Store number stays a string."""
    title = (title or "").strip()
    m = STORE_RE.match(title)
    if m and "," not in m.group("role"):
        return m.group("role").strip(), m.group("num"), (m.group("name").strip() or None)
    m = STORE_ANYWHERE_RE.search(title)
    if not m:
        return title, None, None
    # Role = text before the first comma/dash; store name = the segment just
    # before "Store#" (e.g. "Empire State Building").
    before = title[: m.start()].rstrip(" ,-–")
    role = re.split(r"\s*[,–-]\s*", before, maxsplit=1)[0]
    name = re.split(r"\s+[-–]\s+|,\s*", before)[-1].strip() if before else None
    return role.strip(), m.group("num"), (name or None)


# Order matters: more specific titles are tested first.
ROLE_RULES = [
    ("DISTRICT_MANAGER", ["district manager", "district leader"]),
    ("STORE_MANAGER", ["assistant store manager", "store manager", "coffeehouse leader", "store leader"]),
    ("SHIFT_SUPERVISOR", ["shift supervisor", "shift manager"]),
    ("BARISTA", ["barista"]),
]

# Other in-store hourly roles, mostly at Reserve Roasteries / Reserve stores.
OTHER_RETAIL_TITLES = ["mixologist", "operations lead", "baker", "porter", "coffeehouse coach"]

# Job functions (the API's `department`) that indicate store/field retail work
# even when the title has no store number.
RETAIL_DEPARTMENTS = {
    "barista", "siren barista", "shift supervisor", "shift manager", "coffeehouse leader",
    "coffeehouse coach", "store manager", "assistant store manager", "district manager",
    "mixologist", "operations lead", "baker", "porter", "kitchen facilities",
}


def role_bucket(title: str, department: str | None, store_number: str | None) -> str:
    """Bucket a job title into one of the fixed role categories.

    Note: "shift manager" is a newer Starbucks title for the shift-lead role and
    is grouped with SHIFT_SUPERVISOR.
    """
    t = (title or "").lower()
    for bucket, needles in ROLE_RULES:
        if any(n in t for n in needles):
            return bucket
    dept = department.strip().lower() if isinstance(department, str) else ""
    title_is_store_role = any(t.startswith(n) for n in OTHER_RETAIL_TITLES)
    if store_number or title_is_store_role or dept in RETAIL_DEPARTMENTS:
        return "OTHER_RETAIL"
    return "NON_RETAIL"


# --------------------------------------------------------------------------- #
# Location parsing
# --------------------------------------------------------------------------- #

STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "puerto rico": "PR",
}
COUNTRY_CODES = {"united states": "US", "canada": "CA"}


def parse_location(raw_loc: str | None, std_loc: str | None = None) -> dict:
    """Split a location into street/city/state/country.

    raw_loc: "38 Park Row, #4, New York, New York, United States"
             i.e. [street pieces..., city, state name, country]
    std_loc: "New York, NY, US" or just "NY,US". The site often omits the city
             here (e.g. Brooklyn stores), so the raw string is the primary
             source and std_loc only fills gaps.

    postal_code is always None: the site does not expose ZIP codes, and
    5-digit street numbers make guessing from the address unsafe.
    """
    out = {"street_address": None, "city": None, "state": None, "postal_code": None, "country": None}
    parts = [s.strip() for s in (raw_loc or "").split(",") if s.strip()]
    if parts:
        out["country"] = COUNTRY_CODES.get(parts[-1].lower(), parts[-1])
    if len(parts) >= 2:
        out["state"] = STATE_CODES.get(parts[-2].lower())
    if len(parts) >= 3:
        out["city"] = parts[-3]
    if len(parts) >= 4:
        out["street_address"] = ", ".join(parts[:-3])

    std = [s.strip() for s in (std_loc or "").split(",") if s.strip()]
    if len(std) >= 2 and not out["state"]:
        out["state"] = std[-2]
    if len(std) >= 3 and not out["city"]:
        out["city"] = std[-3]
    return out


def _norm_addr(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).lower()).strip()


def load_latlong(path) -> dict[str, tuple[float, float]]:
    """Map normalised raw address -> (lat, lon) from the search response's map facet."""
    try:
        df = pd.read_csv(path, dtype=str)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return {}
    out = {}
    for key, ll in zip(df["location_key"], df["latlong"]):
        try:
            lat, lon = (float(x) for x in str(ll).split(","))
        except ValueError:
            continue
        out[_norm_addr(key)] = (lat, lon)
    return out


def choose_location(locs: list, stds: list, latlong: dict, centres: list[tuple]) -> int:
    """Index of a posting's primary location.

    Store jobs have one location. For multi-location jobs (regional/corporate
    roles) pick the location nearest the centre of any search that found the
    job; ties and jobs without coordinates fall back to the first listed
    location. The rule is deterministic, so the national merge and the pilot
    pick the same way.
    """
    if len(locs) <= 1 or not centres:
        return 0
    best, best_key = 0, None
    for i, loc in enumerate(locs):
        ll = latlong.get(_norm_addr(loc))
        d = min(haversine_km(c[0], c[1], ll[0], ll[1]) for c in centres) if ll else float("inf")
        key = (round(d), i)
        if best_key is None or key < best_key:
            best, best_key = i, key
    return best


# --------------------------------------------------------------------------- #
# Posting dates
# --------------------------------------------------------------------------- #

def posting_dates(posted_ts, snapshot: dt.date):
    """Canonical posting date = backend postedTs (Unix seconds, UTC date)."""
    if pd.isna(posted_ts) or not str(posted_ts).strip():
        return None, None
    d = dt.datetime.fromtimestamp(int(float(posted_ts)), dt.timezone.utc).date()
    return d, (snapshot - d).days


REL_RE = re.compile(
    r"(?P<n>\d+|an?|one)\+?\s*(?P<unit>minute|hour|day|week|month|year)s?\s+ago", re.IGNORECASE
)
UNIT_DAYS = {"minute": 0, "hour": 0, "day": 1, "week": 7, "month": 30, "year": 365}


def parse_relative_age(text: str | None, snapshot: dt.date) -> tuple[dt.date | None, int | None]:
    """VALIDATION ONLY: convert "7 days ago" / "a month ago" text to an estimate.

    Never used for posted_date (the backend timestamp is canonical). Kept so a
    human-readable `posted_text`, if one is ever captured, can be compared
    against posted_ts.
    """
    if not text:
        return None, None
    t = text.strip().lower()
    if t in {"today", "just now", "just posted"}:
        return snapshot, 0
    if t == "yesterday":
        return snapshot - dt.timedelta(days=1), 1
    m = REL_RE.search(t)
    if not m:
        return None, None
    n = m.group("n")
    n = 1 if n in {"a", "an", "one"} else int(n)
    unit = m.group("unit")
    days = n // 24 if unit == "hour" else n * UNIT_DAYS[unit]
    return snapshot - dt.timedelta(days=days), days


# --------------------------------------------------------------------------- #
# Cleaning
# --------------------------------------------------------------------------- #

def dedup_key(job_id, title, store_no, loc_raw) -> str:
    """job_id when available, else a stable title + store + location key."""
    if job_id:
        return f"id:{job_id}"
    return f"fb:{(title or '').lower()}|{store_no or ''}|{(loc_raw or '').lower()}"


def clean_raw(raw: pd.DataFrame, latlong: dict, job_url_base: str) -> pd.DataFrame:
    """Collapse discovery rows (search x posting) into one cleaned row per posting."""
    raw = raw.copy()
    raw["_job_id"] = raw["display_job_id"].where(raw["display_job_id"].notna(), None)
    rows = []
    for _, grp in raw.groupby(raw["position_id"], sort=False):
        r = grp.iloc[0]
        snapshot = dt.date.fromisoformat(r.snapshot_date)
        locs = json.loads(r.locations) if isinstance(r.locations, str) else []
        stds = json.loads(r.standardized_locations) if isinstance(r.standardized_locations, str) else []
        stds = list(stds) + [None] * (len(locs) - len(stds))
        centres = [(float(a), float(b)) for a, b in zip(grp.query_latitude, grp.query_longitude)
                   if pd.notna(a) and pd.notna(b)]
        i = choose_location(locs, stds, latlong, centres)
        loc_raw = locs[i] if locs else None
        loc = parse_location(loc_raw, stds[i] if stds else None)
        all_states = sorted({s for s in (parse_location(l, sd)["state"] for l, sd in zip(locs, stds)) if s})
        role_text, store_no, store_name = parse_title(r["name"])
        posted_date, days_since = posting_dates(r.posted_ts, snapshot)
        lat, lon = latlong.get(_norm_addr(loc_raw), (None, None)) if loc_raw else (None, None)
        job_id = str(r._job_id) if r._job_id else None
        # Store-level join key: store number when present; otherwise the
        # normalised street address (e.g. Reserve Roasteries, which carry no
        # store number). Never an invented store number.
        if store_no:
            store_key = f"store:{store_no}"
        elif loc["street_address"]:
            store_key = f"addr:{_norm_addr(loc['street_address'])}|{_norm_addr(loc['city'])}|{loc['state']}"
        else:
            store_key = None

        rows.append({
            "snapshot_date": r.snapshot_date,
            "job_id": job_id,
            "job_url": job_url_base + r.position_url if isinstance(r.position_url, str) else None,
            "job_title_raw": r["name"],
            "role_bucket": role_bucket(role_text, r.department, store_no),
            "store_number": store_no,
            "store_name": store_name,
            **loc,
            "posted_text": None,          # not exposed by the API (rendered client-side)
            "posted_ts_raw": r.posted_ts,
            "posted_date": posted_date.isoformat() if posted_date else None,
            "days_since_posted": days_since,
            "latitude": lat,
            "longitude": lon,
            "position_id": r.position_id,
            "dedup_key": dedup_key(job_id, r["name"], store_no, loc_raw),
            "store_key": store_key,
            "department": r.department,
            "work_location_option": r.work_location_option,
            "location_raw": loc_raw,
            "n_locations": len(locs),
            "all_states": ";".join(all_states),
            "search_ids": ";".join(sorted(set(grp.search_id))),
            "n_searches": grp.search_id.nunique(),
        })
    df = pd.DataFrame(rows, columns=CLEAN_COLUMNS)
    df["days_since_posted"] = df["days_since_posted"].astype("Int64")
    # Different position_ids can share a job_id (re-posted requisitions):
    # keep one row per dedup_key.
    return df.drop_duplicates(subset="dedup_key", keep="first").reset_index(drop=True)


SUMMARY_COLUMNS = [
    "store_number", "store_name", "city", "state", "active_postings", "barista_postings",
    "shift_supervisor_postings", "store_manager_postings", "district_manager_postings",
    "median_days_since_posted", "max_days_since_posted",
]


def store_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per store number with posting counts by role and posting age."""
    stores = df[df["store_number"].notna()].copy()
    if stores.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    stores["days"] = stores["days_since_posted"].astype("float")

    def count(bucket):
        return lambda s: int((s == bucket).sum())

    out = stores.groupby("store_number").agg(
        store_name=("store_name", "first"),
        city=("city", "first"),
        state=("state", "first"),
        active_postings=("dedup_key", "nunique"),
        barista_postings=("role_bucket", count("BARISTA")),
        shift_supervisor_postings=("role_bucket", count("SHIFT_SUPERVISOR")),
        store_manager_postings=("role_bucket", count("STORE_MANAGER")),
        district_manager_postings=("role_bucket", count("DISTRICT_MANAGER")),
        median_days_since_posted=("days", "median"),
        max_days_since_posted=("days", "max"),
    ).reset_index()
    return out[SUMMARY_COLUMNS].sort_values("store_number").reset_index(drop=True)


def read_raw(cfg: dict, snapshot_date: str, run_name: str) -> tuple[pd.DataFrame, dict]:
    rdir = raw_dir(cfg, snapshot_date)
    # dtype=str keeps IDs and leading zeros intact.
    raw = pd.read_csv(rdir / f"{run_name}.csv", dtype=str, keep_default_na=False, na_values=[""])
    return raw, load_latlong(rdir / f"{run_name}_latlong.csv")


def clean_run(cfg: dict, snapshot_date: str, run_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw, latlong = read_raw(cfg, snapshot_date, run_name)
    clean = clean_raw(raw, latlong, cfg["api"]["job_url_base"])
    summary = store_summary(clean)

    out_dir = processed_dir(cfg, snapshot_date)
    out_dir.mkdir(parents=True, exist_ok=True)
    clean.to_csv(out_dir / f"{run_name}_clean.csv", index=False)
    summary_name = (cfg["pilot"]["store_summary_filename"] if run_name == cfg["pilot"]["run_name"]
                    else f"{run_name}_store_summary.csv")
    summary.to_csv(out_dir / summary_name, index=False)
    print(f"Cleaned {len(raw)} discovery rows -> {len(clean)} unique postings -> {out_dir / f'{run_name}_clean.csv'}")
    print(f"Store summary: {len(summary)} stores -> {out_dir / summary_name}")
    return clean, summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-name", default=None, help="raw file stem (default: pilot.run_name)")
    ap.add_argument("--snapshot-date", default=today_str())
    ap.add_argument("--config")
    args = ap.parse_args()
    cfg = load_config(args.config)
    clean_run(cfg, args.snapshot_date, args.run_name or cfg["pilot"]["run_name"])


if __name__ == "__main__":
    main()
