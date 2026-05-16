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
