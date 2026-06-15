from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)
from dart_footing_reconciler.semantic_layer import build_semantic_dataset


def _section(section_id: str, title: str, kind: str, note_no: str, table: ReportTable) -> ReportSection:
    return ReportSection(section_id, title, kind, note_no, [ReportBlock("table", "", table, table.location)])


def _table(section_id: str, index: int, rows: list[list[str]], heading: str) -> ReportTable:
    return ReportTable(index, rows, heading, SourceLocation(section_id, 0, index))


def test_semantic_dataset_attaches_signatures_and_amount_facts_to_company_specific_tables():
    rows = [
        ["구분", "금액"],
        ["기초장부금액", "1,000"],
        ["취득", "200"],
        ["기말장부금액", "1,200"],
    ]
    report_a = FullReport(
        "a.html",
        "A사",
        [],
        [_section("note:11", "유형자산", "note", "11", _table("note:11", 0, rows, "11. 유형자산"))],
    )
    report_b = FullReport(
        "b.html",
        "B사",
        [],
        [_section("note:44", "유형자산", "note", "44", _table("note:44", 3, rows, "44. 유형자산"))],
    )

    dataset_a = build_semantic_dataset(report_a)
    dataset_b = build_semantic_dataset(report_b)

    assert dataset_a.company == "A사"
    assert dataset_b.company == "B사"
    assert dataset_a.tables[0].source == "note:11/table:0"
    assert dataset_b.tables[0].source == "note:44/table:3"
    assert {match.signature for match in dataset_a.tables[0].signatures} == {
        match.signature for match in dataset_b.tables[0].signatures
    }
    assert "rollforward_axis" in {match.signature for match in dataset_a.tables[0].signatures}
    assert [fact.label for fact in dataset_a.amount_facts] == ["기초장부금액", "취득", "기말장부금액"]
    assert dataset_a.amount_facts[0].cell_source == "note:11/table:0/row:1/col:1"
    assert dataset_a.amount_facts[0].amount == 1000
    assert dataset_a.amount_facts[-1].role == "ending"


def test_semantic_dataset_exposes_report_order_and_fact_lookup():
    report = FullReport(
        "sample.html",
        "Sample",
        [],
        [
            _section("note:20", "후순위 주석", "note", "20", _table("note:20", 0, [["구분", "당기"], ["합계", "1"]], "20")),
            _section("note:3", "선행 후순위 번호", "note", "3", _table("note:3", 1, [["구분", "당기"], ["합계", "1"]], "3")),
        ],
    )

    dataset = build_semantic_dataset(report)

    assert [table.source for table in dataset.tables] == ["note:20/table:0", "note:3/table:1"]
    assert dataset.table_for_source("note:3/table:1/row:1/col:1").note_no == "3"
    assert dataset.amount_facts_for_table("note:3/table:1")[0].cell_source == "note:3/table:1/row:1/col:1"
    assert dataset.table_for_source("missing") is None
