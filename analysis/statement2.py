"""Statement 2: both charts leap forward at the start of the fiscal year and are more likely to
advance at the start of each quarter."""
from __future__ import annotations

from common import *
from scipy.stats import mannwhitneyu

FOLDER = ANALYSIS / "02-fiscal-year-and-quarter-jumps"
GROUPS = {"Oct": [1], "Jan/Apr/Jul": [4, 7, 10], "Other months": [2, 3, 5, 6, 8, 9, 11, 12]}


def group_of(fy_month):
    return next(name for name, members in GROUPS.items() if fy_month in members)


def bulletins(events):
    """One row per chart and bulletin: share of distinct series advancing and their mean net
    date-to-date movement in months (holds count as zero, retrogressions as negative)."""
    e = events.assign(adv=events.direction == "advance",
                      net=np.where(events.dated, months(events.delta_days), np.nan))
    b = e.groupby(["chart", "month", "fy_month"]).agg(adv=("adv", "mean"), net=("net", "mean")).reset_index()
    b["group"] = b.fy_month.map(group_of)
    return b


def boot_ci(values, reps=4000, seed=7):
    rng = np.random.default_rng(seed)
    values = np.asarray(values.dropna())
    means = rng.choice(values, (reps, len(values))).mean(axis=1)
    return np.percentile(means, [2.5, 97.5])


def month_colors(chart):
    return [CHART_COLORS[chart] if m in QUARTER_STARTS else GRAY for m in range(1, 13)]


def quarter_legend(ax, chart):
    handles = [matplotlib.patches.Patch(color=CHART_COLORS[chart], label="Quarter start (Oct, Jan, Apr, Jul)"),
               matplotlib.patches.Patch(color=GRAY, label="Other months")]
    ax.legend(handles=handles, loc="upper right", fontsize=8.5)


def fig_advance_share(events):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, chart in zip(axes, CHART_LABELS):
        g = events[events.chart == chart].groupby("fy_month").direction
        k, n = g.apply(lambda d: (d == "advance").sum()), g.size()
        lo, hi = wilson(k, n)
        p = k / n
        x = np.arange(12)
        ax.bar(x, p, width=0.7, color=month_colors(chart), edgecolor=SURFACE, linewidth=1)
        ax.errorbar(x, p, yerr=[p - lo, hi - p], fmt="none", ecolor=INK_2, elinewidth=0.8)
        ax.set_xticks(x, FISCAL_MONTHS)
        ax.set_title(CHART_LABELS[chart])
        ax.grid(axis="x", visible=False)
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
        ax.set_ylim(0, 1)
        quarter_legend(ax, chart)
    axes[0].set_ylabel("Distinct series that advanced")
    fig.suptitle("How often cutoffs advance, by bulletin month · whiskers: 95% Wilson interval",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return save(fig, FOLDER, "advance-share-by-month.png")


def fig_net_movement(bulletin_rows):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, chart in zip(axes, CHART_LABELS):
        b = bulletin_rows[bulletin_rows.chart == chart]
        means = b.groupby("fy_month").net.mean().reindex(range(1, 13))
        cis = np.array([boot_ci(b[b.fy_month == m].net) for m in range(1, 13)])
        x = np.arange(12)
        ax.bar(x, means, width=0.7, color=month_colors(chart), edgecolor=SURFACE, linewidth=1)
        ax.errorbar(x, means, yerr=[means - cis[:, 0], cis[:, 1] - means], fmt="none", ecolor=INK_2, elinewidth=0.8)
        ax.axhline(0, color=AXIS, linewidth=0.8)
        ax.set_xticks(x, FISCAL_MONTHS)
        ax.set_title(CHART_LABELS[chart])
        ax.grid(axis="x", visible=False)
        quarter_legend(ax, chart)
    axes[0].set_ylabel("Mean movement per series (months)")
    fig.suptitle("How far cutoffs move in each bulletin month (date-to-date moves; holds = 0) · whiskers: 95% bootstrap CI over bulletins",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return save(fig, FOLDER, "net-movement-by-month.png")


def fig_advance_size(events):
    adv = events[events.dated & (events.delta_days > 0)]
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.6), sharex=True, sharey=True)
    for r, chart in enumerate(CHART_LABELS):
        for c, pref in enumerate(["family", "employment"]):
            ax = axes[r, c]
            sub = adv[(adv.chart == chart) & (adv.preference == pref)]
            data = [months(sub[sub.fy_month == m].delta_days).values for m in range(1, 13)]
            box = ax.boxplot(data, positions=range(12), widths=0.6, patch_artist=True, showfliers=True,
                             medianprops=dict(color=INK, linewidth=1.4), whiskerprops=dict(color=MUTED, linewidth=0.8),
                             capprops=dict(color=MUTED, linewidth=0.8),
                             flierprops=dict(marker="o", markersize=2.5, markerfacecolor=MUTED, markeredgewidth=0, alpha=0.6))
            for patch, color in zip(box["boxes"], month_colors(chart)):
                patch.set(facecolor=color, edgecolor=SURFACE, alpha=0.85)
            ax.set_yscale("log")
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
            ax.set_xticks(range(12), FISCAL_MONTHS)
            ax.set_title(f"{CHART_LABELS[chart]} · {pref.title()}", fontsize=10)
            ax.grid(axis="x", visible=False)
        axes[r, 0].set_ylabel("Advance size (months, log)")
    fig.suptitle("Size of each date-to-date advance, by bulletin month (quarter starts coloured)",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return save(fig, FOLDER, "advance-size-by-month.png")


def fig_heatmaps(events):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.6), gridspec_kw=dict(width_ratios=[1, 1]))
    for ax, chart in zip(axes, CHART_LABELS):
        im = heatmap(ax, events, chart)
        ax.set_title(CHART_LABELS[chart])
    cb = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, format=matplotlib.ticker.PercentFormatter(1.0))
    cb.outline.set_visible(False)
    cb.set_label("Distinct series advancing in the bulletin", color=INK_2)
    fig.suptitle("Share of distinct series advancing, per bulletin · hatched = no data",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    return save(fig, FOLDER, "advance-heatmaps.png")


def run(df, moves):
    style()
    events = distinct(moves)
    b = bulletins(events)
    figs = dict(share=fig_advance_share(events), net=fig_net_movement(b), size=fig_advance_size(events),
                heat=fig_heatmaps(events))

    # Per bulletin month, both charts.
    rows = []
    for m in range(1, 13):
        row = {"Bulletin month": FISCAL_MONTHS[m - 1], "Quarter start": "yes" if m in QUARTER_STARTS else ""}
        for chart, short in (("final_action", "FAD"), ("date_for_filing", "DFF")):
            e = events[(events.chart == chart)]
            fwd = e[e.dated & (e.delta_days > 0)]
            bb = b[(b.chart == chart) & (b.fy_month == m)]
            row[f"{short} advancing"] = pct(bb.adv.mean())
            row[f"{short} mean move (mo)"] = f"{bb.net.mean():.2f}"
            row[f"{short} share of forward movement"] = pct(fwd[fwd.fy_month == m].delta_days.sum() / fwd.delta_days.sum(), 1)
        rows.append(row)
    table_month = pd.DataFrame(rows)

    # Bulletin-level tests.
    tests, stats = [], {}
    for chart in CHART_LABELS:
        bc = b[b.chart == chart]
        for metric, label, fmt in (("adv", "Share of series advancing", pct), ("net", "Mean move per series (months)",
                                                                              lambda v: f"{v:.2f}")):
            for a_name, a_mask, b_name, b_mask in (
                    ("Oct", bc.fy_month == 1, "all other months", bc.fy_month != 1),
                    ("Jan/Apr/Jul", bc.group == "Jan/Apr/Jul", "non-quarter months", bc.group == "Other months")):
                xa, xb = bc[a_mask][metric].dropna(), bc[b_mask][metric].dropna()
                p = mannwhitneyu(xa, xb, alternative="two-sided").pvalue
                stats[(chart, metric, a_name)] = (xa.mean(), xb.mean(), p)
                tests.append({"Chart": CHART_LABELS[chart], "Metric": label, "Comparison": f"{a_name} vs {b_name}",
                              "Bulletins": f"{len(xa)} vs {len(xb)}", "Mean": f"{fmt(xa.mean())} vs {fmt(xb.mean())}",
                              "Mann–Whitney p": p_text(p)})
    table_tests = pd.DataFrame(tests)

    # The quarter pattern depends on the era: before FY2022 most series advanced in almost every bulletin.
    b["fy"] = b.month.dt.year + (b.month.dt.month >= 10)
    era_rows, era = [], {}
    for chart in CHART_LABELS:
        for name, mask in (("FY2011–FY2021", b.fy <= 2021), ("FY2022–FY2027", b.fy >= 2022)):
            s = b[(b.chart == chart) & mask]
            q, n, o = (s[s.group == g] for g in ("Jan/Apr/Jul", "Other months", "Oct"))
            p_adv = mannwhitneyu(q.adv, n.adv, alternative="two-sided").pvalue
            p_net = mannwhitneyu(q.net.dropna(), n.net.dropna(), alternative="two-sided").pvalue
            era[(chart, name)] = (q.adv.mean(), n.adv.mean(), p_adv)
            era_rows.append({"Chart": CHART_LABELS[chart], "Era": name if chart == "final_action" else
                             name.replace("FY2011", "FY2016"), "Bulletins (Jan/Apr/Jul vs other)": f"{len(q)} vs {len(n)}",
                             "Advancing: Oct": pct(o.adv.mean()),
                             "Advancing: Jan/Apr/Jul vs other": f"{pct(q.adv.mean())} vs {pct(n.adv.mean())}",
                             "p (advancing)": p_text(p_adv),
                             "Mean move (mo): Oct": f"{o.net.mean():.2f}",
                             "Mean move (mo): Jan/Apr/Jul vs other": f"{q.net.mean():.2f} vs {n.net.mean():.2f}",
                             "p (move)": p_text(p_net)})
    table_era = pd.DataFrame(era_rows)
    early_fad, late_fad = era[("final_action", "FY2011–FY2021")], era[("final_action", "FY2022–FY2027")]
    early_dff, late_dff = era[("date_for_filing", "FY2011–FY2021")], era[("date_for_filing", "FY2022–FY2027")]

    # Family vs employment.
    e = events.assign(adv=events.direction == "advance", group=events.fy_month.map(group_of),
                      size=np.where(events.dated & (events.delta_days > 0), months(events.delta_days), np.nan))
    pref_rows = []
    for chart in CHART_LABELS:
        for pref in ("family", "employment"):
            sub = e[(e.chart == chart) & (e.preference == pref)]
            row = {"Chart": CHART_LABELS[chart], "Preference": pref.title()}
            for g in GROUPS:
                row[f"Advancing · {g}"] = pct(sub[sub.group == g].adv.mean())
            for g in GROUPS:
                row[f"Median advance (mo) · {g}"] = f"{sub[sub.group == g]['size'].median():.1f}"
            pref_rows.append(row)
    table_pref = pd.DataFrame(pref_rows)
    size_med = {(c, p, g): e[(e.chart == c) & (e.preference == p) & (e.group == g)]["size"].median()
                for c in CHART_LABELS for p in ("family", "employment") for g in GROUPS}

    fwd_oct = {}
    for chart in CHART_LABELS:
        fwd = events[(events.chart == chart) & events.dated & (events.delta_days > 0)]
        fwd_oct[chart] = fwd[fwd.fy_month == 1].delta_days.sum() / fwd.delta_days.sum()

    fad_oct = stats[("final_action", "net", "Oct")]
    dff_oct = stats[("date_for_filing", "net", "Oct")]
    fad_q = stats[("final_action", "adv", "Jan/Apr/Jul")]
    dff_q = stats[("date_for_filing", "adv", "Jan/Apr/Jul")]
    fad_oct_adv = stats[("final_action", "adv", "Oct")]
    dff_oct_adv = stats[("date_for_filing", "adv", "Oct")]
    verdicts = {
        "2a": ("Partly supported",
               f"October carries {pct(fwd_oct['final_action'])} (FAD) and {pct(fwd_oct['date_for_filing'])} (DFF) of all "
               f"forward movement, and FAD moves {fad_oct[0]:.1f} vs {fad_oct[1]:.1f} months per series. The leap is an "
               "employment effect; family final action does not jump in October."),
        "2b": ("Supported, mainly since FY2022",
               f"Jan/Apr/Jul bulletins advance more often than non-quarter months: FAD {pct(fad_q[0])} vs {pct(fad_q[1])} "
               f"(p = {p_text(fad_q[2])}), DFF {pct(dff_q[0])} vs {pct(dff_q[1])} (p = {p_text(dff_q[2])}). The gap is "
               f"large from FY2022 on (FAD {pct(late_fad[0])} vs {pct(late_fad[1])}) and weak before."),
    }
    report = f"""
# Statement 2 — Fiscal-year leaps and quarter-start advances

> *Both date for filing and final action dates usually leap forward by a lot at the beginning of a fiscal year
> and more likely to move forward at the beginning of each quarter.*

| Claim | Verdict | Evidence |
|---|---|---|
| **2a.** Both charts leap forward by a lot at the start of the fiscal year (October bulletin) | **{verdicts['2a'][0]}** | {verdicts['2a'][1]} |
| **2b.** Both charts are more likely to advance at the start of each quarter | **{verdicts['2b'][0]}** | {verdicts['2b'][1]} |

Data: {len(events):,} distinct month-over-month moves: final action Feb 2011 – Nov 2026 and dates for filing
Nov 2015 – Nov 2026. See the [method notes](../README.md#method).

The State Department fiscal year starts on October 1, and annual visa numbers reset then. Quarters start in
October, January, April and July. Each bulletin is treated as one observation in the tests, because all series
in a bulletin are set together.

## 2a. Leaps at the start of the fiscal year

October is not unusual for *how often* final action advances. {pct(fad_oct_adv[0])} of series advance in an
average October, against {pct(fad_oct_adv[1])} in other months (p = {p_text(fad_oct_adv[2])}). What changes is *how
far* they move:

- **Final action** moves on average **{fad_oct[0]:.1f} months per series in October**, against {fad_oct[1]:.1f} in
  other months (p = {p_text(fad_oct[2])}).
- **Dates for filing** moves **{dff_oct[0]:.1f} vs {dff_oct[1]:.1f} months**. That gap is not significant with only
  11 October bulletins (p = {p_text(dff_oct[2])}). However, DFF is clearly more *likely* to advance in October:
  {pct(dff_oct_adv[0])} vs {pct(dff_oct_adv[1])} (p = {p_text(dff_oct_adv[2])}).
- **October alone carries {pct(fwd_oct['final_action'], 1)} of all final-action forward movement** and
  {pct(fwd_oct['date_for_filing'], 1)} of dates-for-filing movement, roughly three times the 8.3% expected from
  one month in twelve.

![Net movement by month]({figs['net']})

The leap is concentrated in **employment** categories:

- Employment final action: the median October advance is {size_med[('final_action', 'employment', 'Oct')]:.1f} months,
  against {size_med[('final_action', 'employment', 'Other months')]:.1f} in other months.
- Employment dates for filing: {size_med[('date_for_filing', 'employment', 'Oct')]:.1f} vs
  {size_med[('date_for_filing', 'employment', 'Other months')]:.1f}.
- Family final action has **no** October leap: {size_med[('final_action', 'family', 'Oct')]:.1f} vs
  {size_med[('final_action', 'family', 'Other months')]:.1f}. Family cutoffs mostly creep forward about a month
  at a time, in most bulletins.

![Advance size by month]({figs['size']})

{md_table(table_pref)}

## 2b. Advances at the start of each quarter

![Advance share by month]({figs['share']})

On both charts, the quarter-start bulletins (Jan, Apr, Jul) advance more often than non-quarter months:

- **Final action:** October has a similar advance rate to the other quarter starts, and the two weakest months
  are the last two of the fiscal year (Aug, Sep), when annual limits bind.
- **Dates for filing:** the pattern is noisier. May is as active as the quarter starts, while January is
  quiet.

{md_table(table_tests)}

{md_table(table_month)}

### The quarter effect is mostly a post-FY2022 pattern

The heatmaps show a regime change in final action:

- **Through FY2021**, most series advanced in almost every bulletin, so there was little room for quarter
  starts to stand out.
- **From FY2022**, movement became much sparser, and the Oct/Jan/Apr/Jul columns stand out (with exceptions
  such as May in FY2025).

![Advance heatmaps]({figs['heat']})

Splitting the bulletins at FY2022 confirms this:

- **Final action:** quarter-start bulletins advance {pct(late_fad[0])} vs {pct(late_fad[1])} from FY2022
  (p = {p_text(late_fad[2])}), against {pct(early_fad[0])} vs {pct(early_fad[1])} before (p = {p_text(early_fad[2])}).
- **Dates for filing:** {pct(late_dff[0])} vs {pct(late_dff[1])} from FY2022 (p = {p_text(late_dff[2])}), against
  {pct(early_dff[0])} vs {pct(early_dff[1])} before (p = {p_text(early_dff[2])}).

The October leap in movement size appears in both eras.

{md_table(table_era)}

## Conclusion

- **Fiscal-year leap: partly true.** October brings the largest moves of the year for *employment* cutoffs on
  both charts, and for dates for filing it is also the month most likely to move. It is not a "leap" for
  family final action, which advances by about the same small amount in most months.
- **Quarter-start advances: true, mainly since FY2022.** Over the whole period, quarter-start bulletins
  advance 10–12 percentage points more often than other months on both charts. The gap comes almost entirely
  from FY2022 onward, when movement became sparse and roughly doubled at quarter starts. Before that it was
  weak or absent. May, for dates for filing, is the main exception.

## Caveats

- There are only 11–16 bulletins per calendar month, so per-month estimates are noisy (see the whiskers).
- Size statistics use date-to-date moves only. A jump to Current counts as an advance but has no defined size.
- Retrogressions count as negative movement. Final-action retrogressions cluster in Jun–Sep, when annual
  limits bind, which pulls those months' means down; for example, the June mean is negative. Dates-for-filing
  retrogressions cluster in October.
"""
    write_report(FOLDER, report)
    return {"folder": FOLDER.name, "verdicts": verdicts}


if __name__ == "__main__":
    df = load_frame()
    print(run(df, movements(df)))
