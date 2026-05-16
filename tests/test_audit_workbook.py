from openpyxl import load_workbook

from dart_footing_reconciler.audit_workbook import export_audit_workbook
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)


def test_export_audit_workbook_renders_note_then_validation_block(tmp_path):
    table = ReportTable(
        0, [["구분", "합계"], ["기초", "100"]], "11. 유형자산", SourceLocation("note:11", 1, 0)
    )
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
        CheckResult(
            "total:11:0",
            "total_check",
            MATCHED,
            "note",
            "11",
            "row total",
            100,
            100,
            0,
            1,
            "row total agrees",
            [CheckEvidence("기초", 100, "note:11/table:0/row:1/col:1")],
        )
    ]
    output = tmp_path / "workpaper.xlsx"

    export_audit_workbook(report, checks, output)

    wb = load_workbook(output)
    assert "FS Summary" in wb.sheetnames
    assert "Validation Summary" in wb.sheetnames
    ws = wb["Note 11"]
    assert ws["A1"].value == "11. 유형자산"
    assert ws["A3"].value == "유형자산 변동내역입니다."
    assert ws["A7"].value == "검증 결과"
    assert ws["B9"].value == "total_check"


def test_export_audit_workbook_renders_statement_source_tables(tmp_path):
    statement_table = ReportTable(
        0,
        [["구분", "당기"], ["자산총계", "1,000"]],
        "재무상태표",
        SourceLocation("statement:재무상태표", 0, 0),
    )
    statement = ReportSection(
        section_id="statement:재무상태표",
        title="재무상태표",
        kind="statement",
        note_no="",
        blocks=[ReportBlock("table", "", statement_table, SourceLocation("statement:재무상태표", 0, 0))],
    )
    report = FullReport(str(tmp_path / "report.html"), "Sample Co", [statement], [])
    output = tmp_path / "workpaper.xlsx"

    export_audit_workbook(report, [], output)

    ws = load_workbook(output)["FS Summary"]
    values = [cell.value for row in ws.iter_rows() for cell in row]
    assert "재무상태표" in values
    assert "자산총계" in values
    assert "1,000" in values
