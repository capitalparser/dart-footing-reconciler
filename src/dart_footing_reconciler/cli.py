"""Command line interface."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from dart_footing_reconciler.audit_workbook import export_audit_workbook
from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.checks_note_bridges import check_asset_note_bridges
from dart_footing_reconciler.checks_note_note import check_note_note_matches
from dart_footing_reconciler.checks_prior_year import check_prior_year_reconciliation
from dart_footing_reconciler.checks_reconciliation import check_reconciliation_targets
from dart_footing_reconciler.checks_totals import check_table_totals
from dart_footing_reconciler.corpus import run_workpaper_corpus
from dart_footing_reconciler.document import FullReport, parse_full_report
from dart_footing_reconciler.footing import MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.note_assertions import check_note_assertions
from dart_footing_reconciler.excel import export_company_workbook, export_validation_workbook
from dart_footing_reconciler.report_html import export_audit_reconciliation_html
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


@app.command("workpaper-excel")
def workpaper_excel(
    current_html: Annotated[Path, typer.Argument(help="Current-year DART viewer HTML file")],
    output: Annotated[Path, typer.Argument(help="Output audit workpaper .xlsx path")],
    company: Annotated[str | None, typer.Option(help="Company name for workbook header")] = None,
    prior_html: Annotated[
        Path | None, typer.Option(help="Prior-year DART viewer HTML file")
    ] = None,
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
) -> None:
    """Export a source-first audit workpaper workbook with validation blocks."""
    report = parse_full_report(current_html, company=company or current_html.stem)
    prior_report = (
        parse_full_report(prior_html, company=company or prior_html.stem)
        if prior_html is not None
        else None
    )
    checks: list[CheckResult] = []
    checks.extend(_run_workpaper_checks(report, prior_report, tolerance))
    workbook_path = export_audit_workbook(report, checks, output)
    typer.echo(f"Wrote {workbook_path}")


@app.command("workpaper-html")
def workpaper_html(
    current_html: Annotated[Path, typer.Argument(help="Current-year DART viewer HTML file")],
    output: Annotated[Path, typer.Argument(help="Output audit reconciliation .html path")],
    company: Annotated[str | None, typer.Option(help="Company name for report header")] = None,
    prior_html: Annotated[
        Path | None, typer.Option(help="Prior-year DART viewer HTML file")
    ] = None,
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
) -> None:
    """Export a Korean-first HTML audit reconciliation report."""
    report = parse_full_report(current_html, company=company or current_html.stem)
    prior_report = (
        parse_full_report(prior_html, company=company or prior_html.stem)
        if prior_html is not None
        else None
    )
    checks = _run_workpaper_checks(report, prior_report, tolerance)
    report_path = export_audit_reconciliation_html(report, checks, output)
    typer.echo(f"Wrote {report_path}")


def _run_workpaper_checks(
    report: FullReport, prior_report: FullReport | None, tolerance: int
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    checks.extend(_run_total_checks(report, tolerance))
    checks.extend(check_note_assertions(report, tolerance=tolerance))
    checks.extend(check_reconciliation_targets(report, tolerance=tolerance))
    checks.extend(check_asset_note_bridges(report, tolerance=tolerance))
    checks.extend(check_note_note_matches(report, tolerance=tolerance))
    if prior_report is not None:
        checks.extend(check_prior_year_reconciliation(report, prior_report, tolerance=tolerance))
    return checks


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


@app.command("workpaper-corpus")
def workpaper_corpus(
    manifest: Annotated[Path, typer.Argument(help="Multi-company corpus manifest JSON")],
    output_dir: Annotated[Path, typer.Argument(help="Output directory for raw files, reports, and summary")],
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
    no_fetch: Annotated[bool, typer.Option("--no-fetch", help="Reuse local sources only")] = False,
) -> None:
    """Run workpaper HTML generation and diagnostics for multiple DART filings."""
    payload = run_workpaper_corpus(
        manifest,
        output_dir,
        fetch_missing=not no_fetch,
        tolerance=tolerance,
    )
    typer.echo(
        "Generated {generated}/{samples} reports. Summary: {report}".format(
            generated=payload["summary"]["generated_reports"],
            samples=payload["summary"]["samples"],
            report=Path(output_dir) / "corpus_report.md",
        )
    )


def _summary(results: list) -> dict[str, int]:
    return {
        "total": len(results),
        "matched": sum(1 for result in results if result.status == MATCHED),
        "unexplained_gap": sum(1 for result in results if result.status == UNEXPLAINED_GAP),
    }


def _run_total_checks(report: FullReport, tolerance: int) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for note in report.notes:
        for block in note.blocks:
            if block.table is not None:
                checks.extend(check_table_totals(block.table, note_no=note.note_no, tolerance=tolerance))
    return checks


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
