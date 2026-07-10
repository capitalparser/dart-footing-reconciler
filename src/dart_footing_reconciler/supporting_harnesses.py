"""Supporting verification harnesses outside the two primary note domains."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.checks_note_note import check_note_note_matches
from dart_footing_reconciler.checks_prior_year import check_prior_year_reconciliation
from dart_footing_reconciler.checks_statement_ties import check_statement_ties
from dart_footing_reconciler.verification_harness import (
    LAYER_NOTE_NOTE,
    LAYER_PRIOR_REPORT,
    LAYER_STATEMENT_CROSS,
    VerificationContext,
)


class StatementCrossHarness:
    """Run financial statement body to financial statement body checks."""

    harness_id = "statement_cross"
    layer = LAYER_STATEMENT_CROSS

    def run(self, context: VerificationContext) -> list[CheckResult]:
        return check_statement_ties(context.report, tolerance=context.tolerance)


class NoteNoteHarness:
    """Run deterministic note-to-note relationship checks."""

    harness_id = "note_note"
    layer = LAYER_NOTE_NOTE

    def run(self, context: VerificationContext) -> list[CheckResult]:
        return check_note_note_matches(context.report, tolerance=context.tolerance)


class PriorReportHarness:
    """Run current filing to prior filing checks only when a prior report exists."""

    harness_id = "prior_report"
    layer = LAYER_PRIOR_REPORT

    def run(self, context: VerificationContext) -> list[CheckResult]:
        if context.prior_report is None:
            return []
        return check_prior_year_reconciliation(
            context.report,
            context.prior_report,
            tolerance=context.tolerance,
        )
