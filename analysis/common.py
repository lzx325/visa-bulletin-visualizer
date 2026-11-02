"""Shared data preparation, statistics and plot styling for the Visa Bulletin analyses."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ANALYSIS = Path(__file__).resolve().parent
ROOT = ANALYSIS.parent
sys.path.insert(0, str(ROOT))

from app import load_data  # noqa: E402  (reuses the dashboard's CSV validation)
from shading import inversion_intervals  # noqa: E402  (the dashboard's EB inversion rule)

# Categories with continuous series for the whole period; EB-5 sub-categories were renamed
# several times and EB-4 has long statutory "unavailable" gaps, so they are left out.
CATEGORIES = ["F1", "F2A", "F2B", "F3", "F4", "EB1", "EB2", "EB3", "EB3_OTHER_WORKERS"]
# Areas published in every bulletin of the 2011-01 – 2026-11 span.
AREAS = ["all_chargeability_areas_except_listed", "china_mainland_born", "india", "mexico", "philippines"]
AREA_LABELS = {"all_chargeability_areas_except_listed": "All other areas", "china_mainland_born": "China",
               "india": "India", "mexico": "Mexico", "philippines": "Philippines"}
CHART_LABELS = {"final_action": "Final action", "date_for_filing": "Dates for filing"}
CATEGORY_LABELS = {c: c.replace("_OTHER_WORKERS", " other workers") for c in CATEGORIES}
FISCAL_MONTHS = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]
QUARTER_STARTS = {1, 4, 7, 10}  # fiscal months Oct, Jan, Apr, Jul
DAYS_PER_MONTH = 30.4375  # same convention as waiting.py

# Reference palette (dataviz skill): validated blue/orange pair, diverging blue/red, de-emphasis gray.
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE, ORANGE, RED, VIOLET, GRAY = "#2a78d6", "#eb6834", "#e34948", "#6250d6", "#b9b7ae"
CHART_COLORS = {"final_action": BLUE, "date_for_filing": ORANGE}
SEQUENTIAL = ["#f0efec", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def load_frame():
    """Core categories and areas as a DataFrame with fiscal-calendar fields."""
    df = pd.DataFrame(load_data())
    df = df[df.category.isin(CATEGORIES) & df.chargeability_area.isin(AREAS)].copy()
    df = df.rename(columns={"preference_type": "preference", "chart_type": "chart",
                            "chargeability_area": "area", "cutoff_status": "status"})
    df["month"] = pd.to_datetime(df.month)
    # load_data plots "current" at the bulletin month; unavailable/missing have no cutoff.
    df["cutoff"] = pd.to_datetime(df.cutoff)
    df["fy"] = df.month.dt.year + (df.month.dt.month >= 10)
    df["fy_month"] = (df.month.dt.month - 10) % 12 + 1
    return df[["preference", "chart", "category", "area", "month", "fy", "fy_month", "status", "cutoff"]]


def movements(df):
    """Month-over-month cutoff changes for each series.

    Each row is bulletin month t compared with t-1. Transitions touching unavailable/missing are
    dropped, and current→current is dropped because there is no cutoff to move. "delta_days" is
    the change in the plotted cutoff (current = first day of the bulletin month), so it is only
    a true cutoff distance for date→date moves ("dated" is True).
    """
    keys = ["preference", "chart", "category", "area"]
    df = df.sort_values(keys + ["month"])
    prev = df.groupby(keys)[["month", "status", "cutoff"]].shift()
    moves = df.assign(prev_month=prev.month, prev_status=prev.status, prev_cutoff=prev.cutoff)
    moves = moves[(moves.month - moves.prev_month).dt.days.between(28, 31)]
    usable = moves.status.isin(["date", "current"]) & moves.prev_status.isin(["date", "current"])
    moves = moves[usable & ~((moves.status == "current") & (moves.prev_status == "current"))].copy()
    moves["delta_days"] = (moves.cutoff - moves.prev_cutoff).dt.days
    moves["dated"] = (moves.status == "date") & (moves.prev_status == "date")
    moves["direction"] = np.select([moves.delta_days > 0, moves.delta_days < 0], ["advance", "retrogress"], "hold")
    moves["to_current"] = moves.status == "current"
    return moves.reset_index(drop=True)


def distinct(moves, extra=()):
    """Collapse areas that share the identical move in the same bulletin (e.g. Mexico = all other
    areas), so one State Department decision is counted once."""
    cols = ["preference", "chart", "category", "month", "prev_status", "prev_cutoff", "status", "cutoff", *extra]
    return moves.drop_duplicates(cols)


def wilson(k, n, z=1.96):
    """Wilson score interval for a proportion."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    p = np.divide(k, n, out=np.zeros_like(k), where=n > 0)
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return centre - half, centre + half


def months(days):
    return days / DAYS_PER_MONTH


def pct(x, digits=0):
    return f"{100 * x:.{digits}f}%"


def p_text(p):
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def md_table(frame, index=False):
    # Cells are pre-formatted strings; keep tabulate from re-parsing "0.010" into 0.01.
    return frame.to_markdown(index=index, disable_numparse=True)


def style():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"], "font.size": 10,
        "text.color": INK, "axes.labelcolor": INK_2, "axes.edgecolor": AXIS, "axes.linewidth": 0.8,
        "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 10,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.axisbelow": True,
        "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-",
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
        "legend.frameon": False, "legend.fontsize": 9, "lines.linewidth": 2,
    })


def hatch_missing(ax, values):
    """Mark NaN heatmap cells so "no data" is not confused with the 0% colour."""
    for r, c in zip(*np.where(np.isnan(values))):
        ax.add_patch(matplotlib.patches.Rectangle((c - 0.5, r - 0.5), 1, 1, fill=False, hatch="///",
                                                  edgecolor=GRID, linewidth=0))


def heatmap(ax, events, chart):
    """Fiscal year × fiscal month grid of the share of distinct series advancing in each bulletin."""
    share = (events[events.chart == chart].assign(adv=lambda e: e.direction == "advance")
             .pivot_table(index="fy", columns="fy_month", values="adv", aggfunc="mean")
             .reindex(columns=range(1, 13)))
    values = share.values.astype(float)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("blue", SEQUENTIAL)
    im = ax.imshow(values, aspect="auto", cmap=cmap, vmin=0, vmax=1, interpolation="nearest")
    hatch_missing(ax, values)
    ax.set_xticks(range(12), FISCAL_MONTHS)
    ax.set_yticks(range(len(share)), [f"FY{fy}" for fy in share.index])
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0)
    return im


def save(fig, folder, name):
    path = folder / "figures" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return f"figures/{name}"


def write_report(folder, text):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "README.md").write_text(text.strip() + "\n", encoding="utf-8")
