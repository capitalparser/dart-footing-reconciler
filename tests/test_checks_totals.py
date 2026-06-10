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
        [["구분", "당기"], ["기초 장부금액", "1,000"], ["취득", "200"]],
        "13. 유형자산 변동내역",
        SourceLocation("note:13", 0, 0),
    )

    results = check_table_totals(table, note_no="13")

    assert results[0].status == "parse_uncertain"
