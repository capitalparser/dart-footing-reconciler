"""Generic row and column total checks."""

from __future__ import annotations

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    NOT_TESTED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import ReportTable

TOTAL_LABELS = ("합계", "계", "총계", "자산총계", "부채총계", "자본총계")


def check_table_totals(table: ReportTable, *, note_no: str, tolerance: int = 1) -> list[CheckResult]:
    results = _row_total_results(table, note_no=note_no, tolerance=tolerance)
    results.extend(_column_total_results(table, note_no=note_no, tolerance=tolerance))
    if not results:
        status = PARSE_UNCERTAIN if _has_amounts(table) else NOT_TESTED
        results.append(
            CheckResult(
                check_id=f"total:{note_no}:table{table.index}:not_tested",
                check_type="total_check",
                status=status,
                scope="note",
                note_no=note_no,
                title=f"{table.heading} total check",
                expected=None,
                actual=None,
                difference=None,
                tolerance=tolerance,
                reason="no reliable total label found",
                evidence=[],
            )
        )
    return results


def _row_total_results(table: ReportTable, *, note_no: str, tolerance: int) -> list[CheckResult]:
    results: list[CheckResult] = []
    for row_idx, row in enumerate(table.rows[1:], start=1):
        total_col = _total_column(row)
        if total_col is None or total_col < 2:
            continue
        values = [parse_amount(cell) for cell in row[1:total_col]]
        actual = parse_amount(row[total_col])
        if actual is None or any(value is None for value in values):
            continue
        expected = sum(value for value in values if value is not None)
        results.append(
            _result(
                check_id=f"total:{note_no}:table{table.index}:row{row_idx}",
                note_no=note_no,
                title=f"{row[0]} row total",
                expected=expected,
                actual=actual,
                tolerance=tolerance,
                reason_ok="row total agrees",
                reason_gap="row total does not agree",
                evidence=[
                    CheckEvidence(
                        row[0],
                        actual,
                        f"note:{note_no}/table:{table.index}/row:{row_idx}/col:{total_col}",
                    )
                ],
            )
        )
    return results


def _column_total_results(table: ReportTable, *, note_no: str, tolerance: int) -> list[CheckResult]:
    if len(table.rows) < 3:
        return []
    total_row_idx = _total_row(table.rows)
    if total_row_idx is None:
        return []
    total_row = table.rows[total_row_idx]
    results: list[CheckResult] = []
    for col_idx in range(1, min(len(total_row), max(len(row) for row in table.rows[:total_row_idx]))):
        actual = parse_amount(total_row[col_idx])
        values = [
            parse_amount(row[col_idx])
            for row in table.rows[1:total_row_idx]
            if col_idx < len(row) and not _is_total_label(row[0])
        ]
        if actual is None or not values or any(value is None for value in values):
            continue
        expected = sum(value for value in values if value is not None)
        results.append(
            _result(
                check_id=f"total:{note_no}:table{table.index}:col{col_idx}",
                note_no=note_no,
                title=f"{total_row[0]} column total",
                expected=expected,
                actual=actual,
                tolerance=tolerance,
                reason_ok="column total agrees",
                reason_gap="column total does not agree",
                evidence=[
                    CheckEvidence(
                        total_row[0],
                        actual,
                        f"note:{note_no}/table:{table.index}/row:{total_row_idx}/col:{col_idx}",
                    )
                ],
            )
        )
    return results


def _result(
    *,
    check_id: str,
    note_no: str,
    title: str,
    expected: int,
    actual: int,
    tolerance: int,
    reason_ok: str,
    reason_gap: str,
    evidence: list[CheckEvidence],
) -> CheckResult:
    difference = actual - expected
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    return CheckResult(
        check_id=check_id,
        check_type="total_check",
        status=status,
        scope="note",
        note_no=note_no,
        title=title,
        expected=expected,
        actual=actual,
        difference=difference,
        tolerance=tolerance,
        reason=reason_ok if status == MATCHED else reason_gap,
        evidence=evidence,
    )


def _total_column(row: list[str]) -> int | None:
    for idx, cell in enumerate(row):
        if _is_total_label(cell):
            return idx
    return len(row) - 1 if len(row) >= 4 else None


def _total_row(rows: list[list[str]]) -> int | None:
    for idx in range(len(rows) - 1, 0, -1):
        if rows[idx] and _is_total_label(rows[idx][0]):
            return idx
    return None


def _is_total_label(value: str) -> bool:
    compact = value.replace(" ", "")
    return any(label == compact or compact.endswith(label) for label in TOTAL_LABELS)


def _has_amounts(table: ReportTable) -> bool:
    return any(parse_amount(cell) is not None for row in table.rows for cell in row)
