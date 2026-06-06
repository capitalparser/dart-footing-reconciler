from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.note_inventory import build_note_inventory


def test_build_note_inventory_includes_every_note_table(tmp_path):
    html = """
    <html><body>
      <p>1. 일반사항</p>
      <table><tr><th>구분</th><th>내용</th></tr><tr><td>회사</td><td>샘플</td></tr></table>
      <p>11. 유형자산</p>
      <table><tr><th>구분</th><th>합계</th></tr><tr><td>기말</td><td>1,000</td></tr></table>
      <p>31. 비용의 성격별 분류</p>
      <table><tr><th>구분</th><th>금액</th></tr><tr><td>감가상각비</td><td>100</td></tr></table>
    </body></html>
    """
    source = tmp_path / "sample.html"
    source.write_text(html, encoding="utf-8")

    report = parse_full_report(source, company="Sample Co")
    inventory = build_note_inventory(report)

    assert inventory.company == "Sample Co"
    assert inventory.note_count == 3
    assert len(inventory.tables) == 3
    assert [table.note_no for table in inventory.tables] == ["1", "11", "31"]
    assert inventory.tables[1].source == "note:11/table:1"
    assert inventory.tables[1].row_count == 2
    assert inventory.tables[1].column_count == 2
