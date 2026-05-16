"""Audit workpaper-style Excel workbook export."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.document import FullReport, ReportSection

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
CHECK_FILL = PatternFill("solid", fgColor="FFF2CC")


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
                for table_row in block.table.rows:
                    for col_idx, value in enumerate(table_row, start=1):
                        ws.cell(row, col_idx).value = value
                    row += 1
                row += 1
        row += 1


def _write_summary(ws, report: FullReport, checks: list[CheckResult]) -> None:
    ws["A1"] = "Company"
    ws["B1"] = report.company
    ws["A2"] = "Checks"
    ws["B2"] = len(checks)
    row = 4
    ws.cell(row, 1).value = "status"
    ws.cell(row, 2).value = "count"
    for status, count in Counter(check.status for check in checks).items():
        row += 1
        ws.cell(row, 1).value = status
        ws.cell(row, 2).value = count


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
            for table_row in block.table.rows:
                for col_idx, value in enumerate(table_row, start=1):
                    ws.cell(row, col_idx).value = value
                row += 1
    ws.cell(row, 1).value = "검증 결과"
    ws.cell(row, 1).fill = CHECK_FILL
    row += 1
    headers = [
        "check_id",
        "check_type",
        "status",
        "expected",
        "actual",
        "difference",
        "reason",
    ]
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(row, col_idx).value = header
    row += 1
    for check in checks:
        values = [
            check.check_id,
            check.check_type,
            check.status,
            check.expected,
            check.actual,
            check.difference,
            check.reason,
        ]
        for col_idx, value in enumerate(values, start=1):
            ws.cell(row, col_idx).value = value
        row += 1


def _sheet_name(note: ReportSection) -> str:
    return f"Note {note.note_no}"[:31]
