from dart_footing_reconciler.footing import foot_table
from dart_footing_reconciler.html_tables import extract_tables


def test_foot_table_matches_signed_movement_rows() -> None:
    html = """
    <p>15. 무형자산</p>
    <p>(2) 당기와 전기 중 무형자산의 변동내용은 다음과 같습니다.</p>
    <table>
      <tr><th>구분</th><th>소프트웨어</th><th>합계</th></tr>
      <tr><td>기초장부금액</td><td>1,000</td><td>1,000</td></tr>
      <tr><td>취득</td><td>250</td><td>250</td></tr>
      <tr><td>상각비</td><td>(100)</td><td>(100)</td></tr>
      <tr><td>기말장부금액</td><td>1,150</td><td>1,150</td></tr>
    </table>
    """

    result = foot_table(extract_tables(html)[0])

    assert result.status == "matched"
    assert result.columns[0].label == "소프트웨어"
    assert result.columns[0].expected == 1150
    assert result.columns[0].actual == 1150
    assert result.columns[0].difference == 0


def test_foot_table_applies_label_polarity_when_contra_row_is_positive() -> None:
    html = """
    <p>14. 유형자산</p>
    <p>(2) 보고기간 중 유형자산의 변동내용은 다음과 같습니다.</p>
    <table>
      <tr><th>구분</th><th>차량운반구</th><th>합계</th></tr>
      <tr><td>기초</td><td>1,000</td><td>1,000</td></tr>
      <tr><td>취득</td><td>500</td><td>500</td></tr>
      <tr><td>감가상각비</td><td>200</td><td>200</td></tr>
      <tr><td>기말</td><td>1,300</td><td>1,300</td></tr>
    </table>
    """

    result = foot_table(extract_tables(html)[0])

    assert result.status == "matched"
    assert result.columns[0].expected == 1300


def test_foot_table_reports_unexplained_gap() -> None:
    html = """
    <p>14. 유형자산</p>
    <table>
      <tr><th>구분</th><th>합계</th></tr>
      <tr><td>기초</td><td>1,000</td></tr>
      <tr><td>취득</td><td>500</td></tr>
      <tr><td>처분</td><td>100</td></tr>
      <tr><td>기말</td><td>1,200</td></tr>
    </table>
    """

    result = foot_table(extract_tables(html)[0])

    assert result.status == "unexplained_gap"
    assert result.columns[0].expected == 1400
    assert result.columns[0].actual == 1200
    assert result.columns[0].difference == -200


def test_foot_table_ignores_beginning_and_ending_detail_rows() -> None:
    html = """
    <p>10. 리스</p>
    <p>사용권자산 장부금액의 변동내역은 다음과 같습니다.</p>
    <table>
      <tr><th>구분</th><th>부동산</th><th>합계</th></tr>
      <tr><td>기초 장부금액</td><td>5,336</td><td>5,336</td></tr>
      <tr><td>기초 취득원가</td><td>7,696</td><td>7,696</td></tr>
      <tr><td>기초 상각누계액</td><td>(2,360)</td><td>(2,360)</td></tr>
      <tr><td>증가</td><td>2,116</td><td>2,116</td></tr>
      <tr><td>감가상각</td><td>(2,685)</td><td>(2,685)</td></tr>
      <tr><td>기타</td><td>(8)</td><td>(8)</td></tr>
      <tr><td>기말 장부금액</td><td>4,759</td><td>4,759</td></tr>
      <tr><td>기말 취득원가</td><td>8,775</td><td>8,775</td></tr>
      <tr><td>기말 상각누계액</td><td>(4,016)</td><td>(4,016)</td></tr>
    </table>
    """

    result = foot_table(extract_tables(html)[0], tolerance=1)

    assert result.status == "matched"
    assert result.columns[0].expected == 4759


def test_foot_table_prefers_carrying_amount_when_detail_rows_come_first() -> None:
    html = """
    <p>9. 유형자산</p>
    <table>
      <tr><th>구분</th><th>합계</th></tr>
      <tr><td>기초 취득원가</td><td>1,900</td></tr>
      <tr><td>기초 감가상각누계액</td><td>(900)</td></tr>
      <tr><td>기초 손상차손누계액</td><td>(50)</td></tr>
      <tr><td>기초 장부금액</td><td>1,000</td></tr>
      <tr><td>취득</td><td>500</td></tr>
      <tr><td>감가상각</td><td>(200)</td></tr>
      <tr><td>기말 장부금액</td><td>1,300</td></tr>
      <tr><td>기말 취득원가</td><td>2,400</td></tr>
      <tr><td>기말 감가상각누계액</td><td>(1,100)</td></tr>
      <tr><td>기말 손상차손누계액</td><td>(50)</td></tr>
    </table>
    """

    result = foot_table(extract_tables(html)[0])

    assert result.status == "matched"
    assert result.columns[0].expected == 1300


def test_foot_table_ignores_composition_rows_after_ending_balance() -> None:
    html = """
    <p>13. 유형자산</p>
    <p>유형자산 장부금액의 변동내역 및 구성내역은 다음과 같습니다.</p>
    <table>
      <tr><th>구분</th><th>합계</th></tr>
      <tr><td>(변동내역)</td><td>(변동내역)</td></tr>
      <tr><td>기초금액</td><td>1,000</td></tr>
      <tr><td>취득</td><td>500</td></tr>
      <tr><td>감가상각</td><td>(200)</td></tr>
      <tr><td>기말금액</td><td>1,300</td></tr>
      <tr><td>(구성내역)</td><td>(구성내역)</td></tr>
      <tr><td>취득원가</td><td>2,400</td></tr>
      <tr><td>감가상각누계액</td><td>(1,100)</td></tr>
      <tr><td>장부금액</td><td>1,300</td></tr>
    </table>
    """

    result = foot_table(extract_tables(html)[0])

    assert result.status == "matched"
    assert result.columns[0].expected == 1300


def test_foot_table_preserves_displayed_sign_for_transfer_revaluation_and_fx_rows() -> None:
    html = """
    <p>12. 유형자산</p>
    <table>
      <tr><th>구분</th><th>합계</th></tr>
      <tr><td>기초 유형자산</td><td>1,000</td></tr>
      <tr><td>재평가로 인한 증가(감소), 유형자산</td><td>300</td></tr>
      <tr><td>대체에 따른 증가(감소), 유형자산</td><td>(100)</td></tr>
      <tr><td>손상 누계 대체</td><td>50</td></tr>
      <tr><td>순외환차이에 의한 증가(감소), 유형자산</td><td>(20)</td></tr>
      <tr><td>기말 유형자산</td><td>1,230</td></tr>
    </table>
    """

    result = foot_table(extract_tables(html)[0])

    assert result.status == "matched"
    assert result.columns[0].expected == 1230


def test_foot_table_skips_gross_cost_and_accumulated_depreciation_columns() -> None:
    html = """
    <p>16. 투자부동산</p>
    <table>
      <tr><th></th><th>총장부금액</th><th>감가상각누계액 및 상각누계액</th><th>장부금액 합계</th></tr>
      <tr><td>기초 투자부동산</td><td>1,000</td><td>(400)</td><td>600</td></tr>
      <tr><td>취득, 투자부동산</td><td></td><td></td><td>300</td></tr>
      <tr><td>감가상각비, 투자부동산</td><td></td><td></td><td>(100)</td></tr>
      <tr><td>기말 투자부동산</td><td>1,500</td><td>(700)</td><td>800</td></tr>
    </table>
    """

    result = foot_table(extract_tables(html)[0])

    assert result.status == "matched"
    assert [column.label for column in result.columns] == ["장부금액 합계"]
    assert result.columns[0].expected == 800


def test_foot_table_treats_positive_amortization_as_increase_for_bond_liabilities() -> None:
    html = """
    <p>20. 전환사채</p>
    <p>당기 중 전환사채의 변동내역은 다음과 같습니다.</p>
    <table>
      <tr><th>구분</th><th>전환권조정</th><th>합계</th></tr>
      <tr><td>기초금액</td><td>(1,000)</td><td>9,000</td></tr>
      <tr><td>발행금액</td><td>(500)</td><td>4,500</td></tr>
      <tr><td>상각</td><td>200</td><td>200</td></tr>
      <tr><td>기말금액</td><td>(1,300)</td><td>13,700</td></tr>
    </table>
    """

    result = foot_table(extract_tables(html)[0])

    assert result.status == "matched"
    assert [column.expected for column in result.columns] == [-1300, 13700]


def test_foot_table_excludes_subtotal_row_from_movement_sum() -> None:
    """소계 행이 movement 합산에서 제외되어 이중계상이 차단되는지 검증.

    취득 300 + 취득 200 = 소계 500 (이 소계가 합산에서 제외돼야 함)
    감가상각 (100) → 기말 = 1000 + 300 + 200 - 100 = 1400
    소계가 포함되면 1000 + 300 + 200 + 500 - 100 = 1900 (오류)
    """
    html = """
    <table>
      <tr><th>구분</th><th>합계</th></tr>
      <tr><td>기초장부금액</td><td>1,000</td></tr>
      <tr><td>건물 취득</td><td>300</td></tr>
      <tr><td>기계 취득</td><td>200</td></tr>
      <tr><td>소계</td><td>500</td></tr>
      <tr><td>감가상각</td><td>(100)</td></tr>
      <tr><td>기말장부금액</td><td>1,400</td></tr>
    </table>
    """
    result = foot_table(extract_tables(html)[0])
    assert result.status == "matched"
    assert result.columns[0].expected == 1400


def test_foot_table_excludes_합계_row_from_movement_sum() -> None:
    """'합계' 레이블 행이 중간 소계로 존재할 때 이중계상 없이 footing이 맞는지 검증."""
    html = """
    <table>
      <tr><th>구분</th><th>금액</th></tr>
      <tr><td>기초잔액</td><td>500</td></tr>
      <tr><td>증가</td><td>100</td></tr>
      <tr><td>감소</td><td>(50)</td></tr>
      <tr><td>합계</td><td>50</td></tr>
      <tr><td>기말잔액</td><td>550</td></tr>
    </table>
    """
    result = foot_table(extract_tables(html)[0])
    assert result.status == "matched"
    assert result.columns[0].expected == 550


def test_foot_table_does_not_exclude_valid_movement_with_합계_in_label() -> None:
    """'장부금액합계' 처럼 합계가 포함된 긴 레이블은 소계 행으로 처리하지 않음."""
    html = """
    <table>
      <tr><th>구분</th><th>금액</th></tr>
      <tr><td>기초장부금액</td><td>800</td></tr>
      <tr><td>취득원가증가합계</td><td>200</td></tr>
      <tr><td>기말장부금액</td><td>1,000</td></tr>
    </table>
    """
    result = foot_table(extract_tables(html)[0])
    assert result.status == "matched"
    assert result.columns[0].expected == 1000
