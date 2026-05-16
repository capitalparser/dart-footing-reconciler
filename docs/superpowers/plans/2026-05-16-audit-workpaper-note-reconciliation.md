# Audit Workpaper Note Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-company audit workpaper Excel export that renders every financial statement and note in source order, preserves note/table content, and appends validation blocks for total checks, FS-note matching, note-note matching, CFS-note matching, and prior-year disclosure reconciliation.

**Architecture:** Add a document model above the current movement-table scanner. The new flow is `DART HTML -> FullReport -> ValidationRun -> AuditWorkbook`, while existing `foot`, `foot-excel`, and `validate-excel` remain diagnostic/corpus tools. Checks are rule-based, source-referenced, and allowed to emit `not_tested` or `parse_uncertain` until a rule is reliable.

**Tech Stack:** Python 3.11, BeautifulSoup/lxml, openpyxl, Typer, pytest, current `dart_footing_reconciler` package.

---

## Milestones

| Milestone | Target | Completion Evidence |
|---|---|---|
| M1 Document model | Parse all financial statements and all notes, preserving source order and raw table/text blocks | Unit tests prove a sample report yields FS sections, all note sections, table indices, and source row/cell references |
| M2 Workpaper Excel | Create one workbook per company with one sheet per note and source-like rendering | Workbook test verifies `FS Summary`, `Validation Summary`, `Note 11`, `Note 12` sheets and validation blocks under each note |
| M3 Total checks | Run sum/subtotal checks for all tables, not just movement tables | Tests cover row total, column total, subtotal, grand total, and skipped ambiguous tables |
| M4 FS-note matching | Match BS/PL/SCE/CF statement line items to note amounts | Fixture tests cover at least one BS-note, PL-note, SCE-note, and CF-note match |
| M5 Note-note matching | Match amounts between related notes | Fixture tests cover depreciation/amortization, lease, debt, and tax-related note-note relationships |
| M6 CFS-note matching | Match operating, investing, and financing CFS lines to relevant note movements | Fixture tests cover one operating, one investing, and one financing activity reconciliation |
| M7 Prior-year disclosure reconciliation | Compare current-period comparative amounts and structure to prior-year DART report | Fixture tests cover amount match, note number change, account label change, table row added, and table row removed |
| M8 Debugging/acceptance corpus | Run at least 5 manufacturing companies through the audit workbook export | Saved validation log summarizes failure categories and unresolved parser gaps |

## File Structure

Create:

- `src/dart_footing_reconciler/document.py`
  - Full-report extraction model: statements, notes, blocks, tables, source locations.
- `src/dart_footing_reconciler/checks.py`
  - Validation result dataclasses and shared status constants.
- `src/dart_footing_reconciler/checks_totals.py`
  - Generic row/column total checks for every extracted table.
- `src/dart_footing_reconciler/checks_fs_note.py`
  - Financial statement to note matching rules.
- `src/dart_footing_reconciler/checks_note_note.py`
  - Note to note matching rules.
- `src/dart_footing_reconciler/checks_cfs_note.py`
  - Operating/investing/financing CFS to note reconciliation rules.
- `src/dart_footing_reconciler/checks_prior_year.py`
  - Prior-year amount and structure comparison.
- `src/dart_footing_reconciler/audit_workbook.py`
  - Workpaper-style Excel renderer with source content followed by validation blocks.
- `tests/test_document.py`
- `tests/test_checks_totals.py`
- `tests/test_checks_fs_note.py`
- `tests/test_checks_note_note.py`
- `tests/test_checks_cfs_note.py`
- `tests/test_checks_prior_year.py`
- `tests/test_audit_workbook.py`

Modify:

- `src/dart_footing_reconciler/cli.py`
  - Add `workpaper-excel CURRENT_HTML OUTPUT.xlsx --company ... --prior-html PRIOR_HTML`.
- `src/dart_footing_reconciler/__init__.py`
  - Export stable public functions.
- `README.md`
  - Document the audit workpaper export separately from diagnostic `foot-excel`.
- `.gitignore`
  - Keep generated workbooks/logs out of git if new output folders are added.

## Data Contracts

Create these dataclasses in `src/dart_footing_reconciler/document.py`:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class SourceLocation:
    section_id: str
    block_index: int
    table_index: int | None = None
    row_index: int | None = None
    column_index: int | None = None

@dataclass(frozen=True)
class ReportTable:
    index: int
    rows: list[list[str]]
    heading: str
    location: SourceLocation

@dataclass(frozen=True)
class ReportBlock:
    kind: str  # "text" or "table"
    text: str
    table: ReportTable | None
    location: SourceLocation

@dataclass(frozen=True)
class ReportSection:
    section_id: str
    title: str
    kind: str  # "statement" or "note"
    note_no: str
    blocks: list[ReportBlock]

@dataclass(frozen=True)
class FullReport:
    source: str
    company: str
    statements: list[ReportSection]
    notes: list[ReportSection]
```

Create these dataclasses in `src/dart_footing_reconciler/checks.py`:

```python
from dataclasses import dataclass

MATCHED = "matched"
EXPLAINABLE_GAP = "explainable_gap"
UNEXPLAINED_GAP = "unexplained_gap"
PARSE_UNCERTAIN = "parse_uncertain"
NOT_TESTED = "not_tested"

@dataclass(frozen=True)
class CheckEvidence:
    label: str
    amount: int | None
    source: str

@dataclass(frozen=True)
class CheckResult:
    check_id: str
    check_type: str
    status: str
    scope: str
    note_no: str
    title: str
    expected: int | None
    actual: int | None
    difference: int | None
    tolerance: int
    reason: str
    evidence: list[CheckEvidence]
```

## Task 1: Parse Full Report Into Statements And Notes

**Files:**
- Create: `src/dart_footing_reconciler/document.py`
- Test: `tests/test_document.py`

- [ ] **Step 1: Write failing test for statement and note extraction**

```python
from dart_footing_reconciler.document import parse_full_report

def test_parse_full_report_extracts_statements_and_all_notes(tmp_path):
    html = """
    <p>재무상태표</p>
    <table><tr><th>구분</th><th>당기</th></tr><tr><td>자산총계</td><td>1,000</td></tr></table>
    <p>손익계산서</p>
    <table><tr><th>구분</th><th>당기</th></tr><tr><td>매출액</td><td>500</td></tr></table>
    <p>1. 일반사항</p>
    <p>회사의 개요입니다.</p>
    <p>2. 중요한 회계정책</p>
    <table><tr><th>구분</th><th>금액</th></tr><tr><td>합계</td><td>100</td></tr></table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert report.company == "Sample Co"
    assert [section.title for section in report.statements] == ["재무상태표", "손익계산서"]
    assert [(note.note_no, note.title) for note in report.notes] == [
        ("1", "일반사항"),
        ("2", "중요한 회계정책"),
    ]
    assert report.notes[0].blocks[0].kind == "text"
    assert report.notes[1].blocks[0].kind == "table"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
uv run python -m pytest tests/test_document.py::test_parse_full_report_extracts_statements_and_all_notes -v
```

Expected: FAIL because `dart_footing_reconciler.document` does not exist.

- [ ] **Step 3: Implement minimal parser**

Create `src/dart_footing_reconciler/document.py` with:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import Tag

from dart_footing_reconciler.html_tables import _extract_rows

@dataclass(frozen=True)
class SourceLocation:
    section_id: str
    block_index: int
    table_index: int | None = None
    row_index: int | None = None
    column_index: int | None = None

@dataclass(frozen=True)
class ReportTable:
    index: int
    rows: list[list[str]]
    heading: str
    location: SourceLocation

@dataclass(frozen=True)
class ReportBlock:
    kind: str
    text: str
    table: ReportTable | None
    location: SourceLocation

@dataclass(frozen=True)
class ReportSection:
    section_id: str
    title: str
    kind: str
    note_no: str
    blocks: list[ReportBlock]

@dataclass(frozen=True)
class FullReport:
    source: str
    company: str
    statements: list[ReportSection]
    notes: list[ReportSection]

STATEMENT_TITLES = ("재무상태표", "손익계산서", "포괄손익계산서", "자본변동표", "현금흐름표")

def parse_full_report(source: str | Path, *, company: str = "") -> FullReport:
    path = Path(source)
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "lxml")
    sections: list[ReportSection] = []
    current: dict | None = None
    table_index = 0

    for node in soup.find_all(["p", "div", "table"]):
        if node.name in {"p", "div"}:
            text = _clean(node.get_text(" ", strip=True))
            if not text:
                continue
            statement_title = _statement_title(text)
            note = _note_heading(text)
            if statement_title:
                current = _new_section(statement_title, "statement", "")
                sections.append(current["section"])
                continue
            if note:
                current = _new_section(note[1], "note", note[0])
                sections.append(current["section"])
                continue
            if current is not None:
                _append_text(current["section"], text)
        elif node.name == "table" and current is not None:
            rows = _extract_rows(node)
            table = ReportTable(
                index=table_index,
                rows=[row.cells for row in rows],
                heading=current["section"].title,
                location=SourceLocation(current["section"].section_id, len(current["section"].blocks), table_index),
            )
            current["section"].blocks.append(
                ReportBlock("table", "", table, SourceLocation(current["section"].section_id, len(current["section"].blocks), table_index))
            )
            table_index += 1

    return FullReport(
        source=str(path),
        company=company,
        statements=[section["section"] if isinstance(section, dict) else section for section in []]
        or [section for section in sections if section.kind == "statement"],
        notes=[section for section in sections if section.kind == "note"],
    )

def _new_section(title: str, kind: str, note_no: str) -> dict:
    section_id = f"{kind}:{note_no or title}"
    return {"section": ReportSection(section_id, title, kind, note_no, [])}

def _append_text(section: ReportSection, text: str) -> None:
    section.blocks.append(ReportBlock("text", text, None, SourceLocation(section.section_id, len(section.blocks))))

def _statement_title(text: str) -> str:
    return next((title for title in STATEMENT_TITLES if title == text or text.endswith(title)), "")

def _note_heading(text: str) -> tuple[str, str] | None:
    match = re.match(r"^(\d+(?:-\d+)?)\.\s*(.+)$", text)
    if not match:
        return None
    return match.group(1), match.group(2).strip()

def _clean(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())
```

- [ ] **Step 4: Run document parser tests**

Run:

```bash
uv run python -m pytest tests/test_document.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/document.py tests/test_document.py
git commit -m "add full report document parser"
```

## Task 2: Add Shared Check Result Model

**Files:**
- Create: `src/dart_footing_reconciler/checks.py`
- Test: `tests/test_checks_model.py`

- [ ] **Step 1: Write failing test**

```python
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED

def test_check_result_preserves_source_evidence():
    result = CheckResult(
        check_id="total:note11:table0:row3",
        check_type="total_check",
        status=MATCHED,
        scope="note",
        note_no="11",
        title="유형자산 합계",
        expected=1000,
        actual=1000,
        difference=0,
        tolerance=1,
        reason="row total agrees",
        evidence=[CheckEvidence("합계", 1000, "note:11/table:0/row:3/col:4")],
    )
    assert result.status == "matched"
    assert result.evidence[0].source == "note:11/table:0/row:3/col:4"
```

- [ ] **Step 2: Run RED**

```bash
uv run python -m pytest tests/test_checks_model.py::test_check_result_preserves_source_evidence -v
```

Expected: FAIL because `checks.py` does not exist.

- [ ] **Step 3: Implement dataclasses exactly as defined in Data Contracts**

Create `src/dart_footing_reconciler/checks.py` with the `CheckEvidence`, `CheckResult`, and status constants shown in the Data Contracts section.

- [ ] **Step 4: Run tests**

```bash
uv run python -m pytest tests/test_checks_model.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/checks.py tests/test_checks_model.py
git commit -m "add shared validation result model"
```

## Task 3: Implement Universal Total Checks

**Files:**
- Create: `src/dart_footing_reconciler/checks_totals.py`
- Test: `tests/test_checks_totals.py`

- [ ] **Step 1: Write failing tests for row and column totals**

```python
from dart_footing_reconciler.checks_totals import check_table_totals
from dart_footing_reconciler.document import ReportTable, SourceLocation

def test_check_table_totals_matches_row_total():
    table = ReportTable(
        index=0,
        heading="11. 유형자산",
        location=SourceLocation("note:11", 0, 0),
        rows=[
            ["구분", "토지", "건물", "합계"],
            ["기초", "100", "200", "300"],
        ],
    )
    results = check_table_totals(table, note_no="11", tolerance=0)
    assert results[0].status == "matched"
    assert results[0].expected == 300
    assert results[0].actual == 300

def test_check_table_totals_reports_unexplained_gap():
    table = ReportTable(
        index=0,
        heading="11. 유형자산",
        location=SourceLocation("note:11", 0, 0),
        rows=[
            ["구분", "토지", "건물", "합계"],
            ["기초", "100", "200", "301"],
        ],
    )
    results = check_table_totals(table, note_no="11", tolerance=0)
    assert results[0].status == "unexplained_gap"
    assert results[0].difference == 1
```

- [ ] **Step 2: Run RED**

```bash
uv run python -m pytest tests/test_checks_totals.py -v
```

Expected: FAIL because `checks_totals.py` does not exist.

- [ ] **Step 3: Implement minimal row total logic**

Create `src/dart_footing_reconciler/checks_totals.py`:

```python
from __future__ import annotations

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import ReportTable

TOTAL_LABELS = ("합계", "계", "총계", "자산총계", "부채총계", "자본총계")

def check_table_totals(table: ReportTable, *, note_no: str, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        total_col = _total_column(row)
        if total_col is None or total_col < 2:
            continue
        values = [parse_amount(cell) for cell in row[1:total_col]]
        actual = parse_amount(row[total_col])
        if actual is None or any(value is None for value in values):
            continue
        expected = sum(value for value in values if value is not None)
        difference = actual - expected
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        results.append(
            CheckResult(
                check_id=f"total:{note_no}:table{table.index}:row{row_idx}",
                check_type="total_check",
                status=status,
                scope="note",
                note_no=note_no,
                title=f"{row[0]} row total",
                expected=expected,
                actual=actual,
                difference=difference,
                tolerance=tolerance,
                reason="row total agrees" if status == MATCHED else "row total does not agree",
                evidence=[CheckEvidence(row[0], actual, f"note:{note_no}/table:{table.index}/row:{row_idx}/col:{total_col}")],
            )
        )
    return results

def _total_column(row: list[str]) -> int | None:
    for idx, cell in enumerate(row):
        if any(label == cell.replace(" ", "") for label in TOTAL_LABELS):
            return idx
    if len(row) >= 3 and row[-1].replace(" ", "") in TOTAL_LABELS:
        return len(row) - 1
    return len(row) - 1 if len(row) >= 4 else None
```

- [ ] **Step 4: Add column total test and implementation**

Add test:

```python
def test_check_table_totals_matches_column_total():
    table = ReportTable(
        index=1,
        heading="11. 유형자산",
        location=SourceLocation("note:11", 0, 1),
        rows=[
            ["구분", "금액"],
            ["토지", "100"],
            ["건물", "200"],
            ["합계", "300"],
        ],
    )
    results = check_table_totals(table, note_no="11", tolerance=0)
    assert any(result.status == "matched" and result.expected == 300 for result in results)
```

Extend `check_table_totals` with a `_column_total_results` helper that detects a final row whose first cell contains `합계`, sums numeric cells above it by column, and returns `CheckResult` rows with `check_id=f"total:{note_no}:table{table.index}:col{col_idx}"`.

- [ ] **Step 5: Run tests**

```bash
uv run python -m pytest tests/test_checks_totals.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dart_footing_reconciler/checks_totals.py tests/test_checks_totals.py
git commit -m "add universal table total checks"
```

## Task 4: Render Audit Workpaper Workbook With Source Blocks And Check Blocks

**Files:**
- Create: `src/dart_footing_reconciler/audit_workbook.py`
- Test: `tests/test_audit_workbook.py`
- Modify: `src/dart_footing_reconciler/cli.py`

- [ ] **Step 1: Write failing workbook test**

```python
from openpyxl import load_workbook

from dart_footing_reconciler.audit_workbook import export_audit_workbook
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation

def test_export_audit_workbook_renders_note_then_validation_block(tmp_path):
    table = ReportTable(0, [["구분", "합계"], ["기초", "100"]], "11. 유형자산", SourceLocation("note:11", 1, 0))
    note = ReportSection(
        section_id="note:11",
        title="유형자산",
        kind="note",
        note_no="11",
        blocks=[
            ReportBlock("text", "유형자산 변동내역입니다.", None, SourceLocation("note:11", 0)),
            ReportBlock("table", "", table, SourceLocation("note:11", 1, 0)),
        ],
    )
    report = FullReport(str(tmp_path / "report.html"), "Sample Co", [], [note])
    checks = [
        CheckResult("total:11:0", "total_check", MATCHED, "note", "11", "row total", 100, 100, 0, 1, "row total agrees", [CheckEvidence("기초", 100, "note:11/table:0/row:1/col:1")])
    ]
    output = tmp_path / "workpaper.xlsx"

    export_audit_workbook(report, checks, output)

    wb = load_workbook(output)
    ws = wb["Note 11"]
    assert ws["A1"].value == "11. 유형자산"
    assert ws["A3"].value == "유형자산 변동내역입니다."
    assert ws["A7"].value == "검증 결과"
    assert ws["B9"].value == "total_check"
```

- [ ] **Step 2: Run RED**

```bash
uv run python -m pytest tests/test_audit_workbook.py::test_export_audit_workbook_renders_note_then_validation_block -v
```

Expected: FAIL because `audit_workbook.py` does not exist.

- [ ] **Step 3: Implement source-first workbook renderer**

Create `src/dart_footing_reconciler/audit_workbook.py`:

```python
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.document import FullReport, ReportSection

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
CHECK_FILL = PatternFill("solid", fgColor="FFF2CC")

def export_audit_workbook(report: FullReport, checks: list[CheckResult], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Validation Summary"
    _write_summary(ws, report, checks)
    for note in report.notes:
        note_ws = wb.create_sheet(_sheet_name(note))
        _write_note_sheet(note_ws, note, [check for check in checks if check.note_no == note.note_no])
    wb.save(output)
    return output

def _write_summary(ws, report: FullReport, checks: list[CheckResult]) -> None:
    ws["A1"] = "Company"
    ws["B1"] = report.company
    ws["A2"] = "Checks"
    ws["B2"] = len(checks)

def _write_note_sheet(ws, note: ReportSection, checks: list[CheckResult]) -> None:
    ws["A1"] = f"{note.note_no}. {note.title}".strip()
    ws["A1"].fill = HEADER_FILL
    ws["A1"].font = Font(color="FFFFFF", bold=True)
    row = 3
    for block in note.blocks:
        if block.kind == "text":
            ws.cell(row, 1).value = block.text
            row += 2
        elif block.kind == "table" and block.table is not None:
            for table_row in block.table.rows:
                for col_idx, value in enumerate(table_row, start=1):
                    ws.cell(row, col_idx).value = value
                row += 1
            row += 1
    ws.cell(row, 1).value = "검증 결과"
    ws.cell(row, 1).fill = CHECK_FILL
    row += 1
    headers = ["check_id", "check_type", "status", "expected", "actual", "difference", "reason"]
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(row, col_idx).value = header
    row += 1
    for check in checks:
        values = [check.check_id, check.check_type, check.status, check.expected, check.actual, check.difference, check.reason]
        for col_idx, value in enumerate(values, start=1):
            ws.cell(row, col_idx).value = value
        row += 1

def _sheet_name(note: ReportSection) -> str:
    return f"Note {note.note_no}"[:31]
```

- [ ] **Step 4: Run workbook tests**

```bash
uv run python -m pytest tests/test_audit_workbook.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/audit_workbook.py tests/test_audit_workbook.py
git commit -m "add source-first audit workbook renderer"
```

## Task 5: Add Workpaper CLI Skeleton

**Files:**
- Modify: `src/dart_footing_reconciler/cli.py`
- Test: `tests/test_cli_workpaper.py`

- [ ] **Step 1: Write failing CLI test**

```python
from openpyxl import load_workbook
from typer.testing import CliRunner

from dart_footing_reconciler.cli import app

def test_cli_workpaper_excel_exports_note_sheets(tmp_path):
    source = tmp_path / "report.html"
    source.write_text(
        """
        <p>11. 유형자산</p>
        <p>유형자산 내용입니다.</p>
        <table><tr><th>구분</th><th>합계</th></tr><tr><td>기초</td><td>100</td></tr></table>
        """,
        encoding="utf-8",
    )
    output = tmp_path / "workpaper.xlsx"
    result = CliRunner().invoke(app, ["workpaper-excel", str(source), str(output), "--company", "Sample Co"])
    assert result.exit_code == 0
    wb = load_workbook(output)
    assert "Note 11" in wb.sheetnames
```

- [ ] **Step 2: Run RED**

```bash
uv run python -m pytest tests/test_cli_workpaper.py::test_cli_workpaper_excel_exports_note_sheets -v
```

Expected: FAIL because command is not registered.

- [ ] **Step 3: Implement CLI command**

Add to `src/dart_footing_reconciler/cli.py`:

```python
from dart_footing_reconciler.audit_workbook import export_audit_workbook
from dart_footing_reconciler.checks_totals import check_table_totals
from dart_footing_reconciler.document import parse_full_report
```

Add command:

```python
@app.command("workpaper-excel")
def workpaper_excel(
    current_html: Annotated[Path, typer.Argument(help="Current-year DART viewer HTML file")],
    output: Annotated[Path, typer.Argument(help="Output audit workpaper .xlsx path")],
    company: Annotated[str | None, typer.Option(help="Company name for workbook header")] = None,
    prior_html: Annotated[Path | None, typer.Option(help="Prior-year DART viewer HTML file")] = None,
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
) -> None:
    report = parse_full_report(current_html, company=company or current_html.stem)
    checks = []
    for note in report.notes:
        for block in note.blocks:
            if block.table is not None:
                checks.extend(check_table_totals(block.table, note_no=note.note_no, tolerance=tolerance))
    workbook_path = export_audit_workbook(report, checks, output)
    typer.echo(f"Wrote {workbook_path}")
```

- [ ] **Step 4: Run CLI test**

```bash
uv run python -m pytest tests/test_cli_workpaper.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/cli.py tests/test_cli_workpaper.py
git commit -m "add audit workpaper excel command"
```

## Task 6: Implement FS-Note Matching

**Files:**
- Create: `src/dart_footing_reconciler/checks_fs_note.py`
- Test: `tests/test_checks_fs_note.py`

- [ ] **Step 1: Write failing BS-note match test**

```python
from dart_footing_reconciler.checks_fs_note import check_fs_note_matches
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation

def test_check_fs_note_matches_balance_sheet_line_to_note_total():
    statement_table = ReportTable(0, [["구분", "당기"], ["유형자산", "1,000"]], "재무상태표", SourceLocation("statement:bs", 0, 0))
    note_table = ReportTable(1, [["구분", "합계"], ["장부금액", "1,000"]], "11. 유형자산", SourceLocation("note:11", 0, 1))
    report = FullReport(
        "sample.html",
        "Sample Co",
        [ReportSection("statement:bs", "재무상태표", "statement", "", [ReportBlock("table", "", statement_table, SourceLocation("statement:bs", 0, 0))])],
        [ReportSection("note:11", "유형자산", "note", "11", [ReportBlock("table", "", note_table, SourceLocation("note:11", 0, 1))])],
    )
    results = check_fs_note_matches(report, tolerance=0)
    assert results[0].check_type == "fs_note_match"
    assert results[0].status == "matched"
```

- [ ] **Step 2: Run RED**

```bash
uv run python -m pytest tests/test_checks_fs_note.py -v
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement conservative keyword-based first pass**

Create `src/dart_footing_reconciler/checks_fs_note.py` with a first-pass mapper:

```python
from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import FullReport

FS_NOTE_KEYWORDS = {
    "유형자산": ("유형자산", "장부금액"),
    "무형자산": ("무형자산", "장부금액"),
    "투자부동산": ("투자부동산", "장부금액"),
    "차입금": ("차입금", "기말"),
    "사채": ("사채", "기말"),
    "리스부채": ("리스", "기말"),
}

def check_fs_note_matches(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    for fs_label, note_keywords in FS_NOTE_KEYWORDS.items():
        fs_amount = _find_amount(report.statements, fs_label)
        note_amount, note_no = _find_note_amount(report, note_keywords)
        if fs_amount is None or note_amount is None:
            continue
        difference = note_amount - fs_amount
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        results.append(CheckResult(
            check_id=f"fs_note:{fs_label}:{note_no}",
            check_type="fs_note_match",
            status=status,
            scope="report",
            note_no=note_no,
            title=f"{fs_label} FS to note match",
            expected=fs_amount,
            actual=note_amount,
            difference=difference,
            tolerance=tolerance,
            reason="financial statement amount agrees to note amount" if status == MATCHED else "financial statement amount does not agree to note amount",
            evidence=[CheckEvidence(fs_label, fs_amount, "statement"), CheckEvidence(fs_label, note_amount, f"note:{note_no}")],
        ))
    return results
```

Implement `_find_amount` and `_find_note_amount` by scanning table rows for labels containing the keywords and returning the rightmost parseable amount.

- [ ] **Step 4: Add PL/SCE/CF fixture tests**

Add tests with labels `매출액`, `감가상각비`, `배당`, and `현금및현금성자산의증가` to ensure statements beyond BS are included. Expected statuses are `matched`.

- [ ] **Step 5: Run tests**

```bash
uv run python -m pytest tests/test_checks_fs_note.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dart_footing_reconciler/checks_fs_note.py tests/test_checks_fs_note.py
git commit -m "add financial statement to note matching checks"
```

## Task 7: Implement Note-Note Matching

**Files:**
- Create: `src/dart_footing_reconciler/checks_note_note.py`
- Test: `tests/test_checks_note_note.py`

- [ ] **Step 1: Write failing note-note test**

```python
from dart_footing_reconciler.checks_note_note import check_note_note_matches
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation

def test_check_note_note_matches_depreciation_between_ppe_and_expense_notes():
    ppe = ReportSection("note:11", "유형자산", "note", "11", [
        ReportBlock("table", "", ReportTable(0, [["구분", "합계"], ["감가상각비", "300"]], "11. 유형자산", SourceLocation("note:11", 0, 0)), SourceLocation("note:11", 0, 0))
    ])
    expense = ReportSection("note:25", "비용의 성격별 분류", "note", "25", [
        ReportBlock("table", "", ReportTable(1, [["구분", "합계"], ["감가상각비", "300"]], "25. 비용", SourceLocation("note:25", 0, 1)), SourceLocation("note:25", 0, 1))
    ])
    report = FullReport("sample.html", "Sample Co", [], [ppe, expense])
    results = check_note_note_matches(report, tolerance=0)
    assert results[0].check_type == "note_note_match"
    assert results[0].status == "matched"
```

- [ ] **Step 2: Run RED**

```bash
uv run python -m pytest tests/test_checks_note_note.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement first-pass relationship rules**

Create `src/dart_footing_reconciler/checks_note_note.py` with relationship definitions:

```python
NOTE_NOTE_RULES = [
    ("depreciation_expense", ("유형자산", "감가상각비"), ("비용", "감가상각비")),
    ("amortization_expense", ("무형자산", "상각비"), ("비용", "상각비")),
    ("lease_liability_current_noncurrent", ("리스부채", "유동"), ("리스부채", "비유동")),
    ("tax_temporary_difference", ("이연법인세", "일시적차이"), ("법인세", "일시적차이")),
]
```

Use the same rightmost parseable amount extraction strategy. Emit `parse_uncertain` when more than one candidate exists for either side.

- [ ] **Step 4: Add ambiguity test**

Add a test where two candidate depreciation rows exist in the same note. Expected status: `parse_uncertain`.

- [ ] **Step 5: Run tests**

```bash
uv run python -m pytest tests/test_checks_note_note.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dart_footing_reconciler/checks_note_note.py tests/test_checks_note_note.py
git commit -m "add note to note matching checks"
```

## Task 8: Implement CFS-Note Matching For Operating, Investing, Financing Activities

**Files:**
- Create: `src/dart_footing_reconciler/checks_cfs_note.py`
- Test: `tests/test_checks_cfs_note.py`

- [ ] **Step 1: Write failing investing activity test**

```python
from dart_footing_reconciler.checks_cfs_note import check_cfs_note_matches
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation

def test_check_cfs_note_matches_ppe_acquisition_to_investing_cash_flow():
    cfs = ReportSection("statement:cfs", "현금흐름표", "statement", "", [
        ReportBlock("table", "", ReportTable(0, [["구분", "당기"], ["유형자산의 취득", "(500)"]], "현금흐름표", SourceLocation("statement:cfs", 0, 0)), SourceLocation("statement:cfs", 0, 0))
    ])
    ppe = ReportSection("note:11", "유형자산", "note", "11", [
        ReportBlock("table", "", ReportTable(1, [["구분", "합계"], ["취득", "500"]], "11. 유형자산", SourceLocation("note:11", 0, 1)), SourceLocation("note:11", 0, 1))
    ])
    report = FullReport("sample.html", "Sample Co", [cfs], [ppe])
    results = check_cfs_note_matches(report, tolerance=0)
    assert results[0].check_type == "cfs_note_match"
    assert results[0].scope == "investing"
    assert results[0].status == "matched"
```

- [ ] **Step 2: Run RED**

```bash
uv run python -m pytest tests/test_checks_cfs_note.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement activity mapping**

Create `src/dart_footing_reconciler/checks_cfs_note.py` with:

```python
CFS_NOTE_RULES = [
    ("operating", "감가상각비", ("유형자산", "감가상각비"), 1),
    ("investing", "유형자산의취득", ("유형자산", "취득"), -1),
    ("investing", "무형자산의취득", ("무형자산", "취득"), -1),
    ("financing", "차입금의차입", ("차입금", "차입"), 1),
    ("financing", "차입금의상환", ("차입금", "상환"), -1),
    ("financing", "리스부채의상환", ("리스부채", "상환"), -1),
]
```

Normalize labels by removing spaces. Compare absolute signs after applying the rule sign. Emit `explainable_gap` only when a separately disclosed non-cash adjustment row exactly explains the gap; otherwise emit `unexplained_gap`.

- [ ] **Step 4: Add operating and financing tests**

Add one operating test for depreciation and one financing test for borrowings repayment. Expected statuses: `matched`.

- [ ] **Step 5: Run tests**

```bash
uv run python -m pytest tests/test_checks_cfs_note.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dart_footing_reconciler/checks_cfs_note.py tests/test_checks_cfs_note.py
git commit -m "add cash flow statement to note matching checks"
```

## Task 9: Implement Prior-Year Amount And Structure Reconciliation

**Files:**
- Create: `src/dart_footing_reconciler/checks_prior_year.py`
- Test: `tests/test_checks_prior_year.py`
- Modify: `src/dart_footing_reconciler/cli.py`

- [ ] **Step 1: Write failing amount reconciliation test**

```python
from dart_footing_reconciler.checks_prior_year import check_prior_year_reconciliation
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation

def test_prior_year_reconciles_current_comparative_to_prior_current_amount():
    current_note = ReportSection("note:11", "유형자산", "note", "11", [
        ReportBlock("table", "", ReportTable(0, [["구분", "당기", "전기"], ["기말", "1,200", "1,000"]], "11. 유형자산", SourceLocation("note:11", 0, 0)), SourceLocation("note:11", 0, 0))
    ])
    prior_note = ReportSection("note:10", "유형자산", "note", "10", [
        ReportBlock("table", "", ReportTable(0, [["구분", "당기"], ["기말", "1,000"]], "10. 유형자산", SourceLocation("note:10", 0, 0)), SourceLocation("note:10", 0, 0))
    ])
    current = FullReport("current.html", "Sample Co", [], [current_note])
    prior = FullReport("prior.html", "Sample Co", [], [prior_note])
    results = check_prior_year_reconciliation(current, prior, tolerance=0)
    assert results[0].check_type == "prior_year_amount_match"
    assert results[0].status == "matched"
```

- [ ] **Step 2: Write failing structure-diff test**

```python
def test_prior_year_detects_note_number_and_row_structure_changes():
    current_note = ReportSection("note:11", "유형자산", "note", "11", [
        ReportBlock("table", "", ReportTable(0, [["구분", "당기", "전기"], ["토지", "600", "500"], ["건물", "600", "500"], ["기계장치", "0", "0"]], "11. 유형자산", SourceLocation("note:11", 0, 0)), SourceLocation("note:11", 0, 0))
    ])
    prior_note = ReportSection("note:10", "유형자산", "note", "10", [
        ReportBlock("table", "", ReportTable(0, [["구분", "당기"], ["토지", "500"], ["건물", "500"]], "10. 유형자산", SourceLocation("note:10", 0, 0)), SourceLocation("note:10", 0, 0))
    ])
    current = FullReport("current.html", "Sample Co", [], [current_note])
    prior = FullReport("prior.html", "Sample Co", [], [prior_note])
    results = check_prior_year_reconciliation(current, prior, tolerance=0)
    structure = [result for result in results if result.check_type == "prior_year_structure_change"]
    assert structure
    assert "note number changed from 10 to 11" in structure[0].reason
    assert any("기계장치" in result.reason for result in structure)
```

- [ ] **Step 3: Run RED**

```bash
uv run python -m pytest tests/test_checks_prior_year.py -v
```

Expected: FAIL.

- [ ] **Step 4: Implement prior-year matching**

Create `src/dart_footing_reconciler/checks_prior_year.py`:

```python
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP, EXPLAINABLE_GAP
from dart_footing_reconciler.document import FullReport

def check_prior_year_reconciliation(current: FullReport, prior: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    for current_note in current.notes:
        prior_note = _match_prior_note(current_note.title, prior)
        if prior_note is None:
            continue
        if current_note.note_no != prior_note.note_no:
            results.append(CheckResult(
                f"prior_structure:note:{current_note.note_no}:number",
                "prior_year_structure_change",
                EXPLAINABLE_GAP,
                "prior_year",
                current_note.note_no,
                current_note.title,
                None,
                None,
                None,
                tolerance,
                f"note number changed from {prior_note.note_no} to {current_note.note_no}",
                [],
            ))
        results.extend(_compare_note_tables(current_note, prior_note, tolerance))
    return results
```

Implement `_match_prior_note` by normalized title equality. Implement `_compare_note_tables` by row-label matching where current `전기` column equals prior `당기` column. Emit `prior_year_structure_change` for labels in current but not prior and labels in prior but not current.

- [ ] **Step 5: Wire `--prior-html` into CLI**

Update `workpaper_excel` so that when `prior_html` is provided:

```python
from dart_footing_reconciler.checks_prior_year import check_prior_year_reconciliation

prior_report = parse_full_report(prior_html, company=company or prior_html.stem) if prior_html else None
if prior_report is not None:
    checks.extend(check_prior_year_reconciliation(report, prior_report, tolerance=tolerance))
```

- [ ] **Step 6: Run tests**

```bash
uv run python -m pytest tests/test_checks_prior_year.py tests/test_cli_workpaper.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/dart_footing_reconciler/checks_prior_year.py src/dart_footing_reconciler/cli.py tests/test_checks_prior_year.py tests/test_cli_workpaper.py
git commit -m "add prior year disclosure reconciliation"
```

## Task 10: Integrate All Checks Into Workpaper Export

**Files:**
- Modify: `src/dart_footing_reconciler/cli.py`
- Test: `tests/test_cli_workpaper.py`

- [ ] **Step 1: Add integration test asserting all check types appear**

```python
def test_cli_workpaper_excel_includes_required_check_types(tmp_path):
    current = tmp_path / "current.html"
    prior = tmp_path / "prior.html"
    current.write_text(
        """
        <p>재무상태표</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>유형자산</td><td>1,000</td></tr></table>
        <p>현금흐름표</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>유형자산의 취득</td><td>(500)</td></tr></table>
        <p>11. 유형자산</p><table><tr><th>구분</th><th>당기</th><th>전기</th><th>합계</th></tr><tr><td>취득</td><td>500</td><td>400</td><td>900</td></tr><tr><td>장부금액</td><td>1,000</td><td>800</td><td>1,800</td></tr></table>
        """,
        encoding="utf-8",
    )
    prior.write_text(
        """
        <p>10. 유형자산</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>장부금액</td><td>800</td></tr></table>
        """,
        encoding="utf-8",
    )
    output = tmp_path / "workpaper.xlsx"
    result = CliRunner().invoke(app, ["workpaper-excel", str(current), str(output), "--company", "Sample Co", "--prior-html", str(prior)])
    assert result.exit_code == 0
    wb = load_workbook(output)
    values = [cell.value for row in wb["Note 11"].iter_rows() for cell in row]
    assert "total_check" in values
    assert "fs_note_match" in values
    assert "cfs_note_match" in values
    assert "prior_year_amount_match" in values
```

- [ ] **Step 2: Run RED or partial failure**

```bash
uv run python -m pytest tests/test_cli_workpaper.py::test_cli_workpaper_excel_includes_required_check_types -v
```

Expected: FAIL until all check modules are called in `workpaper_excel`.

- [ ] **Step 3: Update CLI to call all check modules**

In `workpaper_excel`, build `checks` in this order:

```python
checks = []
checks.extend(_run_total_checks(report, tolerance))
checks.extend(check_fs_note_matches(report, tolerance=tolerance))
checks.extend(check_note_note_matches(report, tolerance=tolerance))
checks.extend(check_cfs_note_matches(report, tolerance=tolerance))
if prior_report is not None:
    checks.extend(check_prior_year_reconciliation(report, prior_report, tolerance=tolerance))
```

Create private helper `_run_total_checks(report, tolerance)` inside `cli.py` or move orchestration into `src/dart_footing_reconciler/workpaper.py` if `cli.py` becomes too large.

- [ ] **Step 4: Run integration tests**

```bash
uv run python -m pytest tests/test_cli_workpaper.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/cli.py tests/test_cli_workpaper.py
git commit -m "integrate audit workpaper validation checks"
```

## Task 11: Debugging And Corpus Validation Milestone

**Files:**
- Create: `docs/validation/2026-05-16-audit-workpaper-corpus.md`
- Test/Command: real DART files under `/tmp/dart_footing_manufacturing_30/raw`

- [ ] **Step 1: Generate 5 workbooks**

Run:

```bash
mkdir -p outputs/workpaper_smoke
uv run dart-footing workpaper-excel /tmp/dart_footing_manufacturing_30/raw/02_265520_20250320001493.html outputs/workpaper_smoke/ap_system.xlsx --company AP시스템
uv run dart-footing workpaper-excel /tmp/dart_footing_manufacturing_30/raw/07_097950_20250317000648.html outputs/workpaper_smoke/cj_cheiljedang.xlsx --company CJ제일제당
uv run dart-footing workpaper-excel /tmp/dart_footing_manufacturing_30/raw/11_000990_20250312001130.html outputs/workpaper_smoke/db_hitek.xlsx --company DB하이텍
uv run dart-footing workpaper-excel /tmp/dart_footing_manufacturing_30/raw/23_017860_20250321001800.html outputs/workpaper_smoke/ds_danseok.xlsx --company DS단석
uv run dart-footing workpaper-excel /tmp/dart_footing_manufacturing_30/raw/28_083450_20250318000728.html outputs/workpaper_smoke/gst.xlsx --company GST
```

Expected: all commands exit 0 and create `.xlsx` files.

- [ ] **Step 2: Programmatically inspect workbook shape**

Run:

```bash
uv run python - <<'PY'
from pathlib import Path
from openpyxl import load_workbook

for path in Path("outputs/workpaper_smoke").glob("*.xlsx"):
    wb = load_workbook(path, data_only=True)
    note_sheets = [name for name in wb.sheetnames if name.startswith("Note ")]
    assert "Validation Summary" in wb.sheetnames
    assert note_sheets, path
    print(path.name, len(note_sheets), "note sheets")
PY
```

Expected: prints each workbook name and note sheet count.

- [ ] **Step 3: Write validation summary**

Create `docs/validation/2026-05-16-audit-workpaper-corpus.md` with:

```markdown
# Audit Workpaper Corpus Smoke

Date: 2026-05-16

## Scope

Generated single-company audit workpaper Excel files for 5 public DART manufacturing filings.

## Results

Create one completed row per company with these columns:

| Column | Required value |
|---|---|
| Company | One of AP시스템, CJ제일제당, DB하이텍, DS단석, GST |
| Workbook generated | `yes` only when the workbook file exists and opens with openpyxl |
| Note sheets | Integer count printed by the Step 2 inspection command |
| Known parser gaps | Concrete observed issue, or `none observed in smoke inspection` |

## Failure Categories

- Structure parsing gaps
- Ambiguous total labels
- Statement-note mapping gaps
- Note-note mapping gaps
- Prior-year mapping gaps
```

Use the Step 2 inspection output for note sheet counts. Open at least one note sheet and one validation summary sheet per workbook before writing the parser gap note.

- [ ] **Step 4: Commit**

```bash
git add docs/validation/2026-05-16-audit-workpaper-corpus.md
git commit -m "document audit workpaper corpus smoke results"
```

## Task 12: README And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README command section**

Add:

```markdown
dart-footing workpaper-excel current_report.html audit_workpaper.xlsx --company "Company Name"
dart-footing workpaper-excel current_report.html audit_workpaper.xlsx --company "Company Name" --prior-html prior_report.html
```

Add the distinction:

- `workpaper-excel`: audit workpaper output; all notes rendered; validation blocks appended below each note.
- `foot-excel`: diagnostic movement-table output; not the final audit sharing format.
- `validate-excel`: corpus development output.

- [ ] **Step 2: Run full test suite**

```bash
uv run python -m pytest
```

Expected: all tests pass.

- [ ] **Step 3: Run one real workbook verification**

```bash
uv run dart-footing workpaper-excel /tmp/dart_footing_manufacturing_30/raw/07_097950_20250317000648.html outputs/cj_cheiljedang_audit_workpaper.xlsx --company CJ제일제당
uv run python - <<'PY'
from openpyxl import load_workbook
wb = load_workbook("outputs/cj_cheiljedang_audit_workpaper.xlsx", data_only=True)
assert "Validation Summary" in wb.sheetnames
assert any(name.startswith("Note ") for name in wb.sheetnames)
print("verified", len(wb.sheetnames), "sheets")
PY
```

Expected: command exits 0 and prints verified sheet count.

- [ ] **Step 4: Commit README and final updates**

```bash
git add README.md
git commit -m "document audit workpaper excel export"
```

- [ ] **Step 5: Push**

```bash
git push
```

Expected: branch pushes to `origin/main`.

## Debugging Protocol

Use this loop whenever a real DART report fails:

1. Reproduce with one command:

```bash
uv run dart-footing workpaper-excel <current.html> outputs/debug.xlsx --company "<company>"
```

2. Minimize to the smallest HTML snippet that reproduces the failure.
3. Add a failing unit test in the closest module:
   - Parser failure: `tests/test_document.py`
   - Total check failure: `tests/test_checks_totals.py`
   - FS-note failure: `tests/test_checks_fs_note.py`
   - Note-note failure: `tests/test_checks_note_note.py`
   - CFS-note failure: `tests/test_checks_cfs_note.py`
   - Prior-year failure: `tests/test_checks_prior_year.py`
   - Workbook layout failure: `tests/test_audit_workbook.py`
4. Run the single failing test and confirm RED.
5. Patch the smallest relevant module.
6. Run the single test and confirm GREEN.
7. Run the related module test file.
8. Run `uv run python -m pytest`.
9. Regenerate the real workbook and inspect sheet count plus the relevant note sheet.
10. Commit the fix with the fixture-style test.

## Acceptance Criteria

The implementation is acceptable when all of these are true:

- Every parsed note appears as a separate Excel sheet.
- Each note sheet renders source text and source tables before any validation result.
- Each note sheet appends a `검증 결과` block at the bottom.
- All tables receive total-check attempts or explicit `not_tested`/`parse_uncertain` results.
- The workbook includes FS-note, note-note, CFS-note, and prior-year check results when relevant evidence exists.
- Prior-year comparison detects both amount mismatches and structure changes including note number changes, account label changes, row additions, and row removals.
- `uv run python -m pytest` passes.
- At least 5 real DART manufacturing reports generate workbooks without crashing.
- Known parser/check limitations are documented in `docs/validation/2026-05-16-audit-workpaper-corpus.md`.

## Self-Review

- Spec coverage: Requirements for all-note export, source-first note rendering, bottom validation blocks, total checks, FS-note matching, note-note matching, CFS-note matching, and prior-year amount/structure reconciliation are covered by Tasks 1-12.
- Placeholder scan: No open placeholder values remain.
- Type consistency: `FullReport`, `ReportSection`, `ReportBlock`, `ReportTable`, `CheckResult`, and `CheckEvidence` are introduced before downstream tasks use them.
- Scope check: This is a large but coherent single subsystem: audit workpaper export. Existing diagnostic commands remain intact.
