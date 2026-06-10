from dart_footing_reconciler.document import parse_full_report


def test_parse_full_report_extracts_statements_and_all_notes(tmp_path):
    html = """
    <p>재무상태표</p>
    <table><tr><th>구분</th><th>당기</th></tr><tr><td>자산총계</td><td>1,000</td></tr></table>
    <p>손익계산서</p>
    <table><tr><th>구분</th><th>당기</th></tr><tr><td>매출액</td><td>500</td></tr></table>
    <p>1. 일반사항</p>
    <p>회사의 개요입니다.</p>
    <p>2. 중요한 회계정책</p>
    <table><tr><th>구분</th><th>금액</th></tr><tr><td>합계</td><td>100</td></tr></table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert report.company == "Sample Co"
    assert [section.title for section in report.statements] == ["재무상태표", "손익계산서"]
    assert [(note.note_no, note.title) for note in report.notes] == [
        ("1", "일반사항"),
        ("2", "중요한 회계정책"),
    ]
    assert report.notes[0].blocks[0].kind == "text"
    assert report.notes[1].blocks[0].kind == "table"


def test_parse_full_report_starts_new_statement_after_populated_statement_heading(tmp_path):
    notes = "\n".join(f"<p>{idx}. 주석 {idx}</p><p>본문</p>" for idx in range(1, 23))
    html = f"""
    <p>2-1. 연결 재무상태표</p>
    <p>연결 재무상태표</p>
    <table>
      <tr><td>구분</td><td>당기</td></tr>
      <tr><td>자산총계</td><td>1,000</td></tr>
    </table>
    <p>2-2. 연결 포괄손익계산서</p>
    <p>연결 포괄손익계산서</p>
    <table>
      <tr><td>구분</td><td>당기</td></tr>
      <tr><td>당기순이익</td><td>100</td></tr>
      <tr><td>총포괄손익</td><td>100</td></tr>
    </table>
    <p>2-3. 연결 자본변동표</p>
    <p>연결 자본변동표</p>
    <table>
      <tr><td>구분</td><td>자본금</td><td>이익잉여금</td></tr>
      <tr><td>기초자본</td><td>10</td><td>20</td></tr>
      <tr><td>기말자본</td><td>10</td><td>30</td></tr>
    </table>
    <p>2-4. 연결 현금흐름표</p>
    <p>연결 현금흐름표</p>
    <table>
      <tr><td>구분</td><td>당기</td></tr>
      <tr><td>영업활동으로 인한 현금흐름</td><td>90</td></tr>
    </table>
    <p>3. 연결재무제표 주석</p>
    {notes}
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert [section.title for section in report.statements] == [
        "재무상태표",
        "포괄손익계산서",
        "자본변동표",
        "현금흐름표",
    ]


def test_parse_full_report_handles_dart_note_prefix(tmp_path):
    path = tmp_path / "report.html"
    path.write_text("<p>주석 11. 유형자산</p><table><tr><td>구분</td><td>금액</td></tr></table>", encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert [(note.note_no, note.title) for note in report.notes] == [("11", "유형자산")]


def test_parse_full_report_reads_cp949_dart_html(tmp_path):
    path = tmp_path / "report.html"
    path.write_text(
        "<p>재무상태표</p><table><tr><td>구분</td><td>당기</td></tr><tr><td>매출채권</td><td>1,000</td></tr></table>",
        encoding="cp949",
    )

    report = parse_full_report(path, company="Sample Co")

    assert report.statements[0].title == "재무상태표"
    assert report.statements[0].blocks[0].table.rows[1] == ["매출채권", "1,000"]


def test_parse_full_report_preserves_dart_acodes_and_table_heading_context(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <table><tr><td>7. 금융상품</td></tr></table>
    <table><tr><td>(1) 금융자산의 범주별 장부금액</td></tr></table>
    <table>
      <tr><td>구분</td><td>합계</td></tr>
      <tr>
        <td>영업채권</td>
        <td acode="ifrs-full_TradeReceivables|CFY|0|KRW|">1,000</td>
      </tr>
    </table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    table = report.notes[0].blocks[-1].table
    assert table.heading == "7. 금융상품 (1) 금융자산의 범주별 장부금액"
    assert table.row_acodes[1][1] == "ifrs-full_TradeReceivables|CFY|0|KRW|"


def test_parse_full_report_carries_dart_unit_table_to_following_data_table(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <table><tr><td>11. 유형자산</td></tr></table>
    <table><tr><td>당기</td><td>(단위 : 천원)</td></tr></table>
    <table>
      <tr><td>구분</td><td>합계</td></tr>
      <tr><td>기말</td><td>1,000</td></tr>
    </table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert report.notes[0].blocks[-1].table.unit_multiplier == 1000


def test_parse_full_report_uses_current_table_heading_unit_over_previous_marker(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <table><tr><td>19. 무형자산</td></tr></table>
    <table><tr><td>당기</td><td>(단위 : 백만원)</td></tr></table>
    <p>무형자산상각비의 기능별 배분 당기 (단위 : 천원)</p>
    <table>
      <tr><td></td><td></td><td>무형자산상각비</td></tr>
      <tr><td>기능별 항목</td><td>제조원가</td><td>1,000</td></tr>
    </table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert report.notes[0].blocks[-1].table.unit_multiplier == 1000


def test_parse_full_report_preserves_note_heading_unit_after_colon(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <p>16. 유형자산 가. 보고기간 중 유형자산의 변동내역은 다음과 같습니다(단위: 천원).</p>
    <table>
      <tr><td>구분</td><td>합계</td></tr>
      <tr><td>취득 및 자본적지출</td><td>4,408,846</td></tr>
    </table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")
    table = report.notes[0].blocks[-1].table

    assert table.unit_multiplier == 1000
    assert "천원" in table.heading


def test_parse_full_report_applies_embedded_unit_header_row(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <p>13. 유형자산</p>
    <table>
      <tr><td>(단위: 천원)</td><td>(단위: 천원)</td><td>(단위: 천원)</td></tr>
      <tr><td>구분</td><td>당기말</td><td>전기말</td></tr>
      <tr><td>장부금액</td><td>1,000</td><td>900</td></tr>
    </table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")
    table = report.notes[0].blocks[-1].table

    assert table.unit_multiplier == 1000
    assert table.rows[0] == ["구분", "당기말", "전기말"]
    assert table.rows[1] == ["장부금액", "1,000", "900"]


def test_parse_full_report_does_not_skip_income_statement_with_eps_unit_row(tmp_path):
    html = """
    <table>
      <tr><td>손익계산서</td></tr>
      <tr><td>제 1 기 2023.01.01 부터 2023.12.31 까지</td></tr>
      <tr><td>(단위 : 원)</td></tr>
    </table>
    <table>
      <tr><td>구분</td><td>당기</td></tr>
      <tr><td>매출액</td><td>1,000</td></tr>
      <tr><td>당기순이익</td><td>100</td></tr>
      <tr><td>주당이익 기본및희석주당이익(단위 : 원)</td><td>10</td></tr>
    </table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert report.statements[0].title == "손익계산서"
    assert report.statements[0].blocks[0].table.rows == [
        ["구분", "당기"],
        ["매출액", "1,000"],
        ["당기순이익", "100"],
        ["주당이익 기본및희석주당이익(단위 : 원)", "10"],
    ]


def test_parse_full_report_keeps_income_statement_with_revenue_parenthetical_label_under_strict_filter(tmp_path):
    notes = "\n".join(f"<p>{idx}. 주석 {idx}</p><p>본문</p>" for idx in range(1, 23))
    html = f"""
    <p>2-2. 연결 손익계산서</p>
    <p>연결 손익계산서</p>
    <table>
      <tr><td>구분</td><td>당기</td></tr>
      <tr><td>수익(매출액)</td><td>1,000</td></tr>
      <tr><td>매출원가</td><td>700</td></tr>
    </table>
    <p>재무제표 주석</p>
    {notes}
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert [section.title for section in report.statements] == ["손익계산서"]
    assert report.statements[0].blocks[0].table.rows[1][0] == "수익(매출액)"


def test_parse_full_report_prefers_comprehensive_income_statement_title(tmp_path):
    html = """
    <p>포괄손익계산서</p>
    <table>
      <tr><td>구분</td><td>당기</td></tr>
      <tr><td>기타포괄손익</td><td>100</td></tr>
    </table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert report.statements[0].title == "포괄손익계산서"


def test_parse_full_report_does_not_start_statement_from_note_column_label(tmp_path):
    html = """
    <table>
      <tr><td>손익계산서</td></tr>
      <tr><td>제 1 기 2023.01.01 부터 2023.12.31 까지</td></tr>
    </table>
    <table><tr><td>구분</td><td>당기</td></tr><tr><td>매출액</td><td>1,000</td></tr></table>
    <p>재무제표 주석</p>
    <p>24. 법인세비용</p>
    <table><tr><td>구분</td><td>손익계산서</td></tr><tr><td>일시적차이</td><td>100</td></tr></table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert len(report.statements) == 1
    assert report.statements[0].blocks[0].table.rows[1] == ["매출액", "1,000"]
    assert report.notes[0].blocks[0].table.rows[0] == ["구분", "손익계산서"]


def test_parse_full_report_starts_note_area_from_table_marker(tmp_path):
    html = """
    <p>현금흐름표</p>
    <table><tr><td>구분</td><td>당기</td></tr><tr><td>영업활동</td><td>1</td></tr></table>
    <table><tr><td>재무제표 주석</td></tr></table>
    <table><tr><td>1. 일반사항</td></tr></table>
    <table><tr><td>본문</td></tr></table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert len(report.statements[0].blocks) == 1
    assert [(note.note_no, note.title) for note in report.notes] == [("1", "일반사항")]


def test_parse_full_report_starts_new_notes_from_layout_table_headings(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <table><tr><td>2.3 중요한 회계정책</td></tr></table>
    <table><tr><td>2.3.1 금융상품</td></tr></table>
    <table><tr><td>정책 본문입니다.</td></tr></table>
    <table><tr><td>3. 중요한 회계적 판단</td></tr></table>
    <table><tr><td>판단 본문입니다.</td></tr></table>
    <table><tr><td>4. 금융상품</td></tr></table>
    <table><tr><td>구분</td><td>금액</td></tr><tr><td>현금</td><td>100</td></tr></table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert [(note.note_no, note.title) for note in report.notes] == [
        ("2.3", "중요한 회계정책"),
        ("3", "중요한 회계적 판단"),
        ("4", "금융상품"),
    ]
    assert report.notes[0].blocks[0].text == "2.3.1 금융상품"
    assert report.notes[2].blocks[-1].table.heading == "4. 금융상품"


def test_parse_full_report_does_not_start_note_from_date_range_text(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <span>23. 차입금</span>
    <table><tr><td>23.9.15 ~'26.5.14</td></tr></table>
    <table><tr><td>구분</td><td>금액</td></tr><tr><td>장기차입금</td><td>100</td></tr></table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert [(note.note_no, note.title) for note in report.notes] == [("23", "차입금")]
    assert report.notes[0].blocks[0].text == "23.9.15 ~'26.5.14"


def test_parse_full_report_keeps_policy_subsections_inside_single_note(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <p>2. 중요한 회계정책</p>
    <p>2.1 재무제표 작성기준</p>
    <p>연결회사는 한국채택국제회계기준을 적용하고 있습니다.</p>
    <p>2.2 회계정책과 공시의 변경</p>
    <p>당기부터 적용되는 기준서 내용입니다.</p>
    <p>3. 중요한 회계추정 및 가정</p>
    <p>추정 불확실성의 주요 원천입니다.</p>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert [(note.note_no, note.title) for note in report.notes] == [
        ("2", "중요한 회계정책"),
        ("3", "중요한 회계추정 및 가정"),
    ]
    assert [block.text for block in report.notes[0].blocks] == [
        "2.1 재무제표 작성기준",
        "연결회사는 한국채택국제회계기준을 적용하고 있습니다.",
        "2.2 회계정책과 공시의 변경",
        "당기부터 적용되는 기준서 내용입니다.",
    ]


def test_parse_full_report_starts_decimal_note_when_parent_heading_is_absent(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <table><tr><td>1. 일반사항</td></tr></table>
    <table><tr><td>2.1 재무제표 작성기준</td></tr></table>
    <table><tr><td>2.3.11 유형자산</td></tr></table>
    <table><tr><td>정책 본문입니다.</td></tr></table>
    <table><tr><td>3. 중요한 회계추정 및 가정</td></tr></table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert [(note.note_no, note.title) for note in report.notes] == [
        ("1", "일반사항"),
        ("2.1", "재무제표 작성기준"),
        ("2.3.11", "유형자산"),
        ("3", "중요한 회계추정 및 가정"),
    ]
    assert report.notes[2].blocks[0].text == "정책 본문입니다."


def test_parse_full_report_keeps_same_number_subheading_inside_current_note(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <p>1. 일반사항</p>
    <p>1. 회사의 개요</p>
    <p>회사의 설립과 영업 현황입니다.</p>
    <p>2. 중요한 회계정책</p>
    <p>정책 본문입니다.</p>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert [(note.note_no, note.title) for note in report.notes] == [
        ("1", "일반사항"),
        ("2", "중요한 회계정책"),
    ]
    assert report.notes[0].blocks[0].text == "1. 회사의 개요"


def test_parse_full_report_ignores_financial_statement_section_heading_in_note_area(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <p>42. 보고기간 후 사건</p>
    <p>해당사항 없습니다.</p>
    <p>4. 재무제표</p>
    <p>1. 일반사항</p>
    <p>별도 재무제표 일반사항입니다.</p>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert [(note.note_no, note.title) for note in report.notes] == [
        ("42", "보고기간 후 사건"),
        ("1", "일반사항"),
    ]


def test_parse_full_report_skips_dart_layout_container_tables(tmp_path):
    html = """
    <p>재무제표 주석</p>
    <p>2. 중요한 회계정책</p>
    <table>
      <tr>
        <td>
          <p>정책 본문입니다.</p>
          <table><tr><td>-</td><td>공정가치 측정 금융자산</td></tr></table>
          <table>
            <tr><td>구 분</td><td>추정 내용연수</td></tr>
            <tr><td>건물</td><td>8 ~ 40년</td></tr>
          </table>
        </td>
      </tr>
    </table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    note = report.notes[0]
    assert [(block.kind, block.text) for block in note.blocks[:2]] == [
        ("text", "정책 본문입니다."),
        ("text", "- 공정가치 측정 금융자산"),
    ]
    assert note.blocks[2].kind == "table"
    assert note.blocks[2].table.rows == [["구 분", "추정 내용연수"], ["건물", "8 ~ 40년"]]


def test_parse_full_report_skips_nb_class_tables(tmp_path):
    """DART class='nb' 테이블은 레이아웃 컨테이너로 처리되어 데이터 테이블로 파싱되지 않음."""
    html = """
    <p>재무제표 주석</p>
    <p>11. 유형자산</p>
    <table class="nb">
      <tr><td>이 테이블은 주석 말주기(nb) 영역입니다.</td></tr>
    </table>
    <table>
      <tr><th>구분</th><th>합계</th></tr>
      <tr><td>기말장부금액</td><td>1,000</td></tr>
    </table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    note = report.notes[0]
    # nb 테이블은 건너뛰고, 실제 데이터 테이블만 파싱돼야 함
    table_blocks = [b for b in note.blocks if b.kind == "table"]
    assert len(table_blocks) == 1
    assert table_blocks[0].table.rows == [["구분", "합계"], ["기말장부금액", "1,000"]]


def test_parse_full_report_nb_class_with_multiple_values(tmp_path):
    """class='nb' 속성이 다른 class와 함께 있어도 필터링됨."""
    html = """
    <p>재무제표 주석</p>
    <p>5. 현금흐름</p>
    <table class="nb some-other-class">
      <tr><td>nb 클래스 포함 테이블</td></tr>
    </table>
    <table>
      <tr><th>구분</th><th>금액</th></tr>
      <tr><td>영업활동</td><td>500</td></tr>
    </table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")
    note = report.notes[0]
    table_blocks = [b for b in note.blocks if b.kind == "table"]
    assert len(table_blocks) == 1
    assert table_blocks[0].table.rows[1][0] == "영업활동"


def test_parse_full_report_scope_split_business_report(tmp_path):
    """사업보고서 TOC 구조에서 연결/별도 본문과 주석이 스코프로 구분됨."""
    html = """
    <p class='section-1'><a name='toc1'>III. 재무에 관한 사항</a></p>
    <p class='section-2'><a name='toc2'>1. 요약재무정보</a></p>
    <table><tr><td>구분</td><td>제3기</td></tr><tr><td>유동자산</td><td>10</td></tr></table>
    <p class='section-2'><a name='toc3'>2. 연결재무제표</a></p>
    <table><tr><td>연결재무상태표 제 3 기 2024년 12월 31일 현재</td></tr></table>
    <table><tr><th>과목</th><th>당기</th></tr><tr><td>유동자산</td><td>700</td></tr><tr><td>자산총계</td><td>1,000</td></tr></table>
    <p class='section-2'><a name='toc4'>3. 연결재무제표 주석</a></p>
    <p>1. 일반적인 사항</p>
    <p>회사의 개요입니다.</p>
    <p class='section-2'><a name='toc5'>4. 재무제표</a></p>
    <table><tr><td>재무상태표 제 3 기 2024년 12월 31일 현재</td></tr></table>
    <table><tr><th>과목</th><th>당기</th></tr><tr><td>유동자산</td><td>500</td></tr><tr><td>자산총계</td><td>800</td></tr></table>
    <p>4-5. 이익잉여금처분계산서</p>
    <table><tr><td>1. 미처분이익잉여금</td><td>50</td></tr></table>
    <p class='section-2'><a name='toc6'>5. 재무제표 주석</a></p>
    <p>1. 일반적인 사항</p>
    <p>별도 회사의 개요입니다.</p>
    <p class='section-2'><a name='toc7'>6. 배당에 관한 사항</a></p>
    <p>1. 배당 개요</p>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    statement_scopes = [(s.title, s.scope) for s in report.statements]
    assert ("재무상태표", "consolidated") in statement_scopes
    assert ("재무상태표", "separate") in statement_scopes
    note_scopes = {(n.note_no, n.scope) for n in report.notes}
    assert ("1", "consolidated") in note_scopes
    assert ("1", "separate") in note_scopes
    # 배당 영역의 번호 매긴 제목과 이익잉여금처분계산서 행은 주석으로 오인되지 않음
    titles = [n.title for n in report.notes]
    assert "배당 개요" not in titles
    assert "미처분이익잉여금" not in titles


def test_parse_full_report_table_cell_text_not_duplicated(tmp_path):
    """데이터 테이블 셀 내부 <p> 텍스트가 별도 텍스트 블록으로 중복되지 않음."""
    html = """
    <p>재무제표 주석</p>
    <p>7. 유형자산</p>
    <p>유형자산 변동 내역입니다.</p>
    <table>
      <tr><th><p>구분</p></th><th><p>금액</p></th></tr>
      <tr><td><p>기초</p></td><td><p>1,234</p></td></tr>
      <tr><td><p>기말</p></td><td><p>5,678</p></td></tr>
    </table>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")
    note = report.notes[0]
    texts = [b.text for b in note.blocks if b.kind == "text"]
    assert texts == ["유형자산 변동 내역입니다."]
    table_blocks = [b for b in note.blocks if b.kind == "table"]
    assert len(table_blocks) == 1
    assert table_blocks[0].table.rows[1] == ["기초", "1,234"]


def test_parse_full_report_audit_report_single_scope_backward_compat(tmp_path):
    """TOC 마커가 없는 감사보고서식 파일은 기존처럼 단일 흐름으로 파싱됨."""
    html = """
    <p>재무상태표</p>
    <table><tr><th>과목</th><th>당기</th></tr><tr><td>유동자산</td><td>700</td></tr><tr><td>자산총계</td><td>1,000</td></tr></table>
    <p>재무제표 주석</p>
    <p>1. 일반사항</p>
    <p>개요.</p>
    """
    path = tmp_path / "report.html"
    path.write_text(html, encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")
    assert [s.title for s in report.statements] == ["재무상태표"]
    assert report.statements[0].scope == ""
    assert [n.note_no for n in report.notes] == ["1"]
    assert report.notes[0].scope == "separate"
