from __future__ import annotations

from typer.testing import CliRunner

from dart_footing_reconciler.cli import app


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
