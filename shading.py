"""Monthly EB3-versus-EB2 cutoff comparisons for background shading."""
from datetime import date


def inversion_intervals(rows, chart_type, chargeability_area):
    """Return merged month intervals; current outranks dates, unknowns never qualify."""
    months = {}
    for row in rows:
        if (row['preference_type'] == 'employment' and row['chart_type'] == chart_type
                and row['chargeability_area'] == chargeability_area and row['category'] in {'EB2', 'EB3'}):
            months.setdefault(row['month'], {})[row['category']] = row
    intervals = []
    for month, records in sorted(months.items()):
        eb2, eb3 = records.get('EB2'), records.get('EB3')
        if not eb2 or not eb3 or eb2['cutoff_status'] != 'date':
            continue
        inverted = eb3['cutoff_status'] == 'current' or (
            eb3['cutoff_status'] == 'date' and eb3['cutoff'] > eb2['cutoff'])
        if not inverted:
            continue
        end = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
        if intervals and intervals[-1][1] == month:
            intervals[-1] = (intervals[-1][0], end)
        else:
            intervals.append((month, end))
    return intervals
