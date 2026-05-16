from dart_footing_reconciler.scan import scan_html


def test_scan_html_returns_only_footable_tables() -> None:
    html = """
    <p>재무상태표</p>
    <table>
      <tr><th>구분</th><th>당기</th></tr>
      <tr><td>자산</td><td>1,000</td></tr>
    </table>
    <p>14. 유형자산</p>
    <p>(2) 보고기간 중 유형자산의 변동내용은 다음과 같습니다.</p>
    <table>
      <tr><th>구분</th><th>합계</th></tr>
      <tr><td>기초</td><td>1,000</td></tr>
      <tr><td>취득</td><td>500</td></tr>
      <tr><td>감가상각비</td><td>200</td></tr>
      <tr><td>기말</td><td>1,300</td></tr>
    </table>
    """

    results = scan_html(html)

    assert len(results) == 1
    assert results[0].status == "matched"
    assert "유형자산" in results[0].heading


def test_scan_html_skips_non_target_movement_tables_by_default() -> None:
    html = """
    <p>21. 자본금과 자본잉여금</p>
    <p>2) 자본금 및 주식발행초과금의 변동내용은 다음과 같습니다.</p>
    <table>
      <tr><th>구분</th><th>자본금</th></tr>
      <tr><td>기초</td><td>1,000</td></tr>
      <tr><td>증가</td><td>500</td></tr>
      <tr><td>기말</td><td>1,500</td></tr>
    </table>
    """

    assert scan_html(html) == []


def test_scan_html_skips_capital_table_even_when_convertible_bond_text_appears() -> None:
    html = """
    <p>21. 자본금과 자본잉여금</p>
    <p>2) 자본금 및 주식발행초과금의 변동내용은 다음과 같습니다.</p>
    <table>
      <tr><th>구분</th><th>자본금</th></tr>
      <tr><td>기초</td><td>1,000</td></tr>
      <tr><td>전환사채의 전환</td><td>500</td></tr>
      <tr><td>기말</td><td>1,500</td></tr>
    </table>
    """

    assert scan_html(html) == []


def test_scan_html_accepts_xbrl_style_target_table_without_movement_heading() -> None:
    html = """
    <p>17. 유형자산</p>
    <table>
      <tr><th></th><th>토지</th><th>유형자산 합계</th></tr>
      <tr><td>기초 유형자산</td><td>1,000</td><td>1,000</td></tr>
      <tr><td>취득 자본적지출</td><td>500</td><td>500</td></tr>
      <tr><td>처분 및 폐기</td><td>(100)</td><td>(100)</td></tr>
      <tr><td>기말 유형자산</td><td>1,400</td><td>1,400</td></tr>
    </table>
    """

    results = scan_html(html)

    assert len(results) == 1
    assert results[0].status == "matched"


def test_scan_html_skips_cash_flow_statement_even_with_target_line_items() -> None:
    html = """
    <p>2-5. 연결 현금흐름표</p>
    <table>
      <tr><th>구분</th><th>당기</th><th>전기</th></tr>
      <tr><td>기초 현금및현금성자산</td><td>1,000</td><td>900</td></tr>
      <tr><td>유형자산의 취득</td><td>(500)</td><td>(400)</td></tr>
      <tr><td>기말 현금및현금성자산</td><td>700</td><td>1,000</td></tr>
    </table>
    """

    assert scan_html(html) == []


def test_scan_html_skips_table_when_previous_target_section_contaminates_heading() -> None:
    html = """
    <p>21. 차입금 및 사채</p>
    <p>22. 종업원급여</p>
    <table>
      <tr><th>구분</th><th>확정급여채무</th><th>사외적립자산</th></tr>
      <tr><td>기초</td><td>1,000</td><td>(900)</td></tr>
      <tr><td>당기근무원가</td><td>100</td><td>-</td></tr>
      <tr><td>기말</td><td>1,100</td><td>(900)</td></tr>
    </table>
    """

    assert scan_html(html) == []
