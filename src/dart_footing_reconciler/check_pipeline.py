"""Shared report check assembly through verification harnesses."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.note_internal_harness import NoteInternalHarness
from dart_footing_reconciler.semantic_validation import build_semantic_validation_report
from dart_footing_reconciler.statement_note_harness import StatementNoteHarness
from dart_footing_reconciler.supporting_harnesses import PriorReportHarness, StatementCrossHarness
from dart_footing_reconciler.verification_harness import (
    HarnessRun,
    VerificationContext,
    VerificationHarness,
    flatten_harness_runs,
    run_harnesses,
)


def default_report_harnesses() -> list[VerificationHarness]:
    return [
        StatementCrossHarness(),
        NoteInternalHarness(),
        StatementNoteHarness(),
        PriorReportHarness(),
    ]


def split_report_by_scope(report: FullReport) -> list[FullReport]:
    """Split a parsed report into consolidated/separate verification slices.

    Slicing happens only when both concrete scopes are present, so single-scope
    filings (audit reports, separate-only business reports) keep the current
    single-pass behavior. Unscoped residual sections become their own slice so
    no parsed section silently disappears from verification.
    """
    scopes = {section.scope for section in report.statements} | {
        section.scope for section in report.notes
    }
    if not ({"consolidated", "separate"} <= scopes):
        return [report]
    slices: list[FullReport] = []
    for scope in ("consolidated", "separate"):
        statements = [s for s in report.statements if s.scope == scope]
        notes = [n for n in report.notes if n.scope == scope]
        if statements or notes:
            slices.append(
                FullReport(
                    source=report.source,
                    company=report.company,
                    statements=statements,
                    notes=notes,
                )
            )
    residual_statements = [
        s for s in report.statements if s.scope not in {"consolidated", "separate"}
    ]
    residual_notes = [n for n in report.notes if n.scope not in {"consolidated", "separate"}]
    if residual_statements or residual_notes:
        slices.append(
            FullReport(
                source=report.source,
                company=report.company,
                statements=residual_statements,
                notes=residual_notes,
            )
        )
    return slices


def _matching_prior_slice(
    prior_report: FullReport | None, report_slice: FullReport
) -> FullReport | None:
    if prior_report is None:
        return None
    slice_scopes = {s.scope for s in report_slice.statements} | {
        n.scope for n in report_slice.notes
    }
    concrete = slice_scopes & {"consolidated", "separate"}
    if not concrete:
        return prior_report
    prior_slices = split_report_by_scope(prior_report)
    if len(prior_slices) == 1:
        return prior_report
    for prior_slice in prior_slices:
        prior_scopes = {s.scope for s in prior_slice.statements} | {
            n.scope for n in prior_slice.notes
        }
        if prior_scopes & concrete:
            return prior_slice
    return prior_report


def _slice_consolidation_basis(report_slice: FullReport) -> str:
    scopes = {section.scope for section in [*report_slice.statements, *report_slice.notes]}
    concrete = scopes & {"consolidated", "separate"}
    if len(concrete) == 1 and scopes <= concrete:
        return next(iter(concrete))
    return "unknown"


def assemble_report_harness_runs(
    report: FullReport,
    prior_report: FullReport | None,
    *,
    tolerance: int,
) -> list[HarnessRun]:
    runs: list[HarnessRun] = []
    for report_slice in split_report_by_scope(report):
        semantic = build_semantic_validation_report(report_slice, [])
        context = VerificationContext(
            report=report_slice,
            prior_report=_matching_prior_slice(prior_report, report_slice),
            tolerance=tolerance,
            candidates=semantic.candidates,
            consolidation_basis=_slice_consolidation_basis(report_slice),
        )
        runs.extend(run_harnesses(default_report_harnesses(), context))
    return runs


def assemble_report_checks(
    report: FullReport, prior_report: FullReport | None, *, tolerance: int
) -> list[CheckResult]:
    return flatten_harness_runs(
        assemble_report_harness_runs(
            report,
            prior_report,
            tolerance=tolerance,
        )
    )
