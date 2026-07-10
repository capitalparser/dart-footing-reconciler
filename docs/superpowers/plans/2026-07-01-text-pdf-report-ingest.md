# Text PDF Report Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified attachment ingest path so DSD/HTML keeps current behavior and text-layer PDFs can produce `FullReport` objects for the existing validation engine.

**Architecture:** Add a deterministic ingest layer in front of the current parser. `report_ingest.py` owns format detection and `ParsedAttachment`; HTML/DSD delegates to `parse_full_report`; PDF delegates to `pdf_report.py`; CLI and verify-app entrypoints stop calling `parse_full_report` directly. The verification engine continues to consume `FullReport`, and PDF uncertainty is represented as extraction diagnostics or controlled `parse_uncertain` gates rather than probabilistic matches.

**Tech Stack:** Python 3.11+, Typer CLI, BeautifulSoup/lxml for existing DART HTML parsing, optional `pdfplumber>=0.11` and `pypdf>=5` for text PDF extraction, Vitest for browser shell tests, Playwright for rendered smoke checks.

## Global Constraints

- Validation basis is limited to the provided disclosure document; no ERP, GL, TB, journal, or company-source linkage.
- First slice supports text-layer PDF in the Python CLI/server runtime.
- Scanned PDF OCR is out of scope and must fail clearly.
- PDF extraction must never create a `matched` result from weak extraction.
- Existing DSD/HTML status histograms must remain unchanged.
- `SourceLocation` remains unchanged; PDF page coordinates stay in an ingest diagnostic sidecar.
- Browser app must not reject `.pdf` before engine execution; if Pyodide lacks PDF dependencies, show an explicit unsupported-runtime message.
- Every amount used by a check still needs a source reference.
- Final verification includes `uv run pytest`; PDF-specific tests that need optional dependencies run with `uv run --extra pdf --with reportlab pytest ...`.

---

## File Structure

- Create `src/dart_footing_reconciler/report_ingest.py`
  - Owns attachment format detection, decoded text adapters, `DecodedAttachment`, `ParsedAttachment`, `AttachmentDiagnostics`, and public `decode_attached_report_text` / `parse_attached_report` / `parse_attached_report_bytes`.
- Create `src/dart_footing_reconciler/pdf_report.py`
  - Owns optional text-PDF extraction and returns `ParsedAttachment` with a normal `FullReport`.
- Modify `src/dart_footing_reconciler/local_report.py`
  - Delegates detection and decoding to `report_ingest.py`; keeps existing `LocalReportError` import compatibility.
- Modify `src/dart_footing_reconciler/verify_app.py`
  - Adds byte-oriented `verify_attached_report`; keeps `verify_html_report` as a compatibility wrapper.
- Modify `src/dart_footing_reconciler/cli.py`
  - Routes report-taking commands through `parse_attached_report`.
- Modify `src/dart_footing_reconciler/report_html.py`
  - Adds optional input-format and extraction-diagnostic metadata in masthead/diagnostics panels.
- Modify `src/dart_footing_reconciler/__init__.py`
  - Exposes ingest entrypoints.
- Modify `static/dart-verify/app.js`
  - Passes filename and bytes to `verify_attached_report`; removes JS pre-rejection of PDFs.
- Modify `pyproject.toml`
  - Adds optional `pdf` dependency group.
- Create `tests/test_report_ingest.py`
  - Covers format detection, DSD-with-table classification, original source preservation, HTML/DSD parity, text-only decode, and scanned-PDF rejection.
- Create `tests/test_pdf_report.py`
  - Covers text-PDF extraction, weak-table rejection/diagnostics, and scanned-PDF rejection under optional dependencies.
- Modify `tests/test_cli.py`, `tests/test_cli_workpaper.py`, `tests/test_verify_app.py`, `tests/js/dart_verify_app.test.js`, and `tests/test_package.py`.

---

### Task 1: Unified Ingest Models and Format Detection

**Files:**
- Create: `src/dart_footing_reconciler/report_ingest.py`
- Test: `tests/test_report_ingest.py`

**Interfaces:**
- Produces: `ReportIngestError`, `UnsupportedReportFormatError`, `AttachmentDiagnostics`, `DecodedAttachment`, `ParsedAttachment`, `detect_report_format(source, filename="")`, `decode_attached_report_text(source)`, `parse_attached_report(source, company="")`, `parse_attached_report_bytes(data, filename, company="")`
- Consumes: `dart_footing_reconciler.document.parse_full_report`

- [ ] **Step 1: Write failing format detection tests**

Add `tests/test_report_ingest.py`:

```python
from __future__ import annotations

import pytest

from dart_footing_reconciler.report_ingest import (
    UnsupportedReportFormatError,
    decode_attached_report_text,
    detect_report_format,
    parse_attached_report,
    parse_attached_report_bytes,
)


def test_detect_report_format_uses_extension_and_magic_bytes(tmp_path) -> None:
    html = tmp_path / "report.html"
    html.write_text("<html><body>DART</body></html>", encoding="utf-8")
    dsd = tmp_path / "report.dsd"
    dsd.write_bytes("<DOCUMENT></DOCUMENT>".encode("cp949"))
    xml = tmp_path / "report.xml"
    xml.write_text("<dart></dart>", encoding="utf-8")
    pdf = tmp_path / "report.bin"
    pdf.write_bytes(b"%PDF-1.7\n")

    assert detect_report_format(html) == "html"
    assert detect_report_format(dsd) == "dsd"
    assert detect_report_format(xml) == "xml"
    assert detect_report_format(pdf, filename="report.pdf") == "pdf"
    assert detect_report_format(b"%PDF-1.7\n", filename="upload.dat") == "pdf"
    assert detect_report_format(b"<DOCUMENT></DOCUMENT>", filename="upload.txt") == "dsd"


def test_detect_dsd_with_table_does_not_become_html(tmp_path) -> None:
    source = tmp_path / "report.dsd"
    source.write_bytes(
        "<DOCUMENT><table><tr><td>1</td></tr></table></DOCUMENT>".encode("cp949")
    )

    assert detect_report_format(source) == "dsd"


def test_parse_attached_report_preserves_html_parser_behavior(tmp_path) -> None:
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>재무상태표</p>
          <table><tr><th>구분</th><th>당기</th></tr><tr><td>자산총계</td><td>1,000</td></tr></table>
          <p>1. 일반사항</p>
          <table><tr><th>구분</th><th>내용</th></tr><tr><td>회사</td><td>샘플</td></tr></table>
        </body></html>
        """,
        encoding="utf-8",
    )

    parsed = parse_attached_report(source, company="Sample Co")

    assert parsed.input_format == "html"
    assert parsed.report.source == str(source)
    assert parsed.report.company == "Sample Co"
    assert len(parsed.report.statements) == 1
    assert len(parsed.report.notes) == 1
    assert parsed.text is not None
    assert parsed.diagnostics.input_format == "html"
    assert parsed.diagnostics.warnings == ()


def test_parse_attached_report_bytes_decodes_cp949_dsd() -> None:
    data = """
    <DOCUMENT>
    <p>1. 일반사항</p>
    <table><tr><th>구분</th><th>내용</th></tr><tr><td>회사</td><td>샘플</td></tr></table>
    </DOCUMENT>
    """.encode("cp949")

    parsed = parse_attached_report_bytes(data, filename="report.dsd", company="Sample Co")

    assert parsed.input_format == "dsd"
    assert parsed.report.company == "Sample Co"
    assert len(parsed.report.notes) == 1
    assert parsed.text is not None


def test_decode_attached_report_text_does_not_parse_full_report(monkeypatch, tmp_path) -> None:
    import dart_footing_reconciler.report_ingest as ingest

    source = tmp_path / "scan-only.html"
    source.write_text("<table><tr><td>1</td></tr></table>", encoding="utf-8")

    def fail_parse(*args, **kwargs):
        raise AssertionError("decode path must not parse FullReport")

    monkeypatch.setattr(ingest, "parse_full_report", fail_parse)

    decoded = decode_attached_report_text(source)

    assert decoded.input_format == "html"
    assert decoded.source == source
    assert "<table>" in decoded.text


def test_parse_attached_report_rejects_network_source() -> None:
    with pytest.raises(UnsupportedReportFormatError, match="local file path"):
        parse_attached_report("https://dart.fss.or.kr/report.html")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_report_ingest.py -v
```

Expected: FAIL during import because `dart_footing_reconciler.report_ingest` does not exist.

- [ ] **Step 3: Implement ingest models and HTML/DSD adapters**

Create `src/dart_footing_reconciler/report_ingest.py`:

```python
"""Local attachment ingest for DSD, HTML, XML, and text-layer PDF reports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal
from urllib.parse import urlparse

from dart_footing_reconciler.document import FullReport, parse_full_report

ReportFormat = Literal["html", "dsd", "xml", "pdf", "unknown"]

SCANNED_PDF_MESSAGE = (
    "텍스트 레이어가 없는 PDF입니다. OCR PDF는 아직 지원하지 않습니다. "
    "DSD/HTML 또는 텍스트 PDF를 첨부하세요."
)


class ReportIngestError(ValueError):
    """Base error for local report ingest problems."""


class UnsupportedReportFormatError(ReportIngestError):
    """Raised when a report format cannot be parsed safely."""


@dataclass(frozen=True)
class PdfSourceCoordinate:
    source: str
    page: int
    table_index: int | None = None
    row_index: int | None = None
    column_index: int | None = None
    bbox: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class AttachmentDiagnostics:
    input_format: str
    warnings: tuple[str, ...] = ()
    parse_uncertain_reasons: tuple[str, ...] = ()
    page_count: int = 0
    table_count: int = 0
    skipped_table_count: int = 0
    source_coordinates: tuple[PdfSourceCoordinate, ...] = ()


@dataclass(frozen=True)
class DecodedAttachment:
    source: Path | None
    filename: str
    input_format: str
    text: str
    diagnostics: AttachmentDiagnostics


@dataclass(frozen=True)
class ParsedAttachment:
    source: Path | None
    filename: str
    input_format: str
    report: FullReport
    diagnostics: AttachmentDiagnostics
    text: str | None = None


def detect_report_format(source: str | Path | bytes, filename: str = "") -> ReportFormat:
    name = filename or (Path(source).name if not isinstance(source, bytes) else "")
    suffix = Path(name).suffix.lower()
    data = _read_prefix(source)
    stripped = data.lstrip()
    decoded = _decode_text(data).lower()
    if stripped.startswith(b"%PDF") or suffix == ".pdf":
        return "pdf"
    if suffix == ".dsd":
        return "dsd"
    if suffix in {".html", ".htm"}:
        return "html"
    if suffix == ".xml":
        return "xml"
    if re.search(r"<\s*document\b", decoded):
        return "dsd"
    if re.search(r"<\s*dart\b", decoded):
        return "xml"
    if re.search(r"<\s*html\b", decoded) or re.search(r"<\s*body\b", decoded):
        return "html"
    if "<table" in decoded:
        return "html"
    return "unknown"


def parse_attached_report(source: str | Path, *, company: str = "") -> ParsedAttachment:
    path = Path(source)
    _reject_network_source(path)
    if not path.exists():
        raise ReportIngestError("source must be a local file path that exists")
    if not path.is_file():
        raise ReportIngestError("source must be a local file path, not a directory")
    data = path.read_bytes()
    return _parse_attachment_bytes(data, filename=path.name, source=path, company=company)


def decode_attached_report_text(source: str | Path) -> DecodedAttachment:
    path = Path(source)
    _reject_network_source(path)
    if not path.exists():
        raise ReportIngestError("source must be a local file path that exists")
    if not path.is_file():
        raise ReportIngestError("source must be a local file path, not a directory")
    data = path.read_bytes()
    input_format = detect_report_format(data, filename=path.name)
    if input_format == "pdf":
        raise UnsupportedReportFormatError(
            "이 명령은 표 단위 footing용 HTML/DSD 텍스트 입력만 지원합니다. "
            "텍스트 PDF는 workpaper-html 또는 workpaper-excel에서 검증하세요."
        )
    if input_format not in {"html", "dsd", "xml"}:
        raise UnsupportedReportFormatError("지원하지 않는 파일 형식입니다. DSD/HTML 또는 텍스트 PDF를 첨부하세요.")
    return DecodedAttachment(
        source=path,
        filename=path.name,
        input_format=input_format,
        text=_decode_text(data),
        diagnostics=AttachmentDiagnostics(input_format=input_format),
    )


def parse_attached_report_bytes(
    data: bytes,
    *,
    filename: str,
    company: str = "",
) -> ParsedAttachment:
    return _parse_attachment_bytes(data, filename=filename, source=None, company=company)


def _parse_attachment_bytes(
    data: bytes,
    *,
    filename: str,
    source: Path | None,
    company: str,
) -> ParsedAttachment:
    input_format = detect_report_format(data, filename=filename)
    if input_format == "pdf":
        from dart_footing_reconciler.pdf_report import parse_text_pdf_report

        return parse_text_pdf_report(data, filename=filename, source=source, company=company)
    if input_format in {"html", "dsd", "xml"}:
        text = _decode_text(data)
        report = _parse_text_report(text, filename=filename, source=source, company=company)
        diagnostics = AttachmentDiagnostics(input_format=input_format)
        return ParsedAttachment(
            source=source,
            filename=filename,
            input_format=input_format,
            report=report,
            diagnostics=diagnostics,
            text=text,
        )
    raise UnsupportedReportFormatError("지원하지 않는 파일 형식입니다. DSD/HTML 또는 텍스트 PDF를 첨부하세요.")


def _parse_text_report(
    text: str,
    *,
    filename: str,
    source: Path | None,
    company: str,
) -> FullReport:
    with TemporaryDirectory(prefix="dart-ingest-") as tmpdir:
        path = Path(tmpdir) / _safe_filename(filename)
        path.write_text(text, encoding="utf-8")
        parsed = parse_full_report(path, company=company)
    return FullReport(
        str(source or filename),
        parsed.company,
        parsed.statements,
        parsed.notes,
    )


def _read_prefix(source: str | Path | bytes, size: int = 4096) -> bytes:
    if isinstance(source, bytes):
        return source[:size]
    path = Path(source)
    if path.exists() and path.is_file():
        return path.read_bytes()[:size]
    return str(source).encode("utf-8", errors="ignore")[:size]


def _reject_network_source(path: Path) -> None:
    parsed = urlparse(str(path))
    if parsed.scheme in {"http", "https"}:
        raise UnsupportedReportFormatError("source must be a local file path, not a network URL")


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _safe_filename(filename: str) -> str:
    name = Path(filename or "report.html").name
    if not re.search(r"\.(html|htm|dsd|xml)$", name, flags=re.IGNORECASE):
        return "report.html"
    return name
```

- [ ] **Step 4: Add temporary PDF module stub for import stability**

Create `src/dart_footing_reconciler/pdf_report.py`:

```python
"""Text-layer PDF extraction for DART reports."""

from __future__ import annotations

from pathlib import Path

from dart_footing_reconciler.report_ingest import ParsedAttachment, UnsupportedReportFormatError


def parse_text_pdf_report(
    data: bytes,
    *,
    filename: str,
    source: Path | None = None,
    company: str = "",
) -> ParsedAttachment:
    raise UnsupportedReportFormatError(
        "텍스트 PDF 추출기가 아직 연결되지 않았습니다. DSD/HTML 또는 텍스트 PDF 지원 런타임을 사용하세요."
    )
```

- [ ] **Step 5: Run tests to verify Task 1 passes**

Run:

```bash
uv run pytest tests/test_report_ingest.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dart_footing_reconciler/report_ingest.py src/dart_footing_reconciler/pdf_report.py tests/test_report_ingest.py
git commit -m "Add unified report ingest detector"
```

---

### Task 2: Preserve Existing Local Attachment and Public Package Behavior

**Files:**
- Modify: `src/dart_footing_reconciler/local_report.py`
- Modify: `src/dart_footing_reconciler/__init__.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_package.py`
- Test: `tests/test_cli.py`, `tests/test_package.py`, `tests/test_report_ingest.py`

**Interfaces:**
- Consumes: `decode_attached_report_text()`, `detect_report_format()`
- Produces: existing `load_local_report()` and `foot_local_report()` compatibility plus exported `parse_attached_report`

- [ ] **Step 1: Write failing compatibility tests**

Modify `tests/test_cli.py` by replacing `test_cli_foot_rejects_pdf_until_pdf_table_extraction_is_supported` with:

```python
def test_cli_foot_rejects_scanned_pdf_with_text_layer_message(tmp_path) -> None:
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")

    result = CliRunner().invoke(app, ["foot", str(source), "--format", "json"])

    assert result.exit_code != 0
    assert "표 단위 footing용 HTML/DSD" in result.output
    assert "workpaper-html" in result.output
```

Add this test to `tests/test_cli.py`:

```python
def test_cli_foot_does_not_require_full_report_parse(monkeypatch, tmp_path) -> None:
    import dart_footing_reconciler.report_ingest as ingest

    source = tmp_path / "report.html"
    source.write_text(
        """
        <p>15. 무형자산</p>
        <table>
          <tr><th>구분</th><th>합계</th></tr>
          <tr><td>기초</td><td>1,000</td></tr>
          <tr><td>취득</td><td>250</td></tr>
          <tr><td>상각비</td><td>100</td></tr>
          <tr><td>기말</td><td>1,150</td></tr>
        </table>
        """,
        encoding="utf-8",
    )

    def fail_parse(*args, **kwargs):
        raise AssertionError("foot must use text decode, not FullReport parse")

    monkeypatch.setattr(ingest, "parse_full_report", fail_parse)

    result = CliRunner().invoke(app, ["foot", str(source), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["matched"] == 1
```

Modify `tests/test_package.py` import list:

```python
from dart_footing_reconciler import (
    __version__,
    build_coverage_report,
    build_note_inventory,
    build_note_semantic_extraction,
    build_review_backlog,
    classify_layout,
    classify_validation_relevance,
    detect_orientation,
    detect_report_format,
    discover_component_net_formula,
    discover_credit_risk_exposure_formula,
    discover_credit_risk_exposure_formulas,
    discover_debt_split_formula,
    discover_defined_benefit_rollforward_formulas,
    discover_discontinued_operation_cashflow_formula,
    discover_discontinued_operation_income_formulas,
    discover_employee_benefit_expense_formulas,
    discover_expense_summary_formula,
    discover_financial_category_column_formulas,
    discover_financial_category_formulas,
    discover_financial_fair_value_level_formulas,
    discover_inventory_carrying_formulas,
    discover_lease_expense_formulas,
    discover_lease_liability_split_formula,
    discover_liquidity_maturity_formulas,
    discover_net_debt_bridge_formulas,
    discover_provision_column_total_formulas,
    discover_receivable_aging_bucket_formulas,
    discover_receivable_carrying_formulas,
    discover_rollforward_formula,
    discover_tax_expense_composition_formulas,
    extract_verification_candidates,
    foot_local_report,
    parse_attached_report,
    review_disclosure_completeness,
)
```

Add this test to `tests/test_package.py`:

```python
def test_package_exposes_attachment_ingest_helpers(tmp_path) -> None:
    source = tmp_path / "report.html"
    source.write_text("<p>1. 일반사항</p>", encoding="utf-8")

    parsed = parse_attached_report(source, company="Sample Co")

    assert detect_report_format(source) == "html"
    assert parsed.input_format == "html"
    assert parsed.report.company == "Sample Co"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_cli.py::test_cli_foot_rejects_scanned_pdf_with_text_layer_message tests/test_cli.py::test_cli_foot_does_not_require_full_report_parse tests/test_package.py::test_package_exposes_attachment_ingest_helpers -v
```

Expected: FAIL because package exports are missing and `local_report.py` still owns old PDF rejection / parser coupling.

- [ ] **Step 3: Modify local_report to delegate to report_ingest**

Replace `src/dart_footing_reconciler/local_report.py` with:

```python
"""Local attachment report loading and footing workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dart_footing_reconciler.checks import SCHEMA_VERSION, status_summary
from dart_footing_reconciler.report_ingest import (
    ReportIngestError as LocalReportError,
    UnsupportedReportFormatError,
    decode_attached_report_text,
    detect_report_format,
)
from dart_footing_reconciler.scan import scan_html


@dataclass(frozen=True)
class LocalReport:
    """Decoded local report content ready for parser entrypoints."""

    source: Path
    input_format: str
    text: str


def load_local_report(source: str | Path) -> LocalReport:
    """Load a local DART report attachment without network access."""
    decoded = decode_attached_report_text(source)
    return LocalReport(
        source=Path(source),
        input_format=decoded.input_format,
        text=decoded.text,
    )


def foot_local_report(
    source: str | Path,
    *,
    tolerance: int = 1,
    include_all: bool = False,
) -> dict[str, Any]:
    """Run footing checks for a supported local DART report attachment."""
    report = load_local_report(source)
    results = scan_html(report.text, tolerance=tolerance, include_all=include_all)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": str(report.source),
        "input_format": report.input_format,
        "summary": _summary(results),
        "results": [asdict(result) for result in results],
    }


def _is_pdf(path: Path, data: bytes) -> bool:
    """Compatibility helper for old tests and callers."""
    return detect_report_format(data, filename=path.name) == "pdf"


def _input_format(path: Path, data: bytes) -> str:
    """Compatibility helper for old tests and callers."""
    return detect_report_format(data, filename=path.name)


def _summary(results: list[Any]) -> dict[str, int]:
    """Summarize footing statuses for CLI and package consumers."""
    return status_summary(results)
```

- [ ] **Step 4: Export ingest helpers from package**

Modify `src/dart_footing_reconciler/__init__.py` by adding these imports:

```python
from dart_footing_reconciler.report_ingest import (
    AttachmentDiagnostics,
    ParsedAttachment,
    detect_report_format,
    parse_attached_report,
    parse_attached_report_bytes,
)
```

Add names to `__all__` if the file already maintains an explicit `__all__`:

```python
    "AttachmentDiagnostics",
    "ParsedAttachment",
    "detect_report_format",
    "parse_attached_report",
    "parse_attached_report_bytes",
```

- [ ] **Step 5: Run compatibility tests**

Run:

```bash
uv run pytest tests/test_report_ingest.py tests/test_cli.py::test_cli_foot_outputs_json tests/test_cli.py::test_cli_foot_accepts_local_dsd_with_korean_encoding tests/test_cli.py::test_cli_foot_rejects_scanned_pdf_with_text_layer_message tests/test_cli.py::test_cli_foot_does_not_require_full_report_parse tests/test_package.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dart_footing_reconciler/local_report.py src/dart_footing_reconciler/__init__.py tests/test_cli.py tests/test_package.py
git commit -m "Route local attachments through ingest API"
```

---

### Task 3: Text PDF Extraction Adapter and Optional Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/dart_footing_reconciler/pdf_report.py`
- Test: `tests/test_pdf_report.py`

**Interfaces:**
- Consumes: `AttachmentDiagnostics`, `ParsedAttachment`, `PdfSourceCoordinate`, `SCANNED_PDF_MESSAGE`
- Produces: `parse_text_pdf_report(data, filename, source=None, company="") -> ParsedAttachment`

`AttachmentDiagnostics.table_count` means raw PDF table candidates found by the extractor. `skipped_table_count` counts candidates rejected by reliability gates. Accepted/promoted table count is derived from the resulting `FullReport` tables or `source_coordinates`.

- [ ] **Step 1: Add failing PDF extraction tests**

Create `tests/test_pdf_report.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from dart_footing_reconciler.report_ingest import (
    UnsupportedReportFormatError,
    parse_attached_report,
)


pytest.importorskip("pdfplumber")
pytest.importorskip("pypdf")
reportlab = pytest.importorskip("reportlab")


def _write_table_pdf(path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle

    def grid_table(rows):
        table = Table(rows)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        return table

    doc = SimpleDocTemplate(str(path), pagesize=A4)
    story = [
        grid_table([["재무상태표"]]),
        Spacer(1, 12),
        grid_table([["구분", "당기"], ["자산총계", "1,000"]]),
        Spacer(1, 20),
        grid_table([["24. 법인세비용"]]),
        Spacer(1, 12),
        grid_table([["구분", "금액"], ["법인세비용차감전순이익", "1,000"], ["합계", "200"]]),
    ]
    doc.build(story)


def test_parse_text_pdf_report_extracts_statement_and_note_tables(tmp_path) -> None:
    source = tmp_path / "sample.pdf"
    _write_table_pdf(source)

    parsed = parse_attached_report(source, company="PDF Co")

    assert parsed.input_format == "pdf"
    assert parsed.text is None
    assert parsed.report.company == "PDF Co"
    assert parsed.report.source == str(source)
    assert len(parsed.report.statements) >= 1
    assert len(parsed.report.notes) >= 1
    assert parsed.diagnostics.input_format == "pdf"
    assert parsed.diagnostics.page_count >= 1
    assert parsed.diagnostics.table_count >= 2
    assert parsed.diagnostics.source_coordinates


def test_parse_text_pdf_report_rejects_pdf_without_text_layer(tmp_path) -> None:
    source = tmp_path / "scanned.pdf"
    source.write_bytes(b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n")

    with pytest.raises(UnsupportedReportFormatError, match="텍스트 레이어가 없는 PDF"):
        parse_attached_report(source, company="PDF Co")


def test_pdf_unreliable_table_is_not_promoted_to_full_report() -> None:
    from dart_footing_reconciler.pdf_report import _build_report_from_extracted

    extracted = [
        {
            "page": 1,
            "text": "재무상태표\n구분만 있고 금액 열이 없음",
            "headings": ["재무상태표"],
            "tables": [([["구분"], ["자산총계"]], None)],
        }
    ]

    with pytest.raises(UnsupportedReportFormatError, match="PDF 표 구조"):
        _build_report_from_extracted(
            extracted,
            filename="weak.pdf",
            source=None,
            company="PDF Co",
        )


def test_pdf_diagnostics_records_skipped_tables() -> None:
    from dart_footing_reconciler.pdf_report import _build_report_from_extracted

    extracted = [
        {
            "page": 1,
            "text": "재무상태표",
            "headings": ["재무상태표"],
            "tables": [
                ([["구분"], ["자산총계"]], None),
                ([["구분", "당기"], ["자산총계", "1,000"]], (10.0, 10.0, 200.0, 80.0)),
            ],
        }
    ]

    parsed = _build_report_from_extracted(
        extracted,
        filename="mixed.pdf",
        source=None,
        company="PDF Co",
    )

    assert parsed.diagnostics.table_count == 2
    assert parsed.diagnostics.skipped_table_count == 1
    assert any("PDF_TABLE_GRID_UNCERTAIN" in reason for reason in parsed.diagnostics.parse_uncertain_reasons)
```

- [ ] **Step 2: Run optional PDF tests to verify they fail**

Run:

```bash
uv run --extra pdf --with reportlab pytest tests/test_pdf_report.py -v
```

Expected: FAIL because `pyproject.toml` has no `pdf` extra and `pdf_report.py` still raises the temporary unsupported message.

- [ ] **Step 3: Add optional PDF dependencies**

Modify `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
]
mcp = [
    "mcp>=1.0",
]
pdf = [
    "pdfplumber>=0.11",
    "pypdf>=5",
]
reports = [
    "pandas>=2.0",
]
```

- [ ] **Step 4: Implement deterministic text-PDF extraction**

Replace `src/dart_footing_reconciler/pdf_report.py` with:

```python
"""Text-layer PDF extraction for DART reports."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.report_ingest import (
    AttachmentDiagnostics,
    ParsedAttachment,
    PdfSourceCoordinate,
    SCANNED_PDF_MESSAGE,
    UnsupportedReportFormatError,
)


def parse_text_pdf_report(
    data: bytes,
    *,
    filename: str,
    source: Path | None = None,
    company: str = "",
) -> ParsedAttachment:
    try:
        import pdfplumber
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise UnsupportedReportFormatError(
            "텍스트 PDF 추출 런타임이 설치되어 있지 않습니다. "
            "`uv run --extra pdf`로 실행하거나 DSD/HTML 파일을 첨부하세요."
        ) from exc

    _quick_pdf_sanity(data, PdfReader)
    with NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(data)
        tmp.flush()
        with pdfplumber.open(tmp.name) as pdf:
            extracted = [_extract_page(page, page_index) for page_index, page in enumerate(pdf.pages, start=1)]

    if not any(item["text"].strip() for item in extracted):
        raise UnsupportedReportFormatError(SCANNED_PDF_MESSAGE)
    return _build_report_from_extracted(
        extracted,
        filename=filename,
        source=source,
        company=company,
    )


def _quick_pdf_sanity(data: bytes, PdfReader) -> None:
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise UnsupportedReportFormatError("암호화된 PDF는 지원하지 않습니다. DSD/HTML 또는 암호 해제된 텍스트 PDF를 첨부하세요.")
        if len(reader.pages) == 0:
            raise UnsupportedReportFormatError(SCANNED_PDF_MESSAGE)
        sample_text = "\n".join((page.extract_text() or "") for page in list(reader.pages)[:3])
    except UnsupportedReportFormatError:
        raise
    except Exception as exc:
        raise UnsupportedReportFormatError(SCANNED_PDF_MESSAGE) from exc
    if not sample_text.strip():
        raise UnsupportedReportFormatError(SCANNED_PDF_MESSAGE)


def _build_report_from_extracted(
    extracted: list[dict],
    *,
    filename: str,
    source: Path | None,
    company: str,
) -> ParsedAttachment:
    sections: list[ReportSection] = []
    coordinates: list[PdfSourceCoordinate] = []
    warnings: list[str] = []
    uncertain_reasons: list[str] = []
    table_index = 0
    skipped_table_count = 0
    raw_table_count = 0
    current: ReportSection | None = None
    for item in extracted:
        for heading in item["headings"]:
            section = _section_from_heading(heading)
            if section is not None:
                current = section
                sections.append(current)
        for source_table_index, (rows, bbox) in enumerate(item["tables"]):
            raw_table_count += 1
            clean_rows = _clean_table(rows)
            if not _is_reliable_table(clean_rows):
                skipped_table_count += 1
                uncertain_reasons.append(
                    f"PDF_TABLE_GRID_UNCERTAIN page {item['page']} table {source_table_index}: unreliable table structure"
                )
                continue
            inferred = _infer_section_from_rows(clean_rows)
            if inferred is not None:
                current = inferred
                sections.append(current)
            if current is None:
                uncertain_reasons.append(
                    f"PDF_SECTION_UNCERTAIN page {item['page']} table {source_table_index}: heading missing"
                )
                current = ReportSection(
                    section_id="note:pdf-unknown",
                    title="PDF 추출 표",
                    kind="note",
                    note_no="",
                    blocks=[],
                    scope="",
                )
                sections.append(current)
            if bbox is None:
                warnings.append(f"PDF_TABLE_BBOX_MISSING page {item['page']} table {source_table_index}")
            block_index = len(current.blocks)
            table = ReportTable(
                index=table_index,
                rows=clean_rows,
                heading=current.title,
                location=SourceLocation(current.section_id, block_index, table_index),
            )
            current.blocks.append(
                ReportBlock(
                    kind="table",
                    text="",
                    table=table,
                    location=SourceLocation(current.section_id, block_index, table_index),
                    raw_html=_table_to_html(clean_rows),
                )
            )
            for row_index, row in enumerate(clean_rows):
                for column_index, _ in enumerate(row):
                    coordinates.append(
                        PdfSourceCoordinate(
                            source=f"{current.section_id}/table:{table_index}/row:{row_index}/col:{column_index}",
                            page=int(item["page"]),
                            table_index=table_index,
                            row_index=row_index,
                            column_index=column_index,
                            bbox=bbox,
                        )
                    )
            table_index += 1

    statements = [section for section in sections if section.kind == "statement" and section.blocks]
    notes = [section for section in sections if section.kind == "note" and section.blocks]
    if not statements and not notes:
        details = "; ".join(uncertain_reasons[:3])
        suffix = f" ({details})" if details else ""
        raise UnsupportedReportFormatError(
            "PDF 표 구조를 안정적으로 복원하지 못했습니다. DSD/HTML 또는 더 선명한 텍스트 PDF를 첨부하세요."
            + suffix
        )

    diagnostics = AttachmentDiagnostics(
        input_format="pdf",
        warnings=tuple(warnings),
        parse_uncertain_reasons=tuple(uncertain_reasons),
        page_count=max((int(item["page"]) for item in extracted), default=0),
        table_count=raw_table_count,
        skipped_table_count=skipped_table_count,
        source_coordinates=tuple(coordinates),
    )
    report = FullReport(str(source or filename), company, statements, notes)
    return ParsedAttachment(
        source=source,
        filename=filename,
        input_format="pdf",
        report=report,
        diagnostics=diagnostics,
        text=None,
    )


def _extract_page(page, page_index: int) -> dict:
    text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
    headings = [
        line.strip()
        for line in text.splitlines()
        if _is_statement_heading(line.strip()) or _is_note_heading(line.strip())
    ]
    tables = []
    for table in page.find_tables():
        rows = table.extract()
        tables.append((rows, tuple(float(value) for value in table.bbox)))
    if not tables:
        for rows in page.extract_tables() or []:
            tables.append((rows, None))
    return {"page": page_index, "text": text, "headings": headings, "tables": tables}


def _section_from_heading(text: str) -> ReportSection | None:
    if _is_statement_heading(text):
        title = _statement_title(text)
        return ReportSection(
            section_id=f"statement:{title}",
            title=title,
            kind="statement",
            note_no="",
            blocks=[],
            scope=_scope_from_text(text),
        )
    match = _note_heading_match(text)
    if match:
        note_no, title = match.groups()
        return ReportSection(
            section_id=f"note:{note_no}",
            title=title.strip(),
            kind="note",
            note_no=note_no,
            blocks=[],
            scope=_scope_from_text(text),
        )
    return None


def _infer_section_from_rows(rows: list[list[str]]) -> ReportSection | None:
    joined = " ".join(cell for row in rows[:2] for cell in row)
    return _section_from_heading(joined)


def _clean_table(rows: list[list[str | None]]) -> list[list[str]]:
    cleaned = [
        [re.sub(r"\s+", " ", str(cell or "")).strip() for cell in row]
        for row in rows
    ]
    width = max((len(row) for row in cleaned), default=0)
    return [row + [""] * (width - len(row)) for row in cleaned if any(cell for cell in row)]


def _is_reliable_table(rows: list[list[str]]) -> bool:
    if len(rows) < 2:
        return False
    width = max((len(row) for row in rows), default=0)
    if width < 2:
        return False
    non_empty_rows = [row for row in rows if any(cell.strip() for cell in row)]
    if len(non_empty_rows) < 2:
        return False
    header = non_empty_rows[0]
    if sum(1 for cell in header if cell.strip()) < 2:
        return False
    numeric_cells = sum(
        1
        for row in non_empty_rows[1:]
        for cell in row[1:]
        if re.search(r"[-+]?\(?\d[\d,.\s]*\)?", cell)
    )
    if numeric_cells == 0:
        return False
    widths = [len(row) for row in non_empty_rows]
    if max(widths) - min(widths) > 2:
        return False
    return True


def _is_statement_heading(text: str) -> bool:
    return any(title in text for title in ("재무상태표", "손익계산서", "포괄손익계산서", "자본변동표", "현금흐름표"))


def _statement_title(text: str) -> str:
    for title in ("재무상태표", "손익계산서", "포괄손익계산서", "자본변동표", "현금흐름표"):
        if title in text:
            return title
    return "재무제표"


def _is_note_heading(text: str) -> bool:
    return _note_heading_match(text) is not None


def _note_heading_match(text: str):
    return re.match(r"^\s*(\d{1,3})\.\s*(.+)$", text)


def _scope_from_text(text: str) -> str:
    if "연결" in text:
        return "consolidated"
    if "별도" in text:
        return "separate"
    return ""


def _table_to_html(rows: list[list[str]]) -> str:
    html_rows = []
    for row_index, row in enumerate(rows):
        tag = "th" if row_index == 0 else "td"
        cells = "".join(
            f'<{tag} data-cell-keys="r{row_index}c{column_index}">{_esc(cell)}</{tag}>'
            for column_index, cell in enumerate(row)
        )
        html_rows.append(f"<tr>{cells}</tr>")
    return "<table>" + "".join(html_rows) + "</table>"


def _esc(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
```

- [ ] **Step 5: Run PDF tests with optional dependencies**

Run:

```bash
uv run --extra pdf --with reportlab pytest tests/test_pdf_report.py -v
```

Expected: PASS.

- [ ] **Step 6: Run default tests for skip/pass behavior**

Run:

```bash
uv run pytest tests/test_pdf_report.py tests/test_report_ingest.py -v
```

Expected: `tests/test_pdf_report.py` is skipped if optional dependencies are missing; `tests/test_report_ingest.py` passes.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/dart_footing_reconciler/pdf_report.py tests/test_pdf_report.py
git commit -m "Add text PDF report extraction adapter"
```

---

### Task 4: Workpaper CLI Integration and Input Metadata

**Files:**
- Modify: `src/dart_footing_reconciler/cli.py`
- Modify: `src/dart_footing_reconciler/report_html.py`
- Modify: `tests/test_cli_workpaper.py`
- Modify: `tests/test_report_html_new.py`

**Interfaces:**
- Consumes: `parse_attached_report(path, company=...) -> ParsedAttachment`
- Produces: workpaper commands accepting DSD/HTML/PDF via one path and report HTML showing input provenance

- [ ] **Step 1: Write failing CLI and report metadata tests**

Add to `tests/test_report_html_new.py`:

```python
def test_export_surfaces_input_format_metadata(tmp_path: Path):
    report = FullReport("t.pdf", "회사", [], [])
    out = tmp_path / "r.html"

    export_audit_reconciliation_html(
        report,
        [],
        out,
        source_filename="sample.pdf",
        input_format="pdf",
        extraction_warnings=("PDF 텍스트 추출 기반",),
        pdf_page_count=3,
        pdf_table_count=4,
        pdf_skipped_table_count=1,
        parse_uncertain_reasons=("PDF_TABLE_GRID_UNCERTAIN page 2 table 0",),
    )

    content = out.read_text(encoding="utf-8")
    assert "입력 파일명" in content
    assert "sample.pdf" in content
    assert "입력 형식: PDF" in content
    assert "PDF 텍스트 추출 기반" in content
    assert "PDF page count: 3" in content
    assert "PDF extracted table count: 4" in content
    assert "PDF skipped table count: 1" in content
    assert "PDF_TABLE_GRID_UNCERTAIN page 2 table 0" in content
```

Add to `tests/test_cli_workpaper.py`:

```python
def test_cli_workpaper_html_accepts_text_pdf_when_pdf_extra_available(tmp_path):
    pytest.importorskip("pdfplumber")
    pytest.importorskip("pypdf")
    pytest.importorskip("reportlab")
    from tests.test_pdf_report import _write_table_pdf

    source = tmp_path / "sample.pdf"
    output = tmp_path / "workpaper.html"
    _write_table_pdf(source)

    result = CliRunner().invoke(
        app,
        ["workpaper-html", str(source), str(output), "--company", "PDF Co"],
    )

    assert result.exit_code == 0
    content = output.read_text(encoding="utf-8")
    assert "PDF Co" in content
    assert "sample.pdf" in content
    assert "입력 형식: PDF" in content
    assert "PDF 텍스트 추출 기반" in content
    assert "PDF page count:" in content
    assert "PDF extracted table count:" in content
    assert "PDF skipped table count:" in content
```

Ensure `tests/test_cli_workpaper.py` imports `pytest`, `CliRunner`, and `app` if not already present:

```python
import pytest
from typer.testing import CliRunner

from dart_footing_reconciler.cli import app
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --extra pdf --with reportlab pytest tests/test_report_html_new.py::test_export_surfaces_input_format_metadata tests/test_cli_workpaper.py::test_cli_workpaper_html_accepts_text_pdf_when_pdf_extra_available -v
```

Expected: FAIL because `export_audit_reconciliation_html()` has no `input_format` arguments and `workpaper-html` still calls `parse_full_report()` directly.

- [ ] **Step 3: Extend report HTML metadata**

Modify `src/dart_footing_reconciler/report_html.py`:

```python
def export_audit_reconciliation_html(
    report: FullReport,
    checks: list[CheckResult],
    output_path: str | Path,
    *,
    company_name: str = "",
    period_label: str = "",
    source_filename: str = "",
    input_format: str = "",
    extraction_warnings: tuple[str, ...] = (),
    pdf_page_count: int = 0,
    pdf_table_count: int = 0,
    pdf_skipped_table_count: int = 0,
    parse_uncertain_reasons: tuple[str, ...] = (),
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    meta = _ReportMeta(
        company=company_name or report.company or "회사",
        period=period_label,
        source_filename=source_filename,
        input_format=input_format,
        extraction_warnings=tuple(extraction_warnings),
        pdf_page_count=pdf_page_count,
        pdf_table_count=pdf_table_count,
        pdf_skipped_table_count=pdf_skipped_table_count,
        parse_uncertain_reasons=tuple(parse_uncertain_reasons),
    )
    output.write_text(_build_html(report, checks, meta), encoding="utf-8")
    return output


class _ReportMeta(NamedTuple):
    company: str
    period: str
    source_filename: str = ""
    input_format: str = ""
    extraction_warnings: tuple[str, ...] = ()
    pdf_page_count: int = 0
    pdf_table_count: int = 0
    pdf_skipped_table_count: int = 0
    parse_uncertain_reasons: tuple[str, ...] = ()
```

In `_render_report_masthead`, add this metadata beside existing source/count chips:

```python
source_chip = ""
if meta.source_filename:
    source_chip = f'<span>입력 파일명: {_esc(meta.source_filename)}</span>'
format_chip = ""
if meta.input_format:
    format_chip = f'<span>입력 형식: {_esc(meta.input_format.upper())}</span>'
warning_chips = "".join(f"<span>{_esc(item)}</span>" for item in meta.extraction_warnings)
pdf_chips = ""
if meta.input_format == "pdf":
    pdf_chips = (
        f"<span>PDF page count: {meta.pdf_page_count}</span>"
        f"<span>PDF extracted table count: {meta.pdf_table_count}</span>"
        f"<span>PDF skipped table count: {meta.pdf_skipped_table_count}</span>"
    )
reason_chips = "".join(
    f"<span>{_esc(reason)}</span>" for reason in meta.parse_uncertain_reasons
)
```

Then include `{source_chip}{format_chip}{warning_chips}{pdf_chips}{reason_chips}` inside the existing masthead metadata container that already contains source and section counts. Keep the values in a diagnostics/provenance row, not inside the note table markup, so the parsed report table remains visually unchanged.

- [ ] **Step 4: Route workpaper CLI through parse_attached_report**

Modify imports in `src/dart_footing_reconciler/cli.py`:

```python
from dart_footing_reconciler.report_ingest import parse_attached_report
```

Update `workpaper_excel`:

```python
current = parse_attached_report(current_html, company=company or current_html.stem)
prior = (
    parse_attached_report(prior_html, company=company or prior_html.stem)
    if prior_html is not None
    else None
)
report = current.report
prior_report = prior.report if prior is not None else None
checks: list[CheckResult] = []
checks.extend(_run_workpaper_checks(report, prior_report, tolerance))
workbook_path = export_audit_workbook(report, checks, output)
```

Update `workpaper_html`:

```python
current = parse_attached_report(current_html, company=company or current_html.stem)
prior = (
    parse_attached_report(prior_html, company=company or prior_html.stem)
    if prior_html is not None
    else None
)
report = current.report
prior_report = prior.report if prior is not None else None
checks = _run_workpaper_checks(report, prior_report, tolerance)
warnings = current.diagnostics.warnings
if current.input_format == "pdf":
    warnings = ("PDF 텍스트 추출 기반", *warnings)
report_path = export_audit_reconciliation_html(
    report,
    checks,
    output,
    source_filename=current.filename,
    input_format=current.input_format,
    extraction_warnings=warnings,
    pdf_page_count=current.diagnostics.page_count,
    pdf_table_count=current.diagnostics.table_count,
    pdf_skipped_table_count=current.diagnostics.skipped_table_count,
    parse_uncertain_reasons=current.diagnostics.parse_uncertain_reasons,
)
typer.echo(f"Wrote {report_path}")
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --extra pdf --with reportlab pytest tests/test_report_html_new.py::test_export_surfaces_input_format_metadata tests/test_cli_workpaper.py::test_cli_workpaper_html_accepts_text_pdf_when_pdf_extra_available -v
```

Expected: PASS.

- [ ] **Step 6: Run HTML/DSD workpaper regression tests**

Run:

```bash
uv run pytest tests/test_cli_workpaper.py tests/test_report_html_new.py -v
```

Expected: PASS, with optional PDF test skipped if PDF dependencies are unavailable.

- [ ] **Step 7: Commit**

```bash
git add src/dart_footing_reconciler/cli.py src/dart_footing_reconciler/report_html.py tests/test_cli_workpaper.py tests/test_report_html_new.py
git commit -m "Route workpaper commands through report ingest"
```

---

### Task 5: Local Footing, Coverage, and Candidate CLI Integration

**Files:**
- Modify: `src/dart_footing_reconciler/cli.py`
- Modify: `tests/test_cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `parse_attached_report()`
- Produces: `coverage-report` and `candidate-report` using the same attachment ingest path; `foot` remains HTML/DSD-only because it calls `scan_html()`

- [ ] **Step 1: Write failing CLI routing tests**

Add to `tests/test_cli.py`:

```python
def test_cli_coverage_report_uses_ingest_for_dsd(tmp_path) -> None:
    source = tmp_path / "sample.dsd"
    source.write_bytes(
        """
        <DOCUMENT>
          <p>1. 일반사항</p>
          <table><tr><th>구분</th><th>내용</th></tr><tr><td>회사</td><td>샘플</td></tr></table>
          <p>11. 유형자산</p>
          <table><tr><th>구분</th><th>합계</th></tr><tr><td>기말</td><td>1,000</td></tr></table>
        </DOCUMENT>
        """.encode("cp949")
    )

    result = CliRunner().invoke(app, ["coverage-report", str(source), "--company", "Sample Co"])

    assert result.exit_code == 0
    assert "company: Sample Co" in result.output
    assert "total_notes: 2" in result.output
```

Add to `tests/test_cli.py`:

```python
def test_cli_candidate_report_uses_ingest_for_html(tmp_path) -> None:
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>11. 유형자산</p>
          <table><tr><th>구분</th><th>합계</th></tr><tr><td>기말</td><td>1,000</td></tr></table>
        </body></html>
        """,
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["candidate-report", str(source), "--company", "Sample Co"])

    assert result.exit_code == 0
    assert "company: Sample Co" in result.output
    assert "total_note_tables:" in result.output
```

- [ ] **Step 2: Run tests to verify current baseline**

Run:

```bash
uv run pytest tests/test_cli.py::test_cli_coverage_report_uses_ingest_for_dsd tests/test_cli.py::test_cli_candidate_report_uses_ingest_for_html -v
```

Expected: PASS for both tests. These tests establish current DSD/HTML behavior before replacing direct parser calls.

- [ ] **Step 3: Update coverage-report and candidate-report**

Modify `coverage_report` in `src/dart_footing_reconciler/cli.py`:

```python
parsed = parse_attached_report(html, company=company or html.stem)
report = parsed.report
inventory = build_note_inventory(report)
layouts = {table.source: classify_layout(table) for table in inventory.tables}
checks = _run_workpaper_checks(report, None, tolerance)
```

Modify `candidate_report`:

```python
parsed = parse_attached_report(html, company=company or html.stem)
report = parsed.report
inventory = build_note_inventory(report)
```

Keep the rest of each command unchanged.

- [ ] **Step 4: Clarify foot command PDF boundary**

Update the `foot()` docstring:

```python
"""Foot movement-like tables in a local DART DSD/HTML document.

PDF input is accepted by workpaper-html/workpaper-excel because those commands
operate on FullReport. This table-scanning command remains HTML/DSD-only.
"""
```

Update the `load_local_report()` PDF error from Task 2 so `foot report.pdf` clearly says `workpaper-html` supports text PDF:

```python
raise UnsupportedReportFormatError(
    "이 명령은 표 단위 footing용 HTML/DSD 텍스트 입력만 지원합니다. "
    "텍스트 PDF는 workpaper-html 또는 workpaper-excel에서 검증하세요."
)
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
uv run pytest tests/test_cli.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dart_footing_reconciler/cli.py tests/test_cli.py
git commit -m "Use attachment ingest in diagnostic CLI commands"
```

---

### Task 6: Offline Verify App Shared Entrypoint

**Files:**
- Modify: `src/dart_footing_reconciler/verify_app.py`
- Modify: `static/dart-verify/app.js`
- Modify: `tests/test_verify_app.py`
- Modify: `tests/js/dart_verify_app.test.js`

**Interfaces:**
- Consumes: `parse_attached_report_bytes(data, filename, company=...)`
- Produces: `verify_attached_report(file_bytes, filename, company="", tolerance=1) -> str`

- [ ] **Step 1: Write failing Python verify tests**

Modify `tests/test_verify_app.py` imports:

```python
from dart_footing_reconciler.verify_app import verify_attached_report, verify_html_report
```

Replace the PDF rejection test with:

```python
def test_verify_attached_report_routes_pdf_to_engine_message() -> None:
    with pytest.raises(UnsupportedReportFormatError, match="텍스트|PDF"):
        verify_attached_report(b"%PDF-1.7\n%...", filename="report.pdf", company="PDF Co")
```

Add:

```python
def test_verify_attached_report_accepts_html_bytes() -> None:
    html = b"""
    <html><body>
      <p>1. 일반사항</p>
      <table><tr><th>구분</th><th>내용</th></tr><tr><td>회사</td><td>샘플</td></tr></table>
    </body></html>
    """

    cockpit_html = verify_attached_report(html, filename="report.html", company="Sample Co")

    assert cockpit_html.startswith("<!DOCTYPE html>")
    assert "Sample Co" in cockpit_html
```

- [ ] **Step 2: Write failing JS tests**

Replace `tests/js/dart_verify_app.test.js` PDF pre-rejection test with:

```javascript
  test("routes PDF files to the PyOdide engine instead of rejecting in JavaScript", async () => {
    const install = vi.fn();
    const pyodide = {
      FS: { writeFile: vi.fn() },
      globals: { set: vi.fn(), delete: vi.fn() },
      loadPackage: vi.fn(),
      pyimport: vi.fn(() => ({ install })),
      runPython: vi.fn(() => {
        throw new Error("UnsupportedReportFormatError: 텍스트 PDF 추출 런타임이 설치되어 있지 않습니다.");
      }),
    };
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({
      autoBoot: false,
      loadPyodideFn: vi.fn(async () => pyodide),
    });

    await expect(
      controller.verifyFile(new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], "report.pdf")),
    ).rejects.toThrow("텍스트 PDF");

    expect(pyodide.FS.writeFile).toHaveBeenCalledWith(
      "/tmp/dart_verify_current.bin",
      expect.any(Uint8Array),
    );
    expect(pyodide.runPython.mock.calls[0][0]).toContain("verify_attached_report");
    expect(pyodide.globals.set).toHaveBeenCalledWith("dart_verify_filename", "report.pdf");
  });
```

Add a focused error-mapping test:

```javascript
  test("maps scanned PDF text-layer error distinctly", async () => {
    const { initDartVerifyApp } = await import("../../static/dart-verify/app.js");
    const controller = initDartVerifyApp({
      autoBoot: false,
      loadPyodideFn: vi.fn(),
    });

    controller.showError(
      new Error("UnsupportedReportFormatError: 텍스트 레이어가 없는 PDF입니다."),
    );

    expect(document.getElementById("status").textContent).toContain("PDF 추출");
    expect(document.getElementById("status").textContent).toContain("DSD/HTML");
  });
```

In the existing "loads PyOdide packages" test, update the assertion:

```javascript
    expect(pyodide.runPython.mock.calls[0][0]).toContain("verify_attached_report");
    expect(pyodide.runPython.mock.calls[0][0]).not.toContain("_decode_text");
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_verify_app.py -v
npm test -- tests/js/dart_verify_app.test.js
```

Expected: FAIL because `verify_attached_report` does not exist and JS still rejects PDF before engine execution.

- [ ] **Step 4: Implement Python verify entrypoint**

Modify `src/dart_footing_reconciler/verify_app.py`:

```python
"""In-browser verification entrypoints for the offline DART verify app."""

from __future__ import annotations

from dart_footing_reconciler.check_pipeline import assemble_report_checks
from dart_footing_reconciler.report_html import _ReportMeta, _build_html
from dart_footing_reconciler.report_ingest import parse_attached_report_bytes


def verify_attached_report(
    file_bytes: bytes,
    *,
    filename: str,
    company: str = "",
    tolerance: int = 1,
) -> str:
    """Return evidence_cockpit HTML for a DSD/HTML/text-PDF attachment."""
    parsed = parse_attached_report_bytes(file_bytes, filename=filename, company=company)
    report = parsed.report
    checks = assemble_report_checks(report, None, tolerance=tolerance)
    warnings = parsed.diagnostics.warnings
    if parsed.input_format == "pdf":
        warnings = ("PDF 텍스트 추출 기반", *warnings)
    meta = _ReportMeta(
        company=company or report.company or "회사",
        period="",
        source_filename=filename,
        input_format=parsed.input_format,
        extraction_warnings=warnings,
        pdf_page_count=parsed.diagnostics.page_count,
        pdf_table_count=parsed.diagnostics.table_count,
        pdf_skipped_table_count=parsed.diagnostics.skipped_table_count,
        parse_uncertain_reasons=parsed.diagnostics.parse_uncertain_reasons,
    )
    return _build_html(report, checks, meta)


def verify_html_report(
    html_text: str,
    *,
    company: str = "",
    prior_text: str | None = None,
    tolerance: int = 1,
) -> str:
    """Return evidence_cockpit HTML for a DART HTML/DSD report."""
    if prior_text is not None:
        current = parse_attached_report_bytes(
            html_text.encode("utf-8"),
            filename="current.html",
            company=company,
        )
        prior = parse_attached_report_bytes(
            prior_text.encode("utf-8"),
            filename="prior.html",
            company=company,
        )
        checks = assemble_report_checks(current.report, prior.report, tolerance=tolerance)
        meta = _ReportMeta(
            company=company or current.report.company or "회사",
            period="",
            source_filename=current.filename,
            input_format=current.input_format,
        )
        return _build_html(current.report, checks, meta)
    return verify_attached_report(
        html_text.encode("utf-8"),
        filename="current.html",
        company=company,
        tolerance=tolerance,
    )
```

- [ ] **Step 5: Update browser shell Python call**

Modify `static/dart-verify/app.js`:

```javascript
const VERIFY_PYTHON = `
from pathlib import Path
from dart_footing_reconciler.verify_app import verify_attached_report

verify_attached_report(
    Path(dart_verify_path).read_bytes(),
    filename=dart_verify_filename,
    company=dart_verify_company,
    tolerance=int(dart_verify_tolerance),
)
`;
```

Remove this block from `verifyFile(file)`:

```javascript
    if (await isPdfFile(file)) {
      throw new Error("PDF 파일은 지원하지 않습니다. DART HTML/DSD 파일을 사용하세요.");
    }
```

After setting `dart_verify_path`, add:

```javascript
    pyodide.globals.set("dart_verify_filename", file.name || "report.html");
```

In `finally`, add:

```javascript
      deleteGlobal(pyodide, "dart_verify_filename");
```

Update `toKoreanErrorMessage(error)`:

```javascript
  if (
    message.includes("텍스트 PDF")
    || message.includes("텍스트 레이어")
    || message.includes("PDF_TEXT_LAYER_MISSING")
  ) {
    return "이 브라우저 런타임에서는 PDF 추출을 실행할 수 없습니다. CLI/server에서 텍스트 PDF를 처리하거나 DSD/HTML 파일을 사용하세요.";
  }
  if (message.includes("UnsupportedReportFormatError")) {
    return "지원하지 않는 파일 형식입니다. DSD/HTML 또는 텍스트 PDF를 첨부하세요.";
  }
```

Remove `isPdfFile()` because PDF detection now belongs to Python.

- [ ] **Step 6: Run verify tests**

Run:

```bash
uv run pytest tests/test_verify_app.py -v
npm test -- tests/js/dart_verify_app.test.js
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/dart_footing_reconciler/verify_app.py static/dart-verify/app.js tests/test_verify_app.py tests/js/dart_verify_app.test.js
git commit -m "Route verify app uploads through attachment ingest"
```

---

### Task 7: Final Regression, Optional PDF Verification, and Rendered Smoke

**Files:**
- Test-only changes if failures reveal missing assertions.
- Generated smoke output under `output/playwright/` is not committed unless the repository already tracks such artifacts.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: verified implementation ready for review.

- [ ] **Step 1: Run default Python test suite**

Run:

```bash
uv run pytest
```

Expected: PASS. Optional PDF tests are reported as SKIPPED when optional dependencies are not installed.

- [ ] **Step 2: Run optional PDF tests**

Run:

```bash
uv run --extra pdf --with reportlab pytest tests/test_pdf_report.py tests/test_cli_workpaper.py::test_cli_workpaper_html_accepts_text_pdf_when_pdf_extra_available -v
```

Expected: PASS.

- [ ] **Step 3: Run browser shell tests**

Run:

```bash
npm test -- tests/js/dart_verify_app.test.js
```

Expected: PASS.

- [ ] **Step 4: Generate a PDF-backed workpaper smoke artifact**

Run:

```bash
uv run --extra pdf --with reportlab python - <<'PY'
from pathlib import Path
from typer.testing import CliRunner
from dart_footing_reconciler.cli import app
from tests.test_pdf_report import _write_table_pdf

source = Path("output/playwright/text_pdf_ingest_sample.pdf")
output = Path("output/playwright/text_pdf_ingest_workpaper.html")
source.parent.mkdir(parents=True, exist_ok=True)
_write_table_pdf(source)
result = CliRunner().invoke(app, ["workpaper-html", str(source), str(output), "--company", "PDF Co"])
print(result.output)
raise SystemExit(result.exit_code)
PY
```

Expected: command exits 0 and writes `output/playwright/text_pdf_ingest_workpaper.html`.

- [ ] **Step 5: Inspect rendered artifact with Playwright**

Run:

```bash
python3 -m http.server 8765 --directory output/playwright
```

In another terminal:

```bash
$HOME/.codex/skills/playwright/scripts/playwright_cli.sh open http://127.0.0.1:8765/text_pdf_ingest_workpaper.html
$HOME/.codex/skills/playwright/scripts/playwright_cli.sh eval "() => ({title: document.title, text: document.body.innerText.includes('입력 형식: PDF'), provenance: document.body.innerText.includes('PDF 텍스트 추출 기반'), hasOverlapRisk: [...document.querySelectorAll('td,th')].some((el) => el.scrollWidth > el.clientWidth + 4)})"
$HOME/.codex/skills/playwright/scripts/playwright_cli.sh screenshot --filename output/playwright/text_pdf_ingest_workpaper.png --full-page
$HOME/.codex/skills/playwright/scripts/playwright_cli.sh close
```

Expected eval result:

```json
{
  "text": true,
  "provenance": true,
  "hasOverlapRisk": false
}
```

Stop the server with `Ctrl+C`.

- [ ] **Step 6: Check git diff scope**

Run:

```bash
git status --short
git diff --stat
```

Expected tracked source/test/doc changes only. Generated `output/playwright` files stay untracked and are not committed.

- [ ] **Step 7: Commit final verification fixes if any**

If Step 1-6 required fixes:

```bash
git add src tests static pyproject.toml
git commit -m "Stabilize text PDF ingest verification"
```

If no fixes were required:

```bash
git status --short
```

Expected: no staged changes.

---

## Plan Self-Review

- Conditional approval fixes:
  - DSD files containing `<table>` are classified as DSD before generic table/HTML heuristics, with `test_detect_dsd_with_table_does_not_become_html`.
  - HTML/DSD parsing reconstructs `FullReport.source` from the original source path after temporary-file parsing, with an explicit source-preservation assertion.
  - `foot` uses `decode_attached_report_text()` and remains scan-text-only; it does not require `FullReport` parsing.
  - PDF table promotion has reliability gates for row count, width, non-empty headers, numeric cells, and irregular row widths.
  - Weak/skipped PDF tables populate `parse_uncertain_reasons`, `warnings`, `table_count`, and `skipped_table_count`, and these diagnostics are surfaced in generated HTML.
  - Browser error mapping covers `"텍스트 PDF"`, `"텍스트 레이어"`, and `PDF_TEXT_LAYER_MISSING`.
- Spec coverage:
  - DSD/HTML unchanged path: Task 1, Task 2, Task 4, Task 5.
  - Text-layer PDF Python runtime support: Task 3 and Task 4.
  - Scanned PDF/OCR exclusion: Task 1, Task 2, Task 3, Task 6.
  - No external company-source linkage: Global Constraints; no task introduces external data.
  - `FullReport` remains engine contract: Task 1, Task 3, Task 4, Task 6.
  - PDF coordinate sidecar without `SourceLocation` schema change: Task 1 and Task 3.
  - CLI integration: Task 4 and Task 5.
  - Offline verify app routing and deterministic runtime message: Task 6.
  - Workpaper provenance metadata and diagnostics placement: Task 4.
  - Tests and rendered smoke: Task 7.
- Placeholder scan: clean; no unresolved implementation decisions remain.
- Type consistency: `AttachmentDiagnostics`, `ParsedAttachment`, `parse_attached_report`, `parse_attached_report_bytes`, `parse_text_pdf_report`, and `verify_attached_report` signatures are introduced before later tasks consume them.
