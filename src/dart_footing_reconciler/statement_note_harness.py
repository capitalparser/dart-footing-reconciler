"""Financial statement body to note verification harness."""

from __future__ import annotations

from dataclasses import replace

from dart_footing_reconciler.checks import CheckResult, NOT_TESTED
from dart_footing_reconciler.checks_cfs_note import check_cfs_note_matches
from dart_footing_reconciler.checks_fs_note import check_fs_note_matches
from dart_footing_reconciler.checks_note_bridges import check_asset_note_bridges
from dart_footing_reconciler.checks_note_references import check_note_references
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
        balance_checks = _non_cashflow_statement_note_checks(reconciliation)
        bridge_checks = check_asset_note_bridges(
            context.report, tolerance=context.tolerance
        )
        cashflow_checks = _cashflow_statement_note_checks(reconciliation)
        fs_checks = _without_dominated_legacy_checks(
            check_fs_note_matches(context.report, tolerance=context.tolerance),
            balance_checks,
            strong_types={"primary_balance_reconciliation"},
        )
        cfs_checks = _without_dominated_legacy_checks(
            check_cfs_note_matches(context.report, tolerance=context.tolerance),
            [*cashflow_checks, *bridge_checks],
            strong_types={"cashflow_reconciliation", "asset_note_bridge_check"},
        )
        results: list[CheckResult] = []
        results.extend(balance_checks)
        results.extend(bridge_checks)
        results.extend(fs_checks)
        results.extend(cashflow_checks)
        results.extend(cfs_checks)
        results.extend(check_prior_column_matches(context.report, tolerance=context.tolerance))
        results.extend(check_note_references(context.report))
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


def _without_dominated_legacy_checks(
    legacy_checks: list[CheckResult],
    stronger_checks: list[CheckResult],
    *,
    strong_types: set[str],
) -> list[CheckResult]:
    """같은 계정의 더 정교한 대사가 있으면 단순 금액 비교를 중복 노출하지 않는다."""
    strong_account_keys = {
        check.account_key
        for check in stronger_checks
        if check.check_type in strong_types and check.account_key != "unknown"
    }
    return [
        replace(
            check,
            status=NOT_TESTED,
            reason="더 정교한 계정 대사 결과로 대체됨",
        )
        if check.account_key != "unknown" and check.account_key in strong_account_keys
        else check
        for check in legacy_checks
    ]
