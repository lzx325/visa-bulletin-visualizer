from datetime import date

import pytest

from app import build_figure, create_app
from shading import inversion_intervals


def record(category, month=1, status="date", cutoff=date(2019, 1, 1), **overrides):
    return dict(preference_type="employment", chart_type="final_action", category=category,
                chargeability_area="china_mainland_born", month=date(2020, month, 1),
                cutoff_status=status, cutoff=cutoff) | overrides


@pytest.mark.parametrize("status2,status3,cutoff2,cutoff3,expected", [
    ("date", "date", date(2019, 1, 1), date(2019, 2, 1), True),
    ("date", "date", date(2019, 1, 1), date(2019, 1, 1), False),
    ("date", "date", date(2019, 2, 1), date(2019, 1, 1), False),
    ("date", "current", date(2021, 1, 1), date(2020, 1, 1), True),
    ("current", "date", date(2020, 1, 1), date(2021, 1, 1), False),
    ("current", "current", date(2020, 1, 1), date(2020, 1, 1), False),
] + [(a, b, None, None, False) for a, b in [
    ("missing", "date"), ("date", "missing"), ("unavailable", "date"),
    ("date", "unavailable"), ("missing", "current"), ("unavailable", "current")]])
def test_inversion_status_comparisons(status2, status3, cutoff2, cutoff3, expected):
    rows = [record("EB2", status=status2, cutoff=cutoff2), record("EB3", status=status3, cutoff=cutoff3)]
    assert bool(inversion_intervals(rows, "final_action", "china_mainland_born")) is expected


def test_inversion_series_filters_and_merging():
    rows = [record(c, month=m, cutoff=date(2019, 1 if c == "EB2" else 2, 1))
            for m in (1, 2, 4, 6) for c in ("EB2", "EB3")]
    rows = [r for r in rows if not (r['month'].month == 6 and r['category'] == 'EB2')]
    rows += [record('EB3_OTHER_WORKERS', month=3, status='current'),
             record('EB2', month=3), record('EB3', month=3, status='current', chart_type='date_for_filing'),
             record('EB3', month=3, status='current', chargeability_area='india')]
    assert inversion_intervals(rows, 'final_action', 'china_mainland_born') == [
        (date(2020, 1, 1), date(2020, 3, 1)), (date(2020, 4, 1), date(2020, 5, 1))]
    assert inversion_intervals(rows, 'date_for_filing', 'china_mainland_born') == []
    assert inversion_intervals(rows, 'final_action', 'india') == []


def test_modes_clipping_and_category_independence():
    rows = [record(c, month=m, cutoff=date(2019, 1 if c == "EB2" else 2, 1))
            for m in (1, 2, 3) for c in ("EB2", "EB3")]
    def figure(mode, categories):
        return build_figure(rows, 'employment', 'final_action', categories, 'china_mainland_born',
                            date(2020, 2, 1), date(2020, 3, 1), True, True, shading=mode)
    for categories in (['EB2', 'EB3'], ['EB2'], []):
        fig = figure('eb_inversion', categories)
        bands = [s for s in fig.layout.shapes if s.type == 'rect']
        assert len(bands) == 1
        assert bands[0].x0 == date(2020, 2, 1) and bands[0].x1 == date(2020, 3, 1)
        assert bands[0].layer == 'below' and bands[0].yref == 'y domain'
        assert not any(a.text == 'Trump (1st)' for a in fig.layout.annotations)
    none = figure('none', ['EB2'])
    assert not any(s.type == 'rect' for s in none.layout.shapes)
    assert not none.layout.annotations
    admin = figure('administration', ['EB2'])
    assert any(a.text == 'Trump (1st)' for a in admin.layout.annotations)
    assert len([s for s in none.layout.shapes if s.type == 'line']) == len([
        s for s in admin.layout.shapes if s.type == 'line'])
    # One selected month covers that month's inversion rather than producing a zero-width band.
    one = build_figure(rows, 'employment', 'final_action', ['EB2'], 'china_mainland_born',
                       date(2020, 2, 1), date(2020, 2, 1), shading='eb_inversion')
    assert one.layout.shapes[0].x1 == date(2020, 3, 1)


def test_covid_closure_band_and_clipping():
    rows = [record('EB2', month=m) for m in range(1, 13)] + [record('F1', preference_type='family')]
    def figure(start, end, preference='employment'):
        return build_figure(rows, preference, 'final_action', ['EB2' if preference == 'employment' else 'F1'],
                            'china_mainland_born', start, end, shading='covid_closure')
    def bands(fig):
        return [(s.name, s.x0, s.x1) for s in fig.layout.shapes if s.type == 'rect']
    def labels(fig):
        return {a.text: a.y for a in fig.layout.annotations if 'COVID' in a.text}
    full = figure(date(2019, 6, 1), date(2023, 6, 1))
    # The wider China period is drawn first, so the consular closure sits in front of it.
    assert bands(full) == [('China COVID-19 period', date(2019, 12, 31), date(2023, 1, 8)),
                           ('COVID-19 closure', date(2020, 3, 20), date(2020, 7, 15))]
    assert all(s.layer == 'below' and s.yref == 'y domain' for s in full.layout.shapes)
    assert full.layout.shapes[0].fillcolor != full.layout.shapes[1].fillcolor
    assert labels(full)['China COVID-19 period'] > labels(full)['COVID-19 closure']
    assert bands(figure(date(2020, 5, 1), date(2020, 6, 1))) == [
        ('China COVID-19 period', date(2020, 5, 1), date(2020, 6, 1)),
        ('COVID-19 closure', date(2020, 5, 1), date(2020, 6, 1))]
    after_closure = figure(date(2021, 1, 1), date(2021, 6, 1))
    assert bands(after_closure) == [('China COVID-19 period', date(2021, 1, 1), date(2021, 6, 1))]
    assert list(labels(after_closure)) == ['China COVID-19 period']
    outside = figure(date(2023, 2, 1), date(2023, 6, 1))
    assert not outside.layout.shapes and not labels(outside)
    # One selected month spans the padded axis rather than producing zero-width bands.
    assert [b[1:] for b in bands(figure(date(2020, 4, 1), date(2020, 4, 1)))] == [
        (date(2020, 4, 1), date(2020, 5, 1))] * 2
    assert [b[0] for b in bands(figure(date(2019, 6, 1), date(2023, 6, 1), 'family'))] == [
        'China COVID-19 period', 'COVID-19 closure']


def test_both_tab_callbacks_and_family_fallback():
    app = create_app()
    for prefix in ('', 'wait-'):
        settings = next(v['callback'].__wrapped__ for k, v in app.callback_map.items()
                        if prefix + 'shading.options' in k and (bool(prefix) == ('wait-' in k)))
        opts, value = settings('employment', 'eb_inversion')
        assert value == 'eb_inversion'
        assert [o['label'] for o in opts] == ['None', 'US gov administration', 'COVID-19 closure', 'EB inversion']
        opts, value = settings('family', 'eb_inversion')
        assert value == 'administration' and len(opts) == 3
        assert settings('family', 'none')[1] == 'none'
        assert settings('family', 'covid_closure')[1] == 'covid_closure'
        render = next(v['callback'].__wrapped__ for k, v in app.callback_map.items()
                      if prefix + 'figure.figure' in k and (bool(prefix) == ('wait-' in k)))
        args = ['employment', 'final_action', ['EB1'], 'china_mainland_born', [0, 190], [], []]
        none, _, _ = render(*args, 'none')
        inversion, _, _ = render(*args, 'eb_inversion')
        assert not none.layout.shapes
        assert inversion.layout.shapes and all(s.name == 'EB inversion' for s in inversion.layout.shapes)
        covid, _, _ = render(*args, 'covid_closure')
        assert [s.name for s in covid.layout.shapes] == ['China COVID-19 period', 'COVID-19 closure']
        args[0] = 'family'
        family, _, _ = render(*args, 'eb_inversion')
        assert any(a.text == 'Obama' for a in family.layout.annotations)
        covid, _, _ = render(*args, 'covid_closure')
        assert [s.name for s in covid.layout.shapes] == ['China COVID-19 period', 'COVID-19 closure']
