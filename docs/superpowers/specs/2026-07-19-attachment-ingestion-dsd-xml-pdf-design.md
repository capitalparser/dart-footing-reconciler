# DSD, XML, PDF Attachment Ingestion Design

**Date:** 2026-07-19
**Status:** Approved design, pending written-spec review
**Scope:** Native-text DART HTML, DSD, XML, and PDF attachments that feed the existing audit workbench report

## Objective

Allow a user to attach one DART report and generate the existing Korean audit
workbench from that attachment regardless of whether the source is HTML, DSD,
XML, or a machine-generated PDF. The same validation engine, result schema,
consolidation-basis rules, and report renderer must run after ingestion.

Scanned or image-only PDFs are explicitly outside this phase. They must stop
with a user-facing `OCR 필요` outcome and must never produce an empty or
apparently successful validation report.

## Design Principles

1. **One ingestion contract.** CLI workpapers, browser upload, and package
   callers must use one attachment loader instead of calling
   `parse_full_report()` independently.
2. **Fail closed.** Unsupported, unreadable, image-only, or structurally empty
   inputs return a domain error. A report with zero usable financial-statement
   and note structure is never exported.
3. **Preserve source location.** PDF-derived evidence retains page number and
   bounding box. DSD, XML, and HTML retain their existing section, block,
   table, row, and column locations.
4. **Keep checks separate.** Footing and reconciliation remain distinct checks;
   ingestion only supplies a normalized `FullReport`.
5. **No company-specific PDF rules.** Table extraction and structural
   validation depend on page geometry and document vocabulary, not company
   names.
6. **No React or Next.js.** The existing static web shell and Python engine are
   retained.

## Supported Inputs

| Format | Phase-1 behavior | Rejection boundary |
|---|---|---|
| HTML/HTM | Decode and parse directly | Encoding failure or no report structure |
| DSD | Decode XML/HTML-like DART markup and parse | Unsupported binary/container or no report structure |
| XML | Decode and parse DART XML/HTML-like markup | Malformed/unusable markup or no report structure |
| PDF | Extract machine text, page geometry, and tables | Image-only/scanned, encrypted, no usable tables, or no report structure |

File format detection uses both signature/content and extension. A `.pdf`
extension or `%PDF` signature always selects the PDF path. XML/DSD detection
uses extension and root markers such as `DOCUMENT` and `DART`. Mismatched
extension/content is recorded as a diagnostic and the content signature wins.

## Architecture

### Attachment contract

Create a focused attachment-ingestion module with these public types:

`AttachmentDiagnostic` is an immutable value with `code: str`, `message: str`,
and optional `page: int`. `ParsedAttachment` is an immutable value with
`source: Path`, `input_format: str`, `report: FullReport`, and
`diagnostics: tuple[AttachmentDiagnostic, ...]`. The public entrypoint is:

```text
parse_report_attachment(source: str | Path, *, company: str = "") -> ParsedAttachment
```

The module owns local-path validation, format detection, decoding, PDF
extraction, and post-parse structure validation. Existing `load_local_report()`
may remain as a compatibility wrapper for the simpler footing-only payload,
but it must delegate format detection and decoding to the new contract.

### Structured text inputs

HTML, DSD, and XML are decoded using the existing Korean encoding order:
UTF-8, UTF-8 with BOM, CP949, and EUC-KR. The decoded markup is passed to the
existing full-report parser through a text-based entrypoint so callers do not
need to create extension-specific temporary files.

The parser continues to emit the existing statements, notes, tables, merged
cells, units, consolidation basis, and narrative blocks. Format detection is
metadata only; it must not change validation outcomes for equivalent markup.

### Native PDF extraction

Use `pdfplumber` because it exposes page characters, words, lines, rectangles,
table cells, bounding boxes, and page numbers, and is designed for
machine-generated PDFs. PDF extraction is a separate adapter that produces
the same `FullReport` domain model as the structured-text path.

For each page, the adapter:

1. extracts words with coordinates;
2. finds tables using drawn lines and rectangle edges first;
3. retries only pages without detected tables using text alignment;
4. orders narrative regions and tables by vertical position;
5. carries nearby headings and unit declarations into table context;
6. emits `ReportBlock` and `ReportTable` values without running validation;
7. preserves page and bounding-box provenance.

The adapter does not infer missing amounts, merge tables across pages, or use
an LLM. A continued table on the next page remains a separate source table in
this phase. The validation layer may compare them only through existing,
explicit check logic.

### PDF source location

Extend `SourceLocation` with backward-compatible optional fields:

```python
page_number: int | None = None
bbox: tuple[float, float, float, float] | None = None
input_format: str = "html"
```

Existing constructors remain valid. PDF table cells use the table bounding
box as the minimum provenance guarantee; cell-level boxes are preserved when
the extractor returns them reliably. The report renderer displays `PDF N쪽`
in source captions and drawer links.

### Structure validation

After parsing any format, the loader validates:

- at least one statement or note section exists;
- at least one usable table exists;
- statement/note sections do not consist only of blank blocks;
- PDF text density is sufficient to distinguish native text from image-only
  pages.

Domain errors use a closed set of codes:

| Code | User-facing meaning |
|---|---|
| `PDF_OCR_REQUIRED` | 텍스트를 읽을 수 없는 PDF입니다. OCR 처리된 PDF가 필요합니다. |
| `PDF_ENCRYPTED` | 암호화된 PDF는 검증할 수 없습니다. |
| `PDF_TABLES_NOT_FOUND` | PDF에서 검증 가능한 표를 찾지 못했습니다. |
| `REPORT_STRUCTURE_NOT_FOUND` | 재무제표 또는 주석 구조를 찾지 못했습니다. |
| `ATTACHMENT_FORMAT_UNSUPPORTED` | 지원하지 않는 첨부 형식입니다. |
| `ATTACHMENT_DECODE_FAILED` | 파일 문자 인코딩을 확인할 수 없습니다. |

These errors are caught at CLI and browser boundaries and rendered without
tracebacks or implementation vocabulary.

## CLI Integration

`foot`, `foot-excel`, `workpaper-excel`, and `workpaper-html` all call the
common attachment contract. Argument names and help text change from
`current_html` to source-neutral wording while preserving command invocation
compatibility.

The prior-period option accepts the same supported formats independently of
the current-period file. A current PDF and prior DSD, for example, are valid
if both parse successfully.

No output file is created after an attachment-domain error. This specifically
closes the current defect where `workpaper-html` accepts `%PDF` bytes and emits
an empty report with exit code zero.

## Web Upload Integration

The file picker accepts `.html`, `.htm`, `.dsd`, `.xml`, and `.pdf`.

The deployed/local web shell submits the selected file as multipart field
`file` to `POST /api/verify`. The endpoint is backed by
`parse_report_attachment()` and accepts exactly one multipart request whose
entire encoded body is no greater than 32 MiB. It
returns either:

- `200 text/html` containing the complete audit-workbench; or
- `4xx application/json` containing `error`, `message`, and `next_action`.

For localhost operation the server binds to `127.0.0.1`; the selected report
does not leave the machine. The existing Pyodide path remains a fallback for
HTML/DSD/XML-only static builds, but PDF is enabled only when the verification
endpoint is present. The UI must state that distinction instead of silently
retrying or producing partial output.

The endpoint accepts one current file in this phase. Prior-period upload UI is
not added; the existing CLI/package prior-report option remains available.

## Report UI

The audit-workbench layout and current connection/separate selector remain
unchanged. PDF-derived panels display page provenance in the panel caption,
for example `PDF 37쪽 · 주석 15`.

When the attachment cannot be verified, the report area stays empty and the
input panel shows only:

- what was detected;
- why verification stopped; and
- the next user action.

Stack traces, library names, parser class names, and error codes are not shown
to the user.

## Dependency and Deployment Boundary

Add `pdfplumber` as the machine-generated PDF extraction dependency. The
project does not add OCR software in this phase. PDF visual debugging remains
a development/QA tool, not a runtime dependency.

The server-backed upload path is the production-capable route for PDF. A
static-only bundle continues to support HTML/DSD/XML and explicitly marks PDF
as requiring the verification service.

## Testing Strategy

All behavior changes follow red-green-refactor TDD.

### Unit tests

- content-signature and extension classification;
- CP949 DSD and UTF-8 XML decoding;
- PDF page/table extraction with source page and bounding box;
- image-only PDF detection;
- encrypted PDF detection;
- empty-structure rejection;
- backward compatibility of `SourceLocation` constructors.

### Integration tests

- HTML, DSD, and XML versions of equivalent markup produce equivalent
  statement/note/table structures;
- native PDF fixture produces a non-empty `FullReport` and audit workbench;
- `workpaper-html` with image-only PDF exits nonzero and creates no output;
- web upload accepts all five extensions and renders stable error actions;
- current and prior attachments can use different supported formats.

### Parser fixture requirements

DSD/XML parser tests assert source location and uncertainty. PDF fixtures pin
page number, table bounding box, rows, amounts, unit, and structure-rejection
behavior. Synthetic fixtures are supplemented with at least one redacted or
public machine-generated Korean financial-statement PDF before PDF support is
described as audit-ready.

### Regression commands

```text
uv run pytest -q tests/test_attachment_ingestion.py tests/test_pdf_ingestion.py
uv run pytest -q tests/test_cli.py tests/test_verify_app.py
uv run ruff check src tests
uv run pytest -q
```

Missing external corpus fixtures are reported separately from failures in the
new attachment-ingestion tests.

## Acceptance Criteria

1. HTML, DSD, and XML attachments generate the same audit workbench for
   semantically equivalent markup.
2. A machine-generated PDF containing recognizable financial statements and
   notes generates a non-empty audit workbench with page-backed evidence.
3. Image-only or scanned PDFs show an OCR-required action and generate no
   report artifact.
4. A malformed or structurally empty attachment generates no report artifact.
5. `workpaper-html` can no longer return success for raw `%PDF` bytes without
   extracted report structure.
6. Browser and CLI use the same domain error codes and user-facing actions.
7. Existing HTML report results and ordering remain unchanged for the same
   source document.

## Out of Scope

- OCR and scanned-PDF recognition;
- LLM-assisted table repair or label inference;
- merging continuation tables across PDF pages;
- password entry for encrypted PDFs;
- multiple simultaneous company uploads;
- editing the attached report;
- mobile UI.
