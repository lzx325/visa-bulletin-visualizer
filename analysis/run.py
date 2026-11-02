"""Regenerate every figure, table and report in analysis/. Run with: python analysis/run.py"""
from __future__ import annotations

import statement1
import statement2
import statement3
from common import ANALYSIS, AREA_LABELS, CATEGORY_LABELS, load_frame, movements, write_report

CLAIMS = {
    "1a": "Dates for filing is usually ahead of final action",
    "1b": "Dates for filing usually progresses only at the beginning of each fiscal year",
    "1c": "Dates for filing usually stops progressing at the end of each fiscal year",
    "2a": "Both charts leap forward by a lot at the beginning of the fiscal year",
    "2b": "Both charts are more likely to move forward at the beginning of each quarter",
    "3": "Cutoffs move more quickly while EB2 and EB3 are inverted",
}


def main():
    df = load_frame()
    moves = movements(df)
    results = [module.run(df, moves) for module in (statement1, statement2, statement3)]
    rows = []
    for result in results:
        for key, (verdict, evidence) in result["verdicts"].items():
            rows.append(f"| [{key}](./{result['folder']}/README.md) | {CLAIMS[key]} | **{verdict}** | {evidence} |")
    first, last = df.month.min(), df.month.max()
    index = f"""
# Visa Bulletin hypothesis analysis

Three statements about how Visa Bulletin cutoff dates behave, each tested against
`data/visa-priority-dates.csv` ({df.month.nunique()} bulletins, {first:%b %Y} – {last:%b %Y}). Each folder has
a report (`README.md`) with static figures and tables.

| Folder | Statement |
|---|---|
| [`01-filing-vs-final-action/`](./01-filing-vs-final-action/README.md) | *The date for filing cutoff date is usually ahead of the final action date and usually progresses only at the beginnings of each fiscal year. It usually stops progressing at the end of the fiscal years.* |
| [`02-fiscal-year-and-quarter-jumps/`](./02-fiscal-year-and-quarter-jumps/README.md) | *Both date for filing and final action dates usually leap forward by a lot at the beginning of a fiscal year and more likely to move forward at the beginning of each quarter.* |
| [`03-inversion-speed/`](./03-inversion-speed/README.md) | *Cutoff dates tend to move more quickly when there is EB2 EB3 inversion (as computed in the code).* |

## Verdicts

| Claim | Statement | Verdict | Key evidence |
|---|---|---|---|
{chr(10).join(rows)}

## Method

- **Data:**
  - Loaded with the dashboard's own `app.load_data()`, so the CSV validation and the "Current is plotted at
    the bulletin month" convention match the app.
  - Inversion months come from `shading.inversion_intervals()`.
  - Dates-for-filing charts start in October 2015.
- **Scope:**
  - Categories: {", ".join(CATEGORY_LABELS.values())}. The EB-5 sub-categories were renamed several times,
    and EB-4 has long statutory "unavailable" gaps, so neither has continuous series.
  - Areas: {", ".join(AREA_LABELS.values())}, the five published in every bulletin.
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
"""
    write_report(ANALYSIS, index)
    for result in results:
        print(result["folder"], {k: v[0] for k, v in result["verdicts"].items()})


if __name__ == "__main__":
    main()
