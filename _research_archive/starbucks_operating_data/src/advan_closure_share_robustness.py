"""Step 2: is "Dunkin' gains where Starbucks closed stores" robust to metro size, and does it pass a placebo test?

    python src/advan_closure_share_robustness.py

For each metro (MSA with >= 20 Starbucks locations) and each Starbucks fiscal quarter FY25 Q2 - FY26 Q4:
  share change = Starbucks share of (Starbucks + Dunkin') visits, quarter vs the same 13 weeks a year earlier (pp).
  Regression: share change ~ closures per 100 Starbucks + log(# Starbucks) + starting share. Exposure window: --window.
  PLACEBO: FY25 Q2-Q4 end before the Oct-2025 wave, so closure exposure should NOT predict share change there.
  Robustness: Spearman within metro-size terciles.
Outputs: outputs/advan/closure_share_robustness.csv, closure_share_robustness.json, closure_share_robustness.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs/advan"
sys.path.insert(0, str(ROOT.parent / "starbucks_hiring/src"))
sys.path.insert(0, str(ROOT / "src"))
import charts as C  # noqa: E402
from advan_validation import QUARTERS  # noqa: E402

COLS = ["ID_STORE", "BRAND", "ISO_COUNTRY_CODE", "VISIT_COUNTS", "DATE_RANGE_START", "MSA_CODE", "CLOSE_DATE"]


def load(folder: str, brand: str) -> pd.DataFrame:
    frames = []
    for f in sorted((ROOT / folder).glob("*.parquet")):
        d = pd.read_parquet(f, columns=COLS)
        frames.append(d[(d["ISO_COUNTRY_CODE"] == "US") & d["BRAND"].fillna("").str.contains(brand, case=False) & d["MSA_CODE"].notna()])
    d = pd.concat(frames, ignore_index=True)
    d["week"] = pd.to_datetime(d["DATE_RANGE_START"].astype(str).str[:10])
    d["visits"] = pd.to_numeric(d["VISIT_COUNTS"], errors="coerce")
    return d


def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + X)
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    # HC1 robust standard errors
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    cov = XtX_inv @ (X.T * e ** 2) @ X @ XtX_inv * n / (n - k)
    return b, np.sqrt(np.diag(cov))


# Closure exposure window. Default: the Oct-2025 restructuring wave only, which company filings confirm was
# company-operated (627 closures, 520 U.S., Q4 FY25). Advan's later "closures" (spring 2026) are not matched by
# company-operated store counts (which rose) and may include licensed closures or Advan data clean-up.
WINDOWS = {"oct2025_wave": ("2025-10-01", "2025-11-01"), "all_jul25_aug26": ("2025-07-01", "2026-09-01")}


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", choices=list(WINDOWS), default="oct2025_wave")
    args = ap.parse_args()
    sb, dk = load("data/raw/advan", "Starbucks"), load("data/raw/advan_competitors", "Dunkin")
    last = sb.sort_values("week").drop_duplicates("ID_STORE", keep="last")
    cd = pd.to_datetime(last["CLOSE_DATE"].astype(str).str[:10], errors="coerce")
    w0, w1 = WINDOWS[args.window]
    closures = last[(cd >= w0) & (cd < w1)].groupby("MSA_CODE").size()
    base = sb[(sb["week"] >= "2025-06-30") & (sb["week"] < "2025-09-29")].groupby("MSA_CODE")["ID_STORE"].nunique()
    m = pd.DataFrame({"sb_locations": base, "closures": closures}).fillna({"closures": 0})
    m = m[m["sb_locations"] >= 20]
    m["closures_per_100"] = 100 * m["closures"] / m["sb_locations"]
    m["size_tercile"] = pd.qcut(m["sb_locations"], 3, labels=["small", "mid", "large"])

    def msa_visits(d, weeks):
        return d[d["week"].isin(weeks)].groupby("MSA_CODE")["visits"].sum()

    rows, res = [], {"metros": len(m), "closure_window": args.window, "quarters": {}}
    for name, start, *_ in QUARTERS:
        cur = pd.date_range(start, periods=13, freq="7D")
        cur = cur[cur <= sb["week"].max()]
        prev = cur - pd.Timedelta(weeks=52)
        s1, s0, d1, d0 = msa_visits(sb, cur), msa_visits(sb, prev), msa_visits(dk, cur), msa_visits(dk, prev)
        x = m.join(pd.DataFrame({"s1": s1, "s0": s0, "d1": d1, "d0": d0}), how="inner").dropna()
        x = x[(x[["s0", "d0"]] > 0).all(axis=1)]
        x["share0"] = 100 * x.s0 / (x.s0 + x.d0)
        x["share_change_pp"] = 100 * x.s1 / (x.s1 + x.d1) - x["share0"]
        b, se = ols(x["share_change_pp"].to_numpy(), [x["closures_per_100"].to_numpy(), np.log(x["sb_locations"].to_numpy()), x["share0"].to_numpy()])
        placebo = pd.Timestamp(start) + pd.Timedelta(weeks=13) <= pd.Timestamp("2025-10-13")
        terc = {t: round(float(g["share_change_pp"].rank().corr(g["closures_per_100"].rank())), 3)
                for t, g in x.groupby("size_tercile", observed=True)}
        r = {"quarter": name, "placebo_pre_closure": bool(placebo), "metros": len(x),
             "coef_pp_per_closure_per_100": round(float(b[1]), 4), "se": round(float(se[1]), 4),
             "ci95": [round(float(b[1] - 1.96 * se[1]), 4), round(float(b[1] + 1.96 * se[1]), 4)],
             "coef_log_size": round(float(b[2]), 4), "spearman_raw": round(float(x["share_change_pp"].rank().corr(x["closures_per_100"].rank())), 3),
             "spearman_by_size_tercile": terc}
        rows.append(r)
        res["quarters"][name] = r
    t = pd.DataFrame(rows)
    suffix = "" if args.window == "oct2025_wave" else f"_{args.window}"
    t.to_csv(OUT / f"closure_share_robustness{suffix}.csv", index=False)
    (OUT / f"closure_share_robustness{suffix}.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 3.9))
    xs = range(len(t))
    cols = [C.GRAY if p else C.BLUE for p in t["placebo_pre_closure"]]
    for i, r in t.iterrows():
        ax.plot([i, i], r["ci95"], color=cols[i], linewidth=6, alpha=0.35, solid_capstyle="round")
        ax.scatter([i], [r["coef_pp_per_closure_per_100"]], color=cols[i], s=55, zorder=3)
    ax.axhline(0, color=C.INK_2, linewidth=0.9)
    ax.axvline(2.5, color=C.GRID, linewidth=1)
    ax.text(2.55, ax.get_ylim()[1], " Oct-2025 closure wave", va="top", fontsize=8.5, color=C.INK_2)
    ax.set_xticks(list(xs), [f"{q}\n{'placebo' if p else ''}" for q, p in zip(t["quarter"], t["placebo_pre_closure"])], fontsize=8.5)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("pp share change per\n1 closure per 100 stores")
    ax.set_title("Closure exposure vs Starbucks' share change vs Dunkin', by quarter")
    C._finish(fig, ax, OUT / f"closure_share_robustness{suffix}.png",
              f"OLS across {int(t['metros'].iloc[0])} metros (≥ 20 Starbucks), controlling for metro size and starting share · dot = estimate, bar = 95% CI (robust SE)",
              note=f"Exposure = {'Oct-2025 restructuring closures (company-operated, per filings)' if args.window == 'oct2025_wave' else 'all Advan closures Jul 2025-Aug 2026'}. Grey = placebo quarters before the closures.")


if __name__ == "__main__":
    main()
