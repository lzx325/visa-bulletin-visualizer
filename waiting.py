"""Historical cutoff-based waiting times, independent of the displayed range."""
from collections import defaultdict
from datetime import date

import plotly.graph_objects as go
from plotly.subplots import make_subplots

WAIT_CATEGORIES = {"EB1", "EB2", "EB3", "EB3_OTHER_WORKERS", "F1", "F2A", "F2B", "F3", "F4"}
DAYS_PER_MONTH = 30.4375


def months_between(start, end):
    while start <= end:
        yield start
        start = date(start.year + (start.month == 12), start.month % 12 + 1, 1)


def calculate_waits(rows):
    groups = defaultdict(dict)
    for row in rows:
        if row['category'] in WAIT_CATEGORIES:
            key = tuple(row[k] for k in ('preference_type', 'chart_type', 'category', 'chargeability_area'))
            groups[key][row['month']] = row
    result = []
    for key, records in groups.items():
        months = list(months_between(min(records), max(records)))
        for index, pd in enumerate(months):
            origin = records.get(pd)
            status = origin['cutoff_status'] if origin else 'missing'
            inferred = (pd - origin['cutoff']).days if origin and origin['cutoff'] is not None else None
            match, incomplete = None, False
            for future in months[index:]:
                row = records.get(future)
                if row is None or row['cutoff_status'] == 'missing':
                    incomplete = True
                elif row['cutoff_status'] == 'current' or (row['cutoff_status'] == 'date' and row['cutoff'] >= pd):
                    match = row
                    break
            actual = (match['month'] - pd).days if match else None
            result.append(dict(zip(('preference_type', 'chart_type', 'category', 'chargeability_area'), key)) |
                          dict(month=pd, status=status, cutoff=origin['cutoff'] if origin else None,
                               inferred_days=inferred, actual_days=actual,
                               inferred=inferred / DAYS_PER_MONTH if inferred is not None else None,
                               actual=actual / DAYS_PER_MONTH if actual is not None else None,
                               qualifying_month=match['month'] if match else None,
                               qualifying_status=match['cutoff_status'] if match else None,
                               qualifying_cutoff=match['cutoff'] if match else None,
                               incomplete=incomplete, observed_through=max(records)))
    return result


def lighter(color):
    return '#' + ''.join(f'{round(int(color[i:i+2], 16) * .7 + 255 * .3):02x}' for i in (1, 3, 5))


def build_waiting_figure(waits, preference, chart, categories, area, start, end, colors):
    categories = categories or []
    selected = [r for r in waits if r['preference_type'] == preference and r['chart_type'] == chart
                and r['category'] in categories and r['chargeability_area'] == area and start <= r['month'] <= end]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=.06, row_heights=[.72, .28])
    status_rows = []
    for category in categories:
        points = {r['month']: r for r in selected if r['category'] == category}
        for measure in ('inferred', 'actual'):
            title = category.replace('_', ' ') + ' · ' + measure.title()
            status_rows.append(title)
            color = colors[category] if measure == 'actual' else lighter(colors[category])
            months = list(months_between(start, end))
            for dash in ('solid', 'dash') if measure == 'inferred' else ('solid',):
                xs, ys = [], []
                for left, right in zip(months, months[1:]):
                    a, b = points.get(left), points.get(right)
                    if not a or not b or a[measure] is None or b[measure] is None:
                        continue
                    style = 'dash' if measure == 'inferred' and 'current' in (a['status'], b['status']) else 'solid'
                    if style == dash:
                        xs.extend([left, right, None]); ys.extend([a[measure], b[measure], None])
                fig.add_trace(go.Scatter(x=xs, y=ys, mode='lines', line=dict(color=color, dash=dash),
                                        legendgroup=title, showlegend=False, hoverinfo='skip', connectgaps=False), row=1, col=1)
            known = [r for r in points.values() if r[measure] is not None]
            details = []
            for r in known:
                if measure == 'inferred':
                    detail = 'Current' if r['status'] == 'current' else f"Cutoff: {r['cutoff']}"
                else:
                    cutoff = 'Current' if r['qualifying_status'] == 'current' else str(r['qualifying_cutoff'])
                    detail = f"First qualifying bulletin: {r['qualifying_month']:%b %Y}<br>Cutoff: {cutoff}"
                    if r['incomplete']:
                        detail += '<br>Incomplete history: first observed match'
                details.append([r[measure + '_days'], detail])
            stars = [measure == 'inferred' and r['status'] == 'current' for r in known]
            fig.add_trace(go.Scatter(x=[r['month'] for r in known], y=[r[measure] for r in known],
                                    mode='markers', name=title, legendgroup=title, showlegend=False,
                                    marker=dict(color=color, size=[10 if star else 6 for star in stars],
                                                symbol=['star' if star else 'circle' for star in stars]),
                                    customdata=details,
                                    hovertemplate='PD: %{x|%Y-%m-%d}<br>%{y:.2f} months (%{customdata[0]} days)<br>%{customdata[1]}<extra>'+title+'</extra>'), row=1, col=1)
            statuses = [('unavailable', 'x', 'Unavailable'), ('missing', 'circle-open', 'Missing data')] if measure == 'inferred' else [('unresolved', 'diamond-open', 'Not observed within available data')]
            for status, symbol, description in statuses:
                records = [r for r in points.values() if (r['status'] == status if measure == 'inferred' else r['actual'] is None)]
                fig.add_trace(go.Scatter(x=[r['month'] for r in records], y=[title] * len(records), mode='markers',
                                        marker=dict(color=color, size=9, symbol=symbol), legendgroup=title, showlegend=False,
                                        customdata=[[str(r['observed_through']), 'Incomplete history' if r['incomplete'] else ''] for r in records],
                                        hovertemplate='PD: %{x|%Y-%m-%d}<br>'+description+'<br>Series observed through %{customdata[0]}<br>%{customdata[1]}<extra>'+title+'</extra>'), row=2, col=1)
            fig.add_trace(go.Scatter(x=[None], y=[None], mode='markers', name=title, legendgroup=title,
                                    showlegend=True, marker=dict(color=color, size=7, symbol='circle'), hoverinfo='skip'), row=1, col=1)
    fig.update_xaxes(title_text='Applicant priority date / bulletin month', row=2, col=1)
    fig.update_yaxes(title_text='Waiting time (months)', type='linear', zeroline=False, row=1, col=1)
    fig.update_yaxes(title_text='Status', type='category', categoryorder='array', categoryarray=status_rows,
                     tickvals=status_rows, ticktext=status_rows, automargin=True, row=2, col=1)
    if not selected:
        fig.add_annotation(text='Select at least one category.' if not categories else 'No records match these filters and months.',
                           x=.5, y=.65, xref='paper', yref='paper', showarrow=False)
    return fig
