"""Statement 1: dates for filing run ahead of final action, advance at the start of the fiscal
year and stop advancing at its end."""
from __future__ import annotations

from common import *
from scipy.stats import mannwhitneyu

FOLDER = ANALYSIS / "01-filing-vs-final-action"
RELATIONS = [("DFF later", BLUE), ("Same date", GRAY), ("Both current", "#dddcd5"), ("DFF earlier", RED)]


def paired(df):
    """Same series and bulletin month in both charts, with the filing lead in days."""
    keys = ["preference", "category", "area", "month"]
    usable = df[df.status.isin(["date", "current"])]
    fad = usable[usable.chart == "final_action"].set_index(keys)[["status", "cutoff"]]
    dff = usable[usable.chart == "date_for_filing"].set_index(keys)[["status", "cutoff"]]
    pairs = fad.join(dff, how="inner", lsuffix="_fad", rsuffix="_dff").reset_index()
    pairs["lead_days"] = (pairs.cutoff_dff - pairs.cutoff_fad).dt.days
    both_current = (pairs.status_fad == "current") & (pairs.status_dff == "current")
    pairs["relation"] = np.select([both_current, pairs.lead_days > 0, pairs.lead_days == 0],
                                  ["Both current", "DFF later", "Same date"], "DFF earlier")
    return pairs


def series_years(moves, chart, first_fy, last_fy):
    """One row per distinct series and complete fiscal year, listing the months that advanced."""
    sub = moves[(moves.chart == chart) & moves.fy.between(first_fy, last_fy)]
    rows = []
    for (pref, cat, area, fy), g in sub.groupby(["preference", "category", "area", "fy"]):
        g = g.sort_values("fy_month")
        rows.append(dict(preference=pref, category=cat, area=area, fy=fy,
                         signature=tuple(zip(g.fy_month, g.delta_days, g.status)),
                         advance_months=tuple(g.fy_month[g.direction == "advance"])))
    years = pd.DataFrame(rows).drop_duplicates(["preference", "category", "fy", "signature"])
    years["n_advances"] = years.advance_months.map(len)
    years["last_advance"] = years.advance_months.map(lambda m: max(m) if m else 0)
    return years


def bulletin_shares(events):
    """Share of distinct series that advanced in each bulletin (one observation per bulletin)."""
    return (events.assign(adv=events.direction == "advance")
            .groupby(["chart", "month", "fy_month"]).adv.mean().reset_index())


def fig_relation(pairs_d):
    order = ["All"] + CATEGORIES
    shares = {"All": pairs_d.relation.value_counts(normalize=True)}
    shares |= {c: g.relation.value_counts(normalize=True) for c, g in pairs_d.groupby("category")}
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    for y, cat in enumerate(order):
        left = 0
        for name, color in RELATIONS:
            w = shares[cat].get(name, 0)
            ax.barh(y, w, left=left, height=0.62, color=color, edgecolor=SURFACE, linewidth=1.5,
                    label=name if y == 0 else None)
            if name == "DFF later" and w > 0.12:
                ax.text(left + 0.012, y, pct(w), va="center", ha="left", color="white", fontsize=8.5,
                        fontweight="bold")
            left += w
    ax.set_yticks(range(len(order)), ["All categories"] + [CATEGORY_LABELS[c] for c in CATEGORIES])
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlim(0, 1)
    ax.grid(axis="y", visible=False)
    ax.set_title("Dates-for-filing cutoff compared with the final-action cutoff, same bulletin")
    ax.set_xlabel("Share of distinct bulletin pairs (Oct 2015 – Nov 2026)")
    ax.legend(ncol=4, loc="upper left", bbox_to_anchor=(0, -0.14), handlelength=1.2)
    return save(fig, FOLDER, "dff-vs-fad-relation.png")


def fig_lead(pairs):
    fig, axes = plt.subplots(3, 3, figsize=(10, 7.2), sharex=True)
    for ax, cat in zip(axes.flat, CATEGORIES):
        g = pairs[pairs.category == cat].groupby("month").lead_days
        mid, lo, hi = (months(g.median()), months(g.min()), months(g.max()))
        ax.fill_between(mid.index, lo, hi, color=BLUE, alpha=0.16, linewidth=0)
        ax.plot(mid.index, mid, color=BLUE, linewidth=1.6)
        ax.axhline(0, color=INK_2, linewidth=0.8)
        ax.set_title(CATEGORY_LABELS[cat], fontsize=10)
        ax.tick_params(axis="x", labelrotation=0)
    for ax in axes[:, 0]:
        ax.set_ylabel("Filing lead (months)")
    fig.suptitle("Dates-for-filing lead over final action: median of the five areas (line) and range (band)",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.text(0.01, -0.01, "Lead = DFF cutoff − FAD cutoff; a Current cutoff is placed at the bulletin month. "
             "Above zero means dates for filing is ahead.", fontsize=8.5, color=INK_2)
    fig.tight_layout()
    return save(fig, FOLDER, "dff-lead-over-time.png")


def fig_advance_by_month(events):
    fig, ax = plt.subplots(figsize=(9, 4))
    x = np.arange(12)
    for offset, chart in ((-0.2, "final_action"), (0.2, "date_for_filing")):
        g = events[events.chart == chart].groupby("fy_month").direction
        k, n = g.apply(lambda d: (d == "advance").sum()), g.size()
        lo, hi = wilson(k, n)
        p = k / n
        ax.bar(x + offset, p, width=0.38, color=CHART_COLORS[chart], label=CHART_LABELS[chart],
               edgecolor=SURFACE, linewidth=1)
        ax.errorbar(x + offset, p, yerr=[p - lo, hi - p], fmt="none", ecolor=INK_2, elinewidth=0.8, capsize=0)
    ax.set_xticks(x, FISCAL_MONTHS)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_ylim(0, 1)
    ax.grid(axis="x", visible=False)
    ax.set_title("Share of distinct series whose cutoff advanced, by bulletin month (fiscal-year order)")
    ax.set_xlabel("Bulletin month (fiscal year starts in October) · whiskers: 95% Wilson interval")
    ax.legend(loc="upper right", ncol=2)
    return save(fig, FOLDER, "advance-share-by-fiscal-month.png")


def fig_dff_heatmap(events):
    fig, ax = plt.subplots(figsize=(8, 5))
    im = heatmap(ax, events, "date_for_filing")
    ax.set_title("Dates for filing: share of distinct series advancing, per bulletin")
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02, format=matplotlib.ticker.PercentFormatter(1.0))
    cb.outline.set_visible(False)
    ax.set_xlabel("Bulletin month · hatched = no data (filing charts start Oct 2015; data end Nov 2026)")
    return save(fig, FOLDER, "dff-advance-heatmap.png")


def fig_last_advance(years):
    fig, ax = plt.subplots(figsize=(9, 3.8))
    x = np.arange(13)
    labels = ["None"] + FISCAL_MONTHS
    for offset, chart in ((-0.2, "final_action"), (0.2, "date_for_filing")):
        y = years[years.chart == chart].last_advance.value_counts(normalize=True).reindex(range(13), fill_value=0)
        ax.bar(x + offset, y.values, width=0.38, color=CHART_COLORS[chart], label=CHART_LABELS[chart],
               edgecolor=SURFACE, linewidth=1)
    ax.set_xticks(x, labels)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.grid(axis="x", visible=False)
    ax.set_title("Month of the last advance within each fiscal year (distinct series-years)")
    ax.set_xlabel("Fiscal month of the year's last advance · 'None' = no advance all year")
    ax.legend(loc="upper left")
    return save(fig, FOLDER, "last-advance-month.png")


def run(df, moves):
    style()
    events = distinct(moves)
    pairs = paired(df)
    pairs_d = pairs.drop_duplicates(["preference", "category", "month", "status_fad", "cutoff_fad",
                                     "status_dff", "cutoff_dff"])
    # --- 1a: is DFF ahead of FAD?
    rel = pairs_d.relation.value_counts(normalize=True)
    by_cat = (pairs_d.groupby("category").relation.value_counts(normalize=True).unstack(fill_value=0)
              .reindex(CATEGORIES))
    dated = pairs_d[(pairs_d.status_fad == "date") & (pairs_d.status_dff == "date")]
    lead = dated.groupby("category").lead_days.median().reindex(CATEGORIES)
    table_1a = pd.DataFrame({
        "Category": [CATEGORY_LABELS[c] for c in CATEGORIES],
        "Distinct pairs": pairs_d.groupby("category").size().reindex(CATEGORIES).values,
        **{name: [pct(v, 1) for v in by_cat.get(name, pd.Series(0, index=CATEGORIES))] for name, _ in RELATIONS},
        "Median lead when both dated (months)": months(lead).round(1).values,
    })
    # --- 1b/1c: when does DFF advance?
    dff_ev = events[events.chart == "date_for_filing"]
    fad_ev = events[events.chart == "final_action"]
    by_month = []
    forward = dff_ev[dff_ev.dated & (dff_ev.delta_days > 0)].groupby("fy_month").delta_days.sum()
    for m in range(1, 13):
        d, f = dff_ev[dff_ev.fy_month == m], fad_ev[fad_ev.fy_month == m]
        by_month.append({"Bulletin month": FISCAL_MONTHS[m - 1], "DFF events": len(d),
                         "DFF advance": pct((d.direction == "advance").mean(), 1),
                         "DFF hold": pct((d.direction == "hold").mean(), 1),
                         "DFF retrogress": pct((d.direction == "retrogress").mean(), 1),
                         "Share of all DFF forward movement": pct(forward.get(m, 0) / forward.sum(), 1),
                         "FAD advance (reference)": pct((f.direction == "advance").mean(), 1)})
    table_month = pd.DataFrame(by_month)
    dff_adv = dff_ev[dff_ev.direction == "advance"]
    oct_share_of_advances = (dff_adv.fy_month == 1).mean()
    oct_forward = forward.get(1, 0) / forward.sum()
    p_dff = dff_ev.assign(adv=dff_ev.direction == "advance").groupby("fy_month").adv.mean()

    # Complete fiscal years: DFF Oct 2016 – Sep 2026 (Oct 2015 has no prior bulletin), FAD FY2012 – FY2026.
    years = pd.concat([series_years(moves, "date_for_filing", 2017, 2026).assign(chart="date_for_filing"),
                       series_years(moves, "final_action", 2012, 2026).assign(chart="final_action")])
    dy = years[years.chart == "date_for_filing"]
    moving = dy[dy.n_advances > 0]
    only_oct = moving.advance_months.map(lambda m: set(m) <= {1}).mean()
    only_q1 = moving.advance_months.map(lambda m: set(m) <= {1, 2, 3}).mean()
    with_oct = moving.advance_months.map(lambda m: 1 in m).mean()
    last_q4 = (moving.last_advance >= 10).mean()
    last_sep = (moving.last_advance == 12).mean()
    fad_last_q4 = (years[(years.chart == "final_action") & (years.n_advances > 0)].last_advance >= 10).mean()
    table_years = pd.DataFrame([
        {"Measure (DFF, distinct series-years FY2017–FY2026)": "Series-years", "Value": f"{len(dy)}"},
        {"Measure (DFF, distinct series-years FY2017–FY2026)": "No advance at all during the year",
         "Value": pct((dy.n_advances == 0).mean(), 1)},
        {"Measure (DFF, distinct series-years FY2017–FY2026)": "Median advancing bulletins per year (years with ≥1 advance)",
         "Value": f"{moving.n_advances.median():.0f} of 12"},
        {"Measure (DFF, distinct series-years FY2017–FY2026)": "Advanced in October (years with ≥1 advance)",
         "Value": pct(with_oct, 1)},
        {"Measure (DFF, distinct series-years FY2017–FY2026)": "Advanced **only** in October",
         "Value": pct(only_oct, 1)},
        {"Measure (DFF, distinct series-years FY2017–FY2026)": "Advanced only in Oct–Dec (fiscal Q1)",
         "Value": pct(only_q1, 1)},
        {"Measure (DFF, distinct series-years FY2017–FY2026)": "Last advance in Jul–Sep (fiscal Q4)",
         "Value": pct(last_q4, 1)},
        {"Measure (DFF, distinct series-years FY2017–FY2026)": "Last advance in September",
         "Value": pct(last_sep, 1)},
    ])

    shares = bulletin_shares(dff_ev)
    oct_b, rest_b = shares[shares.fy_month == 1].adv, shares[shares.fy_month != 1].adv
    q4_b, mid_b = shares[shares.fy_month >= 10].adv, shares[shares.fy_month.between(2, 9)].adv
    p_oct = mannwhitneyu(oct_b, rest_b, alternative="two-sided").pvalue
    p_q4 = mannwhitneyu(q4_b, mid_b, alternative="two-sided").pvalue
    sep_b = shares[shares.fy_month == 12].adv
    p_sep = mannwhitneyu(sep_b, mid_b, alternative="two-sided").pvalue
    table_tests = pd.DataFrame([
        {"Comparison (DFF bulletins)": "October vs all other months", "Bulletins": f"{len(oct_b)} vs {len(rest_b)}",
         "Mean share advancing": f"{pct(oct_b.mean())} vs {pct(rest_b.mean())}", "Mann–Whitney p": p_text(p_oct)},
        {"Comparison (DFF bulletins)": "Jul–Sep (fiscal Q4) vs Nov–Jun", "Bulletins": f"{len(q4_b)} vs {len(mid_b)}",
         "Mean share advancing": f"{pct(q4_b.mean())} vs {pct(mid_b.mean())}", "Mann–Whitney p": p_text(p_q4)},
        {"Comparison (DFF bulletins)": "September vs Nov–Jun", "Bulletins": f"{len(sep_b)} vs {len(mid_b)}",
         "Mean share advancing": f"{pct(sep_b.mean())} vs {pct(mid_b.mean())}", "Mann–Whitney p": p_text(p_sep)},
    ])

    figs = dict(relation=fig_relation(pairs_d), lead=fig_lead(pairs), month=fig_advance_by_month(events),
                heat=fig_dff_heatmap(events), last=fig_last_advance(years))
    f2a = pairs_d[(pairs_d.relation == "DFF earlier") & (pairs_d.category == "F2A")]
    f2a_first, f2a_last, f2a_n = f2a.month.min(), f2a.month.max(), len(f2a)
    ahead = rel.get("DFF later", 0)
    no_lead = rel.get("Same date", 0) + rel.get("Both current", 0)
    behind = rel.get("DFF earlier", 0)
    top3 = p_dff.sort_values(ascending=False).index[:4]
    top_text = ", ".join(f"{FISCAL_MONTHS[m - 1]} ({pct(p_dff[m])})" for m in top3)
    low3 = p_dff.sort_values().index[:3]
    low_text = ", ".join(f"{FISCAL_MONTHS[m - 1]} ({pct(p_dff[m])})" for m in low3)

    verdicts = {
        "1a": ("Supported", f"DFF is later than FAD in {pct(ahead)} of distinct pairs and earlier in only {pct(behind, 1)}."),
        "1b": ("Not supported", f"October is the most likely month for DFF to advance, but only {pct(oct_share_of_advances)} "
                                f"of DFF advances happen in October and only {pct(only_oct)} of moving series-years advance only then."),
        "1c": ("Not supported", f"{pct(last_q4)} of moving series-years still advance in Jul–Sep, July is among the "
                                f"busiest months, and September ({pct(p_dff[12])}) is not significantly slower than mid-year."),
    }
    report = f"""
# Statement 1 — Dates for filing vs final action, and when dates for filing move

> *The date for filing cutoff date is usually ahead of the final action date and usually progresses only at
> the beginnings of each fiscal year. It usually stops progressing at the end of the fiscal years.*

The statement makes three separate claims, tested one at a time:

| Claim | Verdict | Evidence |
|---|---|---|
| **1a.** Dates for filing (DFF) is usually ahead of final action (FAD) | **{verdicts['1a'][0]}** | {verdicts['1a'][1]} |
| **1b.** DFF usually progresses only at the beginning of the fiscal year | **{verdicts['1b'][0]}** | {verdicts['1b'][1]} |
| **1c.** DFF usually stops progressing at the end of the fiscal year | **{verdicts['1c'][0]}** | {verdicts['1c'][1]} |

Data: {len(pairs_d):,} distinct DFF/FAD bulletin pairs and {len(dff_ev):,} distinct DFF month-over-month moves
(Oct 2015 – Nov 2026), across the categories and areas listed in the [method notes](../README.md#method).
"Distinct" means areas publishing the identical cutoff (for example Mexico and "all other areas" for most EB
categories) are counted once per bulletin.

## 1a. Dates for filing is ahead of final action

![DFF vs FAD relation by category]({figs['relation']})

Across all distinct pairs, DFF is **later (ahead) in {pct(ahead, 1)}**, identical or both Current in
{pct(no_lead, 1)}, and **earlier in only {pct(behind, 1)}**.

- **No lead:** almost all of these are months when *both* charts were Current, mostly EB1 ({pct(by_cat.loc['EB1'].get('Both current', 0))} of
  EB1 pairs) and EB2 ({pct(by_cat.loc['EB2'].get('Both current', 0))}). A shared non-Current date is very rare
  ({pct(rel.get('Same date', 0), 1)}).
- **DFF earlier:** this is mostly F2A between {f2a_first:%b %Y} and {f2a_last:%b %Y}
  ({f2a_n} of {len(pairs_d[pairs_d.relation == 'DFF earlier'])} cases). In those months F2A *final action* was
  Current while the filing chart kept a date.
- **F1, F2B, F3, F4:** DFF is ahead in essentially every bulletin.

{md_table(table_1a)}

The lead is not constant. It widens and narrows as the State Department moves the two charts. Apart from F2A
during 2019–2022, the median lead stays at or above zero. Two other features stand out:

- **Employment leads collapse to zero** when categories become Current in both charts.
- **Family leads shrink sharply from Sep 2026.** In the latest bulletins, the family filing dates sit only
  about 10 days ahead of final action (for example F1 "all other areas": 01FEB20 vs 22JAN20).

![DFF lead over time]({figs['lead']})

## 1b. Does DFF progress only at the beginning of the fiscal year?

October *is* special:

- It is the month in which DFF is most likely to advance.
- It carries {pct(oct_forward, 1)} of all DFF forward movement, about three times the 8.3% expected if movement
  were spread evenly.
- It is also when most DFF retrogressions happen: {pct((dff_ev[dff_ev.direction == 'retrogress'].fy_month == 1).mean())} of
  all DFF retrogressions are in October.

But DFF also advances regularly in other months. The four most active are {top_text}, and only
{pct(oct_share_of_advances, 1)} of all DFF advances happen in October.

![Advance share by fiscal month]({figs['month']})

{md_table(table_month)}

Looking at each series one fiscal year at a time makes the same point. Among series-years in which DFF moved at
all, **{pct(only_oct, 1)} advanced only in October**, and {pct(only_q1, 1)} advanced only in fiscal Q1. October
was part of the year's movement in {pct(with_oct, 1)} of them.

{md_table(table_years)}

The heatmap shows that DFF movement varies a lot from year to year:

- **October is dark in many years** (FY2017–FY2020, FY2025–FY2026) but quiet in FY2022–FY2024.
- **FY2019–FY2021 advanced through most of the year.**
- **Several years have their busiest bulletin in spring or summer,** for example May in FY2017 and Jul in FY2018.

![DFF advance heatmap]({figs['heat']})

## 1c. Does DFF stop progressing at the end of the fiscal year?

The least active DFF months are {low_text}: the two months right after October, plus September.

- **September** is slightly slower than mid-year (Nov–Jun), but the difference is not statistically
  distinguishable (table below).
- **July and August** are among the more active DFF months.
- **{pct(last_q4, 1)} of moving series-years make their last advance in fiscal Q4** (Jul–Sep), and
  {pct(last_sep, 1)} advance in the very last bulletin, September. Final action does this even more
  ({pct(fad_last_q4, 1)} last advance in Q4).

![Last advance month]({figs['last']})

The tests treat each bulletin as one observation (the share of distinct series that advanced), because the
series in one bulletin are set together and are not independent:

{md_table(table_tests)}

## Conclusion

- **DFF ahead of FAD: yes.** This is the most robust part of the statement.
- **DFF moves "only" at the start of the fiscal year: no.** October is the single biggest month for DFF
  movement, but most DFF movement happens in other bulletins, especially Apr, May and Jul.
- **DFF stops at the end of the fiscal year: no.** Most moving series-years still advance in Jul–Sep, and
  September is not significantly quieter than mid-year. The real lull is November–December, right after the
  October reset.

## Caveats

- DFF charts begin in October 2015, so there are only 10 complete fiscal years of DFF data (FY2017–FY2026).
- USCIS decides each month which chart applies to adjustment-of-status filings. This analysis looks at the
  published cutoffs only.
- A move to or from Current counts as an advance or retrogression. Its size uses the bulletin month as the
  effective cutoff (the dashboard's convention), so tables of distances use date-to-date moves only.
"""
    write_report(FOLDER, report)
    return {"folder": FOLDER.name, "verdicts": verdicts}


if __name__ == "__main__":
    df = load_frame()
    print(run(df, movements(df)))
