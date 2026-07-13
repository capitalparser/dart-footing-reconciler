from dart_footing_reconciler._match_helpers import AmountHit
from dart_footing_reconciler.checks_cfs_note import (
    _select_note_hit_by_keyword,
    check_cfs_note_matches,
)
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation


def _section(section_id, title, kind, note_no, table):
    return ReportSection(section_id, title, kind, note_no, [ReportBlock("table", "", table, table.location)])


def test_check_cfs_note_matches_ppe_acquisition_to_investing_cash_flow():
    cfs = _section("statement:cfs", "현금흐름표", "statement", "", ReportTable(0, [["구분", "당기"], ["유형자산의 취득", "(500)"]], "현금흐름표", SourceLocation("statement:cfs", 0, 0)))
    ppe = _section("note:11", "유형자산", "note", "11", ReportTable(1, [["구분", "합계"], ["취득", "500"]], "11. 유형자산", SourceLocation("note:11", 0, 1)))
    report = FullReport("sample.html", "Sample Co", [cfs], [ppe])
    results = check_cfs_note_matches(report, tolerance=0)
    assert results[0].check_type == "cfs_note_match"
    assert results[0].scope == "investing"
    assert results[0].status == "matched"


def test_check_cfs_note_matches_operating_and_financing():
    cfs = _section(
        "statement:cfs",
        "현금흐름표",
        "statement",
        "",
        ReportTable(0, [["구분", "당기"], ["감가상각비", "300"], ["차입금의 상환", "(700)"]], "현금흐름표", SourceLocation("statement:cfs", 0, 0)),
    )
    notes = [
        _section("note:11", "유형자산", "note", "11", ReportTable(1, [["구분", "합계"], ["감가상각비", "300"]], "11. 유형자산", SourceLocation("note:11", 0, 1))),
        _section("note:20", "차입금", "note", "20", ReportTable(2, [["구분", "합계"], ["상환", "700"]], "20. 차입금", SourceLocation("note:20", 0, 2))),
    ]

    results = check_cfs_note_matches(FullReport("sample.html", "Sample Co", [cfs], notes), tolerance=0)

    assert {result.scope for result in results if result.status == "matched"} == {"operating", "financing"}


def test_cfs_note_ranks_exact_keyword_over_partial():
    cf = _section(
        "statement:cf",
        "현금흐름표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유형자산의취득", "500"]],
            "현금흐름표",
            SourceLocation("statement:cf", 0, 0),
        ),
    )
    note = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        ReportTable(
            1,
            [["구분", "당기"], ["무형자산취득", "490"], ["유형자산의취득", "500"]],
            "11. 유형자산",
            SourceLocation("note:11", 0, 1),
        ),
    )

    results = check_cfs_note_matches(FullReport("s.html", "Co", [cf], [note]), tolerance=0)

    inv = [r for r in results if "유형자산의취득" in r.check_id]
    assert inv and inv[0].status == "matched"
    assert any("유형자산의취득" in e.label for e in inv[0].evidence)


def test_cfs_note_borrowing_draw_abstains_on_name_text_field():
    cf = _section(
        "statement:cf",
        "현금흐름표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["차입금의 차입", "100"]],
            "현금흐름표",
            SourceLocation("statement:cf", 0, 0),
        ),
    )
    note = _section(
        "note:20",
        "차입금",
        "note",
        "20",
        ReportTable(
            1,
            [["구분", "당기"], ["차입금명칭", "20,251,231"]],
            "20. 차입금",
            SourceLocation("note:20", 0, 1),
        ),
    )

    results = check_cfs_note_matches(FullReport("s.html", "Co", [cf], [note]), tolerance=0)

    borrow = [r for r in results if "차입금의차입" in r.check_id]
    assert not borrow, [(r.actual, r.status, [e.label for e in r.evidence]) for r in borrow]


def test_cfs_note_borrowing_draw_never_selects_name_field_when_movement_exists():
    cf = _section(
        "statement:cf",
        "현금흐름표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["차입금의 차입", "100"]],
            "현금흐름표",
            SourceLocation("statement:cf", 0, 0),
        ),
    )
    note = _section(
        "note:20",
        "차입금",
        "note",
        "20",
        ReportTable(
            1,
            [["구분", "당기"], ["차입금명칭", "20,251,231"], ["차입", "100"]],
            "20. 차입금",
            SourceLocation("note:20", 0, 1),
        ),
    )

    results = check_cfs_note_matches(FullReport("s.html", "Co", [cf], [note]), tolerance=0)

    borrow = [r for r in results if "차입금의차입" in r.check_id]
    assert borrow and borrow[0].status == "matched"
    assert any(e.label == "차입" for e in borrow[0].evidence)
    assert not any(e.label == "차입금명칭" for e in borrow[0].evidence)


def test_cfs_note_repayment_abstains_on_absurd_parse_candidate():
    cf = _section(
        "statement:cf",
        "현금흐름표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["차입금의 상환", "(532,700)"]],
            "현금흐름표",
            SourceLocation("statement:cf", 0, 0),
        ),
    )
    note = _section(
        "note:20",
        "차입금",
        "note",
        "20",
        ReportTable(
            1,
            [["구분", "당기"], ["발행자의 중도상환청구권", "202,507,312,026,013,030"]],
            "20. 차입금",
            SourceLocation("note:20", 0, 1),
        ),
    )

    results = check_cfs_note_matches(FullReport("s.html", "Co", [cf], [note]), tolerance=0)

    repay = [r for r in results if "차입금의상환" in r.check_id]
    assert not repay, [(r.actual, r.status, [e.label for e in r.evidence]) for r in repay]


def test_cfs_note_selector_abstains_instead_of_first_candidate_fallback():
    hits = [
        AmountHit(
            amount=100,
            note_no="20",
            section_title="차입금",
            label="기타 변동",
            source="note:20/table:1/row:1/col:1",
        )
    ]

    selected = _select_note_hit_by_keyword(hits, "차입금의차입", "차입")

    assert selected is None
