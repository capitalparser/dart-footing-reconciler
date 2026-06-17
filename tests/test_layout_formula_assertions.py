from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.formula_discovery import discover_rollforward_formula
from dart_footing_reconciler.label_resolver import LOW_CONFIDENCE_MATCH
from dart_footing_reconciler.layout_formula_assertions import (
    _formula_check_result,
    check_layout_formula_assertions,
)
from dart_footing_reconciler.verification_candidates import VerificationCandidate


class _FormulaItem:
    note_no = "11"
    table_index = 0


def _formula_candidate(role, amount, confidence=0.9):
    return VerificationCandidate(
        account_key="property_plant_equipment",
        role=role,
        label=role,
        raw_amount=amount,
        unit_multiplier=1,
        amount=amount,
        note_no="11",
        table_source="note:11/table:0",
        row_index=1,
        column_index=1,
        layout_key="asset_current_period_carrying_amount",
        orientation_key="row_oriented",
        confidence=confidence,
        evidence=("evidence",),
    )


def test_formula_check_result_preserves_parse_uncertain_reason_code():
    formula = discover_rollforward_formula(
        [
            _formula_candidate("beginning", 100, confidence=0.4),
            _formula_candidate("ending", 100),
        ],
        tolerance=0,
    )

    result = _formula_check_result(
        _FormulaItem(),
        "asset_period_rollforward_summary",
        formula,
        tolerance=0,
        account_key="property_plant_equipment",
    )

    assert result.status == "parse_uncertain"
    assert result.parse_uncertain_reason == LOW_CONFIDENCE_MATCH


def test_check_layout_formula_assertions_validates_inventory_allowance_rollforward(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>6. 재고자산</p>
          <p>재고자산 평가충당금의 변동내역 당기 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>재고자산 평가충당금</th></tr>
            <tr><td>기초재고자산</td><td>(3,969,701)</td></tr>
            <tr><td>재고자산 평가손실환입</td><td>427,066</td></tr>
            <tr><td>재고자산 평가손실</td><td>(961,511)</td></tr>
            <tr><td>재고자산 폐기</td><td>0</td></tr>
            <tr><td>기타 (주1)</td><td>(1,553)</td></tr>
            <tr><td>기말재고자산</td><td>(4,505,699)</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", -4_505_699_000, -4_505_699_000)
    ]
    assert checks[0].title == "재고자산 평가충당금 증감표 검산"
    assert checks[0].evidence[0].source == "note:6/table:0/row:1/col:1"


def test_check_layout_formula_assertions_validates_asset_period_rollforward_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>8. 유형자산</p>
          <p>당기와 전기 중 토지의 변동내역은 다음과 같습니다. (단위 : 원)</p>
          <table>
            <tr><th>구분</th><th>기초</th><th>처분</th><th>기말</th></tr>
            <tr><td>당기</td><td>64,487,052</td><td>-</td><td>64,487,052</td></tr>
            <tr><td>전기</td><td>67,148,934</td><td>(2,661,882)</td><td>64,487,052</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 64_487_052, 64_487_052),
        ("note_layout_formula_check", "matched", 64_487_052, 64_487_052),
    ]
    assert checks[0].title == "자산 기간별 증감표 검산 - 당기"
    assert checks[0].evidence[-1].source == "note:8/table:0/row:1/col:3"
    assert checks[1].title == "자산 기간별 증감표 검산 - 전기"
    assert checks[1].evidence[-1].source == "note:8/table:0/row:2/col:3"


def test_check_layout_formula_assertions_validates_earnings_per_share_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>24. 주당순손익 및 배당금</p>
          <p>기본주당이익 산정내역은 다음과 같습니다. (단위 : 천원)</p>
          <table>
            <tr><th></th><th>보통주</th></tr>
            <tr><td>지배기업의 보통주에 귀속되는 계속영업당기순이익(손실)</td><td>8,671,234</td></tr>
            <tr><td>가중평균유통보통주식수</td><td>4,277,208</td></tr>
            <tr><td>계속영업기본주당이익(손실)</td><td>2,027</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 2_027, 2_027)
    ]
    assert checks[0].title == "주당이익 산식 검산 - continuing_basic_eps"
    assert checks[0].evidence[0].amount == 8_671_234_000
    assert checks[0].evidence[1].amount == 4_277_208
    assert checks[0].evidence[2].amount == 2_027


def test_check_layout_formula_assertions_validates_dividend_payout_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>6. 배당에 관한 사항</p>
          <table>
            <tr><th>구 분</th><th>주식의 종류</th><th>당기</th><th>전기</th><th>전전기</th></tr>
            <tr><td>구 분</td><td>주식의 종류</td><td>제44기</td><td>제43기</td><td>제42기</td></tr>
            <tr><td>(연결)당기순이익(백만원)</td><td>(연결)당기순이익(백만원)</td><td>29,040</td><td>34,053</td><td>-2,470</td></tr>
            <tr><td>현금배당금총액(백만원)</td><td>현금배당금총액(백만원)</td><td>17,109</td><td>37,326</td><td>10,664</td></tr>
            <tr><td>(연결)현금배당성향(%)</td><td>(연결)현금배당성향(%)</td><td>58.9</td><td>109.6</td><td>-</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 589, 589),
        ("note_layout_formula_check", "matched", 1_096, 1_096),
    ]
    assert checks[0].title == "현금배당성향 검산 - 당기"
    assert checks[1].title == "현금배당성향 검산 - 전기"


def test_check_layout_formula_assertions_validates_asset_two_label_row_rollforward_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>12. 투자부동산</p>
          <p>투자부동산에 대한 세부 정보 공시 당기 (단위 : 백만원)</p>
          <table>
            <tr><th></th><th></th><th>취득 완료 투자부동산</th></tr>
            <tr><td>투자부동산의 변동에 대한 조정</td><td>투자부동산의 변동에 대한 조정</td><td></td></tr>
            <tr><td>투자부동산의 변동에 대한 조정</td><td>기초</td><td>6,699</td></tr>
            <tr><td>투자부동산의 변동에 대한 조정</td><td>감가상각비</td><td>(31)</td></tr>
            <tr><td>투자부동산의 변동에 대한 조정</td><td>대체</td><td>(4,281)</td></tr>
            <tr><td>투자부동산의 변동에 대한 조정</td><td>기타(환율효과 등)</td><td>711</td></tr>
            <tr><td>투자부동산의 변동에 대한 조정</td><td>기말</td><td>3,098</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 3_098_000_000, 3_098_000_000)
    ]
    assert checks[0].title == "자산 두 라벨 행 증감표 검산 - investment_property"
    assert checks[0].evidence[-1].source == "note:12/table:0/row:6/col:2"


def test_check_layout_formula_assertions_validates_loss_allowance_rollforward(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>5. 매출채권 및 기타채권</p>
          <p>매출채권 및 기타채권 손실충당금과 총장부금액의 변동 당기 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>금융상품</th></tr>
            <tr><td></td><td>매출채권</td></tr>
            <tr><td></td><td>장부금액</td></tr>
            <tr><td></td><td>손상차손누계액</td></tr>
            <tr><td>기초금융자산</td><td>(205,922)</td></tr>
            <tr><td>기대신용손실전(환)입, 금융자산</td><td>66,473</td></tr>
            <tr><td>제거에 따른 감소, 금융자산</td><td>2,866</td></tr>
            <tr><td>외화환산에 따른 증가(감소), 금융자산</td><td>(105)</td></tr>
            <tr><td>기타 변동에 따른 증가(감소), 금융자산</td><td>0</td></tr>
            <tr><td>기말금융자산</td><td>(136,687)</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", -136_687_000, -136_688_000)
    ]
    assert checks[0].title == "손실충당금 변동표 검산 - trade_receivables_loss_allowance"
    assert checks[0].tolerance == 1000
    assert checks[0].evidence[0].source == "note:5/table:0/row:4/col:1"


def test_check_layout_formula_assertions_validates_financial_fair_value_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>34. 금융상품</p>
          <p>금융자산의 공정가치 공시 당기 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>공정가치</th></tr>
            <tr><td>현금및현금성자산</td><td>83,682,420</td></tr>
            <tr><td>단기금융상품</td><td>20,000,000</td></tr>
            <tr><td>매출채권및기타채권 (주1)</td><td>93,397,239</td></tr>
            <tr><td>기타비유동금융자산</td><td>7,976,518</td></tr>
            <tr><td>금융자산</td><td>205,056,177</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 205_056_177_000, 205_056_177_000)
    ]
    assert checks[0].title == "금융상품 공정가치 합계 검산"
    assert checks[0].evidence[-1].source == "note:34/table:0/row:5/col:1"


def test_check_layout_formula_assertions_validates_credit_risk_exposure_row_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>23. 금융상품</p>
          <p>신용위험에 대한 최대 노출정도 (단위 : 백만원)</p>
          <table>
            <tr><th></th><th></th><th>현금성자산</th><th>매출채권및기타채권</th><th>기타금융자산</th><th>금융상품 합계</th></tr>
            <tr><td>신용위험에 대한 최대 노출정도</td><td>신용위험에 대한 최대 노출정도</td><td>94,319</td><td>43,905</td><td>145,521</td><td>283,745</td></tr>
            <tr><td>신용위험에 대한 최대 노출정도</td><td>신용위험에 대한 최대 노출정도 - 유동</td><td>94,319</td><td>43,905</td><td>30,039</td><td>168,263</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 283_745_000_000, 283_745_000_000),
        ("note_layout_formula_check", "matched", 168_263_000_000, 168_263_000_000),
    ]
    assert checks[0].title == "신용위험 최대노출 합계 검산"
    assert checks[0].evidence[-1].source == "note:23/table:0/row:1/col:5"


def test_check_layout_formula_assertions_validates_financial_fair_value_level_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>6. 금융상품 공정가치</p>
          <p>공정가치 서열체계 (단위 : 천원)</p>
          <table>
            <tr><th>구 분</th><th>금융상품</th><th>(수준1)</th><th>(수준2)</th><th>(수준3)</th><th>합 계</th></tr>
            <tr><td>금융자산</td><td>당기손익-공정가치측정금융자산</td><td>127</td><td>700</td><td>3,803</td><td>4,630</td></tr>
            <tr><td>금융자산</td><td>파생상품(위험회피목적)</td><td>-</td><td>134</td><td>-</td><td>134</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 4_630_000, 4_630_000),
        ("note_layout_formula_check", "matched", 134_000, 134_000),
    ]
    assert checks[0].title == "금융상품 공정가치 수준별 합계 검산 - financial_assets_fvtpl"
    assert checks[0].evidence[-1].source == "note:6/table:0/row:1/col:5"


def test_check_layout_formula_assertions_validates_tax_expense_composition_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>35. 법인세비용</p>
          <p>법인세비용의 구성내용은 다음과 같습니다. (단위 : 천원)</p>
          <table>
            <tr><th>구 분</th><th>당기</th><th>전기</th></tr>
            <tr><td>법인세등 부담액</td><td>11,977,263</td><td>11,998,514</td></tr>
            <tr><td>일시적차이 등으로 인한 이연법인세 변동액</td><td>483,495</td><td>(1,697,799)</td></tr>
            <tr><td>자본에 직접 가감된 법인세부담액</td><td>183,151</td><td>1,023,122</td></tr>
            <tr><td>법인세비용</td><td>12,643,908</td><td>11,323,837</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 12_643_908_000, 12_643_909_000),
        ("note_layout_formula_check", "matched", 11_323_837_000, 11_323_837_000),
    ]
    assert checks[0].title == "법인세비용 구성 검산 - 당기"
    assert checks[0].evidence[-1].source == "note:35/table:0/row:4/col:1"


def test_check_layout_formula_assertions_validates_financial_category_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>6. 범주별 금융상품</p>
          <p>당기말 금융상품 범주별 장부금액 (단위 : 천원)</p>
          <table>
            <tr><th>구분</th><th>상각후원가측정 금융자산</th><th>당기손익-공정가치측정 금융자산</th><th>상각후원가측정 금융부채</th><th>당기손익-공정가치측정 금융부채</th><th>합 계</th></tr>
            <tr><td>금융자산</td><td></td><td></td><td></td><td></td><td></td></tr>
            <tr><td>현금및현금성자산</td><td>100</td><td></td><td></td><td></td><td>100</td></tr>
            <tr><td>매출채권</td><td>250</td><td></td><td></td><td></td><td>250</td></tr>
            <tr><td>기타금융자산</td><td>30</td><td>20</td><td></td><td></td><td>50</td></tr>
            <tr><td>금융부채</td><td></td><td></td><td></td><td></td><td></td></tr>
            <tr><td>매입채무</td><td></td><td></td><td>70</td><td></td><td>70</td></tr>
            <tr><td>파생상품부채</td><td></td><td></td><td></td><td>5</td><td>5</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 100_000, 100_000),
        ("note_layout_formula_check", "matched", 250_000, 250_000),
        ("note_layout_formula_check", "matched", 50_000, 50_000),
        ("note_layout_formula_check", "matched", 70_000, 70_000),
        ("note_layout_formula_check", "matched", 5_000, 5_000),
    ]
    assert checks[0].title == "금융상품 범주별 합계 검산 - cash_and_cash_equivalents"
    assert checks[0].evidence[-1].source == "note:6/table:0/row:2/col:5"


def test_check_layout_formula_assertions_validates_financial_category_column_totals(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>6. 범주별 금융상품</p>
          <p>당기말 금융상품 범주별 장부금액 (단위 : 천원)</p>
          <table>
            <tr><th>구분</th><th>상각후원가측정 금융자산</th><th>당기손익-공정가치측정 금융자산</th><th>기타포괄손익-공정가치측정 금융자산</th></tr>
            <tr><td>현금및현금성자산</td><td>100</td><td></td><td></td></tr>
            <tr><td>매출채권</td><td>250</td><td></td><td></td></tr>
            <tr><td>기타금융자산</td><td>30</td><td>20</td><td>10</td></tr>
            <tr><td>합계</td><td>380</td><td>20</td><td>10</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 380_000, 380_000),
        ("note_layout_formula_check", "matched", 20_000, 20_000),
        ("note_layout_formula_check", "matched", 10_000, 10_000),
    ]
    assert checks[0].title == "금융상품 범주별 열 합계 검산 - 상각후원가측정금융자산"
    assert checks[0].evidence[-1].source == "note:6/table:0/row:4/col:1"


def test_check_layout_formula_assertions_validates_receivable_present_value_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>8. 매출채권 및 기타채권</p>
          <p>당기 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>총장부금액</th><th>현재가치할인차금</th><th>손실충당금</th><th>장부금액 합계</th></tr>
            <tr><td>유동매출채권</td><td>1,000</td><td>0</td><td>(100)</td><td>900</td></tr>
            <tr><td>장기미수금</td><td>2,000</td><td>(300)</td><td>0</td><td>1,700</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 900_000, 900_000),
        ("note_layout_formula_check", "matched", 1_700_000, 1_700_000),
    ]
    assert checks[0].title == "매출채권 장부금액 구성 검산 - trade_receivables"
    assert checks[0].evidence[-1].source == "note:8/table:0/row:1/col:4"


def test_check_layout_formula_assertions_validates_receivable_loss_allowance_carrying_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>5. 매출채권, 대여금 및 기타채권</p>
          <p>매출채권 및 기타채권의 공시 당기 (단위 : 백만원)</p>
          <table>
            <tr><th></th><th>총장부금액</th><th>차감: 손실충당금</th><th>장부금액 합계</th></tr>
            <tr><td>유동매출채권</td><td>1,434,687</td><td>(4,647)</td><td>1,430,040</td></tr>
            <tr><td>비유동매출채권</td><td>468</td><td>(428)</td><td>40</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 1_430_040_000_000, 1_430_040_000_000),
        ("note_layout_formula_check", "matched", 40_000_000, 40_000_000),
    ]
    assert checks[0].title == "매출채권 장부금액 구성 검산 - trade_receivables"
    assert checks[0].evidence[-1].source == "note:5/table:0/row:1/col:3"


def test_check_layout_formula_assertions_validates_receivable_two_label_columns(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>5. 매출채권, 대여금 및 기타채권</p>
          <p>대여금 및 기타채권의 공시 당기 (단위 : 백만원)</p>
          <table>
            <tr><th></th><th></th><th>총장부금액</th><th>차감: 손실충당금</th><th>장부금액 합계</th></tr>
            <tr><td>유동</td><td>유동</td><td>104,390</td><td>(6,206)</td><td>98,184</td></tr>
            <tr><td>유동</td><td>미수금</td><td>104,390</td><td>(6,206)</td><td>98,184</td></tr>
            <tr><td>유동</td><td>대여금</td><td>0</td><td>0</td><td>0</td></tr>
            <tr><td>기타 비유동채권</td><td>장기미수금</td><td>33,214</td><td>0</td><td>33,214</td></tr>
            <tr><td>기타 비유동채권</td><td>보증금</td><td>16,278</td><td>0</td><td>16,278</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.status, check.expected, check.actual) for check in checks] == [
        ("matched", 98_184_000_000, 98_184_000_000),
        ("matched", 0, 0),
        ("matched", 33_214_000_000, 33_214_000_000),
        ("matched", 16_278_000_000, 16_278_000_000),
    ]
    assert checks[0].title == "매출채권 장부금액 구성 검산 - short_term_other_receivables"
    assert checks[0].evidence[-1].source == "note:5/table:0/row:2/col:4"


def test_check_layout_formula_assertions_validates_receivable_loss_allowance_aging_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>8. 매출채권</p>
          <p>매출채권 손실충당금의 상세내역</p>
          <table>
            <tr><th>구 분</th><th>6개월 이내 연체 및 정상</th><th>6개월 초과 1년 이내 연체</th><th>1년 초과 연체</th><th>합 계</th></tr>
            <tr><td>총 장부금액</td><td>194,209,849</td><td>8,119,664</td><td>29,657</td><td>202,359,170</td></tr>
            <tr><td>손실충당금</td><td>1,158</td><td>69,660</td><td>29,657</td><td>100,475</td></tr>
            <tr><td>기대 손실률</td><td>0.00</td><td>0.86</td><td>100.00</td><td>0.05</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 202_359_170, 202_359_170),
        ("note_layout_formula_check", "matched", 100_475, 100_475),
    ]
    assert checks[0].title == "매출채권 연체구간 합계 검산 - 총 장부금액"
    assert checks[0].evidence[-1].source == "note:8/table:0/row:1/col:4"


def test_check_layout_formula_assertions_validates_inventory_carrying_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>8. 재고자산</p>
          <p>당기 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>총장부금액</th><th>재고자산 평가충당금</th><th>장부금액 합계</th></tr>
            <tr><td>유동상품</td><td>1,000</td><td>(100)</td><td>900</td></tr>
            <tr><td>유동제품</td><td>2,000</td><td>0</td><td>2,000</td></tr>
            <tr><td>유동재고자산</td><td>3,000</td><td>(100)</td><td>2,900</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 900_000, 900_000),
        ("note_layout_formula_check", "matched", 2_000_000, 2_000_000),
        ("note_layout_formula_check", "matched", 2_900_000, 2_900_000),
    ]
    assert checks[0].title == "재고자산 장부금액 구성 검산 - inventory_goods"
    assert checks[0].evidence[-1].source == "note:8/table:0/row:1/col:3"


def test_check_layout_formula_assertions_validates_functional_expense_research_allocation(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>10. 무형자산</p>
          <p>경상연구개발비 지출액 당기 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>매출원가</th><th>판매비와 일반관리비</th><th>기능별 항목 합계</th></tr>
            <tr><td>연구와 개발 비용</td><td>16,738,912</td><td>1,284,890</td><td>18,023,802</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 18_023_802_000, 18_023_802_000)
    ]
    assert checks[0].title == "연구개발비 기능별 배부 합계 검산"
    assert checks[0].evidence[-1].source == "note:10/table:0/row:1/col:3"


def test_check_layout_formula_assertions_validates_employee_benefit_expense_allocation(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>16. 퇴직급여제도</p>
          <p>당기 및 전기 중 확정급여제도와 관련하여 인식된 손익은 다음과 같습니다. 한편, 각 항목별로 배분된 확정급여제도 손익은 다음과 같습니다.</p>
          <table>
            <tr><th>구분</th><th>당기</th><th>전기</th></tr>
            <tr><td>판관비에 포함된 금액</td><td>2,548,827</td><td>2,723,163</td></tr>
            <tr><td>매출원가에 포함된 금액</td><td>641,676</td><td>628,174</td></tr>
            <tr><td>합계</td><td>3,190,503</td><td>3,351,337</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 3_190_503, 3_190_503),
        ("note_layout_formula_check", "matched", 3_351_337, 3_351_337),
    ]
    assert checks[0].title == "퇴직급여 비용 배부 합계 검산 - 당기"
    assert checks[0].evidence[-1].source == "note:16/table:0/row:3/col:1"


def test_check_layout_formula_assertions_validates_row_oriented_provision_rollforward(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>18. 충당부채</p>
          <p>기타충당부채의 변동 당기 (단위 : 천원)</p>
          <table>
            <tr><th></th><th></th><th>복구충당부채</th><th>기타장기종업원급여부채</th></tr>
            <tr><td>기초 기타충당부채</td><td>기초 기타충당부채</td><td>778,101</td><td>1,697,795</td></tr>
            <tr><td>기타충당부채의 변동에 대한 조정</td><td>당기에 추가된 충당부채 합계, 기타충당부채</td><td>279,165</td><td>312,625</td></tr>
            <tr><td>기타충당부채의 변동에 대한 조정</td><td>사용된 충당부채, 기타충당부채</td><td>0</td><td>(150,000)</td></tr>
            <tr><td>기말 기타충당부채</td><td>기말 기타충당부채</td><td>1,057,266</td><td>1,860,420</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 1_057_266_000, 1_057_266_000),
        ("note_layout_formula_check", "matched", 1_860_420_000, 1_860_420_000),
    ]
    assert checks[0].title == "충당부채 증감표 검산 - restoration_provision"


def test_check_layout_formula_assertions_validates_provision_current_noncurrent_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>17. 충당부채</p>
          <p>기타충당부채 구성 (단위 : 천원)</p>
          <table>
            <tr><th></th><th></th><th>유동</th><th>비유동</th></tr>
            <tr><td>복구충당부채</td><td>복구충당부채</td><td>100</td><td>1,000</td></tr>
            <tr><td>판매보증충당부채</td><td>판매보증충당부채</td><td>30</td><td>2,000</td></tr>
            <tr><td>기타장기종업원급여부채</td><td>기타장기종업원급여부채</td><td>12</td><td>3,000</td></tr>
            <tr><td>기타충당부채 합계</td><td>기타충당부채 합계</td><td>142</td><td>6,000</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 142_000, 142_000),
        ("note_layout_formula_check", "matched", 6_000_000, 6_000_000),
    ]
    assert checks[0].title == "충당부채 유동/비유동 구성 합계 검산 - current_provisions"
    assert checks[0].evidence[-1].source == "note:17/table:0/row:4/col:2"


def test_check_layout_formula_assertions_validates_defined_benefit_rollforward(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>18. 퇴직급여제도</p>
          <table>
            <tr><th></th><th></th><th>확정급여채무의 현재가치</th><th>사외적립자산</th></tr>
            <tr><td>기초</td><td>기초</td><td>100</td><td>70</td></tr>
            <tr><td>당기근무원가</td><td>당기근무원가</td><td>30</td><td>0</td></tr>
            <tr><td>이자비용(이자수익)</td><td>이자비용(이자수익)</td><td>5</td><td>(3)</td></tr>
            <tr><td>기말</td><td>기말</td><td>135</td><td>67</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 135, 135),
        ("note_layout_formula_check", "matched", 67, 67),
    ]
    assert checks[0].title == "확정급여 변동표 검산 - defined_benefit_obligation"


def test_check_layout_formula_assertions_validates_employee_benefit_maturity_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>19. 퇴직급여제도</p>
          <p>확정급여채무의 만기구성에 대한 정보의 공시 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>1년 이내</th><th>1년 초과 5년 이내</th><th>5년 초과 10년 이내</th><th>10년 초과</th><th>합계 구간 합계</th></tr>
            <tr><td>확정급여제도에서 지급될 것으로 예상되는 급여 지급액 추정치</td><td>8,537,047</td><td>45,919,845</td><td>12,261,563</td><td>42,020,488</td><td>108,738,943</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 108_738_943_000, 108_738_943_000)
    ]
    assert checks[0].title == "확정급여 지급예상액 만기 합계 검산"
    assert checks[0].evidence[-1].source == "note:19/table:0/row:1/col:5"


def test_check_layout_formula_assertions_validates_employee_benefit_expected_contribution_maturity_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>18. 퇴직급여제도</p>
          <p>확정급여제도의 예상 기여금 만기구성 (단위 : 백만원)</p>
          <table>
            <tr><th></th><th>1년 이내</th><th>1년 초과 2년 이내</th><th>2년 초과 5년 이내</th><th>5년 초과</th><th>합계 구간 합계</th></tr>
            <tr><td>다음 연차보고기간 동안에 납부할 것으로 예상되는 기여금에 대한 추정치</td><td>13,535</td><td>22,099</td><td>63,885</td><td>271,840</td><td>371,359</td></tr>
            <tr><td>확정급여채무의 가중평균만기</td><td></td><td></td><td></td><td></td><td>8년9개월</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 371_359_000_000, 371_359_000_000)
    ]
    assert checks[0].title == "확정급여 예상기여금 만기 합계 검산"
    assert checks[0].evidence[-1].source == "note:18/table:0/row:1/col:5"


def test_check_layout_formula_assertions_validates_borrowing_detail_present_value_split(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>20. 차입금</p>
          <p>장기차입금에 대한 세부 정보 공시 당기 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>차입금명칭</th><th>차입금명칭</th><th>차입금명칭 합계</th></tr>
            <tr><td>차입금, 만기</td><td></td><td>2032-12-20</td><td></td></tr>
            <tr><td>차입금, 이자율</td><td>0.0198</td><td>0.0492</td><td></td></tr>
            <tr><td>명목금액</td><td></td><td>270,060,586</td><td>466,697,117</td></tr>
            <tr><td>현재가치할인차금</td><td></td><td></td><td>(3,339,418)</td></tr>
            <tr><td>유동 금융기관 차입금 및 비유동 금융기관 차입금(사채 제외)의 유동성 대체 부분</td><td></td><td></td><td>(58,973,133)</td></tr>
            <tr><td>비유동 금융기관 차입금(사채 제외)의 비유동성 대체 부분</td><td></td><td></td><td>404,384,566</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 404_384_566_000, 404_384_566_000)
    ]
    assert checks[0].title == "차입금/사채 상세표 검산 - borrowings"
    assert checks[0].evidence[-1].source == "note:20/table:0/row:6/col:3"


def test_check_layout_formula_assertions_validates_bond_component_columns(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>15. 차입금 및 사채</p>
          <p>사채의 세부내역에 대한 공시 당기 (단위 : 백만원)</p>
          <table>
            <tr><th></th><th></th><th></th><th>발행일</th><th>만기일</th><th>차입금, 이자율</th><th>명목금액</th><th>차감: 유동성사채</th><th>차감: 사채할인발행차금</th><th>비유동 사채의 비유동성 부분</th></tr>
            <tr><td>차입금명칭</td><td>사채</td><td>제83-2회공모사채</td><td>2020-02-20</td><td>2025-02-20</td><td>0.0198</td><td>50,000</td><td></td><td></td><td></td></tr>
            <tr><td>차입금명칭</td><td>사채</td><td>제85-2회공모사채</td><td>2021-04-12</td><td>2026-04-12</td><td>0.0196</td><td>50,000</td><td></td><td></td><td></td></tr>
            <tr><td>차입금명칭 합계</td><td>차입금명칭 합계</td><td>차입금명칭 합계</td><td></td><td></td><td></td><td>100,000</td><td>(50,000)</td><td>(68)</td><td>49,932</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 49_932_000_000, 49_932_000_000)
    ]
    assert checks[0].title == "차입금/사채 상세표 검산 - bonds"
    assert checks[0].evidence[-1].source == "note:15/table:0/row:3/col:9"


def test_check_layout_formula_assertions_validates_asset_component_column_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>13. 무형자산 및 영업권</p>
          <p>개발비 현황 주요 개발비 현황 공시 (단위 : 백만원)</p>
          <table>
            <tr><th></th><th></th><th></th><th></th><th>상각자산</th><th>개발 중인 무형자산</th><th>장부금액</th></tr>
            <tr><td>무형자산 및 영업권</td><td>자본화된 개발비 지출액</td><td>부문</td><td>차량부품</td><td>26,765</td><td>37,868</td><td>64,633</td></tr>
            <tr><td>무형자산 및 영업권</td><td>자본화된 개발비 지출액</td><td>부문</td><td>특수</td><td>3,326</td><td>519</td><td>3,845</td></tr>
            <tr><td>무형자산 및 영업권 합계</td><td>무형자산 및 영업권 합계</td><td>무형자산 및 영업권 합계</td><td>무형자산 및 영업권 합계</td><td>30,091</td><td>38,387</td><td>68,478</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 64_633_000_000, 64_633_000_000),
        ("note_layout_formula_check", "matched", 3_845_000_000, 3_845_000_000),
        ("note_layout_formula_check", "matched", 68_478_000_000, 68_478_000_000),
    ]
    assert checks[0].title == "자산 구성열 합계 검산 - 차량부품"
    assert checks[0].evidence[-1].source == "note:13/table:0/row:1/col:6"


def test_check_layout_formula_assertions_skips_parse_uncertain_debt_detail(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>20. 차입금</p>
          <p>장기차입금에 대한 세부 정보 공시 당기 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>차입금명칭</th><th>차입금명칭 합계</th></tr>
            <tr><td>차입금, 만기</td><td>2032-12-20</td><td></td></tr>
            <tr><td>차입금, 이자율</td><td>0.0198</td><td></td></tr>
            <tr><td>명목금액</td><td>270,060,586</td><td>270,060,586</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert checks == []


def test_check_layout_formula_assertions_skips_nonclosing_debt_detail(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>20. 차입금</p>
          <p>장기차입금에 대한 세부 정보 공시 당기 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>차입금명칭</th><th>차입금명칭</th><th>차입금명칭 합계</th></tr>
            <tr><td>차입금, 만기</td><td></td><td>2032-12-20</td><td></td></tr>
            <tr><td>차입금, 이자율</td><td>0.0198</td><td>0.0492</td><td></td></tr>
            <tr><td>명목금액</td><td></td><td>270,060,586</td><td>466,697,117</td></tr>
            <tr><td>현재가치할인차금</td><td></td><td></td><td>(3,339,418)</td></tr>
            <tr><td>유동 금융기관 차입금 및 비유동 금융기관 차입금(사채 제외)의 유동성 대체 부분</td><td></td><td></td><td>(58,973,133)</td></tr>
            <tr><td>비유동 금융기관 차입금(사채 제외)의 비유동성 대체 부분</td><td></td><td></td><td>404,538,406</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert checks == []


def test_check_layout_formula_assertions_validates_lease_liability_maturity_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>15. 사용권자산 및 리스부채</p>
          <p>리스부채 만기분석 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>1년 이내</th><th>1년 초과 5년 이내</th><th>5년 초과</th><th>합계 구간 합계</th></tr>
            <tr><td>최소리스료</td><td>76,705,355</td><td>48,461,726</td><td>3,894,487</td><td>129,061,568</td></tr>
            <tr><td>리스부채에 대한 이자비용</td><td>18,865,338</td><td>31,254,580</td><td>627,365</td><td>50,747,283</td></tr>
            <tr><td>최소리스료의 현재가치</td><td>57,840,017</td><td>17,207,146</td><td>3,267,122</td><td>78,314,285</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 129_061_568_000, 129_061_568_000),
        ("note_layout_formula_check", "matched", 50_747_283_000, 50_747_283_000),
        ("note_layout_formula_check", "matched", 78_314_285_000, 78_314_285_000),
    ]
    assert checks[0].title == "리스부채 만기 합계 검산 - minimum_lease_payments"
    assert checks[0].evidence[-1].source == "note:15/table:0/row:1/col:4"


def test_check_layout_formula_assertions_validates_lease_liability_current_noncurrent_summary(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>34. 리스</p>
          <p>리스부채 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>공시금액</th></tr>
            <tr><td>유동 리스부채</td><td>1,200</td></tr>
            <tr><td>비유동 리스부채</td><td>2,300</td></tr>
            <tr><td>합계</td><td>3,500</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 3_500_000, 3_500_000),
    ]
    assert checks[0].title == "리스부채 유동/비유동 합계 검산"
    assert checks[0].evidence[-1].source == "note:34/table:0/row:3/col:1"


def test_check_layout_formula_assertions_validates_financing_debt_bridge(tmp_path):
    source = tmp_path / "sample.html"
    source.write_text(
        """
        <html><body>
          <p>연결재무제표 주석</p>
          <p>37. 현금흐름표</p>
          <p>재무활동에서 생기는 부채의 조정에 관한 공시 (단위 : 천원)</p>
          <table>
            <tr><th></th><th>단기차입금</th><th>장기차입금</th></tr>
            <tr><td>재무활동에서 생기는 기초 부채</td><td>19,135</td><td>117,608</td></tr>
            <tr><td>차입금의 증가, 재무활동에서 생기는 부채</td><td>104,568</td><td>41,236</td></tr>
            <tr><td>차입금의 감소, 재무활동에서 생기는 부채</td><td>(54,502)</td><td>(37,159)</td></tr>
            <tr><td>그 밖의 변동, 재무활동에서 생기는 부채의 증가(감소)</td><td>0</td><td>283</td></tr>
            <tr><td>재무활동에서 생기는 기말 부채</td><td>69,201</td><td>121,968</td></tr>
          </table>
        </body></html>
        """,
        encoding="utf-8",
    )
    report = parse_full_report(source, company="Sample Co")

    checks = check_layout_formula_assertions(report, tolerance=1)

    assert [(check.check_type, check.status, check.expected, check.actual) for check in checks] == [
        ("note_layout_formula_check", "matched", 69_201_000, 69_201_000),
        ("note_layout_formula_check", "matched", 121_968_000, 121_968_000),
    ]
    assert checks[0].title == "재무활동 부채 변동표 검산 - short_term_borrowings"
