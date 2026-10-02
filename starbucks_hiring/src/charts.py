"""Pitch charts for the national snapshot (called from analyze.py).

Each chart is saved as PNG with its underlying data as CSV of the same name.
Style: light surface, hairline solid grid, thin single-hue bars (blue), gray
for context/reference, text in ink colours (never the series colour), labels
only where they carry the point.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
BLUE = "#2a78d6"
BLUE_LIGHT = "#9ec5f4"
GRAY = "#b9b8b2"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 10.5, "text.color": INK, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK,
    "axes.edgecolor": GRID, "axes.linewidth": 0.8, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "grid.linestyle": "-", "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 13, "axes.titleweight": "semibold", "axes.titlelocation": "left", "axes.titlepad": 14,
})


def _finish(fig, ax, path: Path, subtitle: str, note: str | None = None) -> None:
    ax.text(0, 1.015, subtitle, transform=ax.transAxes, color=INK_2, fontsize=9.5, va="bottom")
    if note:
        fig.text(0.01, 0.01, note, color=INK_2, fontsize=8, va="bottom")
    fig.tight_layout(rect=(0, 0.04 if note else 0, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _hbar(df: pd.DataFrame, label_col: str, value_col: str, title: str, subtitle: str, path: Path,
          fmt: str, ref: float | None = None, ref_label: str | None = None, note: str | None = None,
          xlabel: str = "") -> None:
    """Sorted horizontal bar chart, largest at top; optional gray reference line."""
    d = df.sort_values(value_col, ascending=True)
    fig, ax = plt.subplots(figsize=(8, 0.34 * len(d) + 1.6))
    ax.barh(d[label_col], d[value_col], color=BLUE, height=0.62, zorder=2)
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)
    xmax = d[value_col].max()
    for y, v in enumerate(d[value_col]):
        ax.text(v + xmax * 0.01, y, fmt.format(v), va="center", fontsize=9, color=INK_2)
    if ref is not None:
        ax.axvline(ref, color=INK_2, linewidth=1, zorder=3)
        ax.text(ref, len(d) - 0.35, f" {ref_label}", color=INK_2, fontsize=8.5, va="bottom")
    ax.set_xlim(0, xmax * 1.15)
    ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.tick_params(axis="y", length=0)
    _finish(fig, ax, path, subtitle, note)


def role_mix(retail: pd.DataFrame, out: Path) -> None:
    labels = {"BARISTA": "Barista", "SHIFT_SUPERVISOR": "Shift supervisor", "STORE_MANAGER": "Store manager",
              "DISTRICT_MANAGER": "District manager", "OTHER_RETAIL": "Other in-store"}
    d = retail["role_bucket"].value_counts().rename_axis("role_bucket").reset_index(name="postings")
    d["share_pct"] = (100 * d["postings"] / d["postings"].sum()).round(1)
    d["role"] = d["role_bucket"].map(labels)
    d.to_csv(out / "01_national_role_mix.csv", index=False)
    d["label"] = d.apply(lambda r: f"{r.postings:,}  ({r.share_pct:.0f}%)", axis=1)
    dd = d.sort_values("postings")
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.barh(dd["role"], dd["postings"], color=BLUE, height=0.6, zorder=2)
    ax.grid(axis="y", visible=False)
    for y, (v, lab) in enumerate(zip(dd["postings"], dd["label"])):
        ax.text(v + dd["postings"].max() * 0.01, y, lab, va="center", fontsize=9, color=INK_2)
    ax.set_xlim(0, dd["postings"].max() * 1.22)
    ax.tick_params(axis="y", length=0)
    ax.set_title("Active retail postings by role")
    _finish(fig, ax, out / "01_national_role_mix.png",
            f"U.S. Starbucks careers site, snapshot {retail['snapshot_date'].iloc[0]}  ·  n = {len(retail):,} retail postings")


def posting_age(retail: pd.DataFrame, out: Path) -> None:
    days = retail["days_open"].dropna()
    step = 5                                   # 30 and 60 fall on bin edges
    cap = int(min(180, -(-days.max() // step) * step + step))
    bins = list(range(0, cap + step, step))
    counts = pd.cut(days.clip(upper=cap - 0.5), bins=bins, right=False).value_counts().sort_index()
    d = pd.DataFrame({"days_open_from": bins[:-1], "days_open_to": bins[1:], "postings": counts.values})
    d.to_csv(out / "02_posting_age_distribution.csv", index=False)
    fig, ax = plt.subplots(figsize=(8, 3.8))
    colors = [BLUE if lo < 30 else (BLUE_LIGHT if lo < 60 else GRAY) for lo in d["days_open_from"]]
    ax.bar(d["days_open_from"] + step / 2, d["postings"], width=step - 0.8, color=colors, zorder=2)
    ax.grid(axis="x", visible=False)
    p30, p60 = 100 * (days > 30).mean(), 100 * (days > 60).mean()
    ymax = d["postings"].max()
    for x, lab, y in [(30, f"{p30:.0f}% open > 30 days", 0.97), (60, f"{p60:.0f}% open > 60 days", 0.80)]:
        ax.axvline(x, color=INK_2, linewidth=1, zorder=3)
        ax.text(x + cap * 0.008, ymax * y, lab, color=INK, fontsize=9, va="top")
    ax.set_xlim(0, cap)
    tail = " (last bar includes older postings)" if days.max() >= cap else ""
    ax.set_xlabel(f"Days since posted (snapshot date − posted date){tail}")
    ax.set_ylabel("Retail postings")
    ax.set_title("How long current retail postings have been open")
    _finish(fig, ax, out / "02_posting_age_distribution.png",
            f"Median {days.median():.0f} days  ·  n = {len(days):,}  ·  posting age measures how long a posting has stayed active, not time-to-fill")


def multi_role(stores: pd.DataFrame, out: Path) -> None:
    def combo(r):
        parts = [n for n, f in [("Barista", r.has_barista_opening), ("Shift supv.", r.has_shift_supervisor_opening),
                                ("Store mgr.", r.has_store_manager_opening)] if f]
        if r.other_retail_postings > 0 or r.district_manager_postings > 0:
            parts.append("Other")
        return " + ".join(parts) if parts else "Other"
    d = stores.apply(combo, axis=1).value_counts().rename_axis("role_combination").reset_index(name="hiring_stores")
    d["pct_of_hiring_stores"] = (100 * d["hiring_stores"] / d["hiring_stores"].sum()).round(1)
    d.to_csv(out / "06_store_role_combinations.csv", index=False)
    top = d.head(8)
    _hbar(top, "role_combination", "hiring_stores", "Which roles each hiring store is recruiting for",
          f"Hiring stores by combination of open roles  ·  n = {len(stores):,} stores with ≥1 retail posting",
          out / "06_store_role_combinations.png", "{:,.0f}",
          note="Store = store number, or street address where no number is published. Top 8 combinations shown.")


def make_all(retail: pd.DataFrame, stores: pd.DataFrame, market: pd.DataFrame, summary: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    role_mix(retail, out)
    posting_age(retail, out)
    multi_role(stores, out)

    th = summary["ranking_thresholds"]
    nat = market[market["geography_level"] == "national"].iloc[0]
    states = market[(market["geography_level"] == "state") & market["meets_ranking_threshold"]]
    cities = market[(market["geography_level"] == "city") & market["meets_ranking_threshold"]]
    cols = ["geography", "unique_stores_hiring", "active_retail_postings", "postings_per_hiring_store",
            "pct_over_30_days", "pct_over_60_days", "leadership_vacancy_intensity",
            "store_manager_postings", "district_manager_postings", "median_days_open"]

    d = states.nlargest(15, "postings_per_hiring_store")[cols]
    d.to_csv(out / "03_states_postings_per_hiring_store.csv", index=False)
    _hbar(d, "geography", "postings_per_hiring_store", "Retail postings per hiring store, top 15 states",
          f"States with ≥ {th['min_hiring_stores_state']} hiring stores", out / "03_states_postings_per_hiring_store.png",
          "{:.2f}", ref=nat["postings_per_hiring_store"], ref_label=f"U.S. {nat['postings_per_hiring_store']:.2f}")

    d = cities.nlargest(15, "pct_over_30_days")[cols]
    d.to_csv(out / "04_markets_pct_over_30_days.csv", index=False)
    _hbar(d, "geography", "pct_over_30_days", "Share of retail postings open > 30 days, top 15 cities",
          f"Cities with ≥ {th['min_hiring_stores_city']} hiring stores (city as written in the address; not metro areas)",
          out / "04_markets_pct_over_30_days.png", "{:.0f}%", ref=nat["pct_over_30_days"],
          ref_label=f"U.S. {nat['pct_over_30_days']:.0f}%")

    d = states.nlargest(15, "leadership_vacancy_intensity")[cols]
    d.to_csv(out / "05_states_leadership_intensity.csv", index=False)
    _hbar(d, "geography", "leadership_vacancy_intensity",
          "Leadership postings per hiring store, top 15 states",
          f"(Store manager + district manager postings) ÷ hiring stores  ·  states with ≥ {th['min_hiring_stores_state']} hiring stores",
          out / "05_states_leadership_intensity.png", "{:.3f}", ref=nat["leadership_vacancy_intensity"],
          ref_label=f"U.S. {nat['leadership_vacancy_intensity']:.3f}")
