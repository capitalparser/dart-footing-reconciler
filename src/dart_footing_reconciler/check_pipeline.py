"""Shared report check assembly."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.checks_cfs_note import check_cfs_note_matches
from dart_footing_reconciler.checks_fs_note import check_fs_note_matches
from dart_footing_reconciler.checks_note_bridges import check_asset_note_bridges
from dart_footing_reconciler.checks_note_note import check_note_note_matches
from dart_footing_reconciler.checks_prior_column import check_prior_column_matches
from dart_footing_reconciler.checks_prior_year import check_prior_year_reconciliation
from dart_footing_reconciler.checks_reconciliation import check_reconciliation_targets
from dart_footing_reconciler.checks_statement_ties import check_statement_ties
from dart_footing_reconciler.checks_totals import check_table_totals
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.layout_formula_assertions import check_layout_formula_assertions
from dart_footing_reconciler.note_assertions import check_note_assertions


def assemble_report_checks(
    report: FullReport, prior_report: FullReport | None, *, tolerance: int
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    checks.extend(check_statement_ties(report, tolerance=tolerance))
    for note in report.notes:
        for block in note.blocks:
            if block.table is not None:
                checks.extend(check_table_totals(block.table, note_no=note.note_no, tolerance=tolerance))
    checks.extend(check_note_assertions(report, tolerance=tolerance))
    checks.extend(check_layout_formula_assertions(report, tolerance=tolerance))
    checks.extend(check_reconciliation_targets(report, tolerance=tolerance))
    checks.extend(check_asset_note_bridges(report, tolerance=tolerance))
    checks.extend(check_fs_note_matches(report, tolerance=tolerance))
    checks.extend(check_cfs_note_matches(report, tolerance=tolerance))
    checks.extend(check_note_note_matches(report, tolerance=tolerance))
    checks.extend(check_prior_column_matches(report, tolerance=tolerance))
    if prior_report is not None:
        checks.extend(check_prior_year_reconciliation(report, prior_report, tolerance=tolerance))
    return checks
