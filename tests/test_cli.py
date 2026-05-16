import json

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
