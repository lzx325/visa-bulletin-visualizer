from datetime import date

import pytest

from app import create_app, category_colors, load_data
from waiting import calculate_waits, build_waiting_figure, lighter, WAIT_CATEGORIES


def row(month, cutoff=None, status='date', category='EB1'):
    return dict(preference_type='employment', chart_type='final_action', category=category,
                chargeability_area='china_mainland_born', month=date(2020, month, 1),
                cutoff_status=status, cutoff=date(2020, month, 1) if status == 'current' else cutoff)


def test_inferred_and_same_month_actual():
    records = calculate_waits([row(1, date(2019, 12, 1)), row(2, date(2020, 3, 1)),
                               row(3, date(2020, 3, 1)), row(4, status='current')])
    assert records[0]['inferred'] == pytest.approx(31 / 30.4375)
    assert records[1]['inferred'] == pytest.approx(-29 / 30.4375)
    assert [r['actual_days'] for r in records] == [31, 0, 0, 0]
    assert records[3]['inferred'] == 0


def test_first_observed_match_missing_history_retrogression_and_unresolved():
    records = calculate_waits([row(1, date(2019, 1, 1)), row(3, status='unavailable'),
                               row(4, date(2020, 1, 1)), row(5, date(2019, 1, 1)),
                               row(6, status='missing')])
    assert records[0]['qualifying_month'] == date(2020, 4, 1)
    assert records[0]['actual_days'] == 91
    assert records[0]['incomplete'] is True
    assert records[1]['status'] == 'missing'
    assert records[1]['inferred'] is None
    assert records[2]['status'] == 'unavailable'
    assert records[2]['actual'] is None
    assert records[-1]['actual'] is None


def test_missing_origin_can_qualify_and_series_are_isolated():
    records = calculate_waits([row(1, status='missing'), row(3, status='current'),
                               row(1, date(2019, 1, 1), category='EB2'),
                               row(3, date(2019, 1, 1), category='EB2'),
                               row(1, status='current', category='EB4')])
    eb1 = [r for r in records if r['category'] == 'EB1']
    assert eb1[0]['actual_days'] == 60
    assert eb1[1]['actual_days'] == 29
    assert eb1[0]['incomplete']
    assert all(r['actual'] is None for r in records if r['category'] == 'EB2')
    assert all(r['category'] != 'EB4' for r in records)


def test_figure_uses_full_history_and_styles():
    waits = calculate_waits([row(1, date(2019, 1, 1)), row(2, status='current'),
                             row(3, date(2019, 1, 1))])
    color = '#1f77b4'
    fig = build_waiting_figure(waits, 'employment', 'final_action', ['EB1'],
                               'china_mainland_born', date(2020, 1, 1), date(2020, 1, 1), {'EB1': color})
    actual = next(t for t in fig.data if t.name == 'EB1 · Actual' and t.showlegend is False)
    assert list(actual.y) == [31 / 30.4375]
    assert actual.marker.color == color
    full = build_waiting_figure(waits, 'employment', 'final_action', ['EB1'],
                                'china_mainland_born', date(2020, 1, 1), date(2020, 3, 1), {'EB1': color})
    inferred = next(t for t in full.data if t.name == 'EB1 · Inferred' and t.showlegend is False)
    assert inferred.marker.color == lighter(color)
    assert list(inferred.marker.symbol) == ['circle', 'star', 'circle']
    assert all(t.marker.symbol == 'circle' for t in full.data if t.showlegend)
    assert any(t.marker.symbol == 'diamond-open' and len(t.x) for t in full.data)
    assert full.layout.yaxis.title.text == 'Waiting time (months)'
    assert full.layout.yaxis.type == 'linear'


def test_waiting_callbacks_have_independent_controls_and_restricted_categories():
    app = create_app()
    client = app.server.test_client()
    callbacks = app.callback_map
    waiting_key = next(k for k in callbacks if 'wait-figure.figure' in k)
    assert all(i['id'].startswith('wait-') for i in callbacks[waiting_key]['inputs'])
    original_key = next(k for k in callbacks if 'figure.figure' in k and 'wait-' not in k)
    assert not any(i['id'].startswith('wait-') for i in callbacks[original_key]['inputs'])
    category_callback = next(v['callback'].__wrapped__ for k, v in callbacks.items() if 'wait-categories.options' in k)
    opts, selected = category_callback('employment', 'final_action', ['EB1', 'EB2', 'EB3'])
    assert {o['value'] for o in opts} == {'EB1', 'EB2', 'EB3', 'EB3_OTHER_WORKERS'}
    assert selected == ['EB1', 'EB2', 'EB3']
    opts, _ = category_callback('family', 'final_action', selected)
    assert {o['value'] for o in opts} == {'F1', 'F2A', 'F2B', 'F3', 'F4'}
    result = client.post('/_dash-update-component', json={
        'output': waiting_key,
        'outputs': [{'id': 'wait-figure', 'property': 'figure'}, {'id': 'wait-range-label', 'property': 'children'}, {'id': 'wait-figure', 'property': 'style'}],
        'inputs': [{'id': 'wait-'+key, 'property': 'value', 'value': value} for key, value in [
            ('preference', 'employment'), ('chart', 'final_action'), ('categories', ['EB1', 'EB2']),
            ('area', 'china_mainland_born'), ('months', [0, 12]), ('fiscal-years', ['show']), ('quarters', ['show']), ('shading', 'administration')]],
        'state': [], 'changedPropIds': ['wait-months.value']})
    assert result.status_code == 200
    figure = result.get_json()['response']['wait-figure']['figure']
    assert figure['layout']['yaxis']['type'] == 'linear'
    assert all(figure['layout'][a]['showgrid'] is False for a in ['xaxis', 'xaxis2', 'yaxis', 'yaxis2'])
    assert len([s for s in figure['layout']['shapes'] if s['type'] == 'line']) == 5
