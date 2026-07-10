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


def test_cfs_note_borrowing_draw_abstains_on_borrowing_balance_row():
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
            [["구분", "공시금액"], ["차입금(사채 포함)", "500"], ["단기차입금", "100"]],
            "20. 차입금 당기말 잔액",
            SourceLocation("note:20", 0, 1),
        ),
    )

    results = check_cfs_note_matches(FullReport("s.html", "Co", [cf], [note]), tolerance=0)

    borrow = [r for r in results if "차입금의차입" in r.check_id]
    assert not borrow, [(r.actual, r.status, [e.label for e in r.evidence]) for r in borrow]


def test_cfs_note_ppe_acquisition_abstains_on_generic_additions_row():
    cf = _section(
        "statement:cf",
        "현금흐름표",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["유형자산의 취득", "(100)"]],
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
            [["구분", "합계"], ["사업결합을 통한 취득 이외의 증가, 유형자산", "120"]],
            "11. 유형자산 변동내역",
            SourceLocation("note:11", 0, 1),
        ),
    )

    results = check_cfs_note_matches(FullReport("s.html", "Co", [cf], [note]), tolerance=0)

    acquisition = [r for r in results if "유형자산의취득" in r.check_id]
    assert not acquisition, [(r.actual, r.status, [e.label for e in r.evidence]) for r in acquisition]


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

def test_cfs_note_gap_not_explained_by_unrelated_note_keyword():
    # 무관한 주석의 키워드 우연 일치(금액만 같은 '리스료' 행)는 더 이상
    # explainable_gap 근거가 될 수 없다 — 관련 주석 연결성 필수.
    cfs = _section(
        "statement:cfs",
        "현금흐름표",
        "statement",
        "",
        ReportTable(0, [["구분", "당기"], ["유형자산의 취득", "(500)"]], "현금흐름표", SourceLocation("statement:cfs", 0, 0)),
    )
    ppe = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        ReportTable(1, [["구분", "합계"], ["취득", "470"]], "11. 유형자산", SourceLocation("note:11", 0, 1)),
    )
    unrelated = _section(
        "note:25",
        "판매비와관리비",
        "note",
        "25",
        ReportTable(2, [["구분", "당기"], ["리스료", "30"]], "25. 판매비와관리비", SourceLocation("note:25", 0, 2)),
    )
    report = FullReport("sample.html", "Sample Co", [cfs], [ppe, unrelated])

    results = check_cfs_note_matches(report, tolerance=0)

    assert results[0].status == "unexplained_gap"


def test_cfs_note_gap_explained_by_same_note_non_cash_disclosure():
    # 동일 주석에 공시된 비현금 조정(미지급금 대체)이 잔차와 정확히 일치하면
    # explainable_gap + 근거(evidence)가 첨부된다.
    cfs = _section(
        "statement:cfs",
        "현금흐름표",
        "statement",
        "",
        ReportTable(0, [["구분", "당기"], ["유형자산의 취득", "(500)"]], "현금흐름표", SourceLocation("statement:cfs", 0, 0)),
    )
    ppe = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        ReportTable(
            1,
            [["구분", "합계"], ["취득", "470"], ["미지급금 대체", "30"]],
            "11. 유형자산",
            SourceLocation("note:11", 0, 1),
        ),
    )
    report = FullReport("sample.html", "Sample Co", [cfs], [ppe])

    results = check_cfs_note_matches(report, tolerance=0)

    assert results[0].status == "explainable_gap"
    assert "미지급금 대체" in results[0].reason
    residual_evidence = [e for e in results[0].evidence if e.role == "residual_explanation"]
    assert len(residual_evidence) == 1
    assert abs(residual_evidence[0].amount) == 30


def test_cfs_note_gap_explained_by_cash_flow_disclosure_note():
    # 비현금거래는 별도의 현금흐름표 관련 주석에 공시되는 경우가 많다 —
    # 해당 주석의 정확 일치 항목은 근거로 인정된다.
    cfs = _section(
        "statement:cfs",
        "현금흐름표",
        "statement",
        "",
        ReportTable(0, [["구분", "당기"], ["유형자산의 취득", "(500)"]], "현금흐름표", SourceLocation("statement:cfs", 0, 0)),
    )
    ppe = _section(
        "note:11",
        "유형자산",
        "note",
        "11",
        ReportTable(1, [["구분", "합계"], ["취득", "470"]], "11. 유형자산", SourceLocation("note:11", 0, 1)),
    )
    noncash = _section(
        "note:30",
        "현금흐름표 관련 주석",
        "note",
        "30",
        ReportTable(2, [["구분", "당기"], ["유형자산 취득 관련 미지급금 증가", "30"]], "30. 현금흐름표", SourceLocation("note:30", 0, 2)),
    )
    report = FullReport("sample.html", "Sample Co", [cfs], [ppe, noncash])

    results = check_cfs_note_matches(report, tolerance=0)

    assert results[0].status == "explainable_gap"
    residual_evidence = [e for e in results[0].evidence if e.role == "residual_explanation"]
    assert len(residual_evidence) == 1
