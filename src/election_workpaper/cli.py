import typer

from election_workpaper import __version__

app = typer.Typer(help="Evidence-based election pledge workpaper CLI.")


@app.callback()
def main() -> None:
    """Evidence-based election pledge workpaper CLI."""


@app.command()
def version() -> None:
    """Print the Election Workpaper version."""
    typer.echo(f"election-workpaper {__version__}")
