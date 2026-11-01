# Visa Priority Dates Validation Report

Generated: 2026-10-30T06:21:05+00:00

## Result

- Source files verified: 191
- Source HTML bytes verified: 14651283
- Output rows: 23603
- Output SHA-256: `e19c42a2f7a91edfc25568c404d5a62d5a1d48b7ff24f310c4b091f6391f0e5e`
- Bulletin coverage: 2011-01 through 2026-11
- Duplicate logical keys: 0
- Unhandled invalid values: 0
- Published blank cells retained: 1
- Documented source-typo corrections: 1

## Rows by year

| Year | Rows |
|---:|---:|
| 2011 | 802 |
| 2012 | 725 |
| 2013 | 720 |
| 2014 | 720 |
| 2015 | 930 |
| 2016 | 1624 |
| 2017 | 1680 |
| 2018 | 1816 |
| 2019 | 1848 |
| 2020 | 1848 |
| 2021 | 1824 |
| 2022 | 1956 |
| 2023 | 1860 |
| 2024 | 1800 |
| 2025 | 1800 |
| 2026 | 1650 |

## Rows by preference and chart

| Preference | Chart | Rows |
|---|---|---:|
| employment | date_for_filing | 6461 |
| employment | final_action | 9002 |
| family | date_for_filing | 3350 |
| family | final_action | 4790 |

## Cutoff statuses

| Status | Rows |
|---|---:|
| current | 9366 |
| date | 13781 |
| missing | 1 |
| unavailable | 455 |

## Source-specific handling

- Date-for-Filing charts are absent before October 2015 and were not synthesized.
- February 2017's duplicate Employment Final Action table was deduplicated after normalized-content comparison.
- May 2015's `2OCT91` value was parsed as `1991-10-02`; the raw value and audit note remain in the CSV.
- March 2011's blank employment cell remains a `missing` record with no parsed date.
- Grouped published chargeability areas were retained rather than expanded into synthetic country rows.
