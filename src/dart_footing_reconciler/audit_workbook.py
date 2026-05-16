"""Audit workpaper-style Excel workbook export."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.document import FullReport, ReportSection

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
CHECK_FILL = PatternFill("solid", fgColor="FFF2CC")
SOURCE_HEADER_FILL = PatternFill("solid", fgColor="D9EAF7")
MATCH_FILL = PatternFill("solid", fgColor="D9EAD3")
GAP_FILL = PatternFill("solid", fgColor="F4CCCC")
WHITE_BOLD = Font(color="FFFFFF", bold=True)
BOLD = Font(bold=True)
THIN_SIDE = Side(style="thin", color="B7B7B7")
TABLE_BORDER = Border(left=THIN_SIDE, right=THIN_SIDE, top=THIN_SIDE, bottom=THIN_SIDE)
AMOUNT_FORMAT = '#,##0;[Red](#,##0);-'

VALIDATION_HEADERS = [
    "검증구분",
    "검증내용",
    "산식 / 대사흔적",
    "기준금액 / 구성항목 합계",
    "대사금액 / 표시금액",
    "차이",
    "검증결과",
    "판단근거",
    "출처",
]


def export_audit_workbook(
    report: FullReport, checks: list[CheckResult], output_path: str | Path
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    fs_ws = wb.active
    fs_ws.title = "FS Summary"
    _write_fs_summary(fs_ws, report)
    summary_ws = wb.create_sheet("Validation Summary")
    _write_summary(summary_ws, report, checks)
    for note in report.notes:
        note_ws = wb.create_sheet(_sheet_name(note))
        _write_note_sheet(note_ws, note, [check for check in checks if check.note_no == note.note_no])
    for ws in wb.worksheets:
        _format_sheet(ws)
    wb.save(output)
    return output


def _write_fs_summary(ws, report: FullReport) -> None:
    ws["A1"] = "Company"
    ws["B1"] = report.company
    ws["A2"] = "Statements"
    ws["B2"] = len(report.statements)
    row = 4
    for statement in report.statements:
        ws.cell(row, 1).value = statement.title
        ws.cell(row, 1).fill = HEADER_FILL
        ws.cell(row, 1).font = Font(color="FFFFFF", bold=True)
        row += 1
        for block in statement.blocks:
            if block.kind == "text":
                ws.cell(row, 1).value = block.text
                row += 2
            elif block.kind == "table" and block.table is not None:
                row = _write_source_table(ws, row, block.table.rows) + 1
        row += 1


def _write_summary(ws, report: FullReport, checks: list[CheckResult]) -> None:
    ws["A1"] = "Company"
    ws["B1"] = report.company
    ws["A2"] = "Checks"
    ws["B2"] = len(checks)
    row = 4
    ws.cell(row, 1).value = "검증결과"
    ws.cell(row, 2).value = "건수"
    _style_header_row(ws, row, 1, 2)
    for status, count in Counter(check.status for check in checks).items():
        row += 1
        ws.cell(row, 1).value = _status_label(status)
        ws.cell(row, 2).value = count
        _style_body_row(ws, row, 1, 2)


def _write_note_sheet(ws, note: ReportSection, checks: list[CheckResult]) -> None:
    title = f"{note.note_no}. {note.title}".strip()
    ws["A1"] = title
    ws["A1"].fill = HEADER_FILL
    ws["A1"].font = Font(color="FFFFFF", bold=True)
    row = 3
    for block in note.blocks:
        if block.kind == "text":
            ws.cell(row, 1).value = block.text
            row += 2
        elif block.kind == "table" and block.table is not None:
            row = _write_source_table(ws, row, block.table.rows)
    ws.cell(row, 1).value = "검증 결과"
    ws.cell(row, 1).fill = CHECK_FILL
    ws.cell(row, 1).font = BOLD
    row += 1
    for col_idx, header in enumerate(VALIDATION_HEADERS, start=1):
        ws.cell(row, col_idx).value = header
    _style_header_row(ws, row, 1, len(VALIDATION_HEADERS))
    row += 1
    for check in checks:
        _write_check_row(ws, row, check)
        row += 1


def _sheet_name(note: ReportSection) -> str:
    return f"Note {note.note_no}"[:31]


def _write_source_table(ws, start_row: int, rows: list[list[str]]) -> int:
    row_idx = start_row
    for table_row_idx, table_row in enumerate(rows):
        for col_idx, value in enumerate(table_row, start=1):
            cell = ws.cell(row_idx, col_idx)
            cell.value = value
            cell.border = TABLE_BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if table_row_idx == 0:
                cell.fill = SOURCE_HEADER_FILL
                cell.font = BOLD
        row_idx += 1
    return row_idx


def _write_check_row(ws, row: int, check: CheckResult) -> None:
    values = [
        _check_type_label(check.check_type),
        check.title,
        _trace_text(check),
        check.expected,
        check.actual,
        f"=D{row}-E{row}" if check.expected is not None and check.actual is not None else None,
        _status_label(check.status),
        check.reason,
        _evidence_text(check),
    ]
    for col_idx, value in enumerate(values, start=1):
        cell = ws.cell(row, col_idx)
        cell.value = value
        cell.border = TABLE_BORDER
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        if col_idx in {4, 5, 6}:
            cell.number_format = AMOUNT_FORMAT
    if check.status == "matched":
        ws.cell(row, 7).fill = MATCH_FILL
    elif check.status in {"unexplained_gap", "parse_uncertain"}:
        ws.cell(row, 7).fill = GAP_FILL
    else:
        ws.cell(row, 7).fill = CHECK_FILL


def _trace_text(check: CheckResult) -> str:
    if check.check_type == "total_check":
        return "구성항목 합계 - 표시 금액 = 차이"
    if len(check.evidence) >= 2:
        return f"{check.evidence[0].label} ↔ {check.evidence[1].label}"
    if check.evidence:
        return check.evidence[0].label
    if check.check_type == "prior_year_structure_change":
        return "당기 공시 구조와 전기 공시 구조 비교"
    return "검증 대상 증거 부족"


def _evidence_text(check: CheckResult) -> str:
    return " / ".join(evidence.source for evidence in check.evidence)


def _check_type_label(check_type: str) -> str:
    labels = {
        "total_check": "합계 검증 결과",
        "fs_note_match": "재무제표-주석 대사",
        "note_note_match": "주석 간 대사",
        "cfs_note_match": "현금흐름표-주석 직접 대사",
        "prior_year_amount_match": "전기 공시 금액 대사",
        "prior_year_structure_change": "전기 공시 구조 변경",
    }
    return labels.get(check_type, check_type)


def _status_label(status: str) -> str:
    labels = {
        "matched": "일치",
        "explainable_gap": "차이 설명 가능",
        "unexplained_gap": "미해소 차이",
        "parse_uncertain": "파싱 불확실",
        "not_tested": "검증 미수행",
    }
    return labels.get(status, status)


def _style_header_row(ws, row: int, start_col: int, end_col: int) -> None:
    for col in range(start_col, end_col + 1):
        cell = ws.cell(row, col)
        cell.fill = HEADER_FILL
        cell.font = WHITE_BOLD
        cell.border = TABLE_BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _style_body_row(ws, row: int, start_col: int, end_col: int) -> None:
    for col in range(start_col, end_col + 1):
        cell = ws.cell(row, col)
        cell.border = TABLE_BORDER
        cell.alignment = Alignment(vertical="top", wrap_text=True)


def _format_sheet(ws) -> None:
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"
    widths = {
        "A": 22,
        "B": 34,
        "C": 42,
        "D": 18,
        "E": 18,
        "F": 16,
        "G": 16,
        "H": 42,
        "I": 50,
    }
    for col_idx in range(1, max(ws.max_column, len(VALIDATION_HEADERS)) + 1):
        letter = get_column_letter(col_idx)
        if letter in widths:
            ws.column_dimensions[letter].width = widths[letter]
        else:
            ws.column_dimensions[letter].width = 16
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
