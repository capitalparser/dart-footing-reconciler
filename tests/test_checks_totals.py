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


def test_check_table_totals_reports_not_tested_for_non_numeric_table():
    table = ReportTable(0, [["구분", "내용"], ["정책", "원가모형"]], "정책", SourceLocation("note:2", 0, 0))

    results = check_table_totals(table, note_no="2")

    assert results[0].status == "not_tested"
