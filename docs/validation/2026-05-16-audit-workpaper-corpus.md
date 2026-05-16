# Audit Workpaper Corpus Smoke

Date: 2026-05-16

## Scope

Generated single-company audit workpaper Excel files for 5 public DART manufacturing filings.

## Results

| Company | Workbook generated | Note sheets | Known parser gaps |
|---|---|---:|---|
| AP시스템 | yes | 154 | Duplicate consolidated/separate note numbers are rendered as separate sheets with openpyxl suffixes; no crash observed in smoke inspection. |
| CJ제일제당 | yes | 157 | Duplicate consolidated/separate note numbers are rendered as separate sheets with openpyxl suffixes; no crash observed in smoke inspection. |
| DB하이텍 | yes | 141 | Duplicate consolidated/separate note numbers are rendered as separate sheets with openpyxl suffixes; no crash observed in smoke inspection. |
| DS단석 | yes | 205 | Dense DART section numbering still creates many parsed note sheets; no crash observed in smoke inspection. |
| GST | yes | 76 | Some DART paragraph nodes combine note title and first body paragraph, so sheet title can include body text. |

## Inspection Evidence

All generated workbooks opened with openpyxl. Each inspected workbook contained `Validation Summary`, at least one `Note ...` sheet, and a `검증 결과` marker on the first note sheet.

| Workbook | Validation summary checks | First note sheet | Validation marker |
|---|---:|---|---|
| `ap_system.xlsx` | 1470 | `Note 1` | yes |
| `cj_cheiljedang.xlsx` | 1962 | `Note 1` | yes |
| `db_hitek.xlsx` | 1731 | `Note 1` | yes |
| `ds_danseok.xlsx` | 1438 | `Note 1` | yes |
| `gst.xlsx` | 454 | `Note 1` | yes |

## Failure Categories

- Structure parsing gaps: DART paragraph nodes can combine note headings with body text; consolidated and separate financial statements create duplicate note numbers.
- Ambiguous total labels: Generic total checks intentionally emit `not_tested` or `parse_uncertain` when no reliable total label is found.
- Statement-note mapping gaps: First-pass keyword matching only covers common audit relationships and skips missing evidence.
- Note-note mapping gaps: Relationship rules are conservative and emit `parse_uncertain` for multiple candidates.
- Prior-year mapping gaps: Prior-year checks require normalized note title equality and are not run in this no-prior smoke.
