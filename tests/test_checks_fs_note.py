from dart_footing_reconciler.checks_fs_note import check_fs_note_matches
from dart_footing_reconciler.document import (
    FullReport,
    ReportBlock,
    ReportSection,
    ReportTable,
    SourceLocation,
)


def _section(section_id, title, kind, note_no, table):
    return ReportSection(section_id, title, kind, note_no, [ReportBlock("table", "", table, table.location)])


def test_check_fs_note_matches_balance_sheet_line_to_note_total():
    statement_table = ReportTable(
        0, [["구분", "당기"], ["유형자산(순액)", "1,000"]], "재무상태표", SourceLocation("statement:bs", 0, 0)
    )
    note_table = ReportTable(
        1, [["구분", "합계"], ["기말 장부금액", "1,000"]], "11. 유형자산 및 사용권자산", SourceLocation("note:11", 0, 1)
    )
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:bs", "재무상태표", "statement", "", statement_table)],
        [_section("note:11", "유형자산 및 사용권자산", "note", "11", note_table)],
    )
    results = check_fs_note_matches(report, tolerance=0)
    assert results[0].check_type == "fs_note_match"
    assert results[0].status == "matched"
    assert results[0].check_id == "fs_note:property_plant_equipment:11"


def test_check_fs_note_matches_pl_sce_and_cf_lines():
    statements = [
        _section("statement:pl", "손익계산서", "statement", "", ReportTable(0, [["구분", "당기"], ["매출액", "500"], ["감가상각비", "30"]], "손익계산서", SourceLocation("statement:pl", 0, 0))),
        _section("statement:sce", "자본변동표", "statement", "", ReportTable(1, [["구분", "당기"], ["배당", "20"]], "자본변동표", SourceLocation("statement:sce", 0, 1))),
        _section("statement:cf", "현금흐름표", "statement", "", ReportTable(2, [["구분", "당기"], ["현금및현금성자산의증가", "10"]], "현금흐름표", SourceLocation("statement:cf", 0, 2))),
    ]
    notes = [
        _section("note:20", "고객과의 계약에서 생기는 수익", "note", "20", ReportTable(3, [["구분", "금액"], ["매출액", "500"]], "20. 수익", SourceLocation("note:20", 0, 3))),
        _section("note:25", "비용의 성격별 분류", "note", "25", ReportTable(4, [["구분", "금액"], ["감가상각비", "30"]], "25. 비용", SourceLocation("note:25", 0, 4))),
        _section("note:30", "배당", "note", "30", ReportTable(5, [["구분", "금액"], ["배당", "20"]], "30. 배당", SourceLocation("note:30", 0, 5))),
        _section("note:31", "현금및현금성자산", "note", "31", ReportTable(6, [["구분", "금액"], ["현금및현금성자산의증가", "10"]], "31. 현금", SourceLocation("note:31", 0, 6))),
    ]

    results = check_fs_note_matches(FullReport("sample.html", "Sample Co", statements, notes), tolerance=0)

    assert {"매출액", "감가상각비", "배당", "현금및현금성자산의증가"} <= {
        result.title.split()[0] for result in results if result.status == "matched"
    }


def test_fs_note_selects_admitted_candidate_by_label_priority():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유형자산(순액)", "1,000"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        ReportTable(
            1,
            [["구분", "당기"], ["장부금액", "980"], ["기말 장부금액", "1,000"]],
            "11. 유형자산",
            SourceLocation("note:11", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=0)

    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].actual == 1000 and ppe[0].status == "matched", [
        (r.actual, r.status) for r in ppe
    ]


def test_fs_note_keeps_honest_gap_when_admitted_row_differs():
    bs = _section(
        "statement:bs",
        "재무상태표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유형자산(순액)", "1,000"]],
            "재무상태표",
            SourceLocation("statement:bs", 0, 0),
        ),
    )
    note = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        ReportTable(
            1,
            [["구분", "당기"], ["장부금액", "1,000"], ["기말 장부금액", "900"]],
            "11. 유형자산",
            SourceLocation("note:11", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [bs], [note]), tolerance=0)

    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].actual == 900 and ppe[0].status == "unexplained_gap", [
        (r.actual, r.status) for r in ppe
    ]


def test_fs_note_uses_current_period_column():
    bs_tbl = ReportTable(
        0,
        [["구분", "당기", "전기"], ["유형자산(순액)", "1,000", "800"]],
        "재무상태표",
        SourceLocation("statement:bs", 0, 0),
    )
    note_tbl = ReportTable(
        1,
        [["구분", "당기", "전기"], ["기말 장부금액", "1,000", "800"]],
        "11. 유형자산",
        SourceLocation("note:11", 0, 1),
    )
    report = FullReport(
        "s.html",
        "Co",
        [_section("statement:bs", "재무상태표", "statement", "", bs_tbl)],
        [_section("note:11", "유형자산", "note", "11", note_tbl)],
    )

    results = check_fs_note_matches(report, tolerance=0)

    ppe = [r for r in results if r.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].expected == 1000 and ppe[0].actual == 1000
