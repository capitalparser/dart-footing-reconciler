"""Command line interface placeholder."""

import typer

app = typer.Typer(help="DART DSD/HTML footing and cash flow reconciliation.")


@app.callback()
def main() -> None:
    """Run DART footing reconciliation commands."""

