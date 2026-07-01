# Text PDF Report Ingest - Design Spec

**Date:** 2026-07-01
**Project:** 09_dart_footing_reconciler
**Status:** Approved design. Implementation not started.
**Surface:** CLI workpaper commands, local attachment footing, and the offline verify app.

## Goal

Allow internal users to attach a DART DSD/HTML file or a text-layer PDF and run the existing
document-internal validation logic without changing the verification engine's basis. The engine
continues to consume `FullReport`; the new work is an ingest layer that turns supported
attachments into `FullReport` plus explicit extraction diagnostics.

The first PDF scope is deliberately narrow: **text-layer PDF only**. Scanned PDF OCR is out of
scope for this slice because OCR table recognition can create false matches. If the PDF cannot
produce reliable table and source-position evidence, the system must abstain or emit
`parse_uncertain`; it must never manufacture a `matched` result from weak extraction.

## Non-goals

- No ERP, GL, TB, journal, or company-source linkage. Validation remains limited to the provided
  disclosure document.
- No OCR-first or scanned-PDF support.
- No LLM-only parsing or probabilistic verdicts.
- No rewrite of checks, taxonomy, amount locator, or report HTML rendering.
- No change to existing DSD/HTML verification counts except metadata showing the normalized input
  format.

## Current State

- `document.py:parse_full_report(path, company=...)` parses local DART HTML/DSD-like text into
  `FullReport`.
- `local_report.py:load_local_report()` rejects PDF by extension or `%PDF` signature.
- `verify_app.py:verify_html_report()` rejects PDF-like text before writing a temporary HTML file.
- `static/dart-verify/app.js` rejects `.pdf` before Pyodide engine execution.
- Workpaper CLI commands call `parse_full_report()` directly, so they bypass `local_report.py`.

This leaves three different input paths. The design consolidates them behind one ingest API.

## Architecture

```text
Attachment bytes/path
  -> detect_report_format()
  -> DSD/HTML/XML text adapter
  -> Text PDF adapter
  -> ParsedAttachment{format, report, diagnostics}
  -> assemble_report_checks(report, ...)
  -> existing HTML/Excel workpaper renderers
```

The new API is package-level and deterministic:

```python
ParsedAttachment = parse_attached_report(source, *, company="")
```

`ParsedAttachment.report` is a normal `FullReport`. `ParsedAttachment.diagnostics` records input
format, extraction warnings, unsupported features, page/table counts, and whether PDF extraction
was complete enough for validation. Existing checks do not read diagnostics to create matches;
diagnostics only gate extraction confidence and drive reviewer-facing messages.

## Components

### 1. Format Detection

Add `report_ingest.py` with:

- `detect_report_format(path_or_bytes, filename="") -> "html" | "dsd" | "xml" | "pdf" | "unknown"`
- extension plus magic-byte/content sniffing:
  - `.html`, `.htm`, HTML tags -> `html`
  - `.dsd`, DART/XML document markers -> `dsd` or `xml`
  - `%PDF` or `.pdf` -> `pdf`
- URL-like sources remain rejected.

This replaces PDF rejection in `local_report.py`, `verify_app.py`, and `static/dart-verify/app.js`.

### 2. DSD/HTML Adapter

Keep the existing path stable:

- Decode text with current Korean encoding ladder.
- Write in-memory bytes to a temp file only when a path is required by `parse_full_report`.
- Call `parse_full_report()`.
- Preserve the existing `raw_html`, `row_acodes`, `unit_multiplier`, and `SourceLocation` behavior.

This path is the regression guard. It should produce the same `FullReport` and status histogram as
today.

### 3. Text PDF Adapter

Add `pdf_report.py` for text-layer PDF extraction. Use a pure-Python stack first so the CLI and
Pyodide/server paths have a chance to share behavior:

- Primary extraction: `pdfplumber` when available.
- Fallback for text-only checks: `pypdf` for page text, but table extraction is then marked
  insufficient unless a deterministic table grid can be reconstructed.
- Add optional dependency group `pdf = ["pdfplumber>=0.11", "pypdf>=5"]`.

The adapter creates `ReportSection`, `ReportBlock`, and `ReportTable` objects by reconstructing
tables from PDF words and coordinates:

- page text is grouped into candidate sections by DART headings and note headings.
- tables are formed from page-local word boxes using stable `y` row clusters and `x` column
  clusters.
- each extracted table receives `SourceLocation(section_id, block_index, table_index)`.
- PDF-specific coordinates are preserved in a sidecar diagnostic map keyed by source reference:
  `pdf:page:{n}/table:{idx}/row:{r}/col:{c}`.

The first implementation maps source strings back to the existing `statement:` and `note:`
format for compatibility, while diagnostics retain the page coordinate sidecar for reviewer
traceability.

### 4. Extraction Confidence and Abstain Rules

PDF extraction may only feed checks when the table is structurally reliable:

- at least two rows and two columns.
- numeric cells are isolated from labels.
- current/prior column labels are detectable or the table is single-period and unambiguous.
- note/statement section assignment is known.
- unit text is detected from nearby text or defaults to `1` with a warning.

If these conditions fail, the adapter still preserves text/table candidates for review, but marks
the section/table diagnostic as uncertain. Downstream checks should then either not run on that
table or emit `parse_uncertain` with a controlled reason such as:

- `PDF_TEXT_LAYER_MISSING`
- `PDF_TABLE_GRID_UNCERTAIN`
- `PDF_SECTION_UNCERTAIN`
- `PDF_COLUMN_UNCERTAIN`
- `PDF_UNIT_UNCERTAIN`

These are extraction confidence gates, not lower-priority matched verdicts.

### 5. CLI Integration

Replace direct parser calls in user-facing commands:

- `foot`
- `foot-excel`
- `workpaper-excel`
- `workpaper-html`
- `coverage`
- `semantic-attempts` or other commands that currently accept one local report path

Each command uses `parse_attached_report()` or a thin wrapper that returns the current decoded text
for legacy `scan_html()` paths. The command output includes `input_format`.

For unsupported scanned PDFs, the message must be explicit:

> 텍스트 레이어가 없는 PDF입니다. OCR PDF는 아직 지원하지 않습니다. DSD/HTML 또는 텍스트 PDF를 첨부하세요.

### 6. Offline Verify App Integration

The browser app should stop rejecting `.pdf` in JavaScript before engine execution. Instead:

- FileReader passes filename and bytes/text to a new Python entrypoint:
  `verify_attached_report(file_bytes, filename, company="", tolerance=1)`.
- HTML/DSD is decoded and parsed as today.
- The first implementation does not require bundling PDF extraction dependencies into Pyodide.
- If the Pyodide runtime lacks the optional PDF dependency group, the UI displays a deterministic
  unsupported-runtime message while CLI/server PDF remains available. This must be tested
  explicitly rather than silently falling back to HTML parsing.

Shared browser PDF extraction is a later performance/packaging slice. Accuracy and deterministic
failure are more important than browser feature parity in this first slice.

### 7. Workpaper UI

The existing `report_html.py` surface remains the main reviewer view. Add only small metadata:

- report masthead shows `입력 형식: DSD/HTML/PDF`.
- PDF reports show `PDF 텍스트 추출 기반` as a non-verdict provenance label.
- extraction diagnostics appear in the parse diagnostics panel, not above note source tables.
- source jumps for PDF may initially jump to extracted source table rows; page coordinates are
  included in technical detail until rendered-page highlighting is added in a later slice.

## Data Flow and Boundaries

The validation basis remains the provided document. The PDF adapter is allowed to convert the
document into tables and text; it is not allowed to infer missing facts from outside sources.

`FullReport` remains the engine contract:

```text
PDF/DSD/HTML -> FullReport -> checks -> CheckResult -> report_html
```

No check should branch on "this came from PDF" to create a match. PDF only affects extraction
confidence and source provenance.

## Testing

### Unit Tests

- format detector classifies extension, magic bytes, and XML/HTML markers.
- existing PDF rejection tests are rewritten to expect text-PDF acceptance or scanned-PDF
  unsupported messages.
- DSD/HTML fixture through `parse_attached_report()` equals `parse_full_report()` on statement/note
  counts and status histogram.
- text PDF fixture with simple statements and one note produces a `FullReport` with source-backed
  tables.
- PDF with no text layer emits `PDF_TEXT_LAYER_MISSING` and does not run normal checks.
- ambiguous PDF table emits `PDF_TABLE_GRID_UNCERTAIN` or `PDF_COLUMN_UNCERTAIN`.

### Integration Tests

- `workpaper-html sample.pdf out.html --company ...` writes a report for a text PDF.
- `workpaper-html scanned.pdf out.html` fails with the Korean scanned-PDF message.
- offline verify app no longer rejects `.pdf` in JS before engine execution; it either returns the
  PDF-backed cockpit or the explicit unsupported-runtime message.
- existing HTML/DSD commands keep the same status histograms.

### Visual Checks

- Render a text-PDF workpaper and inspect that:
  - source tables are readable.
  - diagnostics are visible but not mixed into the note body.
  - no source text/table overlaps.
  - reviewer can distinguish PDF extraction uncertainty from validation gaps.

## Rollout

1. Add `report_ingest.py` and migrate HTML/DSD paths behind it with no behavior change.
2. Add text-PDF extraction for a tiny fixture and CLI `workpaper-html`.
3. Add extraction diagnostics and controlled parse-uncertain reason codes.
4. Wire `workpaper-excel`, local footing commands, and coverage commands.
5. Wire the offline verify app with shared PDF support or explicit runtime limitation.
6. Run full tests and a rendered Playwright smoke for the PDF workpaper.

## Implementation Decisions Locked

- First slice supports text PDF in the Python CLI/server runtime.
- First slice does not require PDF extraction dependencies inside the Pyodide browser bundle. The
  browser must route `.pdf` through the shared entrypoint and then show an explicit
  unsupported-runtime message when PDF dependencies are unavailable.
- PDF page coordinates stay in an ingest diagnostic sidecar for the first slice. `SourceLocation`
  remains unchanged to avoid touching every renderer and check consumer.

## Acceptance Criteria

- Users can attach DSD/HTML exactly as before.
- Users can attach a text-layer PDF and receive an HTML workpaper using the existing validation
  logic.
- Scanned PDFs fail clearly and do not produce misleading partial matches.
- Every amount used by a check still has a source reference.
- Existing HTML/DSD corpus status counts are unchanged.
- `uv run pytest` passes.
