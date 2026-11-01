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

- Solid segments connect dated cutoffs. Circular dots identify dated records.
- Current records use star markers and the first day of the bulletin month as their vertical position. Segments touching a current point are dashed.
- Unavailable records break the line and appear as colored × markers in the status strip.
- Explicit missing records break the line and appear as hollow circles in the strip. Absent months also break the line, without inventing status records.
- Hover over points for the bulletin month, category, status, and cutoff details.
- Subtle background bands mark Obama, Trump’s first term, Biden, and Trump’s second term. Boundaries use January 20 inauguration dates ([National Archives](https://www.archives.gov/research/census/presidents), [USAGov](https://www.usa.gov/presidents)); bands are clipped to the selected month range. Both Trump terms use the same shading.

The chart starts with employment final-action data, only EB1, EB2, and EB3 selected, China (mainland born), and the complete available month range. No database or external data service is required.

## Tests

```bash
python -m pip install pytest
python -m pytest -q
```

Tests cover input validation, current-date substitution, segment styling and gaps, status markers, filter selection behavior, empty states, HTTP routes, and a Dash rendering callback.
