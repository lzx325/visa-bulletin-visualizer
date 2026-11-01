"""Interactive Visa Bulletin dashboard. Run with: python app.py."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from dash import Dash, Input, Output, State, dcc, html
import plotly.graph_objects as go
from plotly.subplots import make_subplots

CSV_PATH = Path(__file__).resolve().parent / "data" / "visa-priority-dates.csv"
# Inauguration boundaries: https://www.archives.gov/research/census/presidents
# Second Trump term: https://www.usa.gov/presidents
ADMINISTRATIONS = [
    ("Obama", date(2009, 1, 20), date(2017, 1, 20), "rgba(59, 130, 246, 0.09)"),
    ("Trump (1st)", date(2017, 1, 20), date(2021, 1, 20), "rgba(234, 137, 64, 0.10)"),
    ("Biden", date(2021, 1, 20), date(2025, 1, 20), "rgba(20, 150, 130, 0.09)"),
    ("Trump (2nd)", date(2025, 1, 20), None, "rgba(234, 137, 64, 0.10)"),
]
REQUIRED = {"bulletin_month", "preference_type", "chart_type", "category",
            "chargeability_area", "cutoff_status", "cutoff_date"}
LABELS = {
    "family": "Family", "employment": "Employment",
    "final_action": "Final action", "date_for_filing": "Dates for filing",
    "all_chargeability_areas_except_listed": "All chargeability areas except listed",
    "china_mainland_born": "China (mainland born)",
    "el_salvador_guatemala_honduras": "El Salvador, Guatemala, Honduras",
}
# A fixed 20-color qualitative palette; colors never depend on selection order.
PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#e67300",
           "#008b8b", "#c21888", "#675037", "#516400", "#333333",
           "#00539c", "#9b2226", "#006b3c", "#682a8a", "#a04a00",
           "#007078", "#9c426b", "#846000", "#4858a8", "#66757f"]


def label(value):
    return LABELS.get(value, value.replace("_", " ").title() if not value.startswith(("EB", "F"))
                      else value.replace("_", " "))


def month_range(start, end):
    result = []
    while start <= end:
        result.append(start)
        start = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return result


def load_data(path=CSV_PATH):
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            missing = REQUIRED - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")
            rows = list(reader)
    except FileNotFoundError as exc:
        raise ValueError(f"Visa Bulletin CSV not found: {path}") from exc
    seen = set()
    for line, row in enumerate(rows, 2):
        try:
            if any(not row.get(key) for key in REQUIRED - {"cutoff_date"}):
                raise ValueError("empty required value")
            row["month"] = date.fromisoformat(row["bulletin_month"] + "-01")
            status = row["cutoff_status"]
            if status not in {"date", "current", "unavailable", "missing"}:
                raise ValueError(f"unknown cutoff status {status!r}")
            if row["preference_type"] not in {"family", "employment"}:
                raise ValueError("unknown preference type")
            row["cutoff"] = (date.fromisoformat(row["cutoff_date"]) if status == "date"
                             else row["month"] if status == "current" else None)
            key = tuple(row[k] for k in ("bulletin_month", "preference_type", "chart_type",
                                        "category", "chargeability_area"))
            if key in seen:
                raise ValueError(f"duplicate series/month key: {key}")
            seen.add(key)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid CSV row {line}: {exc}") from exc
    if not rows:
        raise ValueError("Visa Bulletin CSV has no records")
    return sorted(rows, key=lambda row: row["month"])


def choices(rows, field, **filters):
    return sorted({r[field] for r in rows if all(
        r[k] in v if isinstance(v, list) else r[k] == v for k, v in filters.items())})


def options(values):
    return [{"label": label(v), "value": v} for v in values]


def retain_single(value, values, preferred=None):
    return value if value in values else preferred if preferred in values else next(iter(values), None)


def retain_categories(selected, available):
    if selected == []:
        return []
    return [v for v in (selected or []) if v in available] or available


def category_colors(rows, preference):
    return {c: PALETTE[i % len(PALETTE)] for i, c in enumerate(
        choices(rows, "category", preference_type=preference))}


def build_figure(rows, preference, chart, categories, area, start, end, show_fiscal_years=False,
                 show_quarters=False):
    categories = categories or []
    colors = category_colors(rows, preference)
    selected = [r for r in rows if r["preference_type"] == preference and
                r["chart_type"] == chart and r["category"] in categories and
                r["chargeability_area"] == area and start <= r["month"] <= end]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        row_heights=[0.78, 0.22])
    months = month_range(start, end)
    for category in categories:
        color = colors[category]
        points = {r["month"]: r for r in selected if r["category"] == category}
        # Explicit adjacent-month segments prevent bridging absent or unavailable data.
        for dash in ("solid", "dash"):
            xs, ys = [], []
            for left, right in zip(months, months[1:]):
                a, b = points.get(left), points.get(right)
                if not a or not b or a["cutoff"] is None or b["cutoff"] is None:
                    continue
                style = "dash" if "current" in (a["cutoff_status"], b["cutoff_status"]) else "solid"
                if style == dash:
                    xs.extend([left, right, None])
                    ys.extend([a["cutoff"], b["cutoff"], None])
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, dash=dash),
                                    legendgroup=category, showlegend=False, hoverinfo="skip",
                                    connectgaps=False), row=1, col=1)
        dated = [r for r in points.values() if r["cutoff"] is not None]
        fig.add_trace(go.Scatter(
            x=[r["month"] for r in dated], y=[r["cutoff"] for r in dated], mode="markers",
            name=label(category), legendgroup=category, showlegend=False,
            marker=dict(color=color,
                        size=[10 if r["cutoff_status"] == "current" else 6 for r in dated],
                        symbol=["star" if r["cutoff_status"] == "current" else "circle" for r in dated]),
            customdata=[[r["cutoff_status"].title(),
                         "Current (plotted at bulletin month)" if r["cutoff_status"] == "current"
                         else r["cutoff"].isoformat()] for r in dated],
            hovertemplate="%{x|%b %Y}<br>%{customdata[0]}<br>%{customdata[1]}<extra>" + label(category) + "</extra>"
        ), row=1, col=1)
        for status, symbol, title in [("unavailable", "x", "Unavailable"),
                                      ("missing", "circle-open", "Missing data")]:
            records = [r for r in points.values() if r["cutoff_status"] == status]
            fig.add_trace(go.Scatter(
                x=[r["month"] for r in records], y=[category] * len(records), mode="markers",
                marker=dict(color=color, size=10, symbol=symbol, line=dict(width=2)),
                legendgroup=category, showlegend=False,
                hovertemplate="%{x|%b %Y}<br>" + title + "<extra>" + label(category) + "</extra>"
            ), row=2, col=1)
        # A dedicated legend entry keeps its symbol independent of point status.
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers", name=label(category),
            legendgroup=category, showlegend=True, hoverinfo="skip",
            marker=dict(color=color, size=7, symbol="circle")
        ), row=1, col=1)
    fig.update_layout(template="plotly_white", height=max(620, 480 + 23 * len(categories)),
                      margin=dict(l=80, r=25, t=80, b=60), hovermode="closest",
                      legend=dict(orientation="h", y=1.10, yanchor="bottom", groupclick="togglegroup"))
    # A one-month selection still needs visible horizontal space for markers.
    axis_end = month_range(end, date(end.year + (end.month == 12), end.month % 12 + 1, 1))[-1] if start == end else end
    for name, term_start, term_end, color in ADMINISTRATIONS:
        left, right = max(start, term_start), min(axis_end, term_end or axis_end)
        if left >= right:
            continue
        fig.add_shape(type="rect", xref="x", yref="y domain", x0=left, x1=right,
                      y0=0, y1=1, fillcolor=color, line_width=0, layer="below")
        fig.add_annotation(text=name, x=left + (right - left) / 2, y=1.01,
                           xref="x", yref="paper", yanchor="bottom", showarrow=False,
                           font=dict(size=11, color="#52647a"))
    if show_fiscal_years or show_quarters:
        for year in range(start.year, axis_end.year + 1):
            for month in (1, 4, 7, 10):
                boundary = date(year, month, 1)
                fiscal_boundary = month == 10 and show_fiscal_years
                if not (start <= boundary <= end) or not (fiscal_boundary or show_quarters):
                    continue
                fiscal_year = year + (month == 10)
                quarter = {10: 1, 1: 2, 4: 3, 7: 4}[month]
                fig.add_shape(type="line", name=f"FY {fiscal_year}" if fiscal_boundary else f"FY {fiscal_year} Q{quarter}",
                              xref="x", yref="paper", x0=boundary, x1=boundary,
                              y0=0, y1=1, layer="below",
                              line=dict(color="#64748b" if fiscal_boundary else "#9ca3af",
                                        width=2.5 if fiscal_boundary else 1,
                                        dash="dash" if fiscal_boundary else "3px,3px"))
    fig.update_xaxes(type="date", range=[start, axis_end], tickformat="%b %Y", showgrid=False)
    fig.update_yaxes(showgrid=False)
    fig.update_xaxes(title_text="Bulletin publish month", row=2, col=1)
    fig.update_yaxes(title_text="Cutoff date", type="date", tickformat="%b %Y", row=1, col=1)
    fig.update_yaxes(title_text="Status", type="category", categoryorder="array",
                     categoryarray=categories, tickvals=categories,
                     ticktext=[label(c) for c in categories], row=2, col=1)
    if not selected:
        fig.add_annotation(text="Select at least one category." if not categories else
                           "No records match these filters and months.", x=0.5, y=0.65,
                           xref="paper", yref="paper", showarrow=False)
    return fig


def create_app(path=CSV_PATH):
    rows = load_data(path)
    months = month_range(rows[0]["month"], rows[-1]["month"])
    app = Dash(__name__)
    app.title = "Visa Bulletin Visualizer"
    def control(title, ident, values, value, multi=False):
        return html.Div([html.Label(title, htmlFor=ident), dcc.Dropdown(
            id=ident, options=options(values), value=value, multi=multi, clearable=multi)], className="control")
    categories = choices(rows, "category", preference_type="employment", chart_type="final_action")
    app.layout = html.Main([
        html.Header([html.P("VISA BULLETIN • HISTORICAL DATA", className="eyebrow"),
                     html.H1("Priority dates over time"),
                     html.P("Compare categories and explore how cutoff dates move across monthly bulletins.")]),
        html.Section([
            control("Preference type", "preference", ["family", "employment"], "employment"),
            control("Chart type", "chart", choices(rows, "chart_type", preference_type="employment"), "final_action"),
            control("Category", "categories", categories, ["EB1", "EB2", "EB3"], True),
            control("Chargeability area", "area", choices(rows, "chargeability_area", preference_type="employment", chart_type="final_action"), "china_mainland_born"),
        ], className="filters"),
        html.Section([html.Div(id="range-label", className="range-label"),
                      dcc.RangeSlider(id="months", min=0, max=len(months)-1, step=1,
                                      value=[0, len(months)-1], allowCross=False,
                                      marks={i: str(m.year) for i, m in enumerate(months) if m.month == 1},
                                      updatemode="drag")], className="range-panel"),
        dcc.Checklist(id="fiscal-years",
                      options=[{"label": " Show fiscal year boundaries (October 1)", "value": "show"}],
                      value=[], style={"marginTop": "18px"}),
        dcc.Checklist(id="quarters",
                      options=[{"label": " Show quarter boundaries (Jan, Apr, Jul, Oct 1)", "value": "show"}],
                      value=[]),
        html.P(["Solid lines and circles: dated cutoff. Dashed lines and stars: current, plotted at the first day of the bulletin month. ",
                "Status strip: × unavailable; ○ missing data. Gaps are never connected."], className="key"),
        dcc.Graph(id="figure", config={"displaylogo": False, "responsive": True}),
        html.Footer(f"Source: data/visa-priority-dates.csv · {len(rows):,} records · Restart the server to reload data.")
    ])

    @app.callback(Output("chart", "options"), Output("chart", "value"),
                  Input("preference", "value"), State("chart", "value"))
    def update_chart(preference, current):
        values = choices(rows, "chart_type", preference_type=preference)
        return options(values), retain_single(current, values, "final_action")

    @app.callback(Output("categories", "options"), Output("categories", "value"),
                  Input("preference", "value"), Input("chart", "value"), State("categories", "value"))
    def update_categories(preference, chart, current):
        values = choices(rows, "category", preference_type=preference, chart_type=chart)
        return options(values), retain_categories(current, values)

    @app.callback(Output("area", "options"), Output("area", "value"),
                  Input("preference", "value"), Input("chart", "value"), Input("categories", "value"),
                  State("area", "value"))
    def update_area(preference, chart, selected, current):
        filters = dict(preference_type=preference, chart_type=chart)
        if selected:
            filters["category"] = selected
        values = choices(rows, "chargeability_area", **filters)
        return options(values), retain_single(current, values, "all_chargeability_areas_except_listed")

    @app.callback(Output("figure", "figure"), Output("range-label", "children"),
                  Input("preference", "value"), Input("chart", "value"), Input("categories", "value"),
                  Input("area", "value"), Input("months", "value"), Input("fiscal-years", "value"),
                  Input("quarters", "value"))
    def update_figure(preference, chart, selected, area, bounds, fiscal_years, quarters):
        start, end = (months[i] for i in bounds)
        return build_figure(rows, preference, chart, selected, area, start, end,
                            show_fiscal_years="show" in (fiscal_years or []),
                            show_quarters="show" in (quarters or [])), f"Bulletin months: {start:%b %Y} – {end:%b %Y}"

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=8050, debug=False)
