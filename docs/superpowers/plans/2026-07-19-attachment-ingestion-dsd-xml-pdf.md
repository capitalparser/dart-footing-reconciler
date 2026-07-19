# DSD, XML, PDF Attachment Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate the existing audit-workbench report from HTML, DSD, XML, or native-text PDF attachments while rejecting scanned, encrypted, or structurally empty inputs without writing misleading output artifacts.

**Architecture:** A new attachment-ingestion facade owns local-file validation, content-first format detection, decoding, PDF extraction, and fail-closed structure validation. HTML-like inputs and PDF-normalized markup both feed one text parser, so the existing validation and report layers remain unchanged. CLI commands and a localhost `POST /api/verify` endpoint consume the same facade; the static browser shell uses that endpoint and retains its Pyodide fallback only for HTML/DSD/XML.

**Tech Stack:** Python 3.11+, BeautifulSoup/lxml, pdfplumber, Typer, standard-library HTTP server, vanilla JavaScript, Pyodide fallback, pytest, Vitest, Playwright.

## Global Constraints

- Footing and cash-flow reconciliation remain separate checks.
- Every material PDF amount preserves at least page-level and table-bounding-box source location.
- Label or structure uncertainty is explicit; no LLM or company-name routing is allowed.
- Image-only/scanned PDF input stops with `PDF_OCR_REQUIRED`; OCR is out of scope.
- Empty or unusable parsed structure never produces an HTML or Excel artifact.
- Existing HTML validation result IDs, ordering, amounts, and statuses remain unchanged.
- Keep the existing static desktop web shell; do not add React, Next.js, or mobile UI.
- Do not run git commands. Use test checkpoints instead of commits.
- Parser changes require source-location and uncertainty fixture coverage.

---

## File Structure

- Create `src/dart_footing_reconciler/attachment_ingestion.py`: public attachment contract, domain errors, format detection, decoding, structure validation, and dispatch.
- Create `src/dart_footing_reconciler/pdf_ingestion.py`: native PDF to source-annotated HTML-like markup extraction only; no validation logic.
- Create `src/dart_footing_reconciler/verify_server.py`: localhost static server plus `POST /api/verify` upload boundary.
- Modify `src/dart_footing_reconciler/document.py`: add text parser entrypoint and optional PDF source fields.
- Modify `src/dart_footing_reconciler/local_report.py`: compatibility wrapper over shared format/decode functions.
- Modify `src/dart_footing_reconciler/cli.py`: route workpaper and verify-server commands through the facade.
- Modify `src/dart_footing_reconciler/verify_app.py`: byte/path entrypoint shared by the server.
- Modify `src/dart_footing_reconciler/report_html.py`: display PDF page provenance.
- Modify `src/dart_footing_reconciler/__init__.py`: export the stable attachment API.
- Modify `static/dart-verify/index.html`: accept and describe XML/PDF.
- Modify `static/dart-verify/app.js`: upload to `/api/verify`, retain non-PDF Pyodide fallback.
- Modify `pyproject.toml` and `uv.lock`: add `pdfplumber` runtime and `reportlab` development dependencies.
- Create `tests/test_attachment_ingestion.py`: HTML/DSD/XML equivalence, detection, decoding, empty rejection.
- Create `tests/test_pdf_ingestion.py`: PDF extraction, provenance, OCR/encryption/table failures.
- Create `tests/test_verify_server.py`: multipart endpoint success/error and localhost-only behavior.
- Modify `tests/test_cli.py`, `tests/test_cli_workpaper.py`, `tests/test_document.py`, `tests/test_verify_app.py`, `tests/test_build_verify_app.py`, and `tests/js/dart_verify_app.test.js` for integration contracts.

---

### Task 1: Text Parser Entry Point and Backward-Compatible Source Location

**Files:**
- Modify: `src/dart_footing_reconciler/document.py`
- Test: `tests/test_document.py`

**Interfaces:**
- Produces: `parse_full_report_text(markup: str, *, source: str, company: str = "", input_format: str = "html") -> FullReport`
- Produces: `SourceLocation.page_number`, `SourceLocation.bbox`, and `SourceLocation.input_format` with backward-compatible defaults.
- Consumes: existing `parse_full_report()` callers without behavior changes.

- [ ] **Step 1: Write failing parser API and compatibility tests**

Add:

```python
from dart_footing_reconciler.document import SourceLocation, parse_full_report_text


def test_source_location_pdf_fields_are_backward_compatible():
    original = SourceLocation("note:1", 0, 3, 2, 1)

    assert original.page_number is None
    assert original.bbox is None
    assert original.input_format == "html"


def test_parse_full_report_text_preserves_source_and_format():
    report = parse_full_report_text(
        "<p>재무상태표</p><table><tr><td>구분</td><td>당기</td></tr>"
        "<tr><td>자산총계</td><td>1,000</td></tr></table>",
        source="uploaded.dsd",
        company="Sample Co",
        input_format="dsd",
    )

    assert report.source == "uploaded.dsd"
    assert report.statements[0].blocks[0].location.input_format == "dsd"
```

- [ ] **Step 2: Run RED test**

Run:

```text
uv run pytest -q tests/test_document.py -k "source_location_pdf_fields or parse_full_report_text"
```

Expected: import/attribute failure because the API and fields do not exist.

- [ ] **Step 3: Extract a text-based parser without changing behavior**

Add optional fields to `SourceLocation`:

```python
@dataclass(frozen=True)
class SourceLocation:
    section_id: str
    block_index: int
    table_index: int | None = None
    row_index: int | None = None
    column_index: int | None = None
    page_number: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    input_format: str = "html"
```

Refactor `parse_full_report` into a file wrapper and text entrypoint:

```python
def parse_full_report(source: str | Path, *, company: str = "") -> FullReport:
    path = Path(source)
    return parse_full_report_text(
        _read_dart_html(path),
        source=str(path),
        company=company,
        input_format="html",
    )


def parse_full_report_text(
    markup: str,
    *,
    source: str,
    company: str = "",
    input_format: str = "html",
) -> FullReport:
    soup = BeautifulSoup(markup, "lxml")
    # Move the existing parse_full_report body here unchanged after soup creation.
```

Replace every new `SourceLocation(...)` created inside the text parser with a
small helper that carries `input_format` and optional PDF attributes from the
DOM node:

```python
def _source_location(
    section_id: str,
    block_index: int,
    *,
    table_index: int | None = None,
    node: Tag | None = None,
    input_format: str = "html",
) -> SourceLocation:
    page = int(node["data-pdf-page"]) if node and node.get("data-pdf-page") else None
    bbox = _parse_pdf_bbox(node.get("data-pdf-bbox")) if node else None
    return SourceLocation(
        section_id,
        block_index,
        table_index,
        page_number=page,
        bbox=bbox,
        input_format=input_format,
    )
```

`_parse_pdf_bbox` returns `None` unless exactly four finite floats are present.

- [ ] **Step 4: Run GREEN and full document tests**

Run:

```text
uv run pytest -q tests/test_document.py
```

Expected: all document tests pass with unchanged HTML structures.

---

### Task 2: Common Attachment Contract for HTML, DSD, and XML

**Files:**
- Create: `src/dart_footing_reconciler/attachment_ingestion.py`
- Modify: `src/dart_footing_reconciler/local_report.py`
- Modify: `src/dart_footing_reconciler/__init__.py`
- Test: `tests/test_attachment_ingestion.py`

**Interfaces:**
- Produces: `AttachmentDiagnostic`, `AttachmentIngestionError`, `ParsedAttachment`.
- Produces: `detect_attachment_format(path: Path, data: bytes, text: str | None = None) -> str`.
- Produces: `parse_report_attachment(source: str | Path, *, company: str = "") -> ParsedAttachment`.
- Consumes: `parse_full_report_text` from Task 1.

- [ ] **Step 1: Write failing equivalence, detection, and fail-closed tests**

Create the test module with this shared markup and assertions:

```python
from pathlib import Path

import pytest

from dart_footing_reconciler.attachment_ingestion import (
    AttachmentIngestionError,
    detect_attachment_format,
    parse_report_attachment,
)


MARKUP = """
<DOCUMENT>
<p>재무상태표</p>
<table><tr><th>구분</th><th>당기</th></tr><tr><td>자산총계</td><td>1,000</td></tr></table>
<p>재무제표 주석</p>
<p>8. 매출채권</p>
<table><tr><th>구분</th><th>금액</th></tr><tr><td>합계</td><td>100</td></tr></table>
</DOCUMENT>
"""


@pytest.mark.parametrize("suffix,encoding", [("html", "utf-8"), ("dsd", "cp949"), ("xml", "utf-8")])
def test_equivalent_structured_attachments_produce_equivalent_reports(tmp_path, suffix, encoding):
    path = tmp_path / f"report.{suffix}"
    path.write_bytes(MARKUP.encode(encoding))

    parsed = parse_report_attachment(path, company="Sample Co")

    assert parsed.input_format == suffix
    assert [section.title for section in parsed.report.statements] == ["재무상태표"]
    assert [(note.note_no, note.title) for note in parsed.report.notes] == [("8", "매출채권")]
    assert parsed.report.notes[0].blocks[0].location.input_format == suffix


def test_pdf_signature_wins_over_html_extension(tmp_path):
    path = tmp_path / "wrong.html"
    path.write_bytes(b"%PDF-1.7\n")
    assert detect_attachment_format(path, path.read_bytes()) == "pdf"


def test_structurally_empty_attachment_is_rejected(tmp_path):
    path = tmp_path / "empty.xml"
    path.write_text("<DOCUMENT><p>설명만 있습니다.</p></DOCUMENT>", encoding="utf-8")

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "REPORT_STRUCTURE_NOT_FOUND"
```

- [ ] **Step 2: Run RED test**

Run:

```text
uv run pytest -q tests/test_attachment_ingestion.py
```

Expected: module import failure.

- [ ] **Step 3: Implement the attachment domain model and structured paths**

Create immutable data types and a code-bearing exception:

```python
@dataclass(frozen=True)
class AttachmentDiagnostic:
    code: str
    message: str
    page: int | None = None


class AttachmentIngestionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ParsedAttachment:
    source: Path
    input_format: str
    report: FullReport
    diagnostics: tuple[AttachmentDiagnostic, ...] = ()
```

Implement content-first dispatch:

```python
def detect_attachment_format(path: Path, data: bytes, text: str | None = None) -> str:
    stripped = data.lstrip()
    if path.suffix.lower() == ".pdf" or stripped.startswith(b"%PDF"):
        return "pdf"
    suffix = path.suffix.lower()
    if suffix == ".dsd":
        return "dsd"
    if suffix == ".xml":
        return "xml"
    if suffix in {".html", ".htm"}:
        return "html"
    prefix = (text or "")[:4096].lower()
    if "<document" in prefix or "<dart" in prefix:
        return "dsd"
    if prefix.lstrip().startswith("<?xml"):
        return "xml"
    raise AttachmentIngestionError(
        "ATTACHMENT_FORMAT_UNSUPPORTED",
        "지원하지 않는 첨부 형식입니다.",
    )
```

For non-PDF paths, decode with the existing encoding order, call
`parse_full_report_text`, and reject unless at least one section and one usable
table exist. The PDF branch imports `extract_pdf_markup` lazily and is completed
in Task 3.

Make `local_report._input_format` and `_decode_text` delegate to the new shared
helpers while preserving `LocalReport`, `LocalReportError`, and existing error
messages for package compatibility.

- [ ] **Step 4: Run GREEN tests and existing local-report tests**

Run:

```text
uv run pytest -q tests/test_attachment_ingestion.py tests/test_cli.py -k "foot or attachment"
```

Expected: structured attachment tests and existing footing attachment tests pass.

---

### Task 3: Native PDF Extraction and OCR/Encryption Boundaries

**Files:**
- Create: `src/dart_footing_reconciler/pdf_ingestion.py`
- Modify: `src/dart_footing_reconciler/attachment_ingestion.py`
- Modify: `pyproject.toml`
- Update mechanically: `uv.lock`
- Create: `tests/test_pdf_ingestion.py`

**Interfaces:**
- Produces: `PdfExtraction(markup: str, diagnostics: tuple[AttachmentDiagnostic, ...])`.
- Produces: `extract_pdf_markup(source: Path) -> PdfExtraction`.
- Consumes: `AttachmentIngestionError` and `AttachmentDiagnostic` from Task 2.

- [ ] **Step 1: Add dependencies with the project package manager**

Run:

```text
uv add 'pdfplumber>=0.11,<0.12'
uv add --dev 'reportlab>=4.2,<5' 'pypdf>=5,<6'
```

Expected: `pyproject.toml` and `uv.lock` update without resolving OCR packages.

- [ ] **Step 2: Write failing native, OCR, encrypted, and provenance tests**

Use ReportLab only to create deterministic test PDFs. Register the built-in
Korean CID font so tests do not depend on machine-specific font files:

```python
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
from reportlab.platypus import TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from PIL import Image
from pypdf import PdfReader, PdfWriter


GRID_STYLE = TableStyle([
    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ("FONTNAME", (0, 0), (-1, -1), "HYSMyeongJo-Medium"),
])


def _native_financial_pdf(path):
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "HYSMyeongJo-Medium"
    doc = SimpleDocTemplate(str(path))
    doc.build([
        Paragraph("재무상태표", styles["Heading1"]),
        Table(
            [["구분", "당기"], ["자산총계", "1,000"]],
            style=GRID_STYLE,
        ),
        Spacer(1, 12),
        Paragraph("재무제표 주석", styles["Heading1"]),
        Paragraph("8. 매출채권", styles["Heading2"]),
        Table([["구분", "금액"], ["합계", "100"]], style=GRID_STYLE),
    ])
```

Tests:

```python
def test_native_pdf_produces_report_with_page_and_bbox(tmp_path):
    path = tmp_path / "report.pdf"
    _native_financial_pdf(path)

    parsed = parse_report_attachment(path, company="Sample Co")

    assert parsed.input_format == "pdf"
    assert parsed.report.statements
    assert parsed.report.notes
    locations = [block.location for section in [*parsed.report.statements, *parsed.report.notes] for block in section.blocks]
    assert all(location.input_format == "pdf" for location in locations)
    assert all(location.page_number == 1 for location in locations)
    assert all(location.bbox is not None for location in locations if location.table_index is not None)


def test_image_only_pdf_requires_ocr(tmp_path):
    path = tmp_path / "scan.pdf"
    page = Canvas(str(path))
    scanned_page = Image.new("RGB", (600, 800), "white")
    page.drawImage(ImageReader(scanned_page), 0, 0, width=600, height=800)
    page.save()

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(path)

    assert exc.value.code == "PDF_OCR_REQUIRED"


def test_encrypted_pdf_is_rejected(tmp_path):
    plain = tmp_path / "plain.pdf"
    encrypted = tmp_path / "encrypted.pdf"
    _native_financial_pdf(plain)
    reader = PdfReader(plain)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt("secret")
    with encrypted.open("wb") as stream:
        writer.write(stream)

    with pytest.raises(AttachmentIngestionError) as exc:
        parse_report_attachment(encrypted)

    assert exc.value.code == "PDF_ENCRYPTED"
```

Keep `pypdf` in development dependencies only; it is used solely for the
deterministic encrypted-PDF fixture.

- [ ] **Step 3: Run RED PDF tests**

Run:

```text
uv run pytest -q tests/test_pdf_ingestion.py
```

Expected: missing `pdf_ingestion` module or PDF unsupported error.

- [ ] **Step 4: Implement page-ordered text and table extraction**

Create:

```python
@dataclass(frozen=True)
class PdfExtraction:
    markup: str
    diagnostics: tuple[AttachmentDiagnostic, ...] = ()
```

The extractor opens with `pdfplumber.open(source)`, maps password failures to
`PDF_ENCRYPTED`, and processes every page. Use `page.find_tables()` with line
strategy first; only when no table is found retry with:

```python
{
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
    "min_words_vertical": 2,
    "min_words_horizontal": 1,
    "intersection_tolerance": 4,
    "text_tolerance": 3,
}
```

For each page:

1. collect table `(bbox, rows)` values;
2. extract words and remove words whose center lies inside any table bbox;
3. group remaining words into lines when their `top` values differ by at most 3 points;
4. order line and table blocks by `(top, x0)`;
5. serialize lines as escaped `<p>` and tables as escaped `<table>`;
6. add `data-pdf-page` and comma-separated `data-pdf-bbox` to every block.

Reject `PDF_OCR_REQUIRED` when the document has pages but fewer than 20
non-whitespace extracted characters and at least one page image. Reject
`PDF_TABLES_NOT_FOUND` when no table was found. Return normalized markup only;
call `parse_full_report_text(..., input_format="pdf")` in the attachment facade.

- [ ] **Step 5: Run GREEN and structured-equivalence regression**

Run:

```text
uv run pytest -q tests/test_pdf_ingestion.py tests/test_attachment_ingestion.py tests/test_document.py
```

Expected: all tests pass; PDF locations carry page and bbox.

---

### Task 4: Route Workpaper CLI Commands Through the Common Loader

**Files:**
- Modify: `src/dart_footing_reconciler/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_cli_workpaper.py`

**Interfaces:**
- Consumes: `parse_report_attachment` from Task 2/3.
- Preserves: existing command names and positional argument order.
- Produces: nonzero CLI errors with no output artifact for attachment-domain failures.

- [ ] **Step 1: Write failing CLI tests**

Add:

```python
def test_workpaper_html_accepts_xml_attachment(tmp_path):
    source = tmp_path / "report.xml"
    source.write_text(MARKUP, encoding="utf-8")
    output = tmp_path / "report.html"

    result = CliRunner().invoke(app, ["workpaper-html", str(source), str(output)])

    assert result.exit_code == 0
    assert output.exists()
    assert "재무제표 본문" in output.read_text(encoding="utf-8")


def test_workpaper_html_rejects_image_pdf_without_writing_output(tmp_path):
    source = tmp_path / "scan.pdf"
    _image_only_pdf(source)
    output = tmp_path / "report.html"

    result = CliRunner().invoke(app, ["workpaper-html", str(source), str(output)])

    assert result.exit_code != 0
    assert "OCR 처리된 PDF" in result.output
    assert not output.exists()


def test_workpaper_html_accepts_mixed_current_pdf_and_prior_dsd(tmp_path):
    current = tmp_path / "current.pdf"
    prior = tmp_path / "prior.dsd"
    _native_financial_pdf(current)
    prior.write_text(MARKUP, encoding="utf-8")
    output = tmp_path / "report.html"

    result = CliRunner().invoke(
        app,
        ["workpaper-html", str(current), str(output), "--prior-html", str(prior)],
    )

    assert result.exit_code == 0
    assert output.exists()
```

- [ ] **Step 2: Run RED CLI tests**

Run:

```text
uv run pytest -q tests/test_cli.py tests/test_cli_workpaper.py -k "workpaper_html and (xml or image_pdf or mixed_current)"
```

Expected: PDF still writes an empty report or XML path does not use the common loader.

- [ ] **Step 3: Replace direct full-report parsing at workpaper boundaries**

Add a CLI helper:

```python
def _load_workpaper_attachment(source: Path, company: str | None) -> FullReport:
    try:
        return parse_report_attachment(source, company=company or source.stem).report
    except AttachmentIngestionError as exc:
        raise typer.BadParameter(str(exc)) from exc
```

Use it in `workpaper_html` and `workpaper_excel` for current and prior inputs.
Update help strings from “DART viewer HTML file” to “DART HTML, DSD, XML, or
native-text PDF file”. Preserve `--prior-html` as an alias so existing scripts do
not break; optionally add `--prior-source` as a second option name.

Route `foot` and `foot-excel` through the shared format/decode helpers but keep
their current footing-only result surface.

- [ ] **Step 4: Run GREEN CLI and workpaper tests**

Run:

```text
uv run pytest -q tests/test_cli.py tests/test_cli_workpaper.py
```

Expected: all tests pass and the PDF empty-report reproduction is closed.

---

### Task 5: PDF Page Provenance in the Audit Workbench

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Modify: `tests/test_report_html_new.py`

**Interfaces:**
- Consumes: optional `SourceLocation.page_number`, `.bbox`, `.input_format`.
- Produces: reviewer-facing `PDF N쪽` labels without exposing coordinates or parser terms.

- [ ] **Step 1: Write a failing renderer test**

Build a report containing a note table whose location is:

```python
SourceLocation(
    "note:15",
    0,
    12,
    page_number=37,
    bbox=(42.0, 110.0, 553.0, 420.0),
    input_format="pdf",
)
```

Export HTML and assert:

```python
assert "PDF 37쪽" in content
assert "42.0" not in content
assert "bbox" not in content
```

- [ ] **Step 2: Run RED renderer test**

Run:

```text
uv run pytest -q tests/test_report_html_new.py -k pdf_page_provenance
```

Expected: `PDF 37쪽` is absent.

- [ ] **Step 3: Add a single humanized source-location helper**

Add:

```python
def _source_page_label(location: SourceLocation | None) -> str:
    if location is None or location.input_format != "pdf" or location.page_number is None:
        return ""
    return f"PDF {location.page_number}쪽"
```

Use it in source-table captions, narrative cards, and drawer source labels.
Coordinates remain machine evidence only and are never rendered as user copy.

- [ ] **Step 4: Run GREEN renderer suite**

Run:

```text
uv run pytest -q tests/test_report_html_new.py tests/test_report_html_evidence.py
```

Expected: renderer tests pass without changing HTML-source labels.

---

### Task 6: Local Verification Upload API

**Files:**
- Create: `src/dart_footing_reconciler/verify_server.py`
- Modify: `src/dart_footing_reconciler/verify_app.py`
- Modify: `src/dart_footing_reconciler/cli.py`
- Create: `tests/test_verify_server.py`
- Modify: `tests/test_verify_app.py`
- Modify: `tests/test_build_verify_app.py`

**Interfaces:**
- Produces: `verify_attachment(source: str | Path, *, company: str = "", tolerance: int = 1) -> str`.
- Produces: `POST /api/verify` with one multipart `file` field inside a total
  encoded request no greater than 32 MiB.
- Produces: `200 text/html` or JSON `{error, message, next_action}`.

- [ ] **Step 1: Write failing byte/path and HTTP endpoint tests**

Add a package test:

```python
def test_verify_attachment_returns_audit_workbench_for_dsd(tmp_path):
    source = tmp_path / "company.dsd"
    source.write_text(MARKUP, encoding="utf-8")

    html = verify_attachment(source, company="회사")

    assert 'data-report-profile="audit-workbench"' in html
```

Add server tests that start `_build_verify_server(app_dir, 0)`, run
`serve_forever()` in a daemon thread, and POST a multipart DSD body with
`http.client.HTTPConnection`. Assert `200`, `text/html`, and audit-workbench
content. A second test posts an image-only PDF and asserts:

```python
assert response.status == 422
assert json.loads(body) == {
    "error": "PDF_OCR_REQUIRED",
    "message": "텍스트를 읽을 수 없는 PDF입니다. OCR 처리된 PDF가 필요합니다.",
    "next_action": "DART에서 텍스트 선택이 가능한 PDF 또는 DSD/XML/HTML 원문을 내려받아 다시 선택하세요.",
}
```

- [ ] **Step 2: Run RED API tests**

Run:

```text
uv run pytest -q tests/test_verify_server.py tests/test_verify_app.py tests/test_build_verify_app.py
```

Expected: missing server module and `verify_attachment` function.

- [ ] **Step 3: Implement path verification and a bounded multipart handler**

`verify_attachment` calls `parse_report_attachment`, assembles checks, and
returns `_build_html` exactly as the current `verify_html_report` path does.

Create a `SimpleHTTPRequestHandler` subclass factory. In `do_POST`:

1. require path `/api/verify`;
2. require numeric `Content-Length` for the total multipart request not
   exceeding `32 * 1024 * 1024`;
3. require `multipart/form-data` and extract exactly one `file` part with the
   standard-library `email` parser;
4. write bytes to a `TemporaryDirectory` using a basename-only filename;
5. call `verify_attachment`;
6. return HTML or mapped JSON without traceback text.

Map `AttachmentIngestionError.code` to deterministic `next_action` through one
dictionary in `verify_server.py`. Keep `_build_verify_server` in `cli.py` as a
compatibility import that delegates to the new server factory.

- [ ] **Step 4: Run GREEN API and server tests**

Run:

```text
uv run pytest -q tests/test_verify_server.py tests/test_verify_app.py tests/test_build_verify_app.py
```

Expected: all upload, error, localhost-binding, and legacy Pyodide tests pass.

---

### Task 7: Browser File Selection and Server/Pyodide Routing

**Files:**
- Modify: `static/dart-verify/index.html`
- Modify: `static/dart-verify/app.js`
- Modify: `tests/js/dart_verify_app.test.js`
- Modify: `tests/test_build_verify_app.py`

**Interfaces:**
- Consumes: `POST /api/verify` from Task 6.
- Preserves: Pyodide verification for HTML/HTM/DSD/XML when `/api/verify` is unavailable.
- Rejects: PDF when the verification service is unavailable, with a user action rather than a runtime error.

- [ ] **Step 1: Write failing DOM and JavaScript tests**

Update shell assertions:

```python
assert 'accept=".html,.htm,.dsd,.xml,.pdf,text/html,application/xml,application/pdf"' in html
assert "HTML/DSD/XML/PDF 파일 선택" in html
```

Add Vitest cases with injected `fetchFn`:

```javascript
test("uploads PDF to the verification service and renders returned workbench", async () => {
  const fetchFn = vi.fn(async () => ({
    ok: true,
    headers: new Headers({ "content-type": "text/html; charset=utf-8" }),
    text: async () => '<div data-report-profile="audit-workbench">PDF OK</div>',
  }));
  const controller = initDartVerifyApp({ autoBoot: false, fetchFn });

  await controller.verifyFile(new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], "report.pdf"));

  expect(fetchFn).toHaveBeenCalledWith("/api/verify", expect.objectContaining({ method: "POST" }));
  expect(document.getElementById("result").innerHTML).toContain("PDF OK");
});


test("shows OCR action returned by the verification service", async () => {
  const fetchFn = vi.fn(async () => ({
    ok: false,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => ({
      error: "PDF_OCR_REQUIRED",
      message: "텍스트를 읽을 수 없는 PDF입니다.",
      next_action: "OCR 처리된 PDF를 다시 선택하세요.",
    }),
  }));
  const controller = initDartVerifyApp({ autoBoot: false, fetchFn });

  await expect(controller.verifyFile(new File(["%PDF"], "scan.pdf"))).rejects.toThrow();

  expect(document.getElementById("status").textContent).toBe("텍스트를 읽을 수 없는 PDF입니다.");
  expect(document.getElementById("details").textContent).toBe("OCR 처리된 PDF를 다시 선택하세요.");
});
```

- [ ] **Step 2: Run RED browser-shell tests**

Run:

```text
npx vitest run tests/js/dart_verify_app.test.js
uv run pytest -q tests/test_build_verify_app.py
```

Expected: PDF is rejected before fetch and XML/PDF accept text is absent.

- [ ] **Step 3: Implement server-first routing with structured fallback**

Add `fetchFn = globalThis.fetch?.bind(globalThis)` injection. `verifyFile` first
builds a `FormData` and calls `/api/verify`. On a network/404/405 failure:

- HTML/HTM/DSD/XML call the existing Pyodide path;
- PDF raises `PDF 검증 서비스를 사용할 수 없습니다.` with the action
  `검증 앱을 로컬 서버로 다시 실행하거나 관리자에게 PDF 검증 서비스 상태를 확인하세요.`

For JSON errors, preserve server `message` and `next_action` as explicit error
properties so `showError` displays them. Remove the unconditional PDF rejection
from `isPdfFile`; keep signature detection only for choosing whether fallback is
allowed.

Update picker copy and `accept` exactly as asserted in Step 1.

- [ ] **Step 4: Run GREEN browser-shell tests**

Run:

```text
npx vitest run tests/js/dart_verify_app.test.js
uv run pytest -q tests/test_build_verify_app.py tests/test_verify_app.py
```

Expected: JavaScript and Python browser-shell tests pass.

---

### Task 8: End-to-End Attachment QA and Regression Verification

**Files:**
- Modify only if QA exposes a defect: files owned by Tasks 1-7.
- Generated QA artifacts: `output/pdf/attachment-ingestion/`

**Interfaces:**
- Verifies: browser file upload to the same audit workbench used by CLI.
- Verifies: native PDF page provenance and fail-closed scanned-PDF behavior.

- [ ] **Step 1: Run the focused attachment and parser suite**

Run:

```text
uv run pytest -q tests/test_attachment_ingestion.py tests/test_pdf_ingestion.py tests/test_document.py tests/test_cli.py tests/test_cli_workpaper.py tests/test_verify_server.py tests/test_verify_app.py tests/test_build_verify_app.py
```

Expected: zero failures.

- [ ] **Step 2: Run frontend unit tests**

Run:

```text
npx vitest run tests/js/dart_verify_app.test.js
```

Expected: zero failures.

- [ ] **Step 3: Generate a Korean native-text PDF QA sample**

Create `output/pdf/attachment-ingestion/sk_eternix_native_text.pdf` from the
existing SK이터닉스 HTML using Chromium print-to-PDF. Render it to PNG with:

```text
mkdir -p tmp/pdfs/attachment-ingestion
pdftoppm -png output/pdf/attachment-ingestion/sk_eternix_native_text.pdf tmp/pdfs/attachment-ingestion/sk_eternix
```

Inspect representative statement, note, merged-header, subtotal, and narrative
pages. Confirm Korean glyphs, table lines, and page breaks are readable before
using it as an extraction QA input.

- [ ] **Step 4: Run CLI PDF workpaper QA**

Run:

```text
uv run dart-footing workpaper-html output/pdf/attachment-ingestion/sk_eternix_native_text.pdf output/pdf/attachment-ingestion/sk_eternix_pdf_workbench.html --company SK이터닉스 --tolerance 1
```

Assert statically that the output contains:

- `data-report-profile="audit-workbench"`;
- both statement and note navigation;
- `PDF ` page labels;
- no runtime/library terms;
- at least one footing result and one reconciliation result.

- [ ] **Step 5: Run browser upload QA with Playwright**

Build and serve the app, upload DSD, XML, and PDF one at a time, and verify:

- all supported native formats render the workbench;
- connection/separate switching remains functional;
- a PDF source button shows a page label;
- an image-only PDF shows only reason and next action;
- no empty workbench is shown after an error;
- browser console has no functional errors.

- [ ] **Step 6: Run lint and complete test suite**

Run:

```text
uv run ruff check src tests
uv run pytest -q
```

Expected: lint passes. Record exact pytest totals. If the known external CJ대한통운,
더존비즈온, or INVENI corpus paths are absent, report those `FileNotFoundError`
failures separately and confirm all new attachment tests pass.

- [ ] **Step 7: Remove temporary PDF render artifacts**

Delete `tmp/pdfs/attachment-ingestion/` after visual inspection. Keep only the
stable QA PDF and generated workbench under `output/pdf/attachment-ingestion/`.

---

## Plan Self-Review

- Every design acceptance criterion maps to Tasks 1-8.
- PDF extraction is isolated from validation and does not introduce company routing.
- OCR, encrypted-PDF password entry, and cross-page table merging remain out of scope.
- Browser fallback behavior is explicit and cannot silently accept PDF without a server.
- Existing CLI positional arguments and `--prior-html` automation remain compatible.
- Every production behavior begins with a named failing test and an exact RED command.
- No git command is included because the project instruction forbids git operations.
