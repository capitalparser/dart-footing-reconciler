from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.report_order import build_report_order_index


def _section(section_id: str, title: str, kind: str, note_no: str, table: ReportTable) -> ReportSection:
    return ReportSection(section_id, title, kind, note_no, [ReportBlock("table", "", table, table.location)])


def _table(section_id: str, index: int, heading: str) -> ReportTable:
    return ReportTable(
        index,
        [["구분", "당기"], ["합계", "100"]],
        heading,
        SourceLocation(section_id, 0, index),
    )


def test_report_order_uses_statement_form_order_then_parsed_note_order():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section("statement:cf", "현금흐름표", "statement", "", _table("statement:cf", 0, "현금흐름표")),
            _section("statement:bs", "재무상태표", "statement", "", _table("statement:bs", 1, "재무상태표")),
            _section("statement:pl", "손익계산서", "statement", "", _table("statement:pl", 2, "손익계산서")),
        ],
        [
            _section("note:12", "유형자산", "note", "12", _table("note:12", 3, "12. 유형자산")),
            _section("note:3", "매출", "note", "3", _table("note:3", 4, "3. 매출")),
        ],
    )

    index = build_report_order_index(report)

    assert [entry.source for entry in index.entries] == [
        "statement:bs/table:1",
        "statement:pl/table:2",
        "statement:cf/table:0",
        "note:12/table:3",
        "note:3/table:4",
    ]
    assert index.order_for_source("note:12/table:3") < index.order_for_source("note:3/table:4")


def test_report_order_resolves_evidence_cell_source_to_table_order():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [_section("note:7", "차입금", "note", "7", _table("note:7", 0, "7. 차입금"))],
    )
    index = build_report_order_index(report)

    assert index.order_for_source("note:7/table:0/row:1/col:1") == 10_000
    assert index.table_source_for("note:7/table:0/row:1/col:1") == "note:7/table:0"
    assert index.order_for_source("unplaced") is None
