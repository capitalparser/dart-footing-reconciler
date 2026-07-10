"""Consolidation-basis identity matching for prior reports."""

from __future__ import annotations

from dart_footing_reconciler.document import FullReport

_CONCRETE_BASES = frozenset({"consolidated", "separate"})


def consolidation_basis(report: FullReport) -> str:
    """Return one proven report basis, otherwise ``unknown``."""
    scopes = {
        section.scope
        for section in (*report.statements, *report.notes)
    }
    if len(scopes) == 1:
        basis = next(iter(scopes))
        if basis in _CONCRETE_BASES:
            return basis
    return "unknown"


def match_prior_report(
    current_report: FullReport,
    prior_report: FullReport | None,
) -> FullReport | None:
    """Select the exact-basis prior slice; abstain unless identity is proven."""
    if prior_report is None:
        return None
    basis = consolidation_basis(current_report)
    if basis == "unknown":
        return None

    prior_scopes = {
        section.scope for section in (*prior_report.statements, *prior_report.notes)
    }
    if not prior_scopes or not prior_scopes <= _CONCRETE_BASES:
        return None

    statements = [section for section in prior_report.statements if section.scope == basis]
    notes = [section for section in prior_report.notes if section.scope == basis]
    if not statements and not notes:
        return None
    return FullReport(
        source=prior_report.source,
        company=prior_report.company,
        statements=statements,
        notes=notes,
    )
