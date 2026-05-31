from dart_footing_reconciler.checks_note_bridges import check_asset_note_bridges
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)


def _section(section_id, title, kind, note_no, rows):
    table = ReportTable(0, rows, title, SourceLocation(section_id, 0, 0))
    return ReportSection(
        section_id,
        title,
        kind,
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def test_check_asset_note_bridges_surfaces_asset_cashflow_formula_as_note_bridge():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section(
                "statement:cf",
                "현금흐름표",
                "statement",
                "",
                [["구분", "당기"], ["무형자산의 취득", "(80)"]],
            )
        ],
        [
            _section(
                "note:14",
                "무형자산",
                "note",
                "14",
                [["구분", "합계"], ["기초", "100"], ["취득", "100"], ["미지급금 증가", "20"], ["기말", "200"]],
            )
        ],
    )

    results = check_asset_note_bridges(report, tolerance=0)

    assert [(result.check_type, result.status, result.title) for result in results] == [
        ("asset_note_bridge_check", "matched", "무형자산 취득 주석 연결 대사")
    ]
    assert results[0].expected == 80
    assert results[0].actual == 80
    assert any(evidence.label == "cfs 무형자산의 취득" for evidence in results[0].evidence)
    assert any(evidence.label.startswith("note 14") for evidence in results[0].evidence)
