"""Current opening hours per company-operated store, as a cross-sectional operating proxy.

    python src/store_hours.py
    python src/store_hours.py --hiring-join ../starbucks_store_universe/data/processed/hiring_store_join.csv

Input : ../starbucks_store_universe/data/processed/starbucks_store_universe.csv (read only)
        (opening_hours in OpenStreetMap syntax, from Starbucks' store locator via All the Places, 2026-09-26)
Output: data/processed/store_hours.csv          weekly hours, weekday open/close, short-hours flags
        outputs/store_hours_summary.md           (written by hand from the printed summary)

Limitations: one point in time (no history, so no "reduced hours" trend); posted hours,
not actual hours; temporary closures may not be reflected.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE = ROOT.parent / "starbucks_store_universe/data/processed/starbucks_store_universe.csv"
DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def _expand(spec: str) -> list[str]:
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            i, j = DAYS.index(a), DAYS.index(b)
            out += DAYS[i:j + 1] if i <= j else DAYS[i:] + DAYS[:j + 1]
        elif part in DAYS:
            out.append(part)
    return out


def parse_hours(oh: str) -> dict:
    """'Mo-Fr 04:30-21:00; Sa-Su 05:00-21:00' -> per-day (open, close) in hours."""
    if not isinstance(oh, str) or not oh.strip():
        return {}
    if oh.strip() == "24/7":
        return {d: (0.0, 24.0) for d in DAYS}
    res = {}
    for rule in oh.split(";"):
        m = re.match(r"\s*([A-Za-z,\-]+)\s+(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})\s*$", rule)
        if not m:
            continue
        o = int(m.group(2)) + int(m.group(3)) / 60
        c = int(m.group(4)) + int(m.group(5)) / 60
        if c <= o:
            c += 24
        for d in _expand(m.group(1)):
            res[d] = (o, c)
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hiring-join", help="hiring_store_join.csv to compare hiring vs. non-hiring stores")
    args = ap.parse_args()
    u = pd.read_csv(UNIVERSE, dtype={"locator_id": str, "postal_code": str})
    u = u[u["ownership_type"] == "CO"].copy()
    parsed = u["opening_hours"].map(parse_hours)
    u["days_open_per_week"] = parsed.map(len)
    u["weekly_hours"] = parsed.map(lambda d: round(sum(c - o for o, c in d.values()), 2) if d else None)
    u["weekday_open"] = parsed.map(lambda d: d.get("We", (None, None))[0])
    u["weekday_close"] = parsed.map(lambda d: d.get("We", (None, None))[1])
    u["opens_after_6am_weekday"] = u["weekday_open"] > 6
    u["closes_before_6pm_weekday"] = u["weekday_close"] < 18
    u["short_hours_bottom_decile"] = u["weekly_hours"] < u["weekly_hours"].quantile(0.1)
    out = u[["locator_id", "store_name", "address", "city", "state", "latitude", "longitude", "located_in",
             "opening_hours", "days_open_per_week", "weekly_hours", "weekday_open", "weekday_close",
             "opens_after_6am_weekday", "closes_before_6pm_weekday", "short_hours_bottom_decile"]]
    (ROOT / "data/processed").mkdir(parents=True, exist_ok=True)
    out.to_csv(ROOT / "data/processed/store_hours.csv", index=False)

    print(f"company-operated stores: {len(u)}; hours parsed: {u['weekly_hours'].notna().sum()}")
    print(u["weekly_hours"].describe().round(1).to_string())
    print("weekday open time (share):", (u["weekday_open"].round(1).value_counts(normalize=True).head(6) * 100).round(1).to_dict())
    print(f"open after 6am on weekdays: {100 * u['opens_after_6am_weekday'].mean():.1f}%  | "
          f"close before 6pm: {100 * u['closes_before_6pm_weekday'].mean():.1f}%  | "
          f"in another venue (located_in): {100 * u['located_in'].notna().mean():.1f}%")
    by_state = u.groupby("state")["weekly_hours"].median().sort_values()
    print("lowest median weekly hours by state:", by_state.head(5).to_dict())

    if args.hiring_join:
        j = pd.read_csv(args.hiring_join, dtype={"locator_id": str})
        hiring_ids = set(j.loc[j["matched"] == True, "locator_id"])  # noqa: E712
        u["hiring"] = u["locator_id"].isin(hiring_ids)
        print("\nweekly hours, hiring vs not hiring (company-operated):")
        print(u.groupby("hiring")["weekly_hours"].describe().round(1).to_string())


if __name__ == "__main__":
    main()
