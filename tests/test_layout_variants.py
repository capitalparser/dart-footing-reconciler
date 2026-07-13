from dart_footing_reconciler.layout_variants import classify_layout
from dart_footing_reconciler.note_inventory import NoteTableInventoryItem


def _item(title, headers, rows):
    return NoteTableInventoryItem(
        company="Sample Co",
        section_id="note:11",
        note_no="11",
        title=title,
        table_index=0,
        source="note:11/table:0",
        heading=title,
        unit_multiplier=1000,
        row_count=1 + len(rows),
        column_count=len(headers),
        headers=tuple(headers),
        row_labels=tuple(rows),
    )


def test_classify_ppe_cost_accumulated_grant_total_layout():
    item = _item(
        "유형자산",
        ["구분", "취득원가", "감가상각누계액", "정부보조금", "합계"],
        ["토지", "건물", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "asset_cost_accumulated_grant_total"
    assert result.confidence >= 0.8
    assert "정부보조금" in " ".join(result.evidence)
    assert result.source == "note:11/table:0"


def test_unknown_layout_is_preserved():
    item = _item("일반사항", ["구분", "내용"], ["회사", "주소"])

    result = classify_layout(item)

    assert result.key == "unknown_layout"
    assert result.confidence == 0.0
    assert result.evidence == ()


def test_classify_earnings_per_share_summary_layout():
    item = _item(
        "주당순손익 및 배당금",
        ["", "보통주"],
        [
            "지배기업의 보통주에 귀속되는 계속영업당기순이익(손실)",
            "가중평균유통보통주식수",
            "계속영업기본주당이익(손실)",
        ],
    )

    result = classify_layout(item)

    assert result.key == "earnings_per_share_summary"
    assert result.confidence >= 0.8
    assert "earnings per share rows" in result.evidence


def test_classify_dividend_payout_summary_layout():
    item = _item(
        "배당에 관한 사항",
        ["구 분", "주식의 종류", "당기", "전기", "전전기"],
        [
            "(연결)당기순이익(백만원)",
            "현금배당금총액(백만원)",
            "(연결)현금배당성향(%)",
            "주당 현금배당금(원)",
        ],
    )

    result = classify_layout(item)

    assert result.key == "dividend_payout_summary"
    assert result.confidence >= 0.8
    assert "dividend payout ratio rows" in result.evidence


def test_classify_asset_current_period_carrying_amount_layout():
    item = _item("유형자산", ["구분", "당기"], ["장부금액", "취득"])

    result = classify_layout(item)

    assert result.key == "asset_current_period_carrying_amount"
    assert result.confidence >= 0.75
    assert "current period" in " ".join(result.evidence)


def test_classify_lease_liability_current_noncurrent_summary_layout():
    item = _item(
        "리스",
        ["", "공시금액"],
        ["유동 리스부채", "비유동 리스부채", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "lease_liability_current_noncurrent_summary"
    assert result.confidence >= 0.8
    assert "current and non-current lease liability rows" in result.evidence


def test_classify_lease_liability_current_noncurrent_summary_layout_total_first():
    item = _item(
        "리스 (연결)",
        ["", "공시금액"],
        ["리스부채 합계", "유동 리스부채", "비유동 리스부채"],
    )

    result = classify_layout(item)

    assert result.key == "lease_liability_current_noncurrent_summary"
    assert result.confidence >= 0.8


def test_classify_asset_measure_summary_layout_when_asset_is_row_label():
    item = _item(
        "투자부동산",
        ["", "총장부금액", "감가상각누계액 및 상각누계액", "장부금액 합계"],
        ["투자부동산"],
    )

    result = classify_layout(item)

    assert result.key == "asset_measure_summary"
    assert result.confidence >= 0.8
    assert "asset topic in title or rows" in result.evidence


def test_classify_asset_cost_accumulated_summary_without_carrying_amount_column():
    item = _item(
        "투자부동산",
        ["", "취득원가", "감가상각누계액 및 상각누계액"],
        ["토지", "건물", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "asset_cost_accumulated_summary"
    assert result.confidence >= 0.8
    assert "rows include total" in result.evidence


def test_classify_asset_component_column_summary_layout():
    item = _item(
        "무형자산 및 영업권",
        ["", "", "", "", "상각자산", "개발 중인 무형자산", "장부금액"],
        ["무형자산 및 영업권", "무형자산 및 영업권 합계"],
    )

    result = classify_layout(item)

    assert result.key == "asset_component_column_summary"
    assert result.confidence >= 0.8
    assert "asset component columns" in result.evidence


def test_classify_asset_movement_columns_layout_when_movements_are_headers():
    item = _item(
        "유형자산",
        ["", "", "기초", "처분", "감가상각", "기말"],
        ["유형자산", "유형자산 합계"],
    )

    result = classify_layout(item)

    assert result.key == "asset_movement_columns"
    assert result.confidence >= 0.8
    assert "movement labels in headers" in result.evidence


def test_classify_asset_period_rollforward_summary_layout():
    item = _item(
        "유형자산",
        ["구분", "기초", "처분", "기말"],
        ["당기", "전기"],
    )

    result = classify_layout(item)

    assert result.key == "asset_period_rollforward_summary"
    assert result.confidence >= 0.8
    assert "period labels in rows" in result.evidence


def test_classify_asset_two_label_row_rollforward_summary_layout():
    item = _item(
        "투자부동산",
        ["", "", "취득 완료 투자부동산"],
        [
            "투자부동산의 변동에 대한 조정",
            "투자부동산의 변동에 대한 조정",
            "투자부동산의 변동에 대한 조정",
            "투자부동산의 변동에 대한 조정",
        ],
    )

    result = classify_layout(item)

    assert result.key == "asset_two_label_row_rollforward_summary"
    assert result.confidence >= 0.8
    assert "movement labels in secondary row labels" in result.evidence


def test_classify_asset_row_movement_total_layout_from_lease_note_rows():
    item = _item(
        "리스",
        ["", "부동산", "차량운반구", "자산 합계"],
        ["기초 사용권자산", "취득", "종료", "리스변경", "감가상각비", "기말 사용권자산"],
    )

    result = classify_layout(item)

    assert result.key == "asset_row_movement_total"
    assert result.confidence >= 0.8
    assert "asset movement labels in rows" in result.evidence


def test_classify_asset_stacked_measure_summary_when_asset_is_header():
    item = _item(
        "무형자산",
        ["", "", "영업권 이외의 무형자산"],
        ["장부금액", "장부금액", "장부금액", "장부금액 합계"],
    )

    result = classify_layout(item)

    assert result.key == "asset_stacked_measure_summary"
    assert result.confidence >= 0.8
    assert "asset topic in headers" in result.evidence


def test_classify_financial_instrument_category_summary_layout():
    item = _item(
        "범주별 금융상품",
        [
            "",
            "당기손익인식금융자산",
            "기타포괄손익-공정가치 측정 금융자산",
            "상각후원가측정 금융자산",
            "금융자산",
            "범주 합계",
        ],
        ["현금및현금성자산", "매출채권", "기타유동금융자산"],
    )

    result = classify_layout(item)

    assert result.key == "financial_instrument_category_summary"
    assert result.confidence >= 0.8
    assert "financial instrument categories in headers" in result.evidence


def test_classify_financial_instrument_category_summary_with_plain_total_header():
    item = _item(
        "범주별 금융상품",
        [
            "구분",
            "상각후원가측정 금융자산",
            "당기손익-공정가치측정 금융자산",
            "상각후원가측정 금융부채",
            "당기손익-공정가치측정 금융부채",
            "합 계",
        ],
        ["금융자산", "현금및현금성자산", "매출채권", "합계", "금융부채", "매입채무", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "financial_instrument_category_summary"
    assert result.confidence >= 0.8
    assert "financial instrument categories in headers" in result.evidence


def test_classify_financial_instrument_category_summary_with_total_row_only():
    item = _item(
        "범주별 금융상품",
        [
            "구분",
            "상각후원가측정 금융자산",
            "당기손익-공정가치측정 금융자산",
            "기타포괄손익-공정가치측정 금융자산",
        ],
        ["현금및현금성자산", "매출채권", "기타금융자산", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "financial_instrument_category_summary"
    assert result.confidence >= 0.8
    assert "financial category total row" in result.evidence


def test_classify_financial_instrument_fair_value_summary_layout():
    item = _item(
        "금융상품",
        ["", "공정가치"],
        ["현금및현금성자산", "단기금융상품", "매출채권및기타채권", "기타비유동금융자산", "금융자산"],
    )

    result = classify_layout(item)

    assert result.key == "financial_instrument_fair_value_summary"
    assert result.confidence >= 0.8
    assert "fair value amount column" in result.evidence


def test_classify_financial_fair_value_level_summary_layout():
    item = _item(
        "금융상품 공정가치",
        ["구 분", "금융상품", "(수준1)", "(수준2)", "(수준3)", "합 계"],
        ["금융자산", "금융자산", "금융부채"],
    )

    result = classify_layout(item)

    assert result.key == "financial_fair_value_level_summary"
    assert result.confidence >= 0.8
    assert "fair value hierarchy level columns" in result.evidence


def test_classify_tax_expense_composition_summary_layout():
    item = _item(
        "법인세비용",
        ["구 분", "당기", "전기"],
        [
            "법인세등 부담액",
            "일시적차이 등으로 인한 이연법인세 변동액",
            "자본에 직접 가감된 법인세부담액",
            "법인세비용",
        ],
    )

    result = classify_layout(item)

    assert result.key == "tax_expense_composition_summary"
    assert result.confidence >= 0.8
    assert "tax expense component rows" in result.evidence


def test_classify_receivable_carrying_amount_summary_layout():
    item = _item(
        "매출채권 및 기타채권",
        ["", "총장부금액", "손상차손누계액", "장부금액 합계"],
        ["유동매출채권", "단기미수금", "단기대여금"],
    )

    result = classify_layout(item)

    assert result.key == "receivable_carrying_amount_summary"
    assert result.confidence >= 0.8
    assert "receivable carrying amount columns" in result.evidence


def test_classify_receivable_carrying_amount_summary_loss_allowance_header():
    item = _item(
        "매출채권, 대여금 및 기타채권",
        ["", "총장부금액", "차감: 손실충당금", "장부금액 합계"],
        ["유동매출채권", "비유동매출채권"],
    )

    result = classify_layout(item)

    assert result.key == "receivable_carrying_amount_summary"
    assert result.confidence >= 0.8
    assert "receivable carrying amount columns" in result.evidence


def test_classify_receivable_carrying_amount_summary_with_two_label_columns():
    item = _item(
        "매출채권, 대여금 및 기타채권",
        ["", "", "총장부금액", "차감: 손실충당금", "장부금액 합계"],
        ["유동", "유동", "기타 비유동채권", "기타 비유동채권"],
    )

    result = classify_layout(item)

    assert result.key == "receivable_carrying_amount_summary"
    assert result.confidence >= 0.8
    assert "receivable carrying amount columns" in result.evidence


def test_classify_receivable_loss_allowance_aging_summary_layout():
    item = _item(
        "매출채권",
        ["구 분", "6개월 이내 연체 및 정상", "6개월 초과 1년 이내 연체", "1년 초과 연체", "합 계"],
        ["총 장부금액", "손실충당금", "기대 손실률"],
    )

    result = classify_layout(item)

    assert result.key == "receivable_loss_allowance_aging_summary"
    assert result.confidence >= 0.8
    assert "receivable aging bucket columns" in result.evidence


def test_classify_receivable_present_value_carrying_summary_layout():
    item = _item(
        "매출채권 및 기타채권",
        ["", "총장부금액", "현재가치할인차금", "장부금액 합계"],
        ["유동매출채권", "단기미수금", "장기미수금"],
    )

    result = classify_layout(item)

    assert result.key == "receivable_present_value_carrying_summary"
    assert result.confidence >= 0.8
    assert "receivable present value discount columns" in result.evidence


def test_classify_loss_allowance_rollforward_layout():
    item = _item(
        "매출채권 및 기타채권",
        ["", "금융자산, 분류", "금융자산, 분류"],
        ["", "", "", "기초 손실충당금", "기대신용손실", "환입액", "제각", "기말 손실충당금"],
    )

    result = classify_layout(item)

    assert result.key == "loss_allowance_rollforward"
    assert result.confidence >= 0.8
    assert "loss allowance movement labels in rows" in result.evidence


def test_classify_loss_allowance_rollforward_layout_with_financial_asset_movement_rows():
    item = _item(
        "매출채권 및 기타채권 손실충당금과 총장부금액의 변동",
        ["", "금융상품"],
        [
            "",
            "",
            "",
            "기초금융자산",
            "기대신용손실전(환)입, 금융자산",
            "제거에 따른 감소, 금융자산",
            "외화환산에 따른 증가(감소), 금융자산",
            "기타 변동에 따른 증가(감소), 금융자산",
            "기말금융자산",
        ],
    )

    result = classify_layout(item)

    assert result.key == "loss_allowance_rollforward"
    assert result.confidence >= 0.8
    assert "loss allowance movement labels in rows" in result.evidence


def test_classify_loss_allowance_rollforward_layout_with_financial_asset_rows_without_title_context():
    item = _item(
        "매출채권 및 기타채권",
        ["", "금융상품"],
        [
            "",
            "",
            "",
            "기초금융자산",
            "기대신용손실전(환)입, 금융자산",
            "제거에 따른 감소, 금융자산",
            "외화환산에 따른 증가(감소), 금융자산",
            "기타 변동에 따른 증가(감소), 금융자산",
            "기말금융자산",
        ],
    )

    result = classify_layout(item)

    assert result.key == "loss_allowance_rollforward"
    assert result.confidence >= 0.8


def test_classify_receivable_aging_status_summary_layout():
    item = _item(
        "매출채권 및 기타채권",
        ["", "", "매출채권", "단기미수금", "단기대여금", "장기대여금", "장기보증금"],
        ["연체상태", "연체상태", "연체상태", "연체상태", "연체상태", "연체상태 합계"],
    )

    result = classify_layout(item)

    assert result.key == "receivable_aging_status_summary"
    assert result.confidence >= 0.8
    assert "aging status rows include total" in result.evidence


def test_classify_inventory_carrying_amount_summary_layout():
    item = _item(
        "재고자산",
        ["", "총장부금액"],
        ["유동제품", "원재료 및 저장품", "미착품", "기타재고", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "inventory_carrying_amount_summary"
    assert result.confidence >= 0.8
    assert "inventory carrying amount column" in result.evidence


def test_classify_inventory_carrying_amount_summary_layout_with_inventory_total_row():
    item = _item(
        "재고자산 (연결)",
        ["", "총장부금액", "재고자산 평가충당금", "장부금액 합계"],
        ["상품", "제품", "반제품", "재공품", "원재료", "저장품", "미착품", "재고자산"],
    )

    result = classify_layout(item)

    assert result.key == "inventory_carrying_amount_summary"
    assert result.confidence >= 0.8
    assert "rows include inventory total" in result.evidence


def test_classify_inventory_carrying_amount_summary_layout_with_current_inventory_total_row():
    item = _item(
        "재고자산",
        ["", "총장부금액", "재고자산 평가충당금", "장부금액 합계"],
        ["유동상품", "유동제품", "유동원재료", "유동재고자산"],
    )

    result = classify_layout(item)

    assert result.key == "inventory_carrying_amount_summary"
    assert result.confidence >= 0.8
    assert "rows include inventory total" in result.evidence


def test_classify_inventory_allowance_rollforward_layout():
    item = _item(
        "재고자산",
        ["", "재고자산 평가충당금"],
        ["기초재고자산", "재고자산 평가손실환입", "재고자산 평가손실", "재고자산 폐기", "기말재고자산"],
    )

    result = classify_layout(item)

    assert result.key == "inventory_allowance_rollforward"
    assert result.confidence >= 0.8
    assert "inventory allowance amount column" in result.evidence


def test_classify_functional_expense_allocation_layout_from_asset_note():
    item = _item(
        "유형자산",
        ["", "판매비와 일반관리비", "매출원가", "기능별 항목 합계"],
        ["감가상각비, 유형자산"],
    )

    result = classify_layout(item)

    assert result.key == "functional_expense_allocation"
    assert result.confidence >= 0.8
    assert "functional expense columns" in result.evidence


def test_classify_functional_expense_research_allocation_layout():
    item = _item(
        "무형자산",
        ["", "매출원가", "판매비와 일반관리비", "기능별 항목 합계"],
        ["연구와 개발 비용"],
    )

    result = classify_layout(item)

    assert result.key == "functional_expense_research_allocation"
    assert result.confidence >= 0.8
    assert "research and development expense row" in result.evidence


def test_classify_functional_expense_single_row_allocation_layout():
    item = _item(
        "유형자산(별도)",
        ["", "", "감가상각비, 유형자산"],
        ["기능별 항목"],
    )

    result = classify_layout(item)

    assert result.key == "functional_expense_single_row_allocation"
    assert result.confidence >= 0.8
    assert "single functional expense row" in result.evidence


def test_classify_employee_benefit_expense_allocation_layout():
    item = _item(
        "퇴직급여제도",
        ["구분", "당기", "전기"],
        ["판관비에 포함된 금액", "매출원가에 포함된 금액", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "employee_benefit_expense_allocation"
    assert result.confidence >= 0.8
    assert "employee benefit expense allocation rows" in result.evidence


def test_classify_selling_admin_expense_summary_layout():
    item = _item(
        "판매비와 관리비",
        ["", "금액"],
        ["급여, 판관비", "감가상각비, 판관비", "기타판매비와관리비", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "selling_admin_expense_summary"
    assert result.confidence >= 0.8
    assert "expense amount column" in result.evidence


def test_classify_operating_expense_summary_layout():
    item = _item(
        "영업비용",
        ["", "금액"],
        ["가스매출원가", "금융매출원가", "급여, 판관비", "감가상각비, 판관비", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "operating_expense_summary"
    assert result.confidence >= 0.8
    assert "operating expense amount column" in result.evidence


def test_classify_debt_instrument_detail_summary_layout():
    item = _item(
        "차입금 및 사채",
        ["", "차입금명칭", "차입금명칭", "차입금명칭 합계"],
        ["만기일", "연이자율", "차입금", "1년이내 만기도래분", "비유동성 차입금(사채 제외)"],
    )

    result = classify_layout(item)

    assert result.key == "debt_instrument_detail_summary"
    assert result.confidence >= 0.8
    assert "debt instrument total column" in result.evidence


def test_classify_bond_detail_summary_when_total_header_is_not_first_row():
    item = _item(
        "차입금 및 사채",
        ["", "차입금명칭", "차입금명칭", "차입금명칭"],
        ["만기일", "연이자율", "명목금액", "사채할인발행차금", "소계", "1년이내 만기도래분", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "debt_instrument_detail_summary"
    assert result.confidence >= 0.8
    assert "debt detail rows" in result.evidence


def test_classify_bond_detail_summary_with_component_columns():
    item = _item(
        "차입금 및 사채",
        [
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
        ],
        ["차입금명칭", "차입금명칭", "차입금명칭", "차입금명칭", "차입금명칭 합계"],
    )

    result = classify_layout(item)

    assert result.key == "debt_instrument_detail_summary"
    assert result.confidence >= 0.8
    assert "debt component columns" in result.evidence


def test_classify_provision_rollforward_layout():
    item = _item(
        "충당부채",
        ["", "", "기초", "전입", "연중 사용액", "연결범위변동", "매각예정분류", "기말"],
        ["기타충당부채"],
    )

    result = classify_layout(item)

    assert result.key == "provision_rollforward"
    assert result.confidence >= 0.8
    assert "provision movement columns" in result.evidence


def test_classify_row_oriented_provision_rollforward_layout():
    item = _item(
        "충당부채",
        ["", "", "복구충당부채", "기타장기종업원급여부채", "기타충당부채 합계"],
        [
            "기초 기타충당부채",
            "기타충당부채의 변동에 대한 조정",
            "기타충당부채의 변동에 대한 조정",
            "기말 기타충당부채",
        ],
    )

    result = classify_layout(item)

    assert result.key == "provision_rollforward"
    assert result.confidence >= 0.8
    assert "provision account columns" in result.evidence


def test_classify_provision_current_noncurrent_summary_layout():
    item = _item(
        "충당부채",
        ["", "", "유동충당부채", "비유동충당부채"],
        ["복구충당부채", "판매보증충당부채", "기타장기종업원급여부채", "기타충당부채 합계"],
    )

    result = classify_layout(item)

    assert result.key == "provision_current_noncurrent_summary"
    assert result.confidence >= 0.8
    assert "provision current and non-current columns" in result.evidence


def test_classify_defined_benefit_rollforward_layout():
    item = _item(
        "순확정급여부채(자산)",
        ["", "", "확정급여채무의 현재가치", "사외적립자산"],
        ["기초금액", "당기근무원가", "이자비용(수익)", "재측정요소:", "퇴직급여지급액", "기말금액"],
    )

    result = classify_layout(item)

    assert result.key == "defined_benefit_rollforward"
    assert result.confidence >= 0.8
    assert "defined benefit account columns" in result.evidence


def test_classify_defined_benefit_rollforward_from_employee_benefit_title():
    item = _item(
        "퇴직급여제도",
        ["", "", "확정급여채무의 현재가치", "사외적립자산", "순확정급여부채(자산) 합계"],
        ["기초", "당기근무원가, 순확정급여부채(자산)", "이자비용(이자수익)", "기말"],
    )

    result = classify_layout(item)

    assert result.key == "defined_benefit_rollforward"
    assert result.confidence >= 0.8
    assert "defined benefit account columns" in result.evidence


def test_classify_employee_benefit_maturity_summary_layout():
    item = _item(
        "퇴직급여제도",
        ["", "1년 이내", "1년 초과 5년 이내", "5년 초과 10년 이내", "10년 초과", "합계 구간 합계"],
        ["확정급여제도에서 지급될 것으로 예상되는 급여 지급액 추정치"],
    )

    result = classify_layout(item)

    assert result.key == "employee_benefit_maturity_summary"
    assert result.confidence >= 0.8
    assert "employee benefit expected payment row" in result.evidence


def test_classify_employee_benefit_expected_contribution_maturity_summary_layout():
    item = _item(
        "퇴직급여제도",
        ["", "1년 이내", "1년 초과 2년 이내", "2년 초과 5년 이내", "5년 초과", "합계 구간 합계"],
        ["다음 연차보고기간 동안에 납부할 것으로 예상되는 기여금에 대한 추정치"],
    )

    result = classify_layout(item)

    assert result.key == "employee_benefit_maturity_summary"
    assert result.confidence >= 0.8
    assert "employee benefit expected contribution row" in result.evidence


def test_classify_lease_liability_maturity_summary_layout():
    item = _item(
        "사용권자산 및 리스부채",
        ["", "1년 이내", "1년 초과 5년 이내", "5년 초과", "합계 구간 합계"],
        ["최소리스료", "리스부채에 대한 이자비용", "최소리스료의 현재가치"],
    )

    result = classify_layout(item)

    assert result.key == "lease_liability_maturity_summary"
    assert result.confidence >= 0.8
    assert "lease liability maturity rows" in result.evidence


def test_classify_net_debt_bridge_layout():
    item = _item(
        "영업으로부터 창출된 현금 재무활동에서 생기는 부채의 조정",
        ["", "유동성사채", "리스 부채", "단기차입금", "장기 차입금"],
        ["기초 순부채", "현금흐름", "이자비용", "기말 순부채"],
    )

    result = classify_layout(item)

    assert result.key == "net_debt_bridge"
    assert result.confidence >= 0.8
    assert "net debt movement rows" in result.evidence


def test_classify_financing_debt_bridge_from_cashflow_statement_title():
    item = _item(
        "현금흐름표",
        ["", "단기차입금", "장기차입금", "사채", "리스부채", "미지급배당금"],
        [
            "재무활동에서 생기는 기초 부채",
            "배당금의 지급, 재무활동에서 생기는 부채",
            "차입금의 증가, 재무활동에서 생기는 부채",
            "차입금의 감소, 재무활동에서 생기는 부채",
            "그 밖의 변동, 재무활동에서 생기는 부채의 증가(감소)",
            "재무활동에서 생기는 기말 부채",
        ],
    )

    result = classify_layout(item)

    assert result.key == "net_debt_bridge"
    assert result.confidence >= 0.8
    assert "net debt movement rows" in result.evidence


def test_classify_credit_risk_exposure_summary_layout():
    item = _item(
        "재무위험관리 신용위험 익스포저에 대한 공시",
        ["", "신용위험"],
        ["현금성자산", "단기당기손익-공정가치측정금융자산", "매출채권", "기타비유동금융자산", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "credit_risk_exposure_summary"
    assert result.confidence >= 0.8
    assert "credit risk exposure amount column" in result.evidence


def test_classify_credit_risk_exposure_summary_when_prior_heading_drops_exposure_text():
    item = _item(
        "재무위험관리 718,907,006 전기",
        ["", "신용위험"],
        ["현금성자산", "단기당기손익-공정가치측정금융자산", "매출채권", "기타비유동금융자산", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "credit_risk_exposure_summary"


def test_classify_credit_risk_exposure_summary_with_exposure_row_and_asset_columns():
    item = _item(
        "금융상품",
        ["", "현금및현금성자산", "파생상품자산", "매출채권", "금융보증계약", "금융상품 합계"],
        ["신용위험에 대한 최대 노출정도"],
    )

    result = classify_layout(item)

    assert result.key == "credit_risk_exposure_summary"
    assert result.confidence >= 0.8
    assert "credit risk exposure row" in result.evidence


def test_does_not_classify_collateral_ecl_table_as_credit_risk_exposure_summary():
    item = _item(
        "금융위험의 관리 담보에 의한 신용위험 경감효과",
        ["구분", "담보의 유형", "12개월 기대신용손실대상", "전체기간 기대신용손실대상-신용위험의 유의적인 증가", "합계"],
        ["당기손익-공정가치측정 금융자산", "파생상품자산/ 파생결합증권", "상각후원가측정금융자산", "합계"],
    )

    result = classify_layout(item)

    assert result.key != "credit_risk_exposure_summary"


def test_classify_liquidity_maturity_analysis_layout():
    item = _item(
        "재무위험관리 유동성위험 관리 목적으로 보유한 금융자산에 대한 만기분석 공시",
        ["", "3개월 이내", "3개월 초과 1년 이내", "1년 초과 2년 이내", "2년 초과", "합계 구간 합계"],
        ["매입채무 및 기타채무, 미할인현금흐름", "차입금 및 사채", "리스부채", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "liquidity_maturity_analysis"
    assert result.confidence >= 0.8
    assert "maturity bucket columns" in result.evidence


def test_classify_liquidity_maturity_analysis_when_prior_heading_drops_maturity_text():
    item = _item(
        "재무위험관리 542,631,666 전기",
        ["", "3개월 이내", "3개월 초과 1년 이내", "1년 초과 2년 이내", "2년 초과", "합계 구간 합계"],
        ["매입채무 및 기타채무, 미할인현금흐름", "미지급금", "사채", "미지급비용", "리스부채", "합계"],
    )

    result = classify_layout(item)

    assert result.key == "liquidity_maturity_analysis"


def test_classify_lease_expense_summary_layout():
    item = _item(
        "리스 포괄손익계산서에 인식된 리스와 관련된 비용",
        ["", "자산", "자산", "자산 합계"],
        ["", "", "감가상각비, 사용권자산", "리스부채에 대한 이자비용(금융비용에 포함)", "단기리스료"],
    )

    result = classify_layout(item)

    assert result.key == "lease_expense_summary"
    assert result.confidence >= 0.8
    assert "lease expense rows" in result.evidence


def test_classify_discontinued_operation_income_statement_layout():
    item = _item(
        "매각예정처분자산(부채)집단과 중단영업",
        ["", "", "중단영업"],
        [
            "매출액",
            "매출원가",
            "매출총이익",
            "영업이익(손실)",
            "법인세비용차감전순이익(손실)",
            "중단영업순이익",
        ],
    )

    result = classify_layout(item)

    assert result.key == "discontinued_operation_income_statement"
    assert result.confidence >= 0.8
    assert "discontinued operation income rows" in result.evidence


def test_classify_discontinued_operation_cashflow_summary_layout():
    item = _item(
        "매각예정처분자산(부채)집단과 중단영업",
        ["", "중단영업"],
        [
            "중단영업영업활동현금흐름",
            "중단영업투자활동현금흐름",
            "중단영업재무활동현금흐름",
            "합계",
        ],
    )

    result = classify_layout(item)

    assert result.key == "discontinued_operation_cashflow_summary"
    assert result.confidence >= 0.8
    assert "discontinued operation cash flow rows" in result.evidence
