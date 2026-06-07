from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.report_frame import (
    CANONICAL_STATEMENT_ORDER,
    build_report_frame,
)


def _section(section_id, title, kind, note_no, table):
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def _table(section_id: str, index: int, heading: str) -> ReportTable:
    return ReportTable(
        index,
        [["구분", "당기"], ["유형자산", "100"]],
        heading,
        SourceLocation(section_id, 0, index),
    )


def test_report_frame_orders_statement_sections_by_report_form():
    statements = [
        _section("statement:cfs", "현금흐름표", "statement", "", _table("statement:cfs", 0, "현금흐름표")),
        _section("statement:bs", "재무상태표", "statement", "", _table("statement:bs", 0, "재무상태표")),
        _section("statement:sce", "자본변동표", "statement", "", _table("statement:sce", 0, "자본변동표")),
        _section("statement:pl", "손익계산서", "statement", "", _table("statement:pl", 0, "손익계산서")),
    ]
    frame = build_report_frame(FullReport("sample.html", "Sample Co", statements, []), [])

    assert [section.kind for section in frame.statement_sections] == list(CANONICAL_STATEMENT_ORDER)
    assert [section.title for section in frame.statement_sections] == ["재무상태표", "손익계산서", "자본변동표", "현금흐름표"]


def test_report_frame_maps_checks_to_statement_and_note_tables_from_evidence_sources():
    bs_table = _table("statement:bs", 0, "재무상태표")
    note_table = _table("note:11", 0, "유형자산")
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:bs", "재무상태표", "statement", "", bs_table)],
        [_section("note:11", "유형자산", "note", "11", note_table)],
    )
    check = CheckResult(
        "bs-note",
        "primary_balance_reconciliation",
        "matched",
        "report",
        "11",
        "property_plant_equipment.balance",
        100,
        100,
        0,
        0,
        "financial statement line agrees to note ending balance",
        [
            CheckEvidence("재무상태표 유형자산", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석 11 유형자산", 100, "note:11/table:0/row:1/col:1"),
        ],
    )

    frame = build_report_frame(report, [check])

    statement_table = frame.statement_sections[0].tables[0]
    note_frame = frame.notes[0].tables[0]
    assert statement_table.check_groups["재무제표-주석 대사"] == (check,)
    assert note_frame.check_groups["재무제표-주석 대사"] == (check,)


def test_report_frame_marks_prior_reconciliation_not_performed_without_prior_checks():
    frame = build_report_frame(FullReport("sample.html", "Sample Co", [], []), [])

    assert frame.prior_reconciliation.status == "not_performed"
    assert frame.prior_reconciliation.message == "전기대사 미수행: prior-html 미제공"


def test_report_frame_keeps_text_only_notes_for_note_workspace():
    note = ReportSection(
        "note:1",
        "일반사항",
        "note",
        "1",
        [ReportBlock("text", "회사의 일반사항입니다.", None, SourceLocation("note:1", 0))],
    )

    frame = build_report_frame(FullReport("sample.html", "Sample Co", [], [note]), [])

    assert len(frame.notes) == 1
    assert frame.notes[0].note_no == "1"
    assert frame.notes[0].tables == ()
