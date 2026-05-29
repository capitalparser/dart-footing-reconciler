from typer.testing import CliRunner

from election_workpaper import __version__
from election_workpaper.cli import app


def test_package_exposes_version():
    assert __version__ == "0.1.0"


def test_cli_version_command():
    result = CliRunner().invoke(app, ["version"])
    assert result.exit_code == 0
    assert "election-workpaper 0.1.0" in result.stdout
