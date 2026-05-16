"""Command line interface."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from dart_footing_reconciler.footing import MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.excel import export_company_workbook, export_validation_workbook
from dart_footing_reconciler.scan import scan_html
from dart_footing_reconciler.validation import run_manifest

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


@app.command("foot-excel")
def foot_excel(
    source: Annotated[Path, typer.Argument(help="Local DART viewer HTML file")],
    output: Annotated[Path, typer.Argument(help="Output .xlsx workbook path")],
    company: Annotated[str | None, typer.Option(help="Company name for workbook header")] = None,
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
    include_all: Annotated[
        bool,
        typer.Option("--all", help="Include non-MVP movement tables"),
    ] = False,
) -> None:
    """Export a single-company footing workbook grouped by note number."""
    html = source.read_text(encoding="utf-8")
    results = scan_html(html, tolerance=tolerance, include_all=include_all)
    payload = {
        "source": str(source),
        "company": company or source.stem,
        "tolerance": tolerance,
        "summary": _summary(results),
        "results": [asdict(result) for result in results],
    }
    workbook_path = export_company_workbook(payload, output)
    typer.echo(f"Wrote {workbook_path}")


@app.command()
def validate(
    manifest: Annotated[Path, typer.Argument(help="Validation manifest JSON")],
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: json or markdown"),
    ] = "markdown",
    mode: Annotated[
        str,
        typer.Option(help="Validation mode: conservative or diagnostic"),
    ] = "conservative",
    tag: Annotated[
        str | None,
        typer.Option(help="Run only samples with this tag or industry"),
    ] = None,
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
) -> None:
    """Run a fixture corpus validation manifest."""
    payload = run_manifest(manifest, mode=mode, tag=tag, tolerance=tolerance)
    if output_format == "json":
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if output_format == "markdown":
        typer.echo(_validation_markdown(payload))
        return
    raise typer.BadParameter("format must be json or markdown")


@app.command("validate-excel")
def validate_excel(
    manifest: Annotated[Path, typer.Argument(help="Validation manifest JSON")],
    output: Annotated[Path, typer.Argument(help="Output .xlsx workbook path")],
    mode: Annotated[
        str,
        typer.Option(help="Validation mode: conservative or diagnostic"),
    ] = "conservative",
    tag: Annotated[
        str | None,
        typer.Option(help="Run only samples with this tag or industry"),
    ] = None,
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
) -> None:
    """Run a validation manifest and export a reviewer-facing Excel workbook."""
    payload = run_manifest(
        manifest,
        mode=mode,
        tag=tag,
        tolerance=tolerance,
        include_results=True,
    )
    workbook_path = export_validation_workbook(payload, output)
    typer.echo(f"Wrote {workbook_path}")


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


def _validation_markdown(payload: dict) -> str:
    lines = [
        "# DART Footing Validation",
        "",
        f"- Manifest: `{payload['manifest']}`",
        f"- Mode: `{payload['mode']}`",
        f"- Tag: `{payload['tag'] or 'all'}`",
        f"- Samples: {payload['summary']['samples']}",
        f"- Passed: {payload['summary']['passed']}",
        f"- Failed: {payload['summary']['failed']}",
        f"- Total tables: {payload['summary']['total_tables']}",
        f"- Matched: {payload['summary']['matched']}",
        f"- Unexplained gaps: {payload['summary']['unexplained_gap']}",
        "",
        "| Sample | Industry | Status | Total | Matched | Gaps |",
        "|---|---|---|---:|---:|---:|",
    ]
    for sample in payload["samples"]:
        lines.append(
            f"| {sample['name']} | {sample.get('industry') or ''} | {sample['status']} | "
            f"{sample['actual']['total']} | {sample['actual']['matched']} | "
            f"{sample['actual']['unexplained_gap']} |"
        )
    return "\n".join(lines)
