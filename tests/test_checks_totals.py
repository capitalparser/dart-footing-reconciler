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
    assert results[0].evidence[0].role == "target"


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
    assert [evidence.source for evidence in results[0].evidence] == [
        "note:13/table:0"
    ]


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


def test_column_total_ignores_level_numbers_embedded_in_narrative_header_row():
    """서술형 수준 설명의 2/3을 금액으로 읽지 않고 실제 총계만 검증한다."""
    table = ReportTable(
        157,
        [
            ["", "수준1", "수준2", "수준3", "합계"],
            [
                "공정가치 측정치는 수준1, 수준2 및 수준3으로 분류됩니다.",
                "",
                "수준2는 관측 가능한 투입변수를 사용합니다.",
                "수준3은 관측 불가능한 투입변수를 사용합니다.",
                "",
            ],
            ["장기투자자산", "0", "0", "21,895,759,231", "21,895,759,231"],
            ["위험회피파생상품자산", "0", "5,042,588,619", "0", "5,042,588,619"],
            ["금융자산 합계", "0", "5,042,588,619", "21,895,759,231", "26,938,347,850"],
        ],
        "30. 공정가치 수준별 금융자산",
        SourceLocation("note:30", 0, 157),
    )

    results = check_table_totals(table, note_no="30", tolerance=0)

    final_total = [
        result
        for result in results
        if result.evidence
        and result.evidence[0].source == "note:30/table:157/row:4/col:4"
    ]
    assert len(final_total) == 1
    assert final_total[0].status == "matched"
    assert final_total[0].expected == 26_938_347_850
    assert not [result for result in results if result.status == "unexplained_gap"]


def test_final_section_total_does_not_readd_components_before_previous_subtotal():
    table = ReportTable(
        304,
        [
            ["", "공시금액"],
            ["처분이익", "100"],
            ["잡이익", "20"],
            ["기타수익 합계", "120"],
            ["처분손실", ""],
            ["잡손실", "60"],
            ["기타비용 합계", "60"],
        ],
        "기타수익 및 기타비용",
        SourceLocation("note:26", 0, 304),
    )

    results = check_table_totals(table, note_no="26", tolerance=0)

    assert not [result for result in results if result.status == "unexplained_gap"]
    final = [
        result
        for result in results
        if result.evidence
        and result.evidence[0].source == "note:26/table:304/row:6/col:1"
    ]
    assert len(final) == 1
    assert final[0].expected == 60
    assert final[0].actual == 60


def test_beginning_balance_total_is_component_of_ending_rollforward_total():
    table = ReportTable(
        328,
        [
            ["구분", "당기", "전기"],
            ["1. 기초 대손충당금 잔액합계", "6,714", "1,942"],
            ["2. 순대손처리액", "-", "-"],
            ["3. 대손상각비 계상(환입)액", "217", "4,772"],
            ["4. 기말 대손충당금 잔액합계", "6,931", "6,714"],
        ],
        "대손충당금 변동",
        SourceLocation("note:5", 0, 328),
    )

    results = check_table_totals(table, note_no="5", tolerance=0)

    ending = [
        result
        for result in results
        if result.evidence
        and "/row:4/col:" in result.evidence[0].source
    ]
    assert len(ending) == 2
    assert all(result.status == "matched" for result in ending)
    assert {(result.expected, result.actual) for result in ending} == {
        (6_931, 6_931),
        (6_714, 6_714),
    }
