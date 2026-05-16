import json

from typer.testing import CliRunner

from dart_footing_reconciler.cli import app


def test_cli_validate_outputs_manifest_summary(tmp_path) -> None:
    source = tmp_path / "report.html"
    source.write_text(
        """
        <p>15. 무형자산</p>
        <p>무형자산의 변동내용은 다음과 같습니다.</p>
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
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "samples": [
                    {
                        "name": "sample",
                        "source": source.name,
                        "expected": {"total": 1, "matched": 1, "unexplained_gap": 0},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(app, ["validate", str(manifest), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["summary"]["passed"] == 1
