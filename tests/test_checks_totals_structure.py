from dart_footing_reconciler.checks_totals import check_table_totals
from dart_footing_reconciler.document import ReportTable, SourceLocation


def _table(rows: list[list[str]], *, index: int = 0, heading: str = "13. 차입금") -> ReportTable:
    return ReportTable(
        index=index,
        rows=rows,
        heading=heading,
        location=SourceLocation("note:13", 0, index),
    )


def _targets(results):
    return [result.evidence[0].source for result in results if result.evidence]


def test_total_column_row_footing_matches_amount_row():
    table = _table(
        [
            ["구분", "외화대출", "원화대출", "매출채권할인", "차입금명칭 합계"],
            ["유동 차입금(사채 포함)", "513,308", "130,180", "4,325", "647,813"],
        ]
    )

    results = check_table_totals(table, note_no="13", tolerance=0)

    assert len(results) == 1
    assert results[0].status == "matched"
    assert results[0].title == "유동 차입금(사채 포함) 행 합계"
    assert results[0].expected == 647_813
    assert results[0].actual == 647_813


def test_total_column_row_footing_reports_gap():
    table = _table(
        [
            ["구분", "외화대출", "원화대출", "매출채권할인", "차입금명칭 합계"],
            ["유동 차입금(사채 포함)", "513,308", "130,180", "4,325", "647,814"],
        ]
    )

    results = check_table_totals(table, note_no="13", tolerance=0)

    assert len(results) == 1
    assert results[0].status == "unexplained_gap"
    assert results[0].title == "유동 차입금(사채 포함) 행 합계"
    assert results[0].difference == 1


def test_total_column_row_footing_excludes_rate_rows():
    table = _table(
        [
            ["구분", "외화대출", "원화대출", "매출채권할인", "차입금명칭 합계"],
            ["유동 차입금(사채 포함)", "513,308", "130,180", "4,325", "647,813"],
            ["기준이자율", "3M SOFR", "4.35%", "1.20%", "4.50%"],
        ]
    )

    results = check_table_totals(table, note_no="13", tolerance=0)

    assert len(results) == 1
    assert results[0].status == "matched"
    assert "기준이자율" not in results[0].title


def test_total_column_row_footing_handles_degenerate_repeated_headers():
    # 상단 헤더는 '차입금명칭'으로 반복(병합 아티팩트)되지만, leaf 서브헤더는
    # 외화/원화/매출채권할인으로 서로 다르다 → 배타적 구성요소로 합산 가능.
    table = _table(
        [
            ["", "차입금명칭", "차입금명칭", "차입금명칭", "차입금명칭 합계"],
            ["", "외화대출", "원화대출", "매출채권할인", "차입금명칭 합계"],
            ["유동 차입금(사채 포함)", "513,308", "130,180", "4,325", "647,813"],
        ]
    )

    results = check_table_totals(table, note_no="13", tolerance=0)

    assert len(results) == 1
    assert results[0].status == "matched"
    assert results[0].expected == 647_813
    assert results[0].actual == 647_813


def test_section_total_foots_each_subtotal_to_its_own_components():
    table = _table(
        [
            ["구분", "당기"],
            ["유동매출채권", "9,916,129"],
            ["단기미수금", "368,501"],
            ["유동 대여금 및 수취채권", "1,776"],
            ["매출채권 및 기타유동채권 합계", "10,286,406"],
            ["비유동매출채권", "246"],
            ["장기미수금", "509,249"],
            ["비유동 대여금 및 수취채권", "1,819"],
            ["매출채권 및 기타비유동채권 합계", "511,314"],
        ],
        heading="8. 매출채권",
    )

    results = check_table_totals(table, note_no="8", tolerance=0)

    assert [result.status for result in results] == ["matched", "matched"]
    assert [result.expected for result in results] == [10_286_406, 511_314]
    assert [result.actual for result in results] == [10_286_406, 511_314]


def test_section_total_does_not_treat_last_subtotal_as_grand_total():
    table = _table(
        [
            ["구분", "당기"],
            ["유동매출채권", "9,916,129"],
            ["단기미수금", "368,501"],
            ["유동 대여금 및 수취채권", "1,776"],
            ["매출채권 및 기타유동채권 합계", "10,286,406"],
            ["비유동매출채권", "246"],
            ["장기미수금", "509,249"],
            ["비유동 대여금 및 수취채권", "1,819"],
            ["매출채권 및 기타비유동채권 합계", "511,314"],
        ],
        heading="8. 매출채권",
    )

    results = check_table_totals(table, note_no="8", tolerance=0)

    assert all(result.status != "unexplained_gap" for result in results)
    assert all(result.expected != 10_797_720 for result in results)


def test_structure_checks_dedup_same_target_when_total_column_and_subtotal_overlap():
    table = _table(
        [
            ["구분", "외화대출", "원화대출", "합계"],
            ["유동 차입금", "100", "200", "300"],
            ["비유동 차입금", "40", "60", "100"],
            ["차입금 합계", "140", "260", "400"],
        ],
        index=3,
    )

    results = check_table_totals(table, note_no="13", tolerance=0)

    assert len(_targets(results)) == len(set(_targets(results)))
    assert _targets(results).count("note:13/table:3/row:3/col:3") == 1


def test_total_column_abstains_on_multiple_group_subtotal_columns():
    """배당주식수 type: 중간배당[보통|우선|합계] + 연차배당[보통|우선|합계].
    두 그룹 합계 컬럼을 가로질러 합산하면 거짓 차이 → row-wise는 보류해야 한다."""
    table = _table(
        [
            ["", "중간배당", "중간배당", "주식 합계", "연차배당", "연차배당", "주식 합계"],
            ["", "보통주", "우선주", "주식 합계", "보통주", "우선주", "주식 합계"],
            ["배당주식수(주)", "90,008,643", "3,974", "90,012,617", "90,490,640", "3,974", "90,494,614"],
        ],
        heading="26. 배당금",
    )

    results = check_table_totals(table, note_no="26", tolerance=0)

    assert all(r.status != "unexplained_gap" for r in results)
    # 절대 cols 1..5 (중간 소계 포함)를 최우측 합계와 비교하면 안 된다.
    bad = 90_008_643 + 3_974 + 90_012_617 + 90_490_640 + 3_974
    assert all(r.expected != bad for r in results)


def test_total_column_abstains_on_nested_subtotal_columns():
    """공정가치 type: [수준1|수준2|모든수준(소계)] x2 + 범주 합계. 중첩 소계를 함께
    더하면 중복합산 → row-wise는 보류해야 한다 (leaf 라벨 중복으로 거부)."""
    table = _table(
        [
            ["", "당기손익", "당기손익", "당기손익", "기타포괄", "기타포괄", "기타포괄", "범주 합계"],
            ["", "수준1", "수준2", "모든수준", "수준1", "수준2", "모든수준", "범주 합계"],
            ["금융자산", "0", "399,249", "399,249", "372,654", "388,952", "761,606", "1,160,855"],
        ],
        heading="37. 위험관리",
    )

    results = check_table_totals(table, note_no="37", tolerance=0)

    assert all(r.status != "unexplained_gap" for r in results)


def test_single_header_abstains_on_multiple_total_columns():
    """단일 헤더에도 합계 컬럼이 둘이면(그룹 구조) row-wise 보류."""
    table = _table(
        [
            ["", "보통주", "우선주", "합계", "보통주", "우선주", "합계"],
            ["주식수", "100", "10", "110", "200", "20", "220"],
        ],
        heading="26. 배당금",
    )

    results = check_table_totals(table, note_no="26", tolerance=0)

    assert all(r.status != "unexplained_gap" for r in results)


def test_no_total_column_or_subtotal_abstains_with_parse_uncertain():
    table = _table(
        [
            ["구분", "당기", "전기"],
            ["기초 장부금액", "1,000", "900"],
            ["취득", "200", "100"],
            ["처분", "50", "20"],
        ],
        heading="13. 유형자산 변동내역",
    )

    results = check_table_totals(table, note_no="13", tolerance=0)

    assert len(results) == 1
    assert results[0].status == "parse_uncertain"
    assert results[0].expected is None
    assert results[0].actual is None
