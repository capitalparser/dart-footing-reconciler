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


def test_fs_note_allows_large_statement_note_rounding_under_one_thousand():
    statement = _section(
        "statement:pl",
        "손익계산서",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["매출액", "16,592,248,884,388"]],
            "손익계산서",
            SourceLocation("statement:pl", 0, 0),
        ),
    )
    note = _section(
        "note:6",
        "영업부문",
        "note",
        "6",
        ReportTable(
            1,
            [["구분", "당기"], ["매출액", "16,592,248,884"]],
            "6. 영업부문 매출액 (단위 : 천원)",
            SourceLocation("note:6", 0, 1),
            unit_multiplier=1000,
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [statement], [note]), tolerance=1)

    revenue = [result for result in results if result.check_id.startswith("fs_note:revenue")]
    assert revenue and revenue[0].status == "matched"
    assert revenue[0].difference == -388


def test_fs_note_keeps_eps_difference_in_won_as_gap():
    statement = _section(
        "statement:pl",
        "포괄손익계산서",
        "statement",
        "",
        ReportTable(
            0,
            [["구분", "당기"], ["보통주 기본및희석주당이익 (단위 : 원)", "8,961"]],
            "포괄손익계산서",
            SourceLocation("statement:pl", 0, 0),
        ),
    )
    note = _section(
        "note:30",
        "주당이익",
        "note",
        "30",
        ReportTable(
            1,
            [["구분", "당기"], ["계속영업기본주당이익(손실) - 보통주", "8,138"]],
            "30. 주당이익 (단위 : 원)",
            SourceLocation("note:30", 0, 1),
        ),
    )

    results = check_fs_note_matches(FullReport("s.html", "Co", [statement], [note]), tolerance=1)

    eps = [result for result in results if result.check_id.startswith("fs_note:earnings_per_share")]
    assert eps and eps[0].status == "unexplained_gap"
    assert eps[0].difference == -823


def test_fs_note_ignores_generic_balance_row_from_unrelated_note_topic():
    statement = _section(
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
    risk_note = _section(
        "note:5",
        "금융위험관리",
        "note",
        "5",
        ReportTable(
            1,
            [["구분", "합계"], ["기말 장부금액", "1,000"]],
            "5. 금융위험관리 장부금액",
            SourceLocation("note:5", 0, 1),
        ),
    )
    ppe_note = _section(
        "note:13",
        "유형자산",
        "note",
        "13",
        ReportTable(
            2,
            [["구분", "합계"], ["장부금액", "900"]],
            "13. 유형자산",
            SourceLocation("note:13", 0, 2),
        ),
    )

    results = check_fs_note_matches(
        FullReport("s.html", "Co", [statement], [risk_note, ppe_note]), tolerance=0
    )

    ppe = [result for result in results if result.check_id.startswith("fs_note:property_plant_equipment")]
    assert ppe and ppe[0].note_no == "13"
    assert ppe[0].actual == 900


def test_select_note_hit_prefers_topic_matching_note_over_label_priority():
    """실데이터 FP: taxonomy가 금융위험관리 주석의 '장부금액 합계'를 유형자산으로
    과분류하면, 행 라벨 우선순위('합계')만 보는 선택기는 무관한 주석을 고른다.
    주석 주제(note_title)가 계정과 맞는 후보(유형자산)를 우선해야 한다."""
    from dart_footing_reconciler.checks_fs_note import _select_note_hit_by_label
    from dart_footing_reconciler.taxonomy import ClassifiedNoteAmount

    def _na(note_no, note_title, label, amount):
        return ClassifiedNoteAmount(
            "property_plant_equipment", "유형자산", note_no, note_title, label, amount,
            f"note:{note_no}", 1.0, "",
        )

    hits = [
        _na("5-1", "금융위험관리 (연결)", "장부금액 합계", 3_282_074_209_000),
        _na("13", "유형자산 (연결)", "기말 유형자산", 17_706_530_246_000),
    ]

    chosen = _select_note_hit_by_label(hits, "property_plant_equipment")

    assert chosen is not None and chosen.note_no == "13", chosen
