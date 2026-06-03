from dart_footing_reconciler import __version__, foot_local_report


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_package_exposes_local_attachment_footing(tmp_path) -> None:
    source = tmp_path / "report.html"
    source.write_text(
        """
        <p>14. 유형자산</p>
        <p>당기 중 유형자산의 변동내용은 다음과 같습니다.</p>
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

    payload = foot_local_report(source)

    assert payload["input_format"] == "html"
    assert payload["summary"]["matched"] == 1
