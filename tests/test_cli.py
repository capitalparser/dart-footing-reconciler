import json

from openpyxl import load_workbook
from typer.testing import CliRunner

from dart_footing_reconciler.cli import app


def test_cli_foot_outputs_json(tmp_path) -> None:
    source = tmp_path / "report.html"
    source.write_text(
        """
        <p>15. 무형자산</p>
        <p>(2) 당기와 전기 중 무형자산의 변동내용은 다음과 같습니다.</p>
        <table>
          <tr><th>구분</th><th>합계</th></tr>
          <tr><td>기초</td><td>1,000</td></tr>
          <tr><td>취득</td><td>250</td></tr>
          <tr><td>상각비</td><td>100</td></tr>
          <tr><td>기말</td><td>1,150</td></tr>
        </table>
        """,
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["foot", str(source), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["total"] == 1
    assert payload["summary"]["matched"] == 1
    assert payload["results"][0]["columns"][0]["difference"] == 0


def test_cli_foot_accepts_local_dsd_with_korean_encoding(tmp_path) -> None:
    source = tmp_path / "report.dsd"
    source.write_bytes(
        """
        <DOCUMENT>
        <p>14. 유형자산</p>
        <p>당기 중 유형자산의 변동내용은 다음과 같습니다.</p>
        <table>
          <tr><th>구분</th><th>합계</th></tr>
          <tr><td>기초</td><td>1,000</td></tr>
          <tr><td>취득</td><td>250</td></tr>
          <tr><td>감가상각비</td><td>100</td></tr>
          <tr><td>기말</td><td>1,150</td></tr>
        </table>
        </DOCUMENT>
        """.encode("cp949")
    )

    result = CliRunner().invoke(app, ["foot", str(source), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["input_format"] == "dsd"
    assert payload["summary"]["matched"] == 1
    assert payload["results"][0]["status"] == "matched"


def test_cli_foot_rejects_pdf_until_pdf_table_extraction_is_supported(tmp_path) -> None:
    source = tmp_path / "report.pdf"
    source.write_bytes(b"%PDF-1.7\n")

    result = CliRunner().invoke(app, ["foot", str(source), "--format", "json"])

    assert result.exit_code != 0
    assert "PDF footing is not supported" in result.output
    assert "DSD or HTML" in result.output


def test_cli_foot_rejects_network_sources() -> None:
    result = CliRunner().invoke(app, ["foot", "https://dart.fss.or.kr/report.dsd"])

    assert result.exit_code != 0
    assert "local file path" in result.output


def test_cli_foot_excel_outputs_company_note_workbook(tmp_path) -> None:
    source = tmp_path / "report.html"
    source.write_text(
        """
        <p>11. 유형자산</p>
        <p>유형자산의 변동내용은 다음과 같습니다.</p>
        <table>
          <tr><th>구분</th><th>합계</th></tr>
          <tr><td>기초</td><td>1,000</td></tr>
          <tr><td>취득</td><td>250</td></tr>
          <tr><td>감가상각비</td><td>100</td></tr>
          <tr><td>기말</td><td>1,150</td></tr>
        </table>
        """,
        encoding="utf-8",
    )
    output = tmp_path / "company_review.xlsx"

    result = CliRunner().invoke(
        app,
        ["foot-excel", str(source), str(output), "--company", "Sample Co"],
    )

    assert result.exit_code == 0
    workbook = load_workbook(output)
    assert workbook.sheetnames == ["Dashboard", "Note Summary", "Gap Review", "Note 11"]
    assert workbook["Dashboard"]["B2"].value == "Sample Co"
    assert workbook["Note 11"]["E2"].value == "11"
