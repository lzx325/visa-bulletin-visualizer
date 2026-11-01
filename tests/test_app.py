import csv
from datetime import date

import pytest

from app import (CSV_PATH, REQUIRED, build_figure, category_colors, choices,
                 create_app, load_data, retain_categories, retain_single)


def fixture_csv(tmp_path, statuses):
    path = tmp_path / "dates.csv"
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(REQUIRED))
        writer.writeheader()
        for month, status in statuses:
            writer.writerow(dict(bulletin_month=f"2020-{month:02}", preference_type="family",
                                 chart_type="final_action", category="F1", chargeability_area="india",
                                 cutoff_status=status, cutoff_date="2015-01-01" if status == "date" else ""))
    return path


def test_segments_and_status_strip(tmp_path):
    rows = load_data(fixture_csv(tmp_path, [(1, "date"), (2, "date"), (3, "current"),
                     (4, "current"), (5, "unavailable"), (6, "date"), (8, "date"), (9, "missing")]))
    fig = build_figure(rows, "family", "final_action", ["F1"], "india", date(2020, 1, 1), date(2020, 9, 1))
    solid, dashed, points, unavailable, missing, legend = fig.data
    assert legend.marker.symbol == "circle"
    assert legend.showlegend and not points.showlegend
    assert legend.legendgroup == points.legendgroup
    assert list(solid.x) == [date(2020, 1, 1), date(2020, 2, 1), None]
    assert list(dashed.x) == [date(2020, 2, 1), date(2020, 3, 1), None,
                              date(2020, 3, 1), date(2020, 4, 1), None]
    assert points.y[2] == date(2020, 3, 1)
    assert list(points.marker.symbol) == ["circle", "circle", "star", "star", "circle", "circle"]
    assert unavailable.marker.symbol == "x"
    assert list(unavailable.x) == [date(2020, 5, 1)]
    assert missing.marker.symbol == "circle-open"
    assert unavailable.xaxis == "x2"
    assert fig.layout.xaxis.matches == "x2"
    assert points.marker.color == unavailable.marker.color == missing.marker.color


def test_filters_colors_and_empty_states():
    rows = load_data()
    cats = choices(rows, "category", preference_type="family")
    assert cats == ["F1", "F2A", "F2B", "F3", "F4"]
    assert retain_categories(["F1"], ["EB1", "EB2"]) == ["EB1", "EB2"]
    assert retain_categories([], cats) == []
    assert retain_categories(["F1", "F2A"], ["F1"]) == ["F1"]
    assert retain_single("india", ["india", "mexico"]) == "india"
    assert retain_single("vietnam", ["india", "mexico"], "mexico") == "mexico"
    colors = category_colors(rows, "employment")
    assert len(set(colors.values())) == len(colors)
    for categories, area, message in [([], "india", "Select at least"), (["F1"], "vietnam", "No records")]:
        fig = build_figure(rows, "family", "final_action", categories, area, date(2020, 1, 1), date(2020, 1, 1))
        assert any(message in annotation.text for annotation in fig.layout.annotations)
        assert fig.layout.xaxis.range[0] < fig.layout.xaxis.range[1]


def test_invalid_csv(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        load_data(tmp_path / "absent.csv")
    path = tmp_path / "bad.csv"
    path.write_text("wrong\nvalue\n")
    with pytest.raises(ValueError, match="required columns"):
        load_data(path)
    with pytest.raises(ValueError, match="duplicate"):
        load_data(fixture_csv(tmp_path, [(1, "date"), (1, "current")]))
    with pytest.raises(ValueError, match="unknown cutoff status"):
        load_data(fixture_csv(tmp_path, [(1, "bad")]))


def test_administration_bands():
    rows = load_data()
    def figure(start, end):
        return build_figure(rows, "employment", "final_action", ["EB1"],
                            "china_mainland_born", start, end)
    fig = figure(date(2011, 1, 1), date(2026, 11, 1))
    assert [a.text for a in fig.layout.annotations] == ["Obama", "Trump (1st)", "Biden", "Trump (2nd)"]
    bands = fig.layout.shapes
    assert len(bands) == 4
    assert bands[0].x0 == date(2011, 1, 1)
    assert bands[-1].x1 == date(2026, 11, 1)
    for before, after, boundary in zip(bands, bands[1:], [date(2017, 1, 20), date(2021, 1, 20), date(2025, 1, 20)]):
        assert before.x1 == after.x0 == boundary
    assert all(b.layer == "below" and b.yref == "y domain" for b in bands)
    assert bands[1].fillcolor == bands[3].fillcolor
    narrow = figure(date(2023, 1, 1), date(2023, 6, 1))
    assert len(narrow.layout.shapes) == 1
    assert narrow.layout.annotations[0].text == "Biden"
    transition = figure(date(2025, 1, 1), date(2025, 1, 1))
    assert len(transition.layout.shapes) == 2
    assert transition.layout.shapes[0].x1 == date(2025, 1, 20)


def test_fiscal_year_boundaries():
    rows = load_data()
    def lines(start, end, enabled):
        fig = build_figure(rows, "employment", "final_action", ["EB1"],
                           "china_mainland_born", start, end, show_fiscal_years=enabled)
        return [s for s in fig.layout.shapes if s.type == "line"]
    assert lines(date(2024, 1, 1), date(2026, 11, 1), False) == []
    boundaries = lines(date(2024, 1, 1), date(2026, 11, 1), True)
    assert [s.x0 for s in boundaries] == [date(y, 10, 1) for y in (2024, 2025, 2026)]
    assert [s.name for s in boundaries] == ["FY 2025", "FY 2026", "FY 2027"]
    assert all(s.x0 == s.x1 and s.yref == "paper" and s.line.dash == "dash" and s.line.width == 2.5 for s in boundaries)
    assert lines(date(2024, 1, 1), date(2024, 9, 1), True) == []
    assert len(lines(date(2024, 10, 1), date(2024, 10, 1), True)) == 1


@pytest.mark.parametrize("fiscal_years", [[], ["show"]])
@pytest.mark.parametrize("quarters", [[], ["show"]])
def test_app_routes_and_render_callback(fiscal_years, quarters):
    app = create_app(CSV_PATH)
    client = app.server.test_client()
    for path in ["/", "/_dash-layout", "/_dash-dependencies", "/assets/style.css"]:
        assert client.get(path).status_code == 200
    callback = next(k for k in app.callback_map if "figure.figure" in k)
    result = client.post("/_dash-update-component", json={
        "output": callback,
        "outputs": [{"id": "figure", "property": "figure"}, {"id": "range-label", "property": "children"}, {"id": "figure", "property": "style"}],
        "inputs": [{"id": i, "property": "value", "value": v} for i, v in [
            ("preference", "family"), ("chart", "final_action"), ("categories", ["F1", "F2A"]),
            ("area", "india"), ("months", [0, 12]), ("fiscal-years", fiscal_years), ("quarters", quarters), ("shading", "administration")]],
        "state": [], "changedPropIds": ["months.value"]})
    assert result.status_code == 200
    payload = result.get_json()["response"]
    assert len(payload["figure"]["figure"]["data"]) == 12
    assert "Jan 2011" in payload["range-label"]["children"]
    boundaries = [s for s in payload["figure"]["figure"]["layout"]["shapes"] if s["type"] == "line"]
    assert len(boundaries) == (5 if quarters else 1 if fiscal_years else 0)
    for boundary in boundaries:
        fiscal = bool(fiscal_years) and boundary["x0"] == "2011-10-01"
        assert boundary["line"]["dash"] == ("dash" if fiscal else "3px,3px")
        assert boundary["line"]["width"] == (2.5 if fiscal else 1)
        assert boundary["line"]["color"] == ("#64748b" if fiscal else "#9ca3af")
    if quarters:
        assert [b["x0"] for b in boundaries] == ["2011-01-01", "2011-04-01", "2011-07-01", "2011-10-01", "2012-01-01"]
