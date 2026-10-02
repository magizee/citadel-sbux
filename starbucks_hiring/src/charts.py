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
    "axes.titlesize": 13, "axes.titleweight": "semibold", "axes.titlelocation": "left", "axes.titlepad": 22,
})


# Set by callers: a banner printed on every chart (e.g. the pilot label) and a
# separate folder for chart data (default: next to the PNG).
BANNER = ""
TABLE_DIR: Path | None = None


def _table(df: pd.DataFrame, out: Path, name: str) -> None:
    d = TABLE_DIR or out
    d.mkdir(parents=True, exist_ok=True)
    df.to_csv(d / name, index=False)


def _finish(fig, ax, path: Path, subtitle: str, note: str | None = None) -> None:
    # Fixed offset in points (not axes fraction) so the subtitle sits just under the title at any figure height.
    ax.annotate(subtitle, (0, 1), xycoords="axes fraction", xytext=(0, 5), textcoords="offset points",
                color=INK_2, fontsize=9.5, va="bottom")
    if BANNER:
        fig.text(0.99, 0.995, BANNER, ha="right", va="top", fontsize=8.5, color="#d03b3b", fontweight="bold")
    if note:
        fig.text(0.01, 0.01, note, color=INK_2, fontsize=8, va="bottom")
    fig.tight_layout(rect=(0, 0.04 if note else 0, 1, 1))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _hbar(df: pd.DataFrame, label_col: str, value_col: str, title: str, subtitle: str, path: Path,
          fmt: str, ref: float | None = None, ref_label: str | None = None, note: str | None = None,
          xlabel: str = "", text_col: str | None = None) -> None:
    """Sorted horizontal bar chart, largest at top; optional gray reference line."""
    d = df.sort_values(value_col, ascending=True)
    fig, ax = plt.subplots(figsize=(8, 0.34 * len(d) + 1.6))
    ax.barh(d[label_col], d[value_col], color=BLUE, height=0.62, zorder=2)
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)
    xmax = d[value_col].max()
    texts = d[text_col] if text_col else [fmt.format(v) for v in d[value_col]]
    for y, (v, t) in enumerate(zip(d[value_col], texts)):
        ax.text(v + xmax * 0.01, y, t, va="center", fontsize=9, color=INK_2)
    if ref is not None:
        ax.axvline(ref, color=INK_2, linewidth=1, zorder=3)
        ax.text(ref, len(d) - 0.35, f" {ref_label}", color=INK_2, fontsize=8.5, va="bottom")
    ax.set_xlim(0, xmax * (1.3 if text_col else 1.15))
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
    _table(d, out, "01_national_role_mix.csv")
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
    _table(d, out, "02_posting_age_distribution.csv")
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
            f"Median {days.median():.0f} days  ·  n = {len(days):,}  ·  posting age measures how long a posting has stayed active, not time-to-fill",
            note="Frontline postings expire 90 days after posting, so ages stop at 89 days; the shape largely reflects requisition batch dates.")


def multi_role(stores: pd.DataFrame, out: Path) -> None:
    def combo(r):
        parts = [n for n, f in [("Barista", r.has_barista_opening), ("Shift supv.", r.has_shift_supervisor_opening),
                                ("Store mgr.", r.has_store_manager_opening)] if f]
        if r.other_retail_postings > 0 or r.district_manager_postings > 0:
            parts.append("Other")
        return " + ".join(parts) if parts else "Other"
    d = stores.apply(combo, axis=1).value_counts().rename_axis("role_combination").reset_index(name="hiring_stores")
    d["pct_of_hiring_stores"] = (100 * d["hiring_stores"] / d["hiring_stores"].sum()).round(1)
    _table(d, out, "06_store_role_combinations.csv")
    top = d.head(8)
    _hbar(top, "role_combination", "hiring_stores", "Which roles each hiring store is recruiting for",
          f"Hiring stores by combination of open roles  ·  n = {len(stores):,} stores with ≥1 retail posting",
          out / "06_store_role_combinations.png", "{:,.0f}",
          note="Store = store number, or street address where no number is published. Top 8 combinations shown.")


def age_by_role(retail: pd.DataFrame, out: Path) -> None:
    """Posting age by role: median (dot), interquartile range (thick bar), 10th-90th percentile (thin line)."""
    labels = {"BARISTA": "Barista", "SHIFT_SUPERVISOR": "Shift supervisor", "STORE_MANAGER": "Store manager",
              "DISTRICT_MANAGER": "District manager", "OTHER_RETAIL": "Other in-store"}
    g = retail.groupby("role_bucket")["days_open"]
    d = pd.DataFrame({"postings": g.size(), "p10": g.quantile(0.1), "p25": g.quantile(0.25),
                      "median": g.median(), "p75": g.quantile(0.75), "p90": g.quantile(0.9),
                      "pct_over_30_days": g.apply(lambda x: round(100 * (x > 30).mean(), 1)),
                      "pct_over_60_days": g.apply(lambda x: round(100 * (x > 60).mean(), 1))}).reset_index()
    d["role"] = d["role_bucket"].map(labels)
    _table(d, out, "07_posting_age_by_role.csv")
    d = d.sort_values("median")
    fig, ax = plt.subplots(figsize=(8, 0.55 * len(d) + 1.6))
    for y, r in enumerate(d.itertuples()):
        ax.plot([r.p10, r.p90], [y, y], color=BLUE_LIGHT, linewidth=1.5, zorder=2, solid_capstyle="round")
        ax.plot([r.p25, r.p75], [y, y], color=BLUE, linewidth=6, zorder=3, solid_capstyle="round")
        ax.scatter([r.median], [y], s=60, color=INK, zorder=4, edgecolor=SURFACE, linewidth=2)
        ax.text(d["p90"].max() * 1.03, y, f"median {r.median:.0f}d · n={r.postings:,}", va="center", fontsize=8.5, color=INK_2)
    ax.set_yticks(range(len(d)), d["role"])
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, d["p90"].max() * 1.35)
    ax.set_ylim(-0.6, len(d) - 0.4)
    ax.set_xlabel("Days since posted")
    ax.set_title("Posting age by role")
    _finish(fig, ax, out / "07_posting_age_by_role.png",
            "Dot = median · thick bar = middle 50% · thin line = 10th–90th percentile")


def make_all(retail: pd.DataFrame, stores: pd.DataFrame, market: pd.DataFrame, summary: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    role_mix(retail, out)
    posting_age(retail, out)
    multi_role(stores, out)
    age_by_role(retail, out)

    th = summary["ranking_thresholds"]
    nat = market[market["geography_level"] == "national"].iloc[0]
    states = market[(market["geography_level"] == "state") & market["meets_ranking_threshold"]]
    cities = market[(market["geography_level"] == "city") & market["meets_ranking_threshold"]]
    cols = ["geography", "unique_stores_hiring", "active_retail_postings", "postings_per_hiring_store",
            "pct_over_30_days", "pct_over_60_days", "leadership_vacancy_intensity",
            "store_manager_postings", "district_manager_postings", "median_days_open"]

    d = states.nlargest(15, "postings_per_hiring_store")[cols]
    _table(d, out, "03_states_postings_per_hiring_store.csv")
    _hbar(d, "geography", "postings_per_hiring_store", "Retail postings per hiring store, top 15 states",
          f"States with ≥ {th['min_hiring_stores_state']} hiring stores", out / "03_states_postings_per_hiring_store.png",
          "{:.2f}", ref=nat["postings_per_hiring_store"], ref_label=f"U.S. {nat['postings_per_hiring_store']:.2f}")

    d = cities.nlargest(15, "pct_over_30_days")[cols]
    _table(d, out, "04_markets_pct_over_30_days.csv")
    _hbar(d, "geography", "pct_over_30_days", "Share of retail postings open > 30 days, top 15 cities",
          f"Cities with ≥ {th['min_hiring_stores_city']} hiring stores (city as written in the address; not metro areas)",
          out / "04_markets_pct_over_30_days.png", "{:.0f}%", ref=nat["pct_over_30_days"],
          ref_label=f"U.S. {nat['pct_over_30_days']:.0f}%",
          note="CAVEAT: frontline requisitions are created in rolling batches with a 90-day expiry, so this mostly reflects batch timing, not persistence.")

    d = states.nlargest(15, "leadership_vacancy_intensity")[cols]
    _table(d, out, "05_states_leadership_intensity.csv")
    _hbar(d, "geography", "leadership_vacancy_intensity",
          "Leadership postings per hiring store, top 15 states",
          f"(Store manager + district manager postings) ÷ hiring stores  ·  states with ≥ {th['min_hiring_stores_state']} hiring stores",
          out / "05_states_leadership_intensity.png", "{:.3f}", ref=nat["leadership_vacancy_intensity"],
          ref_label=f"U.S. {nat['leadership_vacancy_intensity']:.3f}")
