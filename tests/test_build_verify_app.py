from __future__ import annotations

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


def test_serve_verify_app_rejects_unbuilt_folder(tmp_path) -> None:
    with pytest.raises(typer.BadParameter):
        _build_verify_server(tmp_path / "missing", 0)
