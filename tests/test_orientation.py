from dart_footing_reconciler.orientation import detect_orientation


def test_detects_row_oriented_rollforward():
    result = detect_orientation(
        headers=("구분", "토지", "건물", "합계"),
        row_labels=("기초", "취득", "감가상각", "기말"),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "movement labels in rows" in result.evidence


def test_detects_column_oriented_asset_measure_table():
    result = detect_orientation(
        headers=("구분", "취득원가", "감가상각누계액", "정부보조금", "합계"),
        row_labels=("토지", "건물", "합계"),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "measure labels in columns" in result.evidence


def test_detects_period_oriented_table():
    result = detect_orientation(
        headers=("구분", "당기", "전기"),
        row_labels=("장부금액", "취득"),
    )

    assert result.key == "period_oriented"
    assert result.confidence >= 0.75
    assert "period labels in columns" in result.evidence


def test_detects_row_orientation_for_earnings_per_share_summary():
    result = detect_orientation(
        headers=("", "보통주"),
        row_labels=(
            "지배기업의 보통주에 귀속되는 계속영업당기순이익(손실)",
            "가중평균유통보통주식수",
            "계속영업기본주당이익(손실)",
        ),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "earnings per share rows" in result.evidence


def test_detects_mixed_orientation_when_both_axes_have_roles():
    result = detect_orientation(
        headers=("구분", "기초", "취득", "기말"),
        row_labels=("장부금액", "상각누계액"),
    )

    assert result.key == "mixed"
    assert result.confidence >= 0.7


def test_detects_mixed_orientation_when_movement_columns_have_asset_rows():
    result = detect_orientation(
        headers=("", "", "기초", "처분", "감가상각", "기말"),
        row_labels=("유형자산", "유형자산 합계"),
    )

    assert result.key == "mixed"
    assert result.confidence >= 0.7
    assert "movement labels in columns" in result.evidence


def test_detects_mixed_orientation_when_movement_columns_embed_asset_topic():
    result = detect_orientation(
        headers=("", "", "", "", "기초 유형자산", "취득", "감가상각", "처분", "기말 유형자산"),
        row_labels=("유형자산", "유형자산"),
    )

    assert result.key == "mixed"
    assert result.confidence >= 0.7
    assert "asset labels in rows" in result.evidence


def test_detects_row_orientation_for_asset_period_rollforward_summary():
    result = detect_orientation(
        headers=("구분", "기초", "처분", "기말"),
        row_labels=("당기", "전기"),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "period labels in rows" in result.evidence


def test_detects_row_orientation_for_asset_two_label_row_rollforward_summary():
    result = detect_orientation(
        headers=("", "", "취득 완료 투자부동산"),
        row_labels=(
            "투자부동산의 변동에 대한 조정",
            "투자부동산의 변동에 대한 조정",
            "투자부동산의 변동에 대한 조정",
            "투자부동산의 변동에 대한 조정",
        ),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "asset movement detail rows" in result.evidence


def test_does_not_treat_tax_temporary_difference_asset_rows_as_mixed():
    result = detect_orientation(
        headers=("구분", "기초", "증감", "기말"),
        row_labels=("일시적차이 구분", "유형자산", "무형자산"),
    )

    assert result.key != "mixed"


def test_detects_mixed_orientation_when_asset_headers_have_measure_rows():
    result = detect_orientation(
        headers=("", "", "영업권 이외의 무형자산"),
        row_labels=("장부금액", "장부금액", "장부금액", "장부금액 합계"),
    )

    assert result.key == "mixed"
    assert result.confidence >= 0.7
    assert "asset labels in columns" in result.evidence


def test_detects_column_orientation_for_asset_component_column_summary():
    result = detect_orientation(
        headers=("", "", "", "", "상각자산", "개발 중인 무형자산", "장부금액"),
        row_labels=("무형자산 및 영업권", "무형자산 및 영업권 합계"),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "asset component columns" in result.evidence


def test_detects_column_orientation_for_financial_category_summary():
    result = detect_orientation(
        headers=(
            "",
            "당기손익인식금융자산",
            "기타포괄손익-공정가치 측정 금융자산",
            "상각후원가측정 금융자산",
            "금융자산",
            "범주 합계",
        ),
        row_labels=("현금및현금성자산", "매출채권", "기타유동금융자산"),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "financial category labels in columns" in result.evidence


def test_detects_row_orientation_for_financial_fair_value_summary():
    result = detect_orientation(
        headers=("", "공정가치"),
        row_labels=("현금및현금성자산", "단기금융상품", "매출채권및기타채권", "기타비유동금융자산", "금융자산"),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "financial fair value amount column" in result.evidence


def test_detects_row_orientation_for_loss_allowance_rollforward():
    result = detect_orientation(
        headers=("", "금융자산, 분류", "금융자산, 분류"),
        row_labels=("", "", "", "기초 손실충당금", "기대신용손실", "환입액", "제각", "기말 손실충당금"),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "loss allowance movement labels in rows" in result.evidence


def test_detects_row_orientation_for_loss_allowance_financial_asset_movement_rows():
    result = detect_orientation(
        headers=("", "금융상품"),
        row_labels=(
            "",
            "",
            "",
            "기초금융자산",
            "기대신용손실전(환)입, 금융자산",
            "제거에 따른 감소, 금융자산",
            "외화환산에 따른 증가(감소), 금융자산",
            "기타 변동에 따른 증가(감소), 금융자산",
            "기말금융자산",
        ),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "loss allowance movement labels in rows" in result.evidence


def test_loss_allowance_rows_take_precedence_over_repeated_financial_product_headers():
    result = detect_orientation(
        headers=("", "금융상품", "금융상품"),
        row_labels=(
            "",
            "",
            "",
            "기초금융자산",
            "손실충당금 전입(환입)",
            "제각",
            "매각예정대체",
            "기타(환율변동효과 등)",
            "기말금융자산",
        ),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "loss allowance movement labels in rows" in result.evidence


def test_detects_column_orientation_for_receivable_aging_summary():
    result = detect_orientation(
        headers=("", "", "매출채권", "단기미수금", "단기대여금", "장기대여금", "장기보증금"),
        row_labels=("연체상태", "연체상태", "연체상태", "연체상태", "연체상태 합계"),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "receivable account labels in columns" in result.evidence


def test_detects_row_orientation_for_receivable_loss_allowance_aging_summary():
    result = detect_orientation(
        headers=("구 분", "6개월 이내 연체 및 정상", "6개월 초과 1년 이내 연체", "1년 초과 연체", "합 계"),
        row_labels=("총 장부금액", "손실충당금", "기대 손실률"),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "receivable aging bucket columns" in result.evidence


def test_detects_column_orientation_for_inventory_carrying_summary():
    result = detect_orientation(
        headers=("", "총장부금액"),
        row_labels=("유동제품", "원재료 및 저장품", "미착품", "기타재고", "합계"),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "inventory carrying amount column" in result.evidence


def test_detects_row_orientation_for_inventory_allowance_rollforward():
    result = detect_orientation(
        headers=("", "재고자산 평가충당금"),
        row_labels=("기초재고자산", "재고자산 평가손실환입", "재고자산 평가손실", "재고자산 폐기", "기말재고자산"),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "inventory allowance movement labels in rows" in result.evidence


def test_detects_column_orientation_for_functional_expense_allocation():
    result = detect_orientation(
        headers=("", "판매비와 일반관리비", "매출원가", "기능별 항목 합계"),
        row_labels=("감가상각비, 유형자산",),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "functional expense columns" in result.evidence


def test_detects_column_orientation_for_functional_expense_research_allocation():
    result = detect_orientation(
        headers=("", "매출원가", "판매비와 일반관리비", "기능별 항목 합계"),
        row_labels=("연구와 개발 비용",),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "functional expense columns" in result.evidence


def test_detects_column_orientation_for_functional_expense_single_row_allocation():
    result = detect_orientation(
        headers=("", "", "감가상각비, 유형자산"),
        row_labels=("기능별 항목",),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "single functional expense row" in result.evidence


def test_detects_column_orientation_for_selling_admin_expense_summary():
    result = detect_orientation(
        headers=("", "금액"),
        row_labels=("급여, 판관비", "감가상각비, 판관비", "기타판매비와관리비", "합계"),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "expense amount column" in result.evidence


def test_detects_row_orientation_for_debt_instrument_detail_summary():
    result = detect_orientation(
        headers=("", "차입금명칭", "차입금명칭", "차입금명칭 합계"),
        row_labels=("만기일", "연이자율", "차입금", "1년이내 만기도래분", "비유동성 차입금"),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "debt detail rows" in result.evidence


def test_detects_row_orientation_for_debt_detail_component_columns():
    result = detect_orientation(
        headers=(
            "",
            "",
            "",
            "발행일",
            "만기일",
            "차입금, 이자율",
            "명목금액",
            "차감: 유동성사채",
            "차감: 사채할인발행차금",
            "비유동 사채의 비유동성 부분",
        ),
        row_labels=("차입금명칭", "차입금명칭", "차입금명칭", "차입금명칭", "차입금명칭 합계"),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "debt component columns" in result.evidence


def test_detects_mixed_orientation_for_provision_rollforward():
    result = detect_orientation(
        headers=("", "", "기초", "전입", "연중 사용액", "연결범위변동", "매각예정분류", "기말"),
        row_labels=("기타충당부채",),
    )

    assert result.key == "mixed"
    assert result.confidence >= 0.8
    assert "provision movement columns" in result.evidence


def test_detects_row_orientation_for_provision_rollforward_account_columns():
    result = detect_orientation(
        headers=("", "", "복구충당부채", "기타장기종업원급여부채", "기타충당부채 합계"),
        row_labels=("기초 기타충당부채", "기타충당부채의 변동에 대한 조정", "기말 기타충당부채"),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "provision account columns" in result.evidence


def test_detects_mixed_orientation_for_defined_benefit_rollforward():
    result = detect_orientation(
        headers=("", "", "확정급여채무의 현재가치", "사외적립자산"),
        row_labels=("기초금액", "당기근무원가", "이자비용(수익)", "재측정요소:", "퇴직급여지급액", "기말금액"),
    )

    assert result.key == "mixed"
    assert result.confidence >= 0.8
    assert "defined benefit account columns" in result.evidence


def test_detects_mixed_orientation_for_net_debt_bridge():
    result = detect_orientation(
        headers=("", "유동성사채", "리스 부채", "단기차입금", "장기 차입금"),
        row_labels=("기초 순부채", "현금흐름", "이자비용", "기말 순부채"),
    )

    assert result.key == "mixed"
    assert result.confidence >= 0.8
    assert "financial liability account columns" in result.evidence
    assert "net debt movement rows" in result.evidence


def test_detects_mixed_orientation_for_financing_debt_bridge():
    result = detect_orientation(
        headers=("", "단기차입금", "장기차입금", "사채", "리스부채", "미지급배당금"),
        row_labels=(
            "재무활동에서 생기는 기초 부채",
            "배당금의 지급, 재무활동에서 생기는 부채",
            "차입금의 증가, 재무활동에서 생기는 부채",
            "차입금의 감소, 재무활동에서 생기는 부채",
            "그 밖의 변동, 재무활동에서 생기는 부채의 증가(감소)",
            "재무활동에서 생기는 기말 부채",
        ),
    )

    assert result.key == "mixed"
    assert result.confidence >= 0.8
    assert "financial liability account columns" in result.evidence
    assert "net debt movement rows" in result.evidence


def test_detects_column_orientation_for_provision_current_noncurrent_summary():
    result = detect_orientation(
        headers=("", "", "유동충당부채", "비유동충당부채"),
        row_labels=("복구충당부채", "판매보증충당부채", "기타장기종업원급여부채", "기타충당부채 합계"),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "provision current and non-current columns" in result.evidence


def test_detects_column_orientation_for_credit_risk_exposure_summary():
    result = detect_orientation(
        headers=("", "신용위험"),
        row_labels=("현금성자산", "단기당기손익-공정가치측정금융자산", "매출채권", "기타비유동금융자산", "합계"),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "credit risk exposure amount column" in result.evidence


def test_detects_column_orientation_for_credit_risk_exposure_row_summary():
    result = detect_orientation(
        headers=("", "현금및현금성자산", "파생상품자산", "매출채권", "금융보증계약", "금융상품 합계"),
        row_labels=("신용위험에 대한 최대 노출정도",),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "credit risk exposure row" in result.evidence


def test_detects_column_orientation_for_liquidity_maturity_analysis():
    result = detect_orientation(
        headers=("", "3개월 이내", "3개월 초과 1년 이내", "1년 초과 2년 이내", "2년 초과", "합계 구간 합계"),
        row_labels=("매입채무 및 기타채무, 미할인현금흐름", "차입금 및 사채", "리스부채", "합계"),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "maturity bucket columns" in result.evidence


def test_detects_row_orientation_for_employee_benefit_maturity_summary():
    result = detect_orientation(
        headers=("", "1년 이내", "1년 초과 5년 이내", "5년 초과 10년 이내", "10년 초과", "합계 구간 합계"),
        row_labels=("확정급여제도에서 지급될 것으로 예상되는 급여 지급액 추정치",),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "maturity bucket columns" in result.evidence
    assert "employee benefit expected payment row" in result.evidence


def test_detects_row_orientation_for_employee_benefit_expected_contribution_maturity_summary():
    result = detect_orientation(
        headers=("", "1년 이내", "1년 초과 2년 이내", "2년 초과 5년 이내", "5년 초과", "합계 구간 합계"),
        row_labels=("다음 연차보고기간 동안에 납부할 것으로 예상되는 기여금에 대한 추정치",),
    )

    assert result.key == "row_oriented"
    assert result.confidence >= 0.8
    assert "maturity bucket columns" in result.evidence
    assert "employee benefit expected contribution row" in result.evidence


def test_detects_column_orientation_for_lease_liability_maturity_summary():
    result = detect_orientation(
        headers=("", "6개월 이내", "6개월 초과 1년 이내", "1년 초과 2년 이내", "2년 초과 5년 이내", "5년 초과", "합계 구간 합계"),
        row_labels=("총 리스부채", "리스부채"),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "maturity bucket columns" in result.evidence
    assert "lease liability maturity rows" in result.evidence


def test_detects_column_orientation_for_lease_expense_summary():
    result = detect_orientation(
        headers=("", "자산", "자산", "자산 합계"),
        row_labels=("", "", "감가상각비, 사용권자산", "리스부채에 대한 이자비용(금융비용에 포함)", "단기리스료"),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "lease expense rows" in result.evidence


def test_detects_column_orientation_for_discontinued_operation_income_statement():
    result = detect_orientation(
        headers=("", "", "중단영업"),
        row_labels=(
            "매출액",
            "매출원가",
            "매출총이익",
            "영업이익(손실)",
            "법인세비용차감전순이익(손실)",
            "중단영업이익(손실)",
            "중단영업순이익",
        ),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "discontinued operation income rows" in result.evidence


def test_detects_column_orientation_for_discontinued_operation_cashflow_summary():
    result = detect_orientation(
        headers=("", "중단영업"),
        row_labels=(
            "중단영업영업활동현금흐름",
            "중단영업투자활동현금흐름",
            "중단영업재무활동현금흐름",
            "합계",
        ),
    )

    assert result.key == "column_oriented"
    assert result.confidence >= 0.8
    assert "discontinued operation cash flow rows" in result.evidence


def test_unknown_orientation_is_preserved():
    result = detect_orientation(
        headers=("구분", "내용"),
        row_labels=("회사", "주소"),
    )

    assert result.key == "unknown"
    assert result.confidence == 0.0
    assert result.evidence == ()
