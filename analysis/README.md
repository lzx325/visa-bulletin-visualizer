# Visa Bulletin hypothesis analysis

Three statements about how Visa Bulletin cutoff dates behave, each tested against
`data/visa-priority-dates.csv` (191 bulletins, Jan 2011 – Nov 2026). Each folder has
a report (`README.md`) with static figures and tables.

| Folder | Statement |
|---|---|
| [`01-filing-vs-final-action/`](./01-filing-vs-final-action/README.md) | *The date for filing cutoff date is usually ahead of the final action date and usually progresses only at the beginnings of each fiscal year. It usually stops progressing at the end of the fiscal years.* |
| [`02-fiscal-year-and-quarter-jumps/`](./02-fiscal-year-and-quarter-jumps/README.md) | *Both date for filing and final action dates usually leap forward by a lot at the beginning of a fiscal year and more likely to move forward at the beginning of each quarter.* |
| [`03-inversion-speed/`](./03-inversion-speed/README.md) | *Cutoff dates tend to move more quickly when there is EB2 EB3 inversion (as computed in the code).* |

## Verdicts

| Claim | Statement | Verdict | Key evidence |
|---|---|---|---|
| [1a](./01-filing-vs-final-action/README.md) | Dates for filing is usually ahead of final action | **Supported** | DFF is later than FAD in 90% of distinct pairs and earlier in only 1.1%. |
| [1b](./01-filing-vs-final-action/README.md) | Dates for filing usually progresses only at the beginning of each fiscal year | **Not supported** | October is the most likely month for DFF to advance, but only 15% of DFF advances happen in October and only 4% of moving series-years advance only then. |
| [1c](./01-filing-vs-final-action/README.md) | Dates for filing usually stops progressing at the end of each fiscal year | **Not supported** | 64% of moving series-years still advance in Jul–Sep, July is among the busiest months, and September (18%) is not significantly slower than mid-year. |
| [2a](./02-fiscal-year-and-quarter-jumps/README.md) | Both charts leap forward by a lot at the beginning of the fiscal year | **Partly supported** | October carries 24% (FAD) and 25% (DFF) of all forward movement, and FAD moves 3.9 vs 0.7 months per series. The leap is an employment effect; family final action does not jump in October. |
| [2b](./02-fiscal-year-and-quarter-jumps/README.md) | Both charts are more likely to move forward at the beginning of each quarter | **Supported, mainly since FY2022** | Jan/Apr/Jul bulletins advance more often than non-quarter months: FAD 72% vs 60% (p = 0.023), DFF 32% vs 22% (p = 0.044). The gap is large from FY2022 on (FAD 47% vs 23%) and weak before. |
| [3](./03-inversion-speed/README.md) | Cutoffs move more quickly while EB2 and EB3 are inverted | **Not supported** | While inverted, EB2 + EB3 final-action cutoffs move 0.46 months per bulletin vs 1.35 otherwise (slower, borderline p = 0.059); dates for filing shows no difference (0.83 vs 0.89). |

## Method

- **Data:**
  - Loaded with the dashboard's own `app.load_data()`, so the CSV validation and the "Current is plotted at
    the bulletin month" convention match the app.
  - Inversion months come from `shading.inversion_intervals()`.
  - Dates-for-filing charts start in October 2015.
- **Scope:**
  - Categories: F1, F2A, F2B, F3, F4, EB1, EB2, EB3, EB3 other workers. The EB-5 sub-categories were renamed several times,
    and EB-4 has long statutory "unavailable" gaps, so neither has continuous series.
  - Areas: All other areas, China, India, Mexico, Philippines, the five published in every bulletin.
- **Moves:**
  - A move is the change in one series' cutoff from one bulletin to the next.
  - Moves to or from Current count as advances or retrogressions. Current→Current, unavailable and missing
    months are dropped.
  - Distances use date-to-date moves only, in months (days / 30.4375, as in `waiting.py`).
- **Distinct moves:** when several areas publish the identical move in the same bulletin (for example Mexico
  and "all other areas"), it counts once, because it is one State Department decision.
- **Fiscal calendar:** the US fiscal year starts on October 1. Quarter-start bulletins are Oct, Jan, Apr and Jul.
- **Statistics:**
  - Series in the same bulletin are set together, so tests on timing (statements 1–2) treat each **bulletin**
    as one observation: the share of distinct series advancing, or their mean move. These use two-sided
    Mann–Whitney tests.
  - Inversion months come in long runs, so statement 3 uses a circular-shift permutation test that rotates
    the inversion timeline by 12 or more months.
  - Proportions carry 95% Wilson intervals and means carry bootstrap intervals.

## Reproduce

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r analysis/requirements.txt
python analysis/run.py
```

`run.py` rewrites every report and figure under `analysis/`. The analysis code lives in `common.py`
(shared preparation and plot style) and `statement1.py` – `statement3.py`.
