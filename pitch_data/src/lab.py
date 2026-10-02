"""Shared loaders and geometry for the labor-productivity study.

Reads (never writes) the existing projects in ../_research_archive/:
  starbucks_operating_data  - Advan weekly patterns (Starbucks + Dunkin') via Dewey
  starbucks_store_universe  - Starbucks store locator (company-operated vs licensed) + hiring-store join
  starbucks_hiring          - national careers snapshot (2026-10-01) and per-store role patterns
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

LAB = Path(__file__).resolve().parent.parent
ARCH = LAB.parent / "_research_archive"
OPS = ARCH / "starbucks_operating_data"
UNIV = ARCH / "starbucks_store_universe"
HIRE = ARCH / "starbucks_hiring"
SNAPSHOT = "2026-10-01"
sys.path.insert(0, str(HIRE / "src"))

ADVAN_COLS = ["ID_STORE", "BRAND", "ISO_COUNTRY_CODE", "VISIT_COUNTS", "DATE_RANGE_START", "LATITUDE", "LONGITUDE",
              "MSA_CODE", "OPEN_DATE", "CLOSE_DATE", "STREET_ADDRESS", "CITY", "REGION"]


def load_advan(brand: str) -> pd.DataFrame:
    """U.S. weekly rows for one brand ("Starbucks" or "Dunkin") from the raw Dewey parquet files."""
    folder = OPS / ("data/raw/advan" if brand == "Starbucks" else "data/raw/advan_competitors")
    frames = []
    for f in sorted(folder.glob("*.parquet")):
        d = pd.read_parquet(f, columns=ADVAN_COLS)
        frames.append(d[(d["ISO_COUNTRY_CODE"] == "US") & d["BRAND"].fillna("").str.contains(brand, case=False)])
    d = pd.concat(frames, ignore_index=True)
    d["week"] = pd.to_datetime(d["DATE_RANGE_START"].astype(str).str[:10])
    d["visits"] = pd.to_numeric(d["VISIT_COUNTS"], errors="coerce")
    return d


def locations(d: pd.DataFrame) -> pd.DataFrame:
    """One row per Advan location: last-known attributes, first/last week, open/close dates (placeholders -> NaT)."""
    last = d.sort_values("week").groupby("ID_STORE").agg(
        lat=("LATITUDE", "last"), lon=("LONGITUDE", "last"), msa=("MSA_CODE", "last"),
        address=("STREET_ADDRESS", "last"), city=("CITY", "last"), state=("REGION", "last"),
        open_date=("OPEN_DATE", "last"), close_date=("CLOSE_DATE", "last"),
        first_week=("week", "min"), last_week=("week", "max")).reset_index()
    last[["lat", "lon"]] = last[["lat", "lon"]].astype(float)
    for c in ("open_date", "close_date"):
        x = pd.to_datetime(last[c].astype(str).str[:10], errors="coerce")
        last[c] = x.where((x > "1971-01-01") & (x < "2037-01-01"))
    return last


def km_matrix(a_lat, a_lon, b_lat, b_lon):
    la, lo = np.radians(np.asarray(a_lat))[:, None], np.radians(np.asarray(a_lon))[:, None]
    pa, po = np.radians(np.asarray(b_lat))[None, :], np.radians(np.asarray(b_lon))[None, :]
    h = np.sin((pa - la) / 2) ** 2 + np.cos(la) * np.cos(pa) * np.sin((po - lo) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def count_within(a_lat, a_lon, b_lat, b_lon, radii=(1, 2, 5), exclude_self=False, chunk=2000):
    """Counts of points b within each radius (km) of every point a; also nearest distance."""
    out = {r: [] for r in radii}
    near = []
    for i in range(0, len(a_lat), chunk):
        d = km_matrix(a_lat[i:i + chunk], a_lon[i:i + chunk], b_lat, b_lon)
        if exclude_self:
            d = np.where(d < 1e-6, np.inf, d)
        for r in radii:
            out[r].append((d <= r).sum(axis=1))
        near.append(d.min(axis=1) if d.shape[1] else np.full(d.shape[0], np.inf))
    return {r: np.concatenate(v) for r, v in out.items()}, np.concatenate(near)


def nearest_match(src_lat, src_lon, dst: pd.DataFrame, max_m: float = 75) -> np.ndarray:
    """Index into dst of the nearest point within max_m metres, else -1 (grid index)."""
    cell = 0.01
    grid: dict[tuple, list[int]] = {}
    dl, dn = dst["latitude"].to_numpy(float), dst["longitude"].to_numpy(float)
    for i, (a, b) in enumerate(zip(dl, dn)):
        grid.setdefault((int(a // cell), int(b // cell)), []).append(i)
    res = np.full(len(src_lat), -1)
    for k, (a, b) in enumerate(zip(src_lat, src_lon)):
        best, bd = -1, float("inf")
        gi, gj = int(a // cell), int(b // cell)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for i in grid.get((gi + di, gj + dj), []):
                    d = math.hypot((dl[i] - a) * 111_195, (dn[i] - b) * 111_195 * math.cos(math.radians(a)))
                    if d < bd:
                        best, bd = i, d
        res[k] = best if bd <= max_m else -1
    return res


def parse_hours(oh) -> dict:
    """OSM opening_hours 'Mo-Fr 04:30-21:00; Sa-Su 05:00-21:00' -> {day: (open, close)} in hours."""
    days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    if not isinstance(oh, str) or not oh.strip():
        return {}
    if oh.strip() == "24/7":
        return {d: (0.0, 24.0) for d in days}
    res = {}
    import re
    for rule in oh.split(";"):
        m = re.match(r"\s*([A-Za-z,\-]+)\s+(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})\s*$", rule)
        if not m:
            continue
        o, c = int(m.group(2)) + int(m.group(3)) / 60, int(m.group(4)) + int(m.group(5)) / 60
        if c <= o:
            c += 24
        for part in m.group(1).split(","):
            if "-" in part:
                a, b = part.split("-")
                if a in days and b in days:
                    i, j = days.index(a), days.index(b)
                    for dd in (days[i:j + 1] if i <= j else days[i:] + days[:j + 1]):
                        res[dd] = (o, c)
            elif part in days:
                res[part] = (o, c)
    return res


def weekly_hours(oh) -> float | None:
    h = parse_hours(oh)
    return round(sum(c - o for o, c in h.values()), 2) if h else None


def save_json(obj, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str))
