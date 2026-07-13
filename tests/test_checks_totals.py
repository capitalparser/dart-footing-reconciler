from dart_footing_reconciler.checks_totals import check_table_totals
from dart_footing_reconciler.document import ReportTable, SourceLocation


def test_check_table_totals_matches_row_total():
    table = ReportTable(
        index=0,
        heading="11. 유형자산",
        location=SourceLocation("note:11", 0, 0),
        rows=[
            ["구분", "토지", "건물", "합계"],
            ["기초", "100", "200", "300"],
        ],
    )
    results = check_table_totals(table, note_no="11", tolerance=0)
    assert results[0].status == "matched"
    assert results[0].expected == 300
    assert results[0].actual == 300


def test_check_table_totals_reports_unexplained_gap():
    table = ReportTable(
        index=0,
        heading="11. 유형자산",
        location=SourceLocation("note:11", 0, 0),
        rows=[
            ["구분", "토지", "건물", "합계"],
            ["기초", "100", "200", "301"],
        ],
    )
    results = check_table_totals(table, note_no="11", tolerance=0)
    assert results[0].status == "unexplained_gap"
    assert results[0].difference == 1


def test_check_table_totals_matches_column_total():
    table = ReportTable(
        index=1,
        heading="11. 유형자산",
        location=SourceLocation("note:11", 0, 1),
        rows=[
            ["구분", "금액"],
            ["토지", "100"],
            ["건물", "200"],
            ["합계", "300"],
        ],
    )
    results = check_table_totals(table, note_no="11", tolerance=0)
    assert any(result.status == "matched" and result.expected == 300 for result in results)


def test_check_table_totals_treats_subtotal_as_total_label():
    table = ReportTable(
        index=1,
        heading="11. 유형자산",
        location=SourceLocation("note:11", 0, 1),
        rows=[
            ["구분", "금액"],
            ["토지", "100"],
            ["건물", "200"],
            ["소계", "300"],
        ],
    )
    results = check_table_totals(table, note_no="11", tolerance=0)
    assert any(result.status == "matched" and result.expected == 300 for result in results)


def test_check_table_totals_reports_not_tested_for_non_numeric_table():
    table = ReportTable(0, [["구분", "내용"], ["정책", "원가모형"]], "정책", SourceLocation("note:2", 0, 0))

    results = check_table_totals(table, note_no="2")

    assert results[0].status == "not_tested"


def test_check_table_totals_reports_not_tested_for_numeric_disclosure_without_total_target():
    table = ReportTable(
        0,
        [["구분", "내용연수"], ["건물", "20년"], ["기계장치", "5년"]],
        "4. 중요한 회계정책 유형자산의 추정 내용연수",
        SourceLocation("note:4", 0, 0),
    )

    results = check_table_totals(table, note_no="4")

    assert results[0].status == "not_tested"


def test_check_table_totals_keeps_validation_relevant_table_parse_uncertain_without_total_label():
    table = ReportTable(
        0,
        [["구분", "당기"], ["기초 장부금액", "1,000"], ["취득", "200"], ["기말 장부금액", "1,200"]],
        "13. 유형자산 변동내역",
        SourceLocation("note:13", 0, 0),
    )

    results = check_table_totals(table, note_no="13")

    assert results[0].status == "parse_uncertain"


def test_check_table_totals_two_row_fragment_without_summable_structure_is_not_tested():
    """합산 구조가 없는 2행 단편(기초/취득만)은 구조 해석 대상이 아님."""
    table = ReportTable(
        0,
        [["구분", "당기"], ["기초 장부금액", "1,000"], ["취득", "200"]],
        "13. 유형자산 변동내역",
        SourceLocation("note:13", 0, 0),
    )

    results = check_table_totals(table, note_no="13")

    assert results[0].status == "not_tested"


def test_check_table_totals_ratio_and_useful_life_tables_are_not_tested():
    """비율/내용연수 표는 footing 대상이 아니므로 parse_uncertain이 아님."""
    ratio_table = ReportTable(
        0,
        [
            ["", "ERP", "보안", "그룹웨어"],
            ["할인율", "0.0610", "0.0610", "0.0610"],
            ["영구성장률", "0.0000", "0.0000", "0.0100"],
            ["성장률", "0.0230", "(0.1809)", "(0.1859)"],
        ],
        "12. 무형자산 회수가능액 사용한 가정과 영업권 손상차손",
        SourceLocation("note:12", 0, 0),
    )
    life_table = ReportTable(
        1,
        [["과목", "내용연수"], ["건물", "5 ~ 40년"], ["기계장치", "4년~5년"], ["차량운반구", "4년~5년"]],
        "2. 회계정책 유형자산 감가상각 내용연수",
        SourceLocation("note:2", 0, 1),
    )
    assert check_table_totals(ratio_table, note_no="12")[0].status == "not_tested"
    assert check_table_totals(life_table, note_no="2")[0].status == "not_tested"


def test_check_table_totals_multirow_header_single_total_column():
    """다단 헤더 아래 단일 '합계' 열은 행 합계 검증으로 승격됨."""
    table = ReportTable(
        0,
        [
            ["", "금융자산", "금융자산", "금융자산"],
            ["", "만기미도래", "30일 미만", "연체상태 합계"],
            ["매출채권", "30,938,040", "1,133,253", "32,071,293"],
            ["기타채권", "100", "200", "300"],
        ],
        "5. 매출채권 연령분석",
        SourceLocation("note:5", 0, 0),
    )
    results = check_table_totals(table, note_no="5")
    row_checks = [c for c in results if ":row2:" in c.check_id or ":row3:" in c.check_id]
    assert len(row_checks) == 2
    assert all(c.status == "matched" for c in row_checks)
