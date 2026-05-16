"""Command line interface."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from dart_footing_reconciler.footing import MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.scan import scan_html

app = typer.Typer(help="DART DSD/HTML footing and cash flow reconciliation.")


@app.callback()
def main() -> None:
    """Run DART footing reconciliation commands."""


@app.command()
def foot(
    source: Annotated[Path, typer.Argument(help="Local DART viewer HTML file")],
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: json or markdown"),
    ] = "markdown",
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
    include_all: Annotated[
        bool,
        typer.Option("--all", help="Include non-MVP movement tables"),
    ] = False,
) -> None:
    """Foot all movement-like tables in a local DART HTML document."""
    html = source.read_text(encoding="utf-8")
    results = scan_html(html, tolerance=tolerance, include_all=include_all)
    payload = {
        "source": str(source),
        "summary": _summary(results),
        "results": [asdict(result) for result in results],
    }

    if output_format == "json":
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if output_format == "markdown":
        typer.echo(_markdown(payload))
        return
    raise typer.BadParameter("format must be json or markdown")


def _summary(results: list) -> dict[str, int]:
    return {
        "total": len(results),
        "matched": sum(1 for result in results if result.status == MATCHED),
        "unexplained_gap": sum(1 for result in results if result.status == UNEXPLAINED_GAP),
    }


def _markdown(payload: dict) -> str:
    lines = [
        "# DART Footing Report",
        "",
        f"- Source: `{payload['source']}`",
        f"- Total footable tables: {payload['summary']['total']}",
        f"- Matched: {payload['summary']['matched']}",
        f"- Unexplained gaps: {payload['summary']['unexplained_gap']}",
        "",
    ]

    for result in payload["results"]:
        lines.extend(
            [
                f"## Table {result['table_index']}: {result['status']}",
                "",
                result["heading"] or "(no heading)",
                "",
                "| Column | Expected | Actual | Difference | Status |",
                "|---|---:|---:|---:|---|",
            ]
        )
        for column in result["columns"]:
            lines.append(
                f"| {column['label']} | {column['expected']} | {column['actual']} | "
                f"{column['difference']} | {column['status']} |"
            )
        lines.append("")

    return "\n".join(lines)
