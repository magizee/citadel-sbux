"""Build the U.S. Starbucks store universe and join it to the hiring data.

    python src/build_universe.py                       # clean + join to the NYC pilot
    python src/build_universe.py --hiring ../starbucks_hiring/data/processed/2026-10-01/starbucks_jobs_US.csv

Source: All the Places (alltheplaces.xyz) spider `starbucks_us`, run 2026-09-26..29, which
collects Starbucks' own store-locator API (starbucks.com/apiproxy/v1/locations).

The locator's `ref` is an internal location ID, not the 5-digit store number shown in job
titles, so stores are joined to hiring data by coordinates (nearest universe store within
MAX_M metres), with branch-name similarity reported as a check.

Outputs:
    data/processed/starbucks_store_universe.csv   one row per location (company-operated and licensed, flagged)
    data/processed/hiring_store_join.csv          one row per hiring store_key with its matched location
"""

from __future__ import annotations

import argparse
import json
import math
import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/starbucks_us_alltheplaces_2026-09-26.geojson"
MAX_M = 75          # coordinate fallback radius (address match is tried first)
NUM_WORDS = {"first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th", "fifth": "5th", "sixth": "6th",
             "seventh": "7th", "eighth": "8th", "ninth": "9th", "tenth": "10th"}


def build_universe() -> pd.DataFrame:
    fs = json.loads(RAW.read_text())["features"]
    rows = []
    for f in fs:
        p, g = f["properties"], f.get("geometry") or {}
        lon, lat = (g.get("coordinates") or [None, None])[:2]
        rows.append({
            "locator_id": p.get("ref"),
            "store_name": p.get("branch"),
            "address": p.get("addr:street_address"),
            "city": p.get("addr:city"),
            "state": p.get("addr:state"),
            "postal_code": p.get("addr:postcode"),
            "latitude": lat,
            "longitude": lon,
            "ownership_type": p.get("ownership_type"),
            "company_operated": p.get("ownership_type") == "CO",
            "located_in": p.get("located_in"),
            "opening_hours": p.get("opening_hours"),
            "source": "alltheplaces starbucks_us 2026-09-26 (Starbucks store locator)",
        })
    df = pd.DataFrame(rows).drop_duplicates("locator_id")
    df.to_csv(ROOT / "data/processed/starbucks_store_universe.csv", index=False)
    return df


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", str(s).lower()).strip()


def addr_key(address, state) -> str | None:
    """'125 Chambers St' + NY -> 'NY|125|chambers'. House number + first street word."""
    words = [NUM_WORDS.get(w, w) for w in _norm(address).split()]
    words = [w for w in words if w not in {"n", "s", "e", "w", "north", "south", "east", "west"}]
    if len(words) < 2 or not words[0][0].isdigit():
        return None
    return f"{state}|{words[0].split('-')[0]}|{words[1]}"


def join_hiring(universe: pd.DataFrame, hiring_csv: str) -> pd.DataFrame:
    """Nearest universe location for each hiring store_key (equirectangular distance on a grid index)."""
    h = pd.read_csv(hiring_csv, dtype={"store_number": str})
    h = h[(h["role_bucket"] != "NON_RETAIL") & h["store_key"].notna() & h["latitude"].notna()]
    stores = h.groupby("store_key").agg(store_number=("store_number", "first"), store_name=("store_name", "first"),
                                        street_address=("street_address", "first"), city=("city", "first"),
                                        state=("state", "first"), latitude=("latitude", "first"),
                                        longitude=("longitude", "first")).reset_index()
    u = universe.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    cell = 0.01  # ~1 km grid buckets
    grid: dict[tuple, list[int]] = {}
    for i, (la, lo) in enumerate(zip(u["latitude"], u["longitude"])):
        grid.setdefault((int(la // cell), int(lo // cell)), []).append(i)
    by_addr: dict[str, list[int]] = {}
    for i, (a, st) in enumerate(zip(u["address"], u["state"])):
        k = addr_key(a, st)
        if k:
            by_addr.setdefault(k, []).append(i)
    out = []
    for _, s in stores.iterrows():
        gi, gj = int(s.latitude // cell), int(s.longitude // cell)
        best, best_d = None, float("inf")
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for i in grid.get((gi + di, gj + dj), []):
                    dy = (u.at[i, "latitude"] - s.latitude) * 111_195
                    dx = (u.at[i, "longitude"] - s.longitude) * 111_195 * math.cos(math.radians(s.latitude))
                    d = math.hypot(dx, dy)
                    if d < best_d:
                        best, best_d = i, d
        method = "coordinates" if best is not None and best_d <= MAX_M else None
        # Prefer an exact address match (house number + street) when there is exactly one.
        cand = by_addr.get(addr_key(s.street_address, s.state) or "", [])
        if len(cand) == 1:
            best, method = cand[0], "address"
            dy = (u.at[best, "latitude"] - s.latitude) * 111_195
            dx = (u.at[best, "longitude"] - s.longitude) * 111_195 * math.cos(math.radians(s.latitude))
            best_d = math.hypot(dx, dy)
        m = u.loc[best] if method else None
        out.append({**s.to_dict(),
                    "matched": m is not None,
                    "match_method": method,
                    "match_distance_m": round(best_d, 1) if m is not None else None,
                    "locator_id": m["locator_id"] if m is not None else None,
                    "universe_store_name": m["store_name"] if m is not None else None,
                    "universe_address": m["address"] if m is not None else None,
                    "ownership_type": m["ownership_type"] if m is not None else None,
                    "name_similarity": round(SequenceMatcher(None, _norm(s.store_name), _norm(m["store_name"])).ratio(), 2)
                    if m is not None and isinstance(s.store_name, str) else None,
                    "address_similarity": round(SequenceMatcher(None, _norm(s.street_address), _norm(m["address"])).ratio(), 2)
                    if m is not None else None})
    j = pd.DataFrame(out)
    # A coordinate-only match must also look like the same store (name or address).
    weak = (j["match_method"] == "coordinates") & (j["name_similarity"].fillna(0) < 0.6) & (j["address_similarity"].fillna(0) < 0.6)
    cols = ["locator_id", "universe_store_name", "universe_address", "ownership_type", "match_distance_m"]
    j.loc[weak, "match_method"] = "rejected_weak_coordinate_match"
    j.loc[weak, "matched"] = False
    j.loc[weak, cols] = None
    j.to_csv(ROOT / "data/processed/hiring_store_join.csv", index=False)
    return j


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hiring", default=str(ROOT.parent / "starbucks_hiring/data/processed/2026-10-01/pilot/pilot_jobs_clean.csv"))
    args = ap.parse_args()
    u = build_universe()
    print(f"universe: {len(u)} locations; ownership: {u['ownership_type'].value_counts().to_dict()}; "
          f"states: {u['state'].nunique()}; located_in set: {u['located_in'].notna().sum()}")
    j = join_hiring(u, args.hiring)
    print(f"hiring stores: {len(j)}; matched within {MAX_M} m: {j['matched'].sum()} ({100 * j['matched'].mean():.1f}%)")
    print("matched ownership:", j["ownership_type"].value_counts(dropna=False).to_dict())
    print("median match distance (m):", j["match_distance_m"].median(),
          "| name similarity median:", j["name_similarity"].median(), "| address similarity median:", j["address_similarity"].median())


if __name__ == "__main__":
    main()
