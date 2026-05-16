from openpyxl import load_workbook
from typer.testing import CliRunner

from dart_footing_reconciler.cli import app


def test_cli_workpaper_excel_exports_note_sheets(tmp_path):
    source = tmp_path / "report.html"
    source.write_text(
        """
        <p>11. 유형자산</p>
        <p>유형자산 내용입니다.</p>
        <table><tr><th>구분</th><th>합계</th></tr><tr><td>기초</td><td>100</td></tr></table>
        """,
        encoding="utf-8",
    )
    output = tmp_path / "workpaper.xlsx"
    result = CliRunner().invoke(app, ["workpaper-excel", str(source), str(output), "--company", "Sample Co"])
    assert result.exit_code == 0
    wb = load_workbook(output)
    assert "Note 11" in wb.sheetnames


def test_cli_workpaper_excel_includes_required_check_types(tmp_path):
    current = tmp_path / "current.html"
    prior = tmp_path / "prior.html"
    current.write_text(
        """
        <p>재무상태표</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>유형자산</td><td>1,000</td></tr></table>
        <p>현금흐름표</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>유형자산의 취득</td><td>(500)</td></tr></table>
        <p>11. 유형자산</p><table><tr><th>구분</th><th>당기</th><th>전기</th><th>합계</th></tr><tr><td>취득</td><td>500</td><td>400</td><td>900</td></tr><tr><td>장부금액</td><td>1,000</td><td>800</td><td>1,800</td></tr></table>
        """,
        encoding="utf-8",
    )
    prior.write_text(
        """
        <p>10. 유형자산</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>장부금액</td><td>800</td></tr></table>
        """,
        encoding="utf-8",
    )
    output = tmp_path / "workpaper.xlsx"
    result = CliRunner().invoke(
        app,
        ["workpaper-excel", str(current), str(output), "--company", "Sample Co", "--prior-html", str(prior)],
    )
    assert result.exit_code == 0
    wb = load_workbook(output)
    values = [cell.value for row in wb["Note 11"].iter_rows() for cell in row]
    assert "합계 검증 결과" in values
    assert "재무제표-주석 대사" in values
    assert "현금흐름표-주석 직접 대사" in values
    assert "전기 공시 금액 대사" in values
