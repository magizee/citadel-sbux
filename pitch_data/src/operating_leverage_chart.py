"""Filings check: North America store operating expenses vs company-operated revenue (8-K releases).

    python src/operating_leverage_chart.py
Reads tables/filings_store_opex.csv and tables/operating_leverage.csv; writes charts/00_operating_leverage.png.
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from lab import LAB


def main() -> None:
    sys.path.insert(0, str(LAB.parent / "_research_archive/starbucks_hiring/src"))
    import charts as C
    import matplotlib.pyplot as plt
    f = pd.read_csv(LAB / "tables/filings_store_opex.csv")
    lev = pd.read_csv(LAB / "tables/operating_leverage.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
    ax = axes[0]
    ax.plot(range(len(f)), f["na_store_opex_pct_of_co_revenue"], color=C.BLUE, linewidth=2, marker="o", markersize=6)
    for i, v in enumerate(f["na_store_opex_pct_of_co_revenue"]):
        ax.text(i, v + 0.35, f"{v:.1f}", ha="center", fontsize=8, color=C.INK_2)
    fy24 = f.loc[f["fiscal_quarter"].str.startswith("FY24"), "na_store_opex_pct_of_co_revenue"].mean()
    ax.axhline(fy24, color=C.INK_2, linewidth=0.8, linestyle="--")
    ax.text(len(f) - 1, fy24 - 0.8, f"FY24 avg {fy24:.1f}%", ha="right", fontsize=8, color=C.INK_2)
    ax.set_xticks(range(len(f)), f["fiscal_quarter"].str.replace(" ", "\n"), fontsize=8)
    ax.set_ylim(48, 61)
    ax.set_ylabel("% of company-operated revenue")
    ax.set_title("North America store operating expenses", fontsize=10)
    ax = axes[1]
    x = np.arange(len(lev))
    ax.bar(x - 0.18, lev["revenue_yoy_pct"], width=0.34, color=C.GRAY, label="Company-operated revenue")
    ax.bar(x + 0.18, lev["store_opex_yoy_pct"], width=0.34, color=C.BLUE, label="Store operating expenses")
    for i, r in lev.iterrows():
        ax.text(i + 0.18, r["store_opex_yoy_pct"] + 0.3, f"{r['store_opex_yoy_pct']:.1f}", ha="center", fontsize=8, color=C.INK_2)
        ax.text(i - 0.18, r["revenue_yoy_pct"] + 0.3, f"{r['revenue_yoy_pct']:.1f}", ha="center", fontsize=8, color=C.INK_2)
    ax.set_xticks(x, lev["fiscal_quarter"].str.replace(" ", "\n"), fontsize=8)
    ax.set_ylabel("YoY growth, %")
    ax.set_title("YoY growth: costs outran revenue until FY26 Q3", fontsize=10)
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax.grid(axis="x", visible=False)
    fig.suptitle("Operating leverage only just turned positive (FY26 Q3), and the cost ratio is still ~5 pp above the same quarter of FY24",
                 x=0.01, y=0.99, ha="left", fontsize=12, fontweight="semibold")
    fig.text(0.01, 0.01, "Source: Starbucks 8-K earnings releases, North America segment · FY25 Q4 includes restructuring in operating income, not shown",
             fontsize=8, color=C.INK_2)
    fig.tight_layout(rect=(0, 0.04, 1, 0.92))
    fig.savefig(LAB / "charts/00_operating_leverage.png", dpi=200)


if __name__ == "__main__":
    main()
