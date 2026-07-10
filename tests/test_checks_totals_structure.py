from dart_footing_reconciler.checks_totals import check_table_totals
from dart_footing_reconciler.document import ReportTable, SourceLocation
from dart_footing_reconciler.label_resolver import AMOUNT_PARSE_FAILED


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


def test_total_column_checks_independent_period_groups():
    table = _table(
        [
            ["", "당기", "당기", "당기 합계", "전기", "전기", "전기 합계"],
            ["", "현금", "매출채권", "당기 합계", "현금", "매출채권", "전기 합계"],
            ["금융자산", "100", "200", "300", "80", "120", "200"],
        ],
        heading="37. 금융상품",
    )

    results = check_table_totals(table, note_no="37", tolerance=0)
    row_results = [result for result in results if result.title == "금융자산 행 합계"]

    assert len(row_results) == 2
    assert [result.status for result in row_results] == ["matched", "matched"]
    assert [result.expected for result in row_results] == [300, 200]
    assert [result.actual for result in row_results] == [300, 200]
    assert [result.evidence[0].source for result in row_results] == [
        "note:37/table:0/row:2/col:3",
        "note:37/table:0/row:2/col:6",
    ]


def test_multirow_header_uses_explicit_sum_column_not_repeated_grand_total_group_label():
    table = _table(
        [
            ["", "기업 전체 총계", "기업 전체 총계", "기업 전체 총계", "기업 전체 총계 합계"],
            ["", "영업부문", "영업부문", "중요한 조정사항", "기업 전체 총계 합계"],
            ["", "신재생에너지", "ESS", "부문간 제거한 금액", "기업 전체 총계 합계"],
            ["자산", "969,759,218,404", "217,685,733,970", "129,627,045,949", "1,317,071,998,323"],
            ["부채", "563,847,376,204", "83,356,422,577", "396,827,667,942", "1,044,031,466,723"],
        ],
        heading="27. 영업부문",
    )

    results = check_table_totals(table, note_no="27", tolerance=0)

    row_totals = [result for result in results if result.title in {"자산 행 합계", "부채 행 합계"}]
    assert [result.status for result in row_totals] == ["matched", "matched"]
    assert [result.expected for result in row_totals] == [1_317_071_998_323, 1_044_031_466_723]


def test_nested_multirow_header_validates_child_subtotals_and_grand_total():
    table = _table(
        [
            ["", "자산", "자산", "자산", "자산", "자산", "자산", "자산", "자산", "자산 합계"],
            ["", "토지", "토지", "토지", "토지", "건물", "건물", "건물", "건물", "자산 합계"],
            ["", "합계 구간", "합계 구간", "합계 구간", "합계 구간 합계", "합계 구간", "합계 구간", "합계 구간", "합계 구간 합계", "자산 합계"],
            ["", "1년 이내", "1년 이상 4년 이내", "4년 이상", "합계 구간 합계", "1년 이내", "1년 이상 4년 이내", "4년 이상", "합계 구간 합계", "자산 합계"],
            ["총 리스부채", "100", "200", "300", "600", "40", "50", "10", "100", "700"],
        ],
        heading="14-2. 리스부채",
    )

    results = check_table_totals(table, note_no="14-2", tolerance=0)
    row_results = [result for result in results if result.title == "총 리스부채 행 합계"]

    assert [result.status for result in row_results] == ["matched", "matched", "matched"]
    assert [result.expected for result in row_results] == [600, 100, 700]
    assert [result.actual for result in row_results] == [600, 100, 700]


def test_nested_multirow_header_validates_revenue_breakdown_parent_totals():
    table = _table(
        [
            ["", "기업 전체 총계", "기업 전체 총계", "기업 전체 총계", "기업 전체 총계", "기업 전체 총계", "기업 전체 총계", "기업 전체 총계 합계"],
            ["", "영업부문", "영업부문", "영업부문", "영업부문", "영업부문", "영업부문", "기업 전체 총계 합계"],
            ["", "신재생에너지", "신재생에너지", "신재생에너지", "ESS", "ESS", "ESS", "기업 전체 총계 합계"],
            ["", "제품과 용역", "제품과 용역", "제품과 용역 합계", "제품과 용역", "제품과 용역", "제품과 용역 합계", "기업 전체 총계 합계"],
            ["", "제품매출", "상품매출", "제품과 용역 합계", "용역수입", "공사수입", "제품과 용역 합계", "기업 전체 총계 합계"],
            ["수익(매출액)", "100", "200", "300", "40", "60", "100", "400"],
        ],
        heading="27. 영업부문",
    )

    results = check_table_totals(table, note_no="27", tolerance=0)
    row_results = [result for result in results if result.title == "수익(매출액) 행 합계"]

    assert [result.status for result in row_results] == ["matched", "matched", "matched"]
    assert [result.expected for result in row_results] == [300, 100, 400]
    assert [result.actual for result in row_results] == [300, 100, 400]


def test_far_right_total_uses_hierarchical_paths_for_repeated_level_labels():
    table = _table(
        [
            ["", "측정 전체", "측정 전체", "측정 전체", "측정 전체", "측정 전체 합계"],
            ["", "공정가치", "공정가치", "취득원가", "취득원가", "측정 전체 합계"],
            ["", "투자 A", "투자 A", "투자 B", "투자 B", "측정 전체 합계"],
            ["", "수준 2", "수준 3", "수준 2", "수준 3", "측정 전체 합계"],
            ["금융자산, 공정가치", "", "1,000", "40", "60", "1,100"],
            ["공정가치측정에 사용된 평가기법에 대한 기술, 자산", "", "현금흐름할인법", "", "순자산가치법", ""],
        ],
        heading="33. 공정가치",
    )

    results = check_table_totals(table, note_no="33", tolerance=0)
    row_results = [result for result in results if result.title == "금융자산, 공정가치 행 합계"]

    assert [result.status for result in row_results] == ["matched"]
    assert row_results[0].expected == 1_100
    assert row_results[0].actual == 1_100


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


def test_column_total_requires_at_least_two_components():
    """계약부채 type: 합계 위에 무관한 단일 행(계약수익)만 있는 표.
    구성요소 1개짜리 합계검증은 무의미하고 무관 항목을 끌어들이므로 보류."""
    table = _table(
        [
            ["", "공시금액"],
            ["고객과의 계약에서 생기는 수익", "9,916,375"],
            ["계약부채 합계", "79,633"],
        ],
        heading="27. 계약잔액",
    )

    results = check_table_totals(table, note_no="27", tolerance=0)

    assert all(r.status != "unexplained_gap" for r in results)


def test_section_ignores_ratio_only_subtotal_for_multi_section_guard():
    """법인세 type: '법인세비용 합계'(금액) + '평균유효세율 합계'(비율). 비율-only
    합계행을 소계로 세면 다중섹션으로 오인해 거짓 차이를 만든다. 비율 합계행은 소계
    카운트에서 제외되어 단일 소계표로 처리되고, 구성요소가 실제로 합계와 맞으면
    column-total로 matched가 되어야 한다(거짓 gap 없음)."""
    table = _table(
        [
            ["", "공시금액"],
            ["적용세율에 의한 법인세비용", "1,188,069"],
            ["세액공제", "(153,104)"],
            ["과거기간 조정", "169,350"],
            ["법인세비용(수익) 합계", "1,204,315"],
            ["평균유효세율 합계", "0.2290"],
        ],
        heading="32. 법인세비용",
    )

    results = check_table_totals(table, note_no="32", tolerance=0)

    assert all(r.status != "unexplained_gap" for r in results)


def test_column_total_accepts_total_label_with_trailing_measure_descriptor():
    table = _table(
        [
            ["", "사외적립자산"],
            ["현금및현금성자산", "255,383"],
            ["정기예금", "4,144,311,037"],
            ["사외적립자산 합계, 공정가치", "4,144,566,420"],
            ["현금및현금성자산 비율", "0.0001"],
            ["정기예금 비율", "0.9999"],
        ],
        heading="18. 퇴직급여제도",
    )

    results = check_table_totals(table, note_no="18", tolerance=0)

    matched = [
        result for result in results
        if result.title == "사외적립자산 합계, 공정가치 column total"
    ]
    assert len(matched) == 1
    assert matched[0].status == "matched"
    assert matched[0].expected == 4_144_566_420
    assert matched[0].actual == 4_144_566_420


def test_column_total_ignores_descriptive_text_rows_before_total():
    table = _table(
        [
            ["", "수준 1", "수준 2", "수준 3", "모든 수준 합계"],
            [
                "공정가치측정에 사용된 평가기법에 대한 기술, 자산",
                "수준1: 활성시장 공시가격",
                "수준2: 관측가능한 투입변수",
                "수준3: 관측가능하지 않은 투입변수",
                "공정가치 서열체계 설명",
            ],
            ["장기투자자산", "0", "0", "22,099,927,588", "22,099,927,588"],
            ["위험회피목적파생상품자산", "0", "2,279,236,826", "0", "2,279,236,826"],
            ["금융자산 합계", "0", "2,279,236,826", "22,099,927,588", "24,379,164,414"],
        ],
        heading="33. 공정가치",
    )

    results = check_table_totals(table, note_no="33", tolerance=0)

    assert all(result.status != "unexplained_gap" for result in results)
    assert all(
        component.label != "공정가치측정에 사용된 평가기법에 대한 기술, 자산"
        for result in results
        for component in result.evidence
        if component.role == "component"
    )


def test_column_total_excludes_tax_profit_before_tax_base_row():
    table = _table(
        [
            ["", "공시금액"],
            ["법인세비용차감전순이익", "38,052,674,805"],
            ["적용세율에 의한 법인세비용(수익)", "8,328,167,879"],
            ["비과세수익 및 비공제비용", "70,423,749"],
            ["기업소득 환류세제 효과", "980,254,948"],
            ["법인세추납액(환급액)", "267,849,411"],
            ["기타(세율차이 등)", "(2,315,802,550)"],
            ["법인세비용(수익) 합계", "7,330,893,437"],
        ],
        heading="30. 법인세비용",
    )

    results = check_table_totals(table, note_no="30", tolerance=0)

    matched = [result for result in results if result.title == "법인세비용(수익) 합계 column total"]
    assert len(matched) == 1
    assert matched[0].status == "matched"
    assert matched[0].expected == 7_330_893_437
    assert all(component.label != "법인세비용차감전순이익" for component in matched[0].evidence)


def test_column_total_excludes_opening_balance_from_period_profit_loss_subtotal():
    table = _table(
        [
            ["", "확정급여채무의 현재가치", "사외적립자산", "순확정급여부채(자산) 합계"],
            ["기초 순확정급여부채(자산)", "2,523,842,360", "(3,031,270,123)", "(507,427,763)"],
            ["당기근무원가, 순확정급여부채(자산)", "701,235,726", "0", "701,235,726"],
            ["이자비용(수익), 순확정급여부채(자산)", "98,913,866", "(152,818,193)", "(53,904,327)"],
            [
                "당기손익으로 인식된 비용(수익)으로 인한 순확정급여부채(자산)의 증가(감소) 합계",
                "800,149,592",
                "(152,818,193)",
                "647,331,399",
            ],
            ["기말 순확정급여부채(자산)", "3,012,138,359", "(4,144,566,420)", "(1,132,428,061)"],
        ],
        heading="18. 퇴직급여제도",
    )

    results = check_table_totals(table, note_no="18", tolerance=0)

    matched = [
        result for result in results
        if result.title.startswith("당기손익으로 인식된 비용")
    ]
    assert [result.status for result in matched] == ["matched", "matched", "matched"]
    assert all(
        component.label != "기초 순확정급여부채(자산)"
        for result in matched
        for component in result.evidence
        if component.role == "component"
    )


def test_column_total_abstains_when_grand_total_has_omitted_components():
    table = _table(
        [
            ["", "현재", "1개월 이내", "1개월 초과 3개월 이내", "3개월 초과", "연체상태 합계"],
            ["매출채권", "53,963,529,960", "0", "0", "0", "53,963,529,960"],
            ["기타채권", "30,430,044,643", "0", "0", "5,933,620", "30,435,978,263"],
            ["유동매출채권 및 기타유동채권 합계", "84,393,574,603", "0", "0", "5,933,620", "84,399,508,223"],
            ["매출채권 및 기타채권 합계", "", "", "", "", "86,158,405,635"],
        ],
        heading="6. 매출채권및기타채권",
    )

    results = check_table_totals(table, note_no="6", tolerance=0)

    assert all(
        result.evidence[0].source != "note:6/table:0/row:4/col:5"
        for result in results
        if result.evidence
    )
    assert all(result.status != "unexplained_gap" for result in results)


def test_section_total_abstains_on_current_subset_without_current_components():
    table = _table(
        [
            ["", "현재", "1개월 이내", "1개월 초과 3개월 이내", "3개월 초과", "연체상태 합계"],
            ["매출채권", "15,036,128,573", "14,248,000", "0", "89,880", "15,050,466,453"],
            ["기타채권", "3,997,705,356", "68,500", "0", "5,865,120", "4,003,638,976"],
            ["유동매출채권 및 기타유동채권 합계", "", "", "", "", "17,320,601,405"],
            ["매출채권 및 기타채권 합계", "19,033,833,929", "14,316,500", "0", "5,955,000", "19,054,105,429"],
        ],
        heading="6. 매출채권및기타채권",
    )

    results = check_table_totals(table, note_no="6", tolerance=0)

    assert all(
        result.evidence[0].source != "note:6/table:0/row:3/col:5"
        for result in results
        if result.evidence
    )
    assert all(result.status != "unexplained_gap" for result in results)


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
    assert results[0].parse_uncertain_reason == AMOUNT_PARSE_FAILED


def test_column_total_attaches_component_evidence_without_changing_result():
    from dart_footing_reconciler.checks_totals import check_table_totals
    from dart_footing_reconciler.document import ReportTable, SourceLocation
    table = ReportTable(0, [["구분", "당기"], ["유동", "100"], ["비유동", "200"], ["합계", "300"]],
                        "13. 차입금", SourceLocation("note:13", 0, 0))
    results = [r for r in check_table_totals(table, note_no="13", tolerance=0)
               if r.check_type == "total_check"]
    r = next(r for r in results if r.status == "matched")
    comps = [e for e in r.evidence if e.role == "component"]
    assert {e.amount for e in comps} == {100, 200}
    assert r.expected == 300 and r.actual == 300 and r.status == "matched"
