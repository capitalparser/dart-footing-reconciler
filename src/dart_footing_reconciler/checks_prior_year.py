"""Prior-year disclosure amount and structure reconciliation."""

from __future__ import annotations

from dart_footing_reconciler._match_helpers import normalize_label
from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    EXPLAINABLE_GAP,
    MATCHED,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable


BalanceRoleAmount = tuple[str, int]


def check_prior_year_reconciliation(
    current: FullReport, prior: FullReport, *, tolerance: int = 1
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for current_note in current.notes:
        prior_note = _match_prior_note(current_note.title, prior)
        if prior_note is None:
            continue
        if current_note.note_no != prior_note.note_no:
            results.append(
                CheckResult(
                    f"prior_structure:note:{current_note.note_no}:number",
                    "prior_year_structure_change",
                    EXPLAINABLE_GAP,
                    "prior_year",
                    current_note.note_no,
                    current_note.title,
                    None,
                    None,
                    None,
                    tolerance,
                    f"note number changed from {prior_note.note_no} to {current_note.note_no}",
                    [],
                )
            )
        results.extend(_compare_note_tables(current_note, prior_note, tolerance))
    return results


def _match_prior_note(title: str, prior: FullReport) -> ReportSection | None:
    current_key = normalize_label(title)
    for note in prior.notes:
        if normalize_label(note.title) == current_key:
            return note
    return None


def _compare_note_tables(
    current_note: ReportSection, prior_note: ReportSection, tolerance: int
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for current_table, prior_table in zip(_tables(current_note), _tables(prior_note), strict=False):
        beginning_match = _compare_prior_ending_to_current_beginning(
            current_note, prior_note, current_table, prior_table, tolerance
        )
        if beginning_match is not None:
            results.append(beginning_match)
        if not current_table.rows or _preferred_col(current_table.rows[0], "전기") is None:
            continue
        current_rows = _label_amounts(current_table, "전기")
        prior_rows = _label_amounts(prior_table, "당기")
        for label, current_amount in current_rows.items():
            if label not in prior_rows:
                results.append(_structure_change(current_note, label, "table row added", tolerance))
                continue
            prior_amount = prior_rows[label]
            difference = current_amount - prior_amount
            status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
            results.append(
                CheckResult(
                    f"prior_amount:{current_note.note_no}:{label}",
                    "prior_year_amount_match",
                    status,
                    "prior_year",
                    current_note.note_no,
                    current_note.title,
                    prior_amount,
                    current_amount,
                    difference,
                    tolerance,
                    "current comparative amount agrees to prior current amount"
                    if status == MATCHED
                    else "current comparative amount does not agree to prior current amount",
                    [
                        CheckEvidence(label, current_amount, f"note:{current_note.note_no}/comparative"),
                        CheckEvidence(label, prior_amount, f"note:{prior_note.note_no}/current"),
                    ],
                )
            )
        for label in prior_rows:
            if label not in current_rows:
                results.append(_structure_change(current_note, label, "table row removed", tolerance))
    return results


def _compare_prior_ending_to_current_beginning(
    current_note: ReportSection,
    prior_note: ReportSection,
    current_table: ReportTable,
    prior_table: ReportTable,
    tolerance: int,
) -> CheckResult | None:
    current_beginning = _label_amount_by_role(current_table, "beginning")
    prior_ending = _label_amount_by_role(prior_table, "ending")
    if current_beginning is None or prior_ending is None:
        return None
    current_beginning_label, current_beginning_amount = current_beginning
    prior_ending_label, prior_ending_amount = prior_ending
    difference = current_beginning_amount - prior_ending_amount
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    return CheckResult(
        f"prior_beginning:{current_note.note_no}:{current_table.index}",
        "prior_year_beginning_balance_match",
        status,
        "prior_year",
        current_note.note_no,
        current_note.title,
        prior_ending_amount,
        current_beginning_amount,
        difference,
        tolerance,
        "prior-year ending balance agrees to current-year beginning balance"
        if status == MATCHED
        else "prior-year ending balance does not agree to current-year beginning balance",
        [
            CheckEvidence(
                f"prior ending {prior_ending_label}",
                prior_ending_amount,
                f"note:{prior_note.note_no}/table:{prior_table.index}/ending",
            ),
            CheckEvidence(
                f"current beginning {current_beginning_label}",
                current_beginning_amount,
                f"note:{current_note.note_no}/table:{current_table.index}/beginning",
            ),
        ],
    )


def _label_amount_by_role(table: ReportTable, role: str) -> BalanceRoleAmount | None:
    if not table.rows:
        return None
    headers = table.rows[0]
    col_idx = _preferred_col(headers, "당기")
    for row in table.rows[1:]:
        if not row or _balance_role(row[0]) != role:
            continue
        amount = parse_amount(row[col_idx]) if col_idx is not None and col_idx < len(row) else None
        if amount is None:
            amount = _rightmost_amount(row)
        if amount is not None:
            return row[0], amount
    return None


def _balance_role(label: str) -> str | None:
    compact = normalize_label(label)
    beginning_labels = ("기초", "기초장부금액", "기초금액", "기초잔액", "당기초")
    ending_labels = (
        "기말",
        "기말장부금액",
        "기말금액",
        "기말잔액",
        "전기말",
        "장부금액",
        "순장부금액",
        "장부가액",
    )
    if compact in beginning_labels:
        return "beginning"
    if compact in ending_labels:
        return "ending"
    return None


def _tables(note: ReportSection) -> list[ReportTable]:
    return [block.table for block in note.blocks if block.table is not None]


def _label_amounts(table: ReportTable, preferred_header: str) -> dict[str, int]:
    if not table.rows:
        return {}
    headers = table.rows[0]
    col_idx = _preferred_col(headers, preferred_header)
    values: dict[str, int] = {}
    for row in table.rows[1:]:
        if not row:
            continue
        amount = parse_amount(row[col_idx]) if col_idx is not None and col_idx < len(row) else None
        if amount is None:
            amount = _rightmost_amount(row)
        if amount is not None:
            values[normalize_label(row[0])] = amount
    return values


def _preferred_col(headers: list[str], preferred_header: str) -> int | None:
    key = normalize_label(preferred_header)
    for idx, header in enumerate(headers):
        if key in normalize_label(header):
            return idx
    return None


def _rightmost_amount(row: list[str]) -> int | None:
    for cell in reversed(row[1:]):
        amount = parse_amount(cell)
        if amount is not None:
            return amount
    return None


def _structure_change(note: ReportSection, label: str, prefix: str, tolerance: int) -> CheckResult:
    return CheckResult(
        f"prior_structure:note:{note.note_no}:{label}",
        "prior_year_structure_change",
        EXPLAINABLE_GAP,
        "prior_year",
        note.note_no,
        note.title,
        None,
        None,
        None,
        tolerance,
        f"{prefix}: {label}",
        [],
    )
