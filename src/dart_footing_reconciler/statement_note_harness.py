"""Financial statement body to note verification harness."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.checks_cfs_note import check_cfs_note_matches
from dart_footing_reconciler.checks_fs_note import check_fs_note_matches
from dart_footing_reconciler.checks_note_bridges import check_asset_note_bridges
from dart_footing_reconciler.checks_prior_column import check_prior_column_matches
from dart_footing_reconciler.checks_reconciliation import check_reconciliation_targets
from dart_footing_reconciler.verification_harness import LAYER_STATEMENT_NOTE, VerificationContext


class StatementNoteHarness:
    """Run checks that compare financial statement body lines to note content."""

    harness_id = "statement_note"
    layer = LAYER_STATEMENT_NOTE

    def run(self, context: VerificationContext) -> list[CheckResult]:
        reconciliation = check_reconciliation_targets(
            context.report,
            tolerance=context.tolerance,
        )
        results: list[CheckResult] = []
        results.extend(_non_cashflow_statement_note_checks(reconciliation))
        results.extend(check_asset_note_bridges(context.report, tolerance=context.tolerance))
        results.extend(check_fs_note_matches(context.report, tolerance=context.tolerance))
        results.extend(_cashflow_statement_note_checks(reconciliation))
        results.extend(check_cfs_note_matches(context.report, tolerance=context.tolerance))
        results.extend(check_prior_column_matches(context.report, tolerance=context.tolerance))
        return results


def _non_cashflow_statement_note_checks(checks: list[CheckResult]) -> list[CheckResult]:
    return [
        check
        for check in checks
        if check.check_type != "cashflow_reconciliation"
    ]


def _cashflow_statement_note_checks(checks: list[CheckResult]) -> list[CheckResult]:
    return [
        check
        for check in checks
        if check.check_type == "cashflow_reconciliation"
    ]
