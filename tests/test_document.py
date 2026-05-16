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


def test_parse_full_report_handles_dart_note_prefix(tmp_path):
    path = tmp_path / "report.html"
    path.write_text("<p>주석 11. 유형자산</p><table><tr><td>구분</td><td>금액</td></tr></table>", encoding="utf-8")

    report = parse_full_report(path, company="Sample Co")

    assert [(note.note_no, note.title) for note in report.notes] == [("11", "유형자산")]
