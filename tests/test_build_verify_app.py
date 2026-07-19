from __future__ import annotations

from http.client import HTTPConnection
from threading import Thread

import pytest
import typer
from typer.testing import CliRunner

from dart_footing_reconciler.cli import app, _build_verify_server


def test_cli_build_verify_app_assembles_offline_folder(tmp_path) -> None:
    output = tmp_path / "dart-verify"
    missing_pyodide = tmp_path / "missing-pyodide"

    result = CliRunner().invoke(
        app,
        [
            "build-verify-app",
            "--output",
            str(output),
            "--pyodide-dir",
            str(missing_pyodide),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (output / "index.html").exists()
    assert (output / "app.js").exists()
    assert len(list(output.glob("*.whl"))) == 1
    assert (output / "vendor" / "pyodide" / "README.md").exists()


def test_verify_app_shell_is_desktop_and_uses_reviewer_facing_language(
    tmp_path,
) -> None:
    output = tmp_path / "dart-verify"

    result = CliRunner().invoke(
        app,
        [
            "build-verify-app",
            "--output",
            str(output),
            "--pyodide-dir",
            str(tmp_path / "missing-pyodide"),
        ],
    )

    assert result.exit_code == 0, result.output
    html = (output / "index.html").read_text(encoding="utf-8")
    assert "검증할 DART 원문 선택" in html
    assert "원문 표" in html
    assert "셀 검증 결과" in html
    assert "표 간 대사 결과" in html
    assert (
        'accept=".html,.htm,.dsd,.xml,.pdf,text/html,application/xml,application/pdf"'
        in html
    )
    assert "HTML/DSD/XML/PDF 파일 선택" in html
    assert (
        '<button class="verify-another-file" id="verify-another-file" '
        'type="button" hidden>' in html
    )
    assert "다른 파일 검증" in html
    assert "body.has-result .workspace" in html
    assert "grid-template-columns: minmax(0, 1fr)" in html
    assert "body.has-result .input-panel" in html
    app_js = (output / "app.js").read_text(encoding="utf-8")
    assert "PDF 파일은 지원하지 않습니다" not in app_js
    assert "LOCAL VERIFY" not in html
    assert "수치 대사 엔진" not in html
    assert "DART Footing Reconciler" not in html
    assert "@media (max-width" not in html


def test_serve_verify_app_binds_localhost_only(tmp_path) -> None:
    app_dir = tmp_path / "dart-verify"
    app_dir.mkdir()
    (app_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    httpd, url = _build_verify_server(app_dir, 0)  # port 0 = auto-pick
    try:
        assert httpd.server_address[0] == "127.0.0.1"  # loopback only, never 0.0.0.0
        assert url.startswith("http://127.0.0.1:")
        assert url.endswith("/index.html")
    finally:
        httpd.server_close()


def test_serve_verify_app_keeps_serving_static_files(tmp_path) -> None:
    app_dir = tmp_path / "dart-verify"
    app_dir.mkdir()
    (app_dir / "index.html").write_text("<html>static app</html>", encoding="utf-8")

    httpd, _url = _build_verify_server(app_dir, 0)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection(*httpd.server_address, timeout=5)
    try:
        connection.request("GET", "/index.html")
        response = connection.getresponse()
        body = response.read()
        assert response.status == 200
        assert body == b"<html>static app</html>"
    finally:
        connection.close()
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_serve_verify_app_rejects_unbuilt_folder(tmp_path) -> None:
    with pytest.raises(typer.BadParameter):
        _build_verify_server(tmp_path / "missing", 0)
