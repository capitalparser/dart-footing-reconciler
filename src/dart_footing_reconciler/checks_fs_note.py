"""Financial statement to note matching checks."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.taxonomy import (
    ClassifiedNoteAmount,
    ClassifiedStatementLine,
    TAXONOMY,
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
        note_hit = _select_note_hit_by_label(note_hits, account_key) or note_hits[0]
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


_NOTE_LABEL_PRIORITY = ("기말장부금액", "기말잔액", "합계", "소계")


def _select_note_hit_by_label(
    note_hits: list[ClassifiedNoteAmount], account_key: str
) -> ClassifiedNoteAmount | None:
    """Pick the semantically strongest note row without considering amount value."""
    if not note_hits:
        return None

    priority = _label_priority_for_account(account_key)
    ranked = [
        (rank, index, hit)
        for index, hit in enumerate(note_hits)
        if (rank := _label_rank(hit.label, priority)) is not None
    ]
    if not ranked:
        return note_hits[0]
    ranked.sort(key=lambda item: (item[0], item[1]))
    return ranked[0][2]


def _label_priority_for_account(account_key: str) -> tuple[str, ...]:
    aliases: list[str] = list(_NOTE_LABEL_PRIORITY)
    entry = next((item for item in TAXONOMY if item.key == account_key), None)
    if entry is not None:
        aliases.extend(entry.note_amount_aliases)
    return tuple(dict.fromkeys(_normalize_label(alias) for alias in aliases if alias))


def _label_rank(label: str, priority: tuple[str, ...]) -> int | None:
    normalized = _normalize_label(label)
    for index, alias in enumerate(priority):
        if alias and alias in normalized:
            return index
    return None


def _normalize_label(value: str) -> str:
    return "".join(value.split())
