"""Shared helpers: config, paths, logging, search units, geometry."""

from __future__ import annotations

import datetime as dt
import logging
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

# starbucks_hiring/ (the folder that contains src/, config/, data/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "config.yaml"


def load_config(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT_CONFIG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def today_str() -> str:
    """Snapshot date in local time, YYYY-MM-DD."""
    return dt.date.today().isoformat()


def resolve(cfg_path: str) -> Path:
    """Resolve a config path relative to the project root."""
    p = Path(cfg_path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def raw_dir(cfg: dict, snapshot_date: str) -> Path:
    return resolve(cfg["output"]["raw_dir"]) / snapshot_date


def processed_dir(cfg: dict, snapshot_date: str) -> Path:
    return resolve(cfg["output"]["processed_dir"]) / snapshot_date


def searches_dir(cfg: dict, snapshot_date: str) -> Path:
    """data/raw/<date>/searches/: one manifest + one page folder per search unit."""
    return raw_dir(cfg, snapshot_date) / "searches"


def setup_logging(cfg: dict, name: str) -> logging.Logger:
    """Log to console and to logs/<name>.log (appending, so resumed runs share a log)."""
    log_dir = resolve(cfg["output"]["log_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(log_dir / f"{name}.log")):
        h.setFormatter(fmt)
        logger.addHandler(h)
    return logger


# --------------------------------------------------------------------------- #
# Search units (collection geography)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class SearchUnit:
    """One geographic query against the search API.

    Either a coordinate search (latitude/longitude + radius_km, sent as
    location="lat,lon") or a free-text search (query_location, e.g. a state
    name). search_id must be unique and filesystem-safe.
    """
    search_id: str
    query_location: str
    query_latitude: float | None = None
    query_longitude: float | None = None
    query_radius_km: float | None = None
    level: int | None = None          # grid level, for adaptive national runs

    @classmethod
    def point(cls, search_id: str, lat: float, lon: float, radius_km: float, level: int | None = None):
        return cls(search_id, f"{lat:.5f},{lon:.5f}", round(lat, 5), round(lon, 5), radius_km, level)

    def params(self, include_remote: bool) -> dict:
        """Query parameters (other than domain/start) for this unit."""
        p = {"location": self.query_location}
        if self.query_radius_km is not None:
            p["filter_distance"] = str(int(self.query_radius_km))
        p["filter_include_remote"] = "1" if include_remote else "0"
        return p

    def to_dict(self) -> dict:
        return asdict(self)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #

EARTH_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))
