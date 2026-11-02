"""Statement 3: cutoff dates move more quickly while EB2 and EB3 are inverted (EB3 later than EB2,
as computed by the dashboard's shading.inversion_intervals)."""
from __future__ import annotations

from common import *

FOLDER = ANALYSIS / "03-inversion-speed"
EB = ["EB2", "EB3"]
EB_COLORS = {"EB2": BLUE, "EB3": ORANGE}
LABELINGS = {"before": ("prev_month", "Inversion in the bulletin before the move"),
             "after": ("month", "Inversion in the bulletin after the move")}
MIN_SHIFT = 12  # months; smaller circular shifts barely change the labels


def inversion_months(rows):
    """{(chart, area): set of inverted bulletin months}, straight from the dashboard's rule."""
    out = {}
    for chart in CHART_LABELS:
        for area in AREAS:
            out[(chart, area)] = {m for s, e in inversion_intervals(rows, chart, area)
                                  for m in pd.date_range(s, e, freq="MS", inclusive="left")}
    return out


def eb_moves(moves, inverted):
    ev = moves[(moves.preference == "employment") & moves.category.isin(EB)].copy()
    for name, (col, _) in LABELINGS.items():
        ev[f"inv_{name}"] = [m in inverted[(c, a)] for c, a, m in zip(ev.chart, ev.area, ev[col])]
    ev["move_mo"] = np.where(ev.dated, months(ev.delta_days), np.nan)
    ev["adv"] = ev.direction == "advance"
    return ev


def summarize(ev, label):
    """Inverted vs not, after collapsing areas that share the identical move and label."""
    d = distinct(ev, extra=(label,))
    g = d.groupby(label)
    return pd.DataFrame({"n": g.size(), "adv": g.adv.mean(), "mean": g.move_mo.mean(), "median": g.move_mo.median()})


def diffs(ev, label):
    s = summarize(ev, label)
    if True not in s.index or False not in s.index:
        return np.nan, np.nan
    return s.loc[True, "mean"] - s.loc[False, "mean"], s.loc[True, "adv"] - s.loc[False, "adv"]


def shift_test(ev, inverted, label):
    """Circular-shift permutation test. Each chart/area inversion timeline is rotated by the same
    k months (k ≥ MIN_SHIFT), which keeps the length and clustering of inversion runs but breaks
    their alignment with the cutoff moves. Returns observed differences, null draws and p-values."""
    col = LABELINGS[label][0]
    timeline = pd.date_range(ev.month.min() - pd.DateOffset(months=1), ev.month.max(), freq="MS")
    T = len(timeline)
    pos = {m: i for i, m in enumerate(timeline)}
    ind = {key: np.array([m in months_set for m in timeline]) for key, months_set in inverted.items()}
    t_idx = ev[col].map(pos).to_numpy()
    keys = list(zip(ev.chart, ev.area))
    observed = diffs(ev, f"inv_{label}")
    null = []
    for k in range(MIN_SHIFT, T - MIN_SHIFT + 1):
        shifted = np.array([ind[key][(t - k) % T] for key, t in zip(keys, t_idx)])
        null.append(diffs(ev.assign(shifted=shifted), "shifted"))
    null = np.array(null, float)
    p = [(1 + np.sum(np.abs(null[:, j]) >= abs(observed[j]))) / (1 + np.sum(~np.isnan(null[:, j])))
         for j in range(2)]
    return observed, null, p


def episode_moves(moves, rows):
    """How EB2 and EB3 moved in the bulletin where each inversion episode started and ended."""
    eb = moves[(moves.preference == "employment") & moves.category.isin(EB)].set_index(
        ["chart", "area", "category", "month"]).direction
    out = []
    for chart in CHART_LABELS:
        for area in AREAS:
            for s, e in inversion_intervals(rows, chart, area):
                for when, m in (("start", pd.Timestamp(s)), ("end", pd.Timestamp(e))):
                    out.append({"when": when, **{cat: eb.get((chart, area, cat, m), "n/a") for cat in EB}})
    return pd.DataFrame(out)


def boot_mean(values, reps=3000, seed=11):
    values = np.asarray(pd.Series(values).dropna())
    rng = np.random.default_rng(seed)
    draws = rng.choice(values, (reps, len(values))).mean(axis=1)
    return np.percentile(draws, [2.5, 97.5])


def fig_timelines(df, inverted):
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True)
    for r, area in enumerate(["china_mainland_born", "india"]):
        for c, chart in enumerate(CHART_LABELS):
            ax = axes[r, c]
            for m in sorted(inverted[(chart, area)]):
                ax.axvspan(m, m + pd.DateOffset(months=1), color=VIOLET, alpha=0.13, linewidth=0)
            for cat in EB:
                s = df[(df.chart == chart) & (df.area == area) & (df.category == cat)].set_index("month").sort_index()
                ax.plot(s.index, s.cutoff, color=EB_COLORS[cat], linewidth=1.6, label=cat)
            ax.set_title(f"{AREA_LABELS[area]} · {CHART_LABELS[chart]}", fontsize=10)
            ax.yaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
        axes[r, 0].set_ylabel("Cutoff date")
    handles = [matplotlib.lines.Line2D([], [], color=EB_COLORS[c], linewidth=2, label=c) for c in EB]
    handles.append(matplotlib.patches.Patch(color=VIOLET, alpha=0.25, label="EB inversion (EB3 later than EB2)"))
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.01, 0.955), ncol=3, frameon=False)
    fig.suptitle("EB2 and EB3 cutoffs with the dashboard's inversion months shaded (Current plotted at the bulletin month)",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return save(fig, FOLDER, "inversion-timelines.png")


def fig_speed(ev):
    groups = [(chart, cat) for chart in CHART_LABELS for cat in EB]
    fig, axes = plt.subplots(2, 2, figsize=(11, 6.4), sharey=True)
    for r, label in enumerate(LABELINGS):
        for c, (metric, title) in enumerate((("adv", "Share advancing"), ("move_mo", "Mean move (months)"))):
            ax = axes[r, c]
            for y, (chart, cat) in enumerate(groups):
                d = distinct(ev[(ev.chart == chart) & (ev.category == cat)], extra=(f"inv_{label}",))
                for state, color, dy in ((False, GRAY, 0.14), (True, VIOLET, -0.14)):
                    vals = d[d[f"inv_{label}"] == state][metric].astype(float)
                    lo, hi = boot_mean(vals)
                    ax.plot([lo, hi], [y + dy] * 2, color=color, linewidth=1.4, solid_capstyle="round")
                    ax.plot(vals.mean(), y + dy, "o", color=color, markersize=7, markeredgecolor=SURFACE,
                            markeredgewidth=1.5, label=("Inverted" if state else "Not inverted") if y == 0 else None)
            ax.set_yticks(range(len(groups)), [f"{CHART_LABELS[ch]} · {cat}" for ch, cat in groups])
            ax.invert_yaxis()
            ax.grid(axis="y", visible=False)
            if metric == "adv":
                ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
            else:
                ax.axvline(0, color=AXIS, linewidth=0.8)
            ax.set_title(f"{title} · state {label} the move" + (" (primary)" if label == "before" else ""),
                         fontsize=9.5)
    axes[0, 0].legend(loc="lower left", fontsize=8.5)
    fig.suptitle("Movement while inverted vs not · dots: mean, bars: 95% bootstrap CI over moves",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return save(fig, FOLDER, "speed-inverted-vs-not.png")


def fig_null(results):
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), sharey=True)
    for ax, chart in zip(axes, CHART_LABELS):
        observed, null, p = results[(chart, "before")]
        ax.hist(null[:, 0], bins=30, color=GRAY, edgecolor=SURFACE, linewidth=0.8)
        ax.axvline(observed[0], color=VIOLET, linewidth=2)
        ax.text(observed[0], ax.get_ylim()[1] * 0.92, f"  observed {observed[0]:+.2f} mo\n  p = {p_text(p[0])}",
                color=INK, fontsize=8.5, va="top")
        ax.set_title(f"{CHART_LABELS[chart]} · EB2 + EB3", fontsize=10)
        ax.set_xlabel("Mean move while inverted − not inverted (months)")
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Circular shifts")
    axes[0].yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    fig.suptitle("Observed difference vs differences after rotating the inversion timeline by 12+ months",
                 x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return save(fig, FOLDER, "shift-test-null.png")


def run(df, moves):
    style()
    rows = load_data()
    inverted = inversion_months(rows)
    ev = eb_moves(moves, inverted)

    inv_table = pd.DataFrame([{"Area": AREA_LABELS[a], **{CHART_LABELS[c]: len(inverted[(c, a)]) for c in CHART_LABELS}}
                              for a in AREAS])
    n_bulletins = {c: df[df.chart == c].month.nunique() for c in CHART_LABELS}

    results, tables, S = {}, {}, {}
    for label in LABELINGS:
        out = []
        for chart in CHART_LABELS:
            for cats in (["EB2"], ["EB3"], EB):
                sub = ev[(ev.chart == chart) & ev.category.isin(cats)]
                s = summarize(sub, f"inv_{label}")
                observed, null, p = shift_test(sub, inverted, label)
                S[(label, chart, "+".join(cats))] = (s, p)
                if cats == EB:
                    results[(chart, label)] = (observed, null, p)
                out.append({"Chart": CHART_LABELS[chart], "Category": " + ".join(cats),
                            "Moves (inverted / not)": f"{s.loc[True, 'n']} / {s.loc[False, 'n']}",
                            "Advancing: inverted vs not": f"{pct(s.loc[True, 'adv'])} vs {pct(s.loc[False, 'adv'])}",
                            "Mean move (mo): inverted vs not": f"{s.loc[True, 'mean']:.2f} vs {s.loc[False, 'mean']:.2f}",
                            "Median move (mo): inverted vs not": f"{s.loc[True, 'median']:.2f} vs {s.loc[False, 'median']:.2f}",
                            "Shift-test p (mean move)": p_text(p[0]), "Shift-test p (advancing)": p_text(p[1])})
        tables[label] = pd.DataFrame(out)

    area_rows = []
    for chart in CHART_LABELS:
        for area in AREAS:
            sub = ev[(ev.chart == chart) & (ev.area == area)]
            g = sub.groupby("inv_before")
            if True not in g.groups:
                continue
            area_rows.append({"Chart": CHART_LABELS[chart], "Area": AREA_LABELS[area],
                              "Inverted months": len(inverted[(chart, area)]),
                              "Moves (inverted / not)": f"{g.size()[True]} / {g.size()[False]}",
                              "Advancing: inverted vs not": f"{pct(g.adv.mean()[True])} vs {pct(g.adv.mean()[False])}",
                              "Mean move (mo): inverted vs not": f"{g.move_mo.mean()[True]:.2f} vs {g.move_mo.mean()[False]:.2f}"})
    table_area = pd.DataFrame(area_rows)

    episodes = episode_moves(moves, rows)
    starts, ends = episodes[episodes.when == "start"], episodes[episodes.when == "end"]
    table_episodes = pd.DataFrame([
        {"Bulletin": "Inversion starts", "Episodes": len(starts),
         "EB3 advanced": int((starts.EB3 == "advance").sum()), "EB2 retrogressed": int((starts.EB2 == "retrogress").sum()),
         "EB2 advanced": int((starts.EB2 == "advance").sum()), "EB3 retrogressed": int((starts.EB3 == "retrogress").sum())},
        {"Bulletin": "Inversion ends", "Episodes": len(ends),
         "EB3 advanced": int((ends.EB3 == "advance").sum()), "EB2 retrogressed": int((ends.EB2 == "retrogress").sum()),
         "EB2 advanced": int((ends.EB2 == "advance").sum()), "EB3 retrogressed": int((ends.EB3 == "retrogress").sum())},
    ])

    figs = dict(timeline=fig_timelines(df, inverted), speed=fig_speed(ev), null=fig_null(results))

    def cell(label, chart, cats, state, stat):
        return S[(label, chart, cats)][0].loc[state, stat]

    def pv(label, chart, cats, j=0):
        return p_text(S[(label, chart, cats)][1][j])

    fad, dff = "final_action", "date_for_filing"
    verdicts = {"3": ("Not supported",
                      f"While inverted, EB2 + EB3 final-action cutoffs move {cell('before', fad, 'EB2+EB3', True, 'mean'):.2f} "
                      f"months per bulletin vs {cell('before', fad, 'EB2+EB3', False, 'mean'):.2f} otherwise (slower, borderline "
                      f"p = {pv('before', fad, 'EB2+EB3')}); dates for filing shows no difference "
                      f"({cell('before', dff, 'EB2+EB3', True, 'mean'):.2f} vs {cell('before', dff, 'EB2+EB3', False, 'mean'):.2f}).")}
    report = f"""
# Statement 3 — Do cutoffs move faster during an EB2/EB3 inversion?

> *Cutoff dates tend to move more quickly when there is EB2 EB3 inversion (as computed in the code).*

| Claim | Verdict | Evidence |
|---|---|---|
| **3.** EB cutoffs move faster while EB3 is ahead of EB2 | **{verdicts['3'][0]}** | {verdicts['3'][1]} |

## What counts as an inversion

Inversion months come straight from the dashboard's `shading.inversion_intervals()`:

- **Inverted:** for a given chart type and area, EB3's cutoff is strictly later than EB2's, or EB3 is Current
  while EB2 has a date.
- **Not inverted:** both Current, equal dates, or missing/unavailable cutoffs.

Inversions are concentrated in China and India. The other three areas had only a few short episodes
(2016–2018 and 2022–2024):

{md_table(inv_table)}

*Inverted bulletin months, out of {n_bulletins['final_action']} final-action and {n_bulletins['date_for_filing']}
dates-for-filing bulletins.*

![Inversion timelines]({figs['timeline']})

## How speed is measured

- **Moves:** each month-over-month change in the EB2 and EB3 cutoffs of the five areas.
- **Metrics:** the share of moves that advance (including jumps to Current) and the mean and median size of
  date-to-date moves in months. Holds count as 0 and retrogressions as negative.
- **Labeling:** a move is "inverted" if the inversion existed in the bulletin **before** the move, i.e. the
  move was made while the inversion was in place. Labeling by the bulletin **after** the move is shown as a
  sensitivity check; it mechanically counts the jump that *creates* an inversion as "inverted" movement.
- **Collapsing:** areas with the identical move and inversion label in a bulletin (usually "all other
  areas" and Mexico) count once.
- **Significance:** a circular-shift test. The inversion timeline is rotated by 12 or more months and the
  difference recomputed, which keeps the long runs of inversion months intact. An ordinary test would treat
  each month as independent and overstate significance.

## Result: cutoffs do not move faster while inverted

![Speed inverted vs not]({figs['speed']})

Using the inversion state before the move:

{md_table(tables['before'])}

**Final action**

- **EB3 stalls or retrogresses** while ahead of EB2: mean move
  {cell('before', fad, 'EB3', True, 'mean'):.2f} vs {cell('before', fad, 'EB3', False, 'mean'):.2f} months
  (p = {pv('before', fad, 'EB3')}).
- **EB2 moves a little more** while behind ({cell('before', fad, 'EB2', True, 'mean'):.2f} vs
  {cell('before', fad, 'EB2', False, 'mean'):.2f}; p = {pv('before', fad, 'EB2')}, not significant).
- **Pooled, the cutoffs move slower, not faster:** {cell('before', fad, 'EB2+EB3', True, 'mean'):.2f} vs
  {cell('before', fad, 'EB2+EB3', False, 'mean'):.2f} months per move (borderline, p = {pv('before', fad, 'EB2+EB3')}).

**Dates for filing**

- **Pooled, no difference:** {cell('before', dff, 'EB2+EB3', True, 'mean'):.2f} vs
  {cell('before', dff, 'EB2+EB3', False, 'mean'):.2f} (p = {pv('before', dff, 'EB2+EB3')}).
- **EB3 advances less often** while inverted: {pct(cell('before', dff, 'EB3', True, 'adv'))} vs
  {pct(cell('before', dff, 'EB3', False, 'adv'))} (p = {pv('before', dff, 'EB3', 1)}).

![Shift test]({figs['null']})

By area, final action moves slower while inverted in every area. Dates for filing moves slightly faster in
China and India and slower in the three areas with only brief inversions:

{md_table(table_area)}

*Per-area moves are not collapsed across areas.*

## Why the opposite labeling looks "faster"

With the state *after* the move, EB3 final action appears to move much faster while inverted:
{cell('after', fad, 'EB3', True, 'mean'):.2f} vs {cell('after', fad, 'EB3', False, 'mean'):.2f} months
(p = {pv('after', fad, 'EB3')}). That comes from how inversions start and end:

{md_table(table_episodes)}

- **Starts:** most inversions begin with an EB3 advance, often together with an EB2 retrogression.
  Labeling by the state after the move counts that jump as movement "during" the inversion.
- **Ends:** most inversions end with EB2 advancing, sometimes with EB3 retrogressing.

In other words, an inversion is the *result* of a fast EB3 move, not a period of faster movement. Once
inverted, EB3 tends to stall and EB2 tends to catch up.

{md_table(tables['after'])}

## Conclusion

**Not supported.** While EB3 is ahead of EB2, neither chart's EB cutoffs move faster. Final-action cutoffs
move *slower* on average, mainly because EB3 stalls or retrogresses. Dates for filing shows no difference.
The impression of faster movement comes from the large EB3 jump that creates each inversion.

## Caveats

- There are only {len(starts)} inversion episodes across both charts and five areas, mostly in China and
  India, so per-category estimates are noisy.
- The inversion rule compares EB3 with EB2 only, not EB3 other workers, matching the dashboard.
- Mean moves are sensitive to a few very large jumps and retrogressions. Medians are shown alongside means
  in the tables.
"""
    write_report(FOLDER, report)
    return {"folder": FOLDER.name, "verdicts": verdicts}


if __name__ == "__main__":
    df = load_frame()
    print(run(df, movements(df)))
