from dart_footing_reconciler.html_tables import extract_tables


def test_extract_tables_keeps_nearby_heading_and_expands_colspan() -> None:
    html = """
    <p>14. 유형자산</p>
    <p>(2) 보고기간 중 유형자산의 변동내용은 다음과 같습니다.</p>
    <table>
      <tr><th rowspan="2">구분</th><th colspan="2">당기</th></tr>
      <tr><th>기계장치</th><th>합계</th></tr>
      <tr><td>기초</td><td>100</td><td>100</td></tr>
      <tr><td>취득</td><td>50</td><td>50</td></tr>
      <tr><td>감가상각비</td><td>10</td><td>10</td></tr>
      <tr><td>기말</td><td>140</td><td>140</td></tr>
    </table>
    """

    table = extract_tables(html)[0]

    assert table.heading == "14. 유형자산 (2) 보고기간 중 유형자산의 변동내용은 다음과 같습니다."
    assert table.rows[0].cells == ["구분", "당기", "당기"]
    assert table.rows[1].cells == ["구분", "기계장치", "합계"]
    assert table.rows[3].cells == ["취득", "50", "50"]


def test_extract_tables_preserves_cell_source_lines() -> None:
    html = """
    <p>14. 유형자산</p>
    <table>
      <tr><th>구분</th><th>합계</th></tr>
      <tr><td>기초</td><td>1,000</td></tr>
      <tr><td>취득</td><td>500</td></tr>
      <tr><td>기말</td><td>1,500</td></tr>
    </table>
    """

    table = extract_tables(html)[0]

    assert table.rows[1].source_line == 5
    assert table.rows[1].cell_source_lines == [5, 5]


def test_extract_tables_skips_layout_container_around_nested_data_table() -> None:
    html = """
    <p>7. 유형자산</p>
    <table>
      <tr>
        <td>
          <p>설명 문단</p>
          <table>
            <tr><td>구분</td><td>금액</td></tr>
            <tr><td>기말</td><td>100</td></tr>
          </table>
        </td>
      </tr>
    </table>
    """

    tables = extract_tables(html)

    assert len(tables) == 1
    assert tables[0].heading == "7. 유형자산"
    assert [row.cells for row in tables[0].rows] == [["구분", "금액"], ["기말", "100"]]


def test_extract_tables_reads_thead_tbody_rows_without_nested_rows() -> None:
    html = """
    <p>8. 매출채권</p>
    <table>
      <thead><tr><th>구분</th><th>금액</th></tr></thead>
      <tbody>
        <tr><td>매출채권</td><td>100</td></tr>
        <tr><td>합계</td><td>100</td></tr>
      </tbody>
    </table>
    """

    table = extract_tables(html)[0]

    assert [row.cells for row in table.rows] == [
        ["구분", "금액"],
        ["매출채권", "100"],
        ["합계", "100"],
    ]
