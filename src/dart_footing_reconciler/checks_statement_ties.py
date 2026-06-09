"""Statement-level tie checks: BS equation and cross-statement amount ties."""

from __future__ import annotations

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.table_semantics import compact

_ASSET_TOTAL_LABELS = frozenset(["자산총계", "자산합계", "총자산", "자본과부채총계"])
_LIAB_TOTAL_LABELS = frozenset(["부채총계", "부채합계", "총부채"])
_EQUITY_TOTAL_LABELS = frozenset(["자본총계", "자본합계", "총자본"])

_CASH_BS_LABELS = frozenset(["현금및현금성자산"])
_CASH_CF_END_LABELS = frozenset([
    "기말현금및현금성자산", "현금및현금성자산기말잔액",
    "현금및현금성자산의기말잔액", "기말의현금및현금성자산",
])
_EQUITY_SCE_END_LABELS = frozenset(["자본총계"])
_EQUITY_SCE_END_FRAGMENTS = ("기말자본", "기말의자본", "자본총계")


def check_statement_ties(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(_bs_equation_checks(report, tolerance=tolerance))
    results.extend(_cash_tie_checks(report, tolerance=tolerance))
    results.extend(_equity_tie_checks(report, tolerance=tolerance))
    return results


def _bs_equation_checks(report: FullReport, *, tolerance: int) -> list[CheckResult]:
    bs = _find_statement(report, ("재무상태표",))
    if bs is None:
        return []
    table = _first_table(bs)
    if table is None:
        return []

    asset_row = _find_row(table, _ASSET_TOTAL_LABELS)
    liab_row = _find_row(table, _LIAB_TOTAL_LABELS)
    equity_row = _find_row(table, _EQUITY_TOTAL_LABELS)

    if asset_row is None or liab_row is None or equity_row is None:
        return [
            _tie_result(
                check_id="statement_bs_equation",
                check_type="statement_bs_equation",
                scope="report",
                note_no="",
                title="재무상태표 기본등식",
                expected=None,
                actual=None,
                difference=None,
                tolerance=tolerance,
                status=PARSE_UNCERTAIN,
                reason="자산총계·부채총계·자본총계 중 하나 이상 미발견",
                evidence=[],
            )
        ]

    equity_val = _current_amount(table, equity_row)
    asset_val = _current_amount(table, asset_row)
    liab_val = _current_amount(table, liab_row)
    if asset_val is None or liab_val is None or equity_val is None:
        return []

    expected = liab_val + equity_val
    actual = asset_val
    difference = actual - expected
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP

    return [_tie_result(
        check_id="statement_bs_equation:current",
        check_type="statement_bs_equation",
        title="재무상태표 BS equation: 자산총계 = 부채총계 + 자본총계",
        expected=expected,
        actual=actual,
        difference=difference,
        tolerance=tolerance,
        status=status,
        reason="BS equation 성립" if status == MATCHED else "BS equation 불일치",
        evidence=[
            CheckEvidence(asset_row[0], asset_val, _row_source(table, asset_row, "bs")),
            CheckEvidence(liab_row[0], liab_val, _row_source(table, liab_row, "bs")),
            CheckEvidence(equity_row[0], equity_val, _row_source(table, equity_row, "bs")),
        ],
        note_no="bs",
    )]


def _cash_tie_checks(report: FullReport, *, tolerance: int) -> list[CheckResult]:
    bs = _find_statement(report, ("재무상태표",))
    cf = _find_statement(report, ("현금흐름표",))
    if bs is None or cf is None:
        return []

    bs_table = _first_table(bs)
    cf_table = _first_table(cf)
    if bs_table is None or cf_table is None:
        return []

    bs_row = _find_row(bs_table, _CASH_BS_LABELS)
    cf_row = _find_row(cf_table, _CASH_CF_END_LABELS)
    if bs_row is None or cf_row is None:
        return []

    bs_val = _current_amount(bs_table, bs_row)
    cf_val = _current_amount(cf_table, cf_row)
    if bs_val is None or cf_val is None:
        return []

    difference = bs_val - cf_val
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP

    return [_tie_result(
        check_id="statement_cash_tie:current",
        check_type="statement_cash_tie",
        title="재무상태표 현금 ↔ 현금흐름표 기말 현금 대사",
        expected=cf_val,
        actual=bs_val,
        difference=difference,
        tolerance=tolerance,
        status=status,
        reason="BS 현금 = CF 기말 현금" if status == MATCHED else "BS 현금 ≠ CF 기말 현금",
        evidence=[
            CheckEvidence(bs_row[0], bs_val, _row_source(bs_table, bs_row, "bs")),
            CheckEvidence(cf_row[0], cf_val, _row_source(cf_table, cf_row, "cf")),
        ],
        note_no="cross_statement",
    )]


def _equity_tie_checks(report: FullReport, *, tolerance: int) -> list[CheckResult]:
    bs = _find_statement(report, ("재무상태표",))
    sce = _find_statement(report, ("자본변동표",))
    if bs is None or sce is None:
        return []

    bs_table = _first_table(bs)
    sce_table = _first_table(sce)
    if bs_table is None or sce_table is None:
        return []

    bs_row = _find_row(bs_table, _EQUITY_TOTAL_LABELS)
    sce_row = _find_sce_equity_end_row(sce_table)
    if bs_row is None or sce_row is None:
        return []

    bs_val = _current_amount(bs_table, bs_row)
    sce_val = _current_amount(sce_table, sce_row)
    if bs_val is None or sce_val is None:
        return []

    difference = bs_val - sce_val
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP

    return [_tie_result(
        check_id="statement_equity_tie:current",
        check_type="statement_equity_tie",
        title="재무상태표 자본총계 ↔ 자본변동표 기말 자본 대사",
        expected=sce_val,
        actual=bs_val,
        difference=difference,
        tolerance=tolerance,
        status=status,
        reason="BS 자본총계 = SCE 기말 자본총계" if status == MATCHED else "BS 자본총계 ≠ SCE 기말 자본총계",
        evidence=[
            CheckEvidence(bs_row[0], bs_val, _row_source(bs_table, bs_row, "bs")),
            CheckEvidence(sce_row[0], sce_val, _row_source(sce_table, sce_row, "sce")),
        ],
        note_no="cross_statement",
    )]


def _find_statement(report: FullReport, title_fragments: tuple[str, ...]) -> ReportSection | None:
    for section in report.statements:
        if any(frag in section.title for frag in title_fragments):
            return section
    return None


def _first_table(section: ReportSection) -> ReportTable | None:
    for block in section.blocks:
        if block.table is not None:
            return block.table
    return None


def _find_row(table: ReportTable, label_set: frozenset[str]) -> list[str] | None:
    for row in table.rows:
        if row and compact(row[0]) in label_set:
            return row
    return None


def _find_sce_equity_end_row(table: ReportTable) -> list[str] | None:
    candidate = None
    for row in table.rows:
        if not row:
            continue
        label = compact(row[0])
        if label in _EQUITY_SCE_END_LABELS or any(frag in label for frag in _EQUITY_SCE_END_FRAGMENTS):
            candidate = row
    return candidate


def _current_amount(table: "ReportTable", row: list[str]) -> int | None:
    for cell in row[1:]:
        val = parse_amount(cell)
        if val is not None:
            return val * table.unit_multiplier
    return None


def _row_source(table: ReportTable, row: list[str], statement_kind: str) -> str:
    for i, r in enumerate(table.rows):
        if r is row:
            return f"statement:{statement_kind}/table:{table.index}/row:{i}"
    return f"statement:{statement_kind}/table:{table.index}/row:unknown"


def _tie_result(
    *,
    check_id: str,
    check_type: str,
    scope: str = "report",
    title: str,
    expected: int | None,
    actual: int | None,
    difference: int | None,
    tolerance: int,
    status: str,
    reason: str,
    evidence: list[CheckEvidence],
    note_no: str,
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type=check_type,
        status=status,
        scope=scope,
        note_no=note_no,
        title=title,
        expected=expected,
        actual=actual,
        difference=difference,
        tolerance=tolerance,
        reason=reason,
        evidence=evidence,
    )
