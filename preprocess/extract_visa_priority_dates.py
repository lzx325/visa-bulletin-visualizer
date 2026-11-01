#!/usr/bin/env python3
"""Extract tidy Visa Bulletin priority-date data from the local HTML archive."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Iterable

from bs4 import BeautifulSoup


ARCHIVE_ROOT = Path("/home/lzx325/visa-bulletins")
MANIFEST_PATH = ARCHIVE_ROOT / "manifest.csv"
OUTPUT_ROOT = Path("/home/lzx325/visa-priority-dates")
STAGING_ROOT = Path("/tmp/visa-priority-date-staging")
YEARS = tuple(range(2011, 2027))
EXPECTED_YEAR_ROWS = {
    2011: 802,
    2012: 725,
    2013: 720,
    2014: 720,
    2015: 930,
    2016: 1624,
    2017: 1680,
    2018: 1816,
    2019: 1848,
    2020: 1848,
    2021: 1824,
    2022: 1956,
    2023: 1860,
    2024: 1800,
    2025: 1800,
    2026: 1650,
}
TOTAL_EXPECTED_ROWS = 23603
FIELDS = [
    "bulletin_month",
    "bulletin_year",
    "bulletin_month_number",
    "preference_type",
    "chart_type",
    "category",
    "category_raw",
    "chargeability_area",
    "chargeability_area_raw",
    "cutoff_status",
    "cutoff_date",
    "cutoff_raw",
    "parse_note",
    "source_url",
    "source_path",
]
MONTH_NUMBERS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def clean_text(value: str) -> str:
    value = value.replace("\xa0", " ").replace("\u2010", "-").replace("\u2011", "-")
    value = value.replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-")
    return " ".join(value.split())


def compact_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())


def atomic_write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".part", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".part", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def load_manifest() -> list[dict[str, str]]:
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 191:
        raise RuntimeError(f"expected 191 manifest rows, found {len(rows)}")
    months = [row["bulletin_month"] for row in rows]
    if len(set(months)) != len(months):
        raise RuntimeError("manifest contains duplicate bulletin months")
    return rows


def verify_sources(rows: list[dict[str, str]]) -> dict[str, object]:
    total_bytes = 0
    for row in rows:
        path = ARCHIVE_ROOT / row["local_path"]
        body = path.read_bytes()
        total_bytes += len(body)
        if len(body) != int(row["byte_size"]):
            raise RuntimeError(f"source size mismatch: {path}")
        if hashlib.sha256(body).hexdigest() != row["sha256"]:
            raise RuntimeError(f"source checksum mismatch: {path}")
        if not re.search(br"<(?:!doctype\s+html|html)\b", body[:4096], re.I):
            raise RuntimeError(f"source is not HTML: {path}")
    return {"files": len(rows), "bytes": total_bytes}


def table_domain(table) -> str | None:
    rows = direct_rows(table)
    if not rows:
        return None
    cells = direct_cells(rows[0])
    if not cells:
        return None
    key = re.sub(r"[^a-z]", "", clean_text(cells[0].get_text(" ", strip=True)).lower())
    if key.startswith("familysponsored"):
        return "family"
    if key.startswith("employmentbased"):
        return "employment"
    return None


def direct_rows(table) -> list:
    return [row for row in table.find_all("tr") if row.find_parent("table") is table]


def direct_cells(row) -> list:
    return row.find_all(["th", "td"], recursive=False)


def normalize_chargeability(raw: str) -> str:
    key = compact_key(raw)
    if key.startswith("ALLCHARGEABILITYAREASEXCEPT") or key.startswith("ALLCHARGEABILITYAREAEXCEPT"):
        return "all_chargeability_areas_except_listed"
    aliases = {
        "CHINAMAINLANDBORN": "china_mainland_born",
        "DOMINICANREPUBLIC": "dominican_republic",
        "INDIA": "india",
        "MEXICO": "mexico",
        "PHILIPPINES": "philippines",
        "VIETNAM": "vietnam",
        "ELSALVADORGUATEMALAHONDURAS": "el_salvador_guatemala_honduras",
    }
    if key not in aliases:
        raise RuntimeError(f"unrecognized chargeability header: {raw!r}")
    return aliases[key]


def normalize_category(preference: str, raw: str) -> str:
    key = compact_key(raw.rstrip("*"))
    if preference == "family":
        aliases = {
            "1ST": "F1",
            "F1": "F1",
            "2A": "F2A",
            "F2A": "F2A",
            "2B": "F2B",
            "F2B": "F2B",
            "3RD": "F3",
            "F3": "F3",
            "4TH": "F4",
            "F4": "F4",
        }
        if key not in aliases:
            raise RuntimeError(f"unrecognized family category: {raw!r}")
        return aliases[key]

    simple = {
        "1ST": "EB1",
        "2ND": "EB2",
        "3RD": "EB3",
        "OTHERWORKERS": "EB3_OTHER_WORKERS",
        "4TH": "EB4",
        "CERTAINRELIGIOUSWORKERS": "EB4_CERTAIN_RELIGIOUS_WORKERS",
        "5TH": "EB5_GENERAL",
    }
    if key in simple:
        return simple[key]
    if "SETASIDE" in key:
        if "RURAL" in key:
            return "EB5_SET_ASIDE_RURAL"
        if "HIGHUNEMPLOYMENT" in key:
            return "EB5_SET_ASIDE_HIGH_UNEMPLOYMENT"
        if "INFRASTRUCTURE" in key:
            return "EB5_SET_ASIDE_INFRASTRUCTURE"
    if "UNRESERVED" in key:
        if "C5T5ANDALLOTHERS" in key:
            return "EB5_UNRESERVED_C5_T5_ALL_OTHERS"
        if "I5ANDR5" in key and "INCLUDING" not in key:
            return "EB5_UNRESERVED_I5_R5"
        return "EB5_UNRESERVED_ALL"
    if "NONREGIONALCENTER" in key:
        return "EB5_NON_REGIONAL_C5_T5"
    if "REGIONALCENTER" in key and "PILOTPROGRAM" not in key and "TARGETEDEMPLOYMENT" not in key:
        return "EB5_REGIONAL_I5_R5"
    if "PILOTPROGRAM" in key and "TARGETEDEMPLOYMENT" not in key:
        return "EB5_PILOT_PROGRAMS"
    if "TARGETEDEMPLOYMENT" in key and "PILOTPROGRAM" in key:
        return "EB5_TARGETED_REGIONAL_AND_PILOT"
    if "TARGETEDEMPLOYMENT" in key or key == "REGIONALCENTERS":
        return "EB5_TARGETED_REGIONAL_CENTERS"
    raise RuntimeError(f"unrecognized employment category: {raw!r}")


def parse_cutoff(raw: str) -> tuple[str, str, str]:
    value = clean_text(raw).upper()
    if not value:
        return "missing", "", ""
    if value in {"C", "CURRENT"}:
        return "current", "", ""
    if value in {"U", "UNAVAILABLE"}:
        return "unavailable", "", ""
    match = re.fullmatch(r"(\d{1,2})([A-Z]{3})(\d{2})", value)
    if not match:
        raise RuntimeError(f"unrecognized cutoff value: {raw!r}")
    day_text, month_text, year_text = match.groups()
    if month_text not in MONTH_NUMBERS:
        raise RuntimeError(f"unrecognized cutoff month: {raw!r}")
    yy = int(year_text)
    year = 1900 + yy if yy >= 80 else 2000 + yy
    parsed = date(year, MONTH_NUMBERS[month_text], int(day_text))
    note = "source_typo_day_zero_padded" if len(day_text) == 1 else ""
    return "date", parsed.isoformat(), note


def chart_signature(preference: str, table) -> tuple:
    rows = direct_rows(table)
    header = [clean_text(cell.get_text(" ", strip=True)) for cell in direct_cells(rows[0])]
    charges = tuple(normalize_chargeability(value) for value in header[1:])
    data = []
    for row in rows[1:]:
        cells = direct_cells(row)
        if not cells:
            continue
        values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
        if not values or not values[0]:
            continue
        data.append((normalize_category(preference, values[0]), tuple(value.upper() for value in values[1:])))
    return charges, tuple(data)


def unique_domain_tables(soup, preference: str) -> list:
    result = []
    signatures = set()
    for table in soup.find_all("table"):
        if table_domain(table) != preference:
            continue
        signature = chart_signature(preference, table)
        if signature in signatures:
            continue
        signatures.add(signature)
        result.append(table)
    return result


def extract_table(
    table,
    preference: str,
    chart_type: str,
    manifest_row: dict[str, str],
) -> list[dict[str, object]]:
    month_key = manifest_row["bulletin_month"]
    bulletin_year, bulletin_month = (int(part) for part in month_key.split("-"))
    table_rows = direct_rows(table)
    header = [clean_text(cell.get_text(" ", strip=True)) for cell in direct_cells(table_rows[0])]
    raw_chargeabilities = header[1:]
    chargeabilities = [normalize_chargeability(value) for value in raw_chargeabilities]
    output = []
    for row in table_rows[1:]:
        cells = direct_cells(row)
        if not cells:
            continue
        values = [clean_text(cell.get_text(" ", strip=True)) for cell in cells]
        if not values or not values[0]:
            continue
        if len(values) != len(header):
            raise RuntimeError(
                f"{month_key} {preference} {chart_type}: row width {len(values)} "
                f"does not match header width {len(header)} for {values[0]!r}"
            )
        raw_category = values[0]
        category = normalize_category(preference, raw_category)
        for index, raw_cutoff in enumerate(values[1:]):
            status, cutoff_date, note = parse_cutoff(raw_cutoff)
            output.append(
                {
                    "bulletin_month": month_key,
                    "bulletin_year": bulletin_year,
                    "bulletin_month_number": bulletin_month,
                    "preference_type": preference,
                    "chart_type": chart_type,
                    "category": category,
                    "category_raw": raw_category,
                    "chargeability_area": chargeabilities[index],
                    "chargeability_area_raw": raw_chargeabilities[index],
                    "cutoff_status": status,
                    "cutoff_date": cutoff_date,
                    "cutoff_raw": raw_cutoff,
                    "parse_note": note,
                    "source_url": manifest_row["source_url"],
                    "source_path": manifest_row["local_path"],
                }
            )
    return output


def extract_bulletin(manifest_row: dict[str, str]) -> list[dict[str, object]]:
    month_key = manifest_row["bulletin_month"]
    soup = BeautifulSoup((ARCHIVE_ROOT / manifest_row["local_path"]).read_bytes(), "lxml")
    output = []
    filing_exists = month_key >= "2015-10"
    for preference in ("family", "employment"):
        tables = unique_domain_tables(soup, preference)
        expected = 2 if filing_exists else 1
        if len(tables) != expected:
            raise RuntimeError(
                f"{month_key}: expected {expected} unique {preference} table(s), found {len(tables)}"
            )
        output.extend(extract_table(tables[0], preference, "final_action", manifest_row))
        if filing_exists:
            output.extend(extract_table(tables[1], preference, "date_for_filing", manifest_row))
    return output


def summarize_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "row_count": len(rows),
        "months": sorted({str(row["bulletin_month"]) for row in rows}),
        "status_counts": dict(sorted(Counter(str(row["cutoff_status"]) for row in rows).items())),
        "preference_counts": dict(sorted(Counter(str(row["preference_type"]) for row in rows).items())),
        "chart_counts": dict(sorted(Counter(str(row["chart_type"]) for row in rows).items())),
        "parse_notes": dict(sorted(Counter(str(row["parse_note"]) for row in rows if row["parse_note"]).items())),
    }


def extract_year(year: int, output_path: Path, report_path: Path) -> dict[str, object]:
    manifest = load_manifest()
    selected = [row for row in manifest if int(row["bulletin_month"][:4]) == year]
    expected_months = 11 if year == 2026 else 12
    if len(selected) != expected_months:
        raise RuntimeError(f"{year}: expected {expected_months} source months, found {len(selected)}")
    verify_sources(selected)
    rows = []
    for manifest_row in selected:
        rows.extend(extract_bulletin(manifest_row))
    if len(rows) != EXPECTED_YEAR_ROWS[year]:
        raise RuntimeError(f"{year}: expected {EXPECTED_YEAR_ROWS[year]} rows, found {len(rows)}")
    atomic_write_csv(output_path, rows)
    summary = {"year": year, "output": str(output_path), **summarize_rows(rows)}
    summary["sha256"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    atomic_write_text(report_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def read_year_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise RuntimeError(f"unexpected columns in {path}: {reader.fieldnames}")
        return list(reader)


def validate_merged(rows: list[dict[str, str]], manifest: list[dict[str, str]]) -> dict[str, object]:
    if len(rows) != TOTAL_EXPECTED_ROWS:
        raise RuntimeError(f"expected {TOTAL_EXPECTED_ROWS} merged rows, found {len(rows)}")
    keys = [
        (
            row["bulletin_month"],
            row["preference_type"],
            row["chart_type"],
            row["category"],
            row["chargeability_area"],
        )
        for row in rows
    ]
    duplicates = len(keys) - len(set(keys))
    if duplicates:
        raise RuntimeError(f"merged data contains {duplicates} duplicate logical keys")
    allowed_statuses = {"date", "current", "unavailable", "missing"}
    for row in rows:
        status = row["cutoff_status"]
        if status not in allowed_statuses:
            raise RuntimeError(f"invalid status: {status!r}")
        if (status == "date") != bool(row["cutoff_date"]):
            raise RuntimeError(f"status/date mismatch: {row}")
        if row["cutoff_date"]:
            date.fromisoformat(row["cutoff_date"])
    missing_rows = [row for row in rows if row["cutoff_status"] == "missing"]
    corrected_rows = [row for row in rows if row["parse_note"] == "source_typo_day_zero_padded"]
    other_notes = [row for row in rows if row["parse_note"] not in {"", "source_typo_day_zero_padded"}]
    if len(missing_rows) != 1:
        raise RuntimeError(f"expected exactly one missing source cell, found {len(missing_rows)}")
    if len(corrected_rows) != 1 or other_notes:
        raise RuntimeError(
            f"expected exactly one documented correction and no other notes; "
            f"found corrected={len(corrected_rows)}, other={len(other_notes)}"
        )
    manifest_urls = {row["source_url"] for row in manifest}
    manifest_paths = {row["local_path"] for row in manifest}
    data_urls = {row["source_url"] for row in rows}
    data_paths = {row["source_path"] for row in rows}
    if data_urls != manifest_urls or data_paths != manifest_paths:
        raise RuntimeError("merged data does not represent every manifest source exactly")
    chart_sets: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        chart_sets[row["bulletin_month"]].add((row["preference_type"], row["chart_type"]))
    for month, charts in chart_sets.items():
        expected = {
            ("family", "final_action"),
            ("employment", "final_action"),
        }
        if month >= "2015-10":
            expected |= {
                ("family", "date_for_filing"),
                ("employment", "date_for_filing"),
            }
        if charts != expected:
            raise RuntimeError(f"{month}: unexpected chart set {sorted(charts)}")
    return summarize_rows(rows)


def render_validation_report(
    rows: list[dict[str, str]],
    summary: dict[str, object],
    output_path: Path,
    source_summary: dict[str, object],
) -> str:
    by_year = Counter(row["bulletin_year"] for row in rows)
    by_preference_chart = Counter((row["preference_type"], row["chart_type"]) for row in rows)
    output_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
    lines = [
        "# Visa Priority Dates Validation Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "## Result",
        "",
        f"- Source files verified: {source_summary['files']}",
        f"- Source HTML bytes verified: {source_summary['bytes']}",
        f"- Output rows: {len(rows)}",
        f"- Output SHA-256: `{output_sha}`",
        f"- Bulletin coverage: {rows[0]['bulletin_month']} through {rows[-1]['bulletin_month']}",
        "- Duplicate logical keys: 0",
        "- Unhandled invalid values: 0",
        "- Published blank cells retained: 1",
        "- Documented source-typo corrections: 1",
        "",
        "## Rows by year",
        "",
        "| Year | Rows |",
        "|---:|---:|",
    ]
    lines.extend(f"| {year} | {by_year[str(year)]} |" for year in YEARS)
    lines.extend(["", "## Rows by preference and chart", "", "| Preference | Chart | Rows |", "|---|---|---:|"])
    for (preference, chart), count in sorted(by_preference_chart.items()):
        lines.append(f"| {preference} | {chart} | {count} |")
    lines.extend(["", "## Cutoff statuses", "", "| Status | Rows |", "|---|---:|"])
    for status, count in sorted(summary["status_counts"].items()):
        lines.append(f"| {status} | {count} |")
    lines.extend(
        [
            "",
            "## Source-specific handling",
            "",
            "- Date-for-Filing charts are absent before October 2015 and were not synthesized.",
            "- February 2017's duplicate Employment Final Action table was deduplicated after normalized-content comparison.",
            "- May 2015's `2OCT91` value was parsed as `1991-10-02`; the raw value and audit note remain in the CSV.",
            "- March 2011's blank employment cell remains a `missing` record with no parsed date.",
            "- Grouped published chargeability areas were retained rather than expanded into synthetic country rows.",
            "",
        ]
    )
    return "\n".join(lines)


def merge_years(staging_dir: Path, output_path: Path, validation_report: Path) -> dict[str, object]:
    manifest = load_manifest()
    source_summary = verify_sources(manifest)
    rows = []
    for year in YEARS:
        year_rows = read_year_csv(staging_dir / f"{year}.csv")
        if len(year_rows) != EXPECTED_YEAR_ROWS[year]:
            raise RuntimeError(f"{year}: expected {EXPECTED_YEAR_ROWS[year]} staged rows, found {len(year_rows)}")
        if {int(row["bulletin_year"]) for row in year_rows} != {year}:
            raise RuntimeError(f"{year}: staged file contains rows for another year")
        rows.extend(year_rows)
    summary = validate_merged(rows, manifest)
    atomic_write_csv(output_path, rows)
    try:
        import pandas as pd

        frame = pd.read_csv(output_path, dtype=str, keep_default_na=False)
        if len(frame) != TOTAL_EXPECTED_ROWS or list(frame.columns) != FIELDS:
            raise RuntimeError("pandas smoke-load validation failed")
    except ImportError as exc:
        raise RuntimeError("pandas is required for the final smoke-load validation") from exc
    report = render_validation_report(rows, summary, output_path, source_summary)
    atomic_write_text(validation_report, report)
    return {
        "rows": len(rows),
        "output": str(output_path),
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "validation_report": str(validation_report),
        **summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser("verify-sources")
    verify_parser.add_argument("--json", action="store_true")
    year_parser = subparsers.add_parser("extract-year")
    year_parser.add_argument("--year", type=int, required=True, choices=YEARS)
    year_parser.add_argument("--output", type=Path)
    year_parser.add_argument("--report", type=Path)
    merge_parser = subparsers.add_parser("merge")
    merge_parser.add_argument("--staging-dir", type=Path, default=STAGING_ROOT)
    merge_parser.add_argument("--output", type=Path, default=OUTPUT_ROOT / "visa-priority-dates.csv")
    merge_parser.add_argument("--validation-report", type=Path, default=OUTPUT_ROOT / "validation-report.md")
    args = parser.parse_args()

    if args.command == "verify-sources":
        result = verify_sources(load_manifest())
    elif args.command == "extract-year":
        output = args.output or STAGING_ROOT / f"{args.year}.csv"
        report = args.report or STAGING_ROOT / f"{args.year}.json"
        result = extract_year(args.year, output, report)
    else:
        result = merge_years(args.staging_dir, args.output, args.validation_report)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
