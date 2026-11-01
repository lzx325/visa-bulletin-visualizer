# Visa Bulletin Visualizer

A local Dash/Plotly dashboard for `data/visa-priority-dates.csv`.

## Run

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8050. The CSV is resolved relative to `app.py`, so launching from another directory also works. Restart the server after replacing the CSV. Invalid input produces an explanatory startup error.

## Explore

Choose preference type, chart type, categories, and chargeability area. Only categories support multiple selections. Dependent options update automatically; historical categories and areas remain separate. Colors stay stable within each preference type.

Use the month-range slider to select the visible interval. Drag within the chart to zoom, use the toolbar to pan, and double-click to reset chart zoom. Both chart panels share the horizontal axis. Click a category in the legend to toggle its lines and markers.

Check **Show fiscal year boundaries (October 1)** to add thick dashed lines across both chart panels. Independently enable **Show quarter boundaries (Jan, Apr, Jul, Oct 1)** for thin grey dashed lines. Every quarter uses the same grey color, 1-pixel width, and short pattern of 3-pixel dashes with 3-pixel gaps. Both options are off by default. When both are enabled, October 1 uses a single thick fiscal-year line.

Each tab has an independent **Plot shading** selector, defaulting to **US gov administration**. Choose **None** to remove shading, **COVID-19 closure** (Family and Employment; kept when switching preference type) for a light-red band over the worldwide consular closure in front of a wider amber band for China's COVID-19 period, or **EB inversion** (Employment only) for light-purple bands where EB3's cutoff is strictly later than EB2's. Inversion uses the selected chart type and chargeability area, regardless of plotted categories, and compares EB3 rather than EB3 other workers. Current outranks every dated cutoff; both current, equal dates, missing records, and unavailable cutoffs are unshaded. Qualifying calendar months are merged and clipped to the visible range. On the waiting-time tab, inversion refers to the bulletin cutoffs for each plotted month. Switching to Family while inversion is selected restores administration shading. Fiscal/quarter boundary toggles remain independent.

- Solid segments connect dated cutoffs. Circular dots identify dated records.
- Current records use star markers and the first day of the bulletin month as their vertical position. Segments touching a current point are dashed.
- Unavailable records break the line and appear as colored × markers in the status strip.
- Explicit missing records break the line and appear as hollow circles in the strip. Absent months also break the line, without inventing status records.
- Hover over points for the bulletin month, category, status, and cutoff details.
- Subtle background bands mark Obama, Trump’s first term, Biden, and Trump’s second term. Boundaries use January 20 inauguration dates ([National Archives](https://www.archives.gov/research/census/presidents), [USAGov](https://www.usa.gov/presidents)); bands are clipped to the selected month range. Both Trump terms use the same shading.
- COVID-19 closure shading covers March 20 – July 15, 2020. On March 20 the State Department suspended routine visa services at all US embassies and consulates ([AILA](https://www.aila.org/library/dos-suspends-routine-visa-services-covid19)); on July 15 posts began a phased, post-by-post resumption ([MIT ISO](https://iso.mit.edu/news/usdos-provides-details-on-phased-resumption-of-routine-visa-services/)), so some posts stayed closed longer. Behind it, an amber **China COVID-19 period** band runs from December 31, 2019, when the Wuhan Municipal Health Commission first reported the pneumonia cluster ([WHO](https://www.who.int/news/item/27-04-2020-who-timeline---covid-19)), to January 8, 2023, when China downgraded COVID-19 to Class B and ended quarantine, the last of its zero-COVID measures ([Library of Congress](https://www.loc.gov/item/global-legal-monitor/2023-01-06/china-management-of-covid-19-downgraded)). Its label sits above the closure label. Both bands are clipped to the selected month range.

The chart starts with employment final-action data, only EB1, EB2, and EB3 selected, China (mainland born), and the complete available month range. No database or external data service is required.

## Waiting times tab

The **Waiting times** tab has its own filters, month range, and boundary toggles. Switching tabs preserves each tab's state. It supports EB1, EB2, EB3, EB3 other workers, and F1/F2A/F2B/F3/F4.

Each plotted month represents a hypothetical applicant whose priority date (PD) is the first day of that month:

- **Inferred:** `(PD − that month's cutoff).days / 30.4375`. Current means zero; negative values are retained. Lighter category colors identify inferred values, with stars/dashed segments for current and circles/solid segments otherwise.
- **Actual:** Search the complete series from that month, inclusive, for the first current bulletin or cutoff **equal to or later than PD**. Plot `(qualifying bulletin month − PD).days / 30.4375`, using stronger category colors with circles and solid lines. This inclusive comparison is the dashboard's chosen analytical convention. These are historical cutoff-based waits, not measured visa issuance or processing times.

Both measures use fractional **months**; hover shows two decimal places and exact days. Narrowing the displayed range never truncates the search for a later qualifying bulletin. Missing history before the first observed match is flagged in hover. Unavailable records are known nonqualifying observations. Unresolved actual waits are left blank and marked with hollow diamonds in the status strip; inferred unavailable/missing values use X/hollow-circle markers. No future values are extrapolated.

Results are precomputed at server startup. No additional data or dependencies are needed.

## Tests

```bash
python -m pip install pytest
python -m pytest -q
```

Tests cover input validation, current-date substitution, segment styling and gaps, status markers, filter selection behavior, empty states, HTTP routes, and a Dash rendering callback.
