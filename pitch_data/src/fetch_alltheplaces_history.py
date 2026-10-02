"""Download past All the Places `starbucks_us` snapshots (Starbucks store locator incl. opening hours).

    python src/fetch_alltheplaces_history.py

Picks the run nearest each target date (that has a starbucks_us output) and saves
data/raw/alltheplaces/starbucks_us_<run_id>.geojson. Source: https://data.alltheplaces.xyz (CC0).
"""
import json
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/raw/alltheplaces"
TARGETS = ["2024-01-15", "2024-07-15", "2025-01-15", "2025-08-15", "2026-01-15", "2026-04-15"]
BASE = "https://data.alltheplaces.xyz/runs"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    hist = requests.get(f"{BASE}/history.json", timeout=120).json()
    runs = sorted(h["run_id"] for h in hist)
    log = []
    for t in TARGETS:
        cands = sorted(runs, key=lambda r: abs((int(r[:4]) * 372 + int(r[5:7]) * 31 + int(r[8:10]))
                                                - (int(t[:4]) * 372 + int(t[5:7]) * 31 + int(t[8:10]))))[:12]
        for rid in cands:
            dest = OUT / f"starbucks_us_{rid}.geojson"
            if dest.exists():
                log.append((t, rid, "exists")); break
            r = requests.get(f"https://alltheplaces-data.openaddresses.io/runs/{rid}/output/starbucks_us.geojson", timeout=300)
            if r.status_code == 200 and r.content[:1] == b"{":
                dest.write_bytes(r.content)
                log.append((t, rid, f"ok {len(r.content)/1e6:.1f} MB")); break
            log.append((t, rid, f"HTTP {r.status_code}"))
            time.sleep(1)
        print(log[-1], flush=True)
    (OUT / "_download_log.json").write_text(json.dumps(log, indent=1))


if __name__ == "__main__":
    main()
