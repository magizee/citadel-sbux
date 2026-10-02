"""Deterministic hexagonal search grids for the adaptive national collection.

Each grid level is a fixed hex lattice of circle centres with radius r and
centre spacing s = r * sqrt(3) * spacing_factor. With s <= r*sqrt(3), circles
on a hex lattice cover the plane with no gaps.

The lattice is built in a simple equirectangular projection whose east-west
scale is taken at the region's SOUTHERN edge (the widest latitude). Further
north, true east-west distances are smaller than projected ones, so true
distances are never larger than projected distances and planar coverage
implies true coverage (the circles just overlap more in the north).
`verify_coverage` checks this numerically with haversine distances.

Subdivision: the children of a parent circle (centre c, radius R) at the next
level are all lattice points within R + r of c. Every point of the parent is
within r of some lattice point, and that point is within R + r of c, so the
children always cover the parent. Children of neighbouring parents share
lattice points (same search_id), so each child is queried once.

    python src/geo_grid.py            # print level sizes and verify coverage
"""

from __future__ import annotations

import math
import random

from common import SearchUnit, haversine_km

KM_PER_DEG = 111.195


class Lattice:
    """Hex lattice of radius-r circles covering one region's bounding box."""

    def __init__(self, region: str, bbox: list[float], radius_km: float, level: int, spacing_factor: float):
        self.region, self.level, self.r = region, level, radius_km
        self.bbox = bbox
        lat_min, lat_max, lon_min, lon_max = bbox
        self.s = radius_km * math.sqrt(3) * spacing_factor     # spacing within a row (km)
        self.h = self.s * math.sqrt(3) / 2                     # spacing between rows (km)
        # Every point lies within s/sqrt(3) (the hex cell's circumradius) of its
        # nearest lattice point, so padding the box by that much covers its edges.
        pad = self.s / math.sqrt(3)
        self.lat_min, self.lat_max = lat_min - pad / KM_PER_DEG, lat_max + pad / KM_PER_DEG
        self.cos_ref = math.cos(math.radians(self.lat_min))
        pad_lon = pad / (KM_PER_DEG * math.cos(math.radians(max(abs(lat_min), abs(lat_max)))))
        self.lon_min, self.lon_max = lon_min - pad_lon, lon_max + pad_lon

    # projected km <-> degrees
    def _xy(self, lat: float, lon: float) -> tuple[float, float]:
        return (lon - self.lon_min) * KM_PER_DEG * self.cos_ref, (lat - self.lat_min) * KM_PER_DEG

    def _latlon(self, x: float, y: float) -> tuple[float, float]:
        return self.lat_min + y / KM_PER_DEG, self.lon_min + x / (KM_PER_DEG * self.cos_ref)

    def unit(self, i: int, j: int) -> SearchUnit:
        lat, lon = self._latlon((j + 0.5 * (i % 2)) * self.s, i * self.h)
        return SearchUnit.point(f"{self.region}_L{self.level}_{i:03d}_{j:03d}", lat, lon, self.r, self.level)

    def _index_range(self, lat_lo, lat_hi, lon_lo, lon_hi):
        x0, y0 = self._xy(max(lat_lo, self.lat_min), max(lon_lo, self.lon_min))
        x1, y1 = self._xy(min(lat_hi, self.lat_max), min(lon_hi, self.lon_max))
        for i in range(max(0, math.floor(y0 / self.h) - 1), math.ceil(y1 / self.h) + 2):
            for j in range(max(-1, math.floor(x0 / self.s) - 1), math.ceil(x1 / self.s) + 2):
                yield i, j

    def _in_box(self, u: SearchUnit) -> bool:
        return (self.lat_min <= u.query_latitude <= self.lat_max + self.h / KM_PER_DEG
                and self.lon_min - self.s / (KM_PER_DEG * self.cos_ref) <= u.query_longitude
                <= self.lon_max + self.s / (KM_PER_DEG * self.cos_ref))

    def all_units(self) -> list[SearchUnit]:
        # Shortcut: if one circle at the box centre covers the whole box, use it.
        lat_min, lat_max, lon_min, lon_max = self.bbox
        clat, clon = (lat_min + lat_max) / 2, (lon_min + lon_max) / 2
        corners = [(a, b) for a in (lat_min, lat_max) for b in (lon_min, lon_max)]
        if all(haversine_km(clat, clon, a, b) <= self.r for a, b in corners):
            return [SearchUnit.point(f"{self.region}_L{self.level}_center", clat, clon, self.r, self.level)]
        units = [self.unit(i, j) for i, j in self._index_range(self.lat_min, self.lat_max, self.lon_min, self.lon_max)]
        return [u for u in units if self._in_box(u)]

    def units_within(self, lat: float, lon: float, dist_km: float) -> list[SearchUnit]:
        """Lattice points whose centre is within dist_km of (lat, lon)."""
        dlat = dist_km / KM_PER_DEG + 1
        dlon = dist_km / (KM_PER_DEG * max(math.cos(math.radians(min(abs(lat) + dlat, 89))), 0.05)) + 1
        out = []
        for i, j in self._index_range(lat - dlat, lat + dlat, lon - dlon, lon + dlon):
            u = self.unit(i, j)
            if self._in_box(u) and haversine_km(lat, lon, u.query_latitude, u.query_longitude) <= dist_km:
                out.append(u)
        return out


def lattices(cfg: dict) -> dict[tuple[str, int], Lattice]:
    """All (region, level) lattices defined by config `national`."""
    nat = cfg["national"]
    return {
        (region, level): Lattice(region, spec["bbox"], r, level, nat["spacing_factor"])
        for region, spec in nat["regions"].items()
        for level, r in enumerate(spec["radii_km"])
    }


def root_units(cfg: dict) -> list[SearchUnit]:
    return [u for (_, level), lat in sorted(lattices(cfg).items()) if level == 0 for u in lat.all_units()]


def children(cfg: dict, unit: SearchUnit) -> list[SearchUnit]:
    """Next-level circles that together cover `unit`'s circle (empty at the finest level)."""
    region = unit.search_id.split("_L")[0]
    nxt = (region, unit.level + 1)
    lats = lattices(cfg)
    if nxt not in lats:
        return []
    lat = lats[nxt]
    # Only lattice points (never a level's "_center" shortcut) are used as children.
    return lat.units_within(unit.query_latitude, unit.query_longitude, unit.query_radius_km + lat.r)


def verify_coverage(units: list[SearchUnit], bbox: list[float], radius_km: float, n: int = 20000, seed: int = 0) -> float:
    """Share of random points in bbox within radius_km (haversine) of some unit centre."""
    rnd = random.Random(seed)
    pts = [(u.query_latitude, u.query_longitude) for u in units]
    lat_min, lat_max, lon_min, lon_max = bbox
    ok = 0
    for _ in range(n):
        la, lo = rnd.uniform(lat_min, lat_max), rnd.uniform(lon_min, lon_max)
        near = (p for p in pts if abs(p[0] - la) * KM_PER_DEG <= radius_km)
        ok += any(haversine_km(la, lo, a, b) <= radius_km for a, b in near)
    return ok / n


if __name__ == "__main__":
    from common import load_config

    cfg = load_config()
    for (region, level), lat in sorted(lattices(cfg).items()):
        units = lat.all_units()
        bbox = cfg["national"]["regions"][region]["bbox"]
        n = 4000 if len(units) > 2000 else 20000
        cov = verify_coverage(units, bbox, lat.r, n=n)
        print(f"{region:<5} level {level} radius {lat.r:>4} km: {len(units):>6} lattice points; coverage of bbox {cov:.4%}")
    # Subdivision check: children must cover a dense parent (NYC area).
    radii = cfg["national"]["regions"]["CONUS"]["radii_km"]
    nyc = SearchUnit.point("CONUS_L0_test", 40.71, -74.0, radii[0], 0)
    kids = children(cfg, nyc)
    r1 = radii[1]
    pad = radii[0] / KM_PER_DEG
    box = [40.71 - pad, 40.71 + pad, -74.0 - pad * 1.3, -74.0 + pad * 1.3]
    rnd = random.Random(1)
    inside = [(a, b) for a, b in ((rnd.uniform(box[0], box[1]), rnd.uniform(box[2], box[3])) for _ in range(20000))
              if haversine_km(40.71, -74.0, a, b) <= nyc.query_radius_km]
    kpts = [(k.query_latitude, k.query_longitude) for k in kids]
    cov = sum(any(haversine_km(a, b, x, y) <= r1 for x, y in kpts) for a, b in inside) / len(inside)
    print(f"Children of a {nyc.query_radius_km:.0f} km NYC circle: {len(kids)} x {r1} km circles; coverage of parent {cov:.4%}")
