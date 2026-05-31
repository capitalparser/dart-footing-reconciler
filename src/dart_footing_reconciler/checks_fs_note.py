"""Financial statement to note matching checks."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.taxonomy import (
    ClassifiedNoteAmount,
    ClassifiedStatementLine,
    classify_report,
)

FS_NOTE_ACCOUNT_KEYS = (
    "property_plant_equipment",
    "intangible_assets",
    "investment_property",
    "borrowings",
    "bonds",
    "lease_liabilities",
    "revenue",
    "cost_of_sales",
    "selling_general_admin",
    "income_tax_expense_benefit",
    "earnings_per_share",
    "depreciation_expense",
    "dividends",
    "cash_and_cash_equivalents_increase",
)


def check_fs_note_matches(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    classified = classify_report(report)
    for account_key in FS_NOTE_ACCOUNT_KEYS:
        fs_hits = [
            line for line in classified.statement_lines if line.account_key == account_key
        ]
        note_hits = [
            amount for amount in classified.note_amounts if amount.account_key == account_key
        ]
        if not fs_hits or not note_hits:
            continue
        fs_hit = fs_hits[0]
        note_hit = note_hits[0]
        difference = note_hit.amount - fs_hit.amount
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        results.append(
            CheckResult(
                check_id=f"fs_note:{account_key}:{note_hit.note_no}",
                check_type="fs_note_match",
                status=status,
                scope="report",
                note_no=note_hit.note_no,
                title=f"{fs_hit.display_name} FS to note match",
                expected=fs_hit.amount,
                actual=note_hit.amount,
                difference=difference,
                tolerance=tolerance,
                reason="financial statement amount agrees to note amount"
                if status == MATCHED
                else "financial statement amount does not agree to note amount",
                evidence=[
                    CheckEvidence(_statement_evidence_label(fs_hit), fs_hit.amount, fs_hit.source),
                    CheckEvidence(_note_evidence_label(note_hit), note_hit.amount, note_hit.source),
                ],
            )
        )
    return results


def _statement_evidence_label(hit: ClassifiedStatementLine) -> str:
    return f"{hit.statement_title} {hit.label}"


def _note_evidence_label(hit: ClassifiedNoteAmount) -> str:
    return f"주석 {hit.note_no} {hit.note_title} {hit.label}"
