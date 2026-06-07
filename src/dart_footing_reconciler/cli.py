"""Command line interface."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from dart_footing_reconciler.audit_workbook import export_audit_workbook
from dart_footing_reconciler.check_pipeline import assemble_report_checks
from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.corpus import run_workpaper_corpus
from dart_footing_reconciler.coverage import build_coverage_report
from dart_footing_reconciler.document import FullReport, parse_full_report
from dart_footing_reconciler.formula_discovery import (
    VerificationFormula,
    discover_component_net_formula,
    discover_credit_risk_exposure_formula,
    discover_credit_risk_exposure_formulas,
    discover_debt_split_formula,
    discover_defined_benefit_rollforward_formulas,
    discover_discontinued_operation_cashflow_formula,
    discover_discontinued_operation_income_formulas,
    discover_employee_benefit_expense_formulas,
    discover_expense_summary_formula,
    discover_financial_category_column_formulas,
    discover_financial_category_formulas,
    discover_financial_fair_value_level_formulas,
    discover_financial_fair_value_formula,
    discover_inventory_carrying_formulas,
    discover_lease_expense_formulas,
    discover_lease_liability_split_formula,
    discover_liquidity_maturity_formulas,
    discover_net_debt_bridge_formulas,
    discover_provision_column_total_formulas,
    discover_receivable_aging_bucket_formulas,
    discover_receivable_carrying_formulas,
    discover_rollforward_formula,
    discover_tax_expense_composition_formulas,
)
from dart_footing_reconciler.footing import MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.layout_variants import classify_layout
from dart_footing_reconciler.note_inventory import build_note_inventory
from dart_footing_reconciler.orientation import detect_orientation
from dart_footing_reconciler.excel import export_company_workbook, export_validation_workbook
from dart_footing_reconciler.local_report import (
    LocalReportError,
    UnsupportedReportFormatError,
    foot_local_report,
    load_local_report,
)
from dart_footing_reconciler.report_html import export_audit_reconciliation_html
from dart_footing_reconciler.scan import scan_html
from dart_footing_reconciler.validation import run_manifest
from dart_footing_reconciler.validation_relevance import classify_validation_relevance
from dart_footing_reconciler.verification_candidates import (
    VerificationCandidate,
    extract_verification_candidates,
)

app = typer.Typer(help="DART DSD/HTML footing and cash flow reconciliation.")


@app.callback()
def main() -> None:
    """Run DART footing reconciliation commands."""


@app.command()
def foot(
    source: Annotated[Path, typer.Argument(help="Local DART DSD or HTML file")],
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
    """Foot all movement-like tables in a local DART DSD/HTML document."""
    try:
        payload = foot_local_report(source, tolerance=tolerance, include_all=include_all)
    except UnsupportedReportFormatError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except LocalReportError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if output_format == "json":
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if output_format == "markdown":
        typer.echo(_markdown(payload))
        return
    raise typer.BadParameter("format must be json or markdown")


@app.command("foot-excel")
def foot_excel(
    source: Annotated[Path, typer.Argument(help="Local DART DSD or HTML file")],
    output: Annotated[Path, typer.Argument(help="Output .xlsx workbook path")],
    company: Annotated[str | None, typer.Option(help="Company name for workbook header")] = None,
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
    include_all: Annotated[
        bool,
        typer.Option("--all", help="Include non-MVP movement tables"),
    ] = False,
) -> None:
    """Export a single-company footing workbook grouped by note number."""
    try:
        report = load_local_report(source)
    except UnsupportedReportFormatError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except LocalReportError as exc:
        raise typer.BadParameter(str(exc)) from exc
    results = scan_html(report.text, tolerance=tolerance, include_all=include_all)
    payload = {
        "source": str(report.source),
        "input_format": report.input_format,
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


@app.command("coverage-report")
def coverage_report(
    html: Annotated[Path, typer.Argument(help="Current-year DART viewer HTML file")],
    company: Annotated[str | None, typer.Option(help="Company name for the report")] = None,
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
) -> None:
    """Report all-note table layout and validation coverage."""
    report = parse_full_report(html, company=company or html.stem)
    inventory = build_note_inventory(report)
    layouts = {table.source: classify_layout(table) for table in inventory.tables}
    checks = _run_workpaper_checks(report, None, tolerance)
    coverage = build_coverage_report(inventory, layouts, checks)
    typer.echo(f"company: {coverage.company}")
    typer.echo(f"total_notes: {coverage.total_notes}")
    typer.echo(f"total_tables: {coverage.total_tables}")
    typer.echo(f"known_layout_tables: {coverage.known_layout_tables}")
    typer.echo(f"unknown_layout_tables: {coverage.unknown_layout_tables}")
    typer.echo(f"validated_tables: {coverage.validated_tables}")
    typer.echo(f"parse_uncertain_tables: {coverage.parse_uncertain_tables}")
    typer.echo(f"unvalidated_tables: {coverage.unvalidated_tables}")


@app.command("candidate-report")
def candidate_report(
    html: Annotated[Path, typer.Argument(help="Current-year DART viewer HTML file")],
    company: Annotated[str | None, typer.Option(help="Company name for the report")] = None,
    tolerance: Annotated[int, typer.Option(help="Allowed absolute difference")] = 1,
) -> None:
    """Report layout-aware target candidates and formulas for one company."""
    report = parse_full_report(html, company=company or html.stem)
    inventory = build_note_inventory(report)
    tables_by_source = {
        f"note:{note.note_no}/table:{block.table.index}": block.table
        for note in report.notes
        for block in note.blocks
        if block.table is not None
    }
    orientation_counts: Counter[str] = Counter()
    layout_counts: Counter[str] = Counter()
    validation_relevance_counts: Counter[str] = Counter()
    validation_relevant_unknown_layout_items = 0
    candidates: list[VerificationCandidate] = []
    formulas = []
    for item in inventory.tables:
        table = tables_by_source.get(item.source)
        if table is None:
            continue
        layout = classify_layout(item)
        orientation = detect_orientation(headers=item.headers, row_labels=item.row_labels)
        layout_counts.update([layout.key])
        orientation_counts.update([orientation.key])
        is_unknown_or_low_confidence = (
            layout.key == "unknown_layout"
            or orientation.key == "unknown"
            or layout.confidence < 0.7
            or orientation.confidence < 0.7
        )
        if is_unknown_or_low_confidence:
            relevance = classify_validation_relevance(
                title=item.title,
                headers=item.headers,
                row_labels=item.row_labels,
            )
            validation_relevance_counts.update([relevance.key])
            if relevance.validation_relevant:
                validation_relevant_unknown_layout_items += 1
        table_candidates = extract_verification_candidates(
            note_no=item.note_no,
            title=item.title,
            table=table,
            layout=layout,
            orientation=orientation,
        )
        candidates.extend(table_candidates)
        if layout.key == "net_debt_bridge":
            formulas.extend(
                discover_net_debt_bridge_formulas(table_candidates, tolerance=tolerance)
            )
        elif layout.key == "defined_benefit_rollforward":
            formulas.extend(
                discover_defined_benefit_rollforward_formulas(
                    table_candidates,
                    tolerance=tolerance,
                )
            )
        elif layout.key == "financial_instrument_category_summary":
            formulas.extend(
                discover_financial_category_formulas(table_candidates, tolerance=tolerance)
            )
            formulas.extend(
                discover_financial_category_column_formulas(
                    table_candidates,
                    tolerance=tolerance,
                )
            )
        elif layout.key == "employee_benefit_expense_allocation":
            formulas.extend(
                discover_employee_benefit_expense_formulas(
                    table_candidates,
                    tolerance=tolerance,
                )
            )
        elif layout.key == "financial_fair_value_level_summary":
            formulas.extend(
                discover_financial_fair_value_level_formulas(
                    table_candidates,
                    tolerance=tolerance,
                )
            )
        elif layout.key == "tax_expense_composition_summary":
            formulas.extend(
                discover_tax_expense_composition_formulas(
                    table_candidates,
                    tolerance=tolerance,
                )
            )
        elif layout.key in {
            "receivable_carrying_amount_summary",
            "receivable_present_value_carrying_summary",
        }:
            formulas.extend(
                discover_receivable_carrying_formulas(table_candidates, tolerance=tolerance)
            )
        elif layout.key == "receivable_loss_allowance_aging_summary":
            formulas.extend(
                discover_receivable_aging_bucket_formulas(
                    table_candidates,
                    tolerance=tolerance,
                )
            )
        elif layout.key == "inventory_carrying_amount_summary":
            formulas.extend(
                discover_inventory_carrying_formulas(table_candidates, tolerance=tolerance)
            )
        elif layout.key == "provision_rollforward":
            formulas.extend(
                _discover_account_rollforward_formulas(
                    table_candidates,
                    tolerance=tolerance,
                )
            )
        elif layout.key == "provision_current_noncurrent_summary":
            formulas.extend(
                discover_provision_column_total_formulas(
                    table_candidates,
                    tolerance=tolerance,
                )
            )
        elif layout.key == "liquidity_maturity_analysis":
            formulas.extend(
                discover_liquidity_maturity_formulas(table_candidates, tolerance=tolerance)
            )
        elif layout.key == "employee_benefit_maturity_summary":
            formulas.extend(
                discover_liquidity_maturity_formulas(table_candidates, tolerance=tolerance)
            )
        elif layout.key == "lease_liability_maturity_summary":
            formulas.extend(
                discover_liquidity_maturity_formulas(table_candidates, tolerance=tolerance)
            )
        elif layout.key == "lease_liability_current_noncurrent_summary":
            formulas.append(
                discover_lease_liability_split_formula(
                    table_candidates,
                    tolerance=tolerance,
                )
            )
        elif layout.key == "lease_expense_summary":
            formulas.extend(
                discover_lease_expense_formulas(table_candidates, tolerance=tolerance)
            )
        elif layout.key == "discontinued_operation_income_statement":
            formulas.extend(
                discover_discontinued_operation_income_formulas(
                    table_candidates,
                    tolerance=tolerance,
                )
            )
        elif layout.key == "discontinued_operation_cashflow_summary":
            if all(
                any(candidate.role == role for candidate in table_candidates)
                for role in (
                    "operating_cashflow",
                    "investing_cashflow",
                    "financing_cashflow",
                    "cashflow_total",
                )
            ):
                formulas.append(
                    discover_discontinued_operation_cashflow_formula(
                        table_candidates,
                        tolerance=tolerance,
                    )
                )
        elif any(candidate.role == "beginning" for candidate in table_candidates) and any(
            candidate.role == "ending" for candidate in table_candidates
        ):
            formulas.append(discover_rollforward_formula(table_candidates, tolerance=tolerance))
        if any(candidate.role == "gross_cost" for candidate in table_candidates) and any(
            candidate.role == "ending" for candidate in table_candidates
        ):
            formulas.append(discover_component_net_formula(table_candidates, tolerance=tolerance))
        if any(candidate.role == "debt_total" for candidate in table_candidates) and any(
            candidate.role == "ending" for candidate in table_candidates
        ):
            formulas.append(discover_debt_split_formula(table_candidates, tolerance=tolerance))
        if any(candidate.role == "expense_component" for candidate in table_candidates) and any(
            candidate.role == "expense_total" for candidate in table_candidates
        ):
            formulas.append(discover_expense_summary_formula(table_candidates, tolerance=tolerance))
        if any(candidate.role == "credit_exposure_component" for candidate in table_candidates) and any(
            candidate.role == "credit_exposure_total" for candidate in table_candidates
        ):
            formulas.extend(discover_credit_risk_exposure_formulas(table_candidates, tolerance=tolerance))
        if any(candidate.role == "fair_value_component" for candidate in table_candidates) and any(
            candidate.role == "fair_value_total" for candidate in table_candidates
        ):
            formulas.append(discover_financial_fair_value_formula(table_candidates, tolerance=tolerance))
    typer.echo(f"company: {report.company}")
    typer.echo(f"total_note_tables: {len(inventory.tables)}")
    for key, count in sorted(orientation_counts.items()):
        typer.echo(f"orientation {key}: {count}")
    for key, count in sorted(layout_counts.items()):
        typer.echo(f"layout {key}: {count}")
    typer.echo(
        "validation_relevant_unknown_layout_items: "
        f"{validation_relevant_unknown_layout_items}"
    )
    for key, count in sorted(validation_relevance_counts.items()):
        typer.echo(f"validation_relevance {key}: {count}")
    typer.echo(f"verification_candidates: {len(candidates)}")
    typer.echo(f"verification_formulas: {len(formulas)}")
    typer.echo(f"matched_formulas: {sum(1 for formula in formulas if formula.status == MATCHED)}")
    typer.echo(
        "parse_uncertain_formulas: "
        f"{sum(1 for formula in formulas if formula.status == 'parse_uncertain')}"
    )


def _discover_account_rollforward_formulas(
    candidates: list[VerificationCandidate],
    *,
    tolerance: int,
) -> list[VerificationFormula]:
    grouped: dict[str, list[VerificationCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.account_key, []).append(candidate)
    formulas: list[VerificationFormula] = []
    for account_key in sorted(
        grouped,
        key=lambda key: min(
            (candidate.row_index, candidate.column_index) for candidate in grouped[key]
        ),
    ):
        account_candidates = grouped[account_key]
        if any(candidate.role == "beginning" for candidate in account_candidates) and any(
            candidate.role == "ending" for candidate in account_candidates
        ):
            formulas.append(
                discover_rollforward_formula(account_candidates, tolerance=tolerance)
            )
    return formulas


def _run_workpaper_checks(
    report: FullReport, prior_report: FullReport | None, tolerance: int
) -> list[CheckResult]:
    return assemble_report_checks(report, prior_report, tolerance=tolerance)


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
    results_only: Annotated[
        bool,
        typer.Option(
            "--results-only",
            help="Delete generated raw/report artifacts after writing summary JSON/Markdown",
        ),
    ] = False,
) -> None:
    """Run workpaper HTML generation and diagnostics for multiple DART filings."""
    payload = run_workpaper_corpus(
        manifest,
        output_dir,
        fetch_missing=not no_fetch,
        tolerance=tolerance,
        keep_artifacts=not results_only,
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
