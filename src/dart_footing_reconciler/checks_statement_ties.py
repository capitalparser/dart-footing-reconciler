"""Statement-level tie checks: BS equation and cross-statement amount ties."""
from __future__ import annotations

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    CheckEvidence, CheckResult,
    MATCHED, PARSE_UNCERTAIN, UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.label_resolver import (
    AccountRole, LabelResolver, RowMatch,
    LABEL_NOT_FOUND, LOW_CONFIDENCE_MATCH,
    _compact,
)


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

    asset_m = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    liab_m = LabelResolver.find_row(table, AccountRole.LIABILITY_TOTAL)
    equity_m = LabelResolver.find_row(table, AccountRole.EQUITY_TOTAL)

    # Guard: if liability row is the same physical row as asset row, it's a false
    # CONTAINS match (e.g. '자본과부채총계' contains '부채총계'). Treat as not found.
    if liab_m is not None and asset_m is not None and liab_m.row is asset_m.row:
        liab_m = None

    if asset_m is None or liab_m is None or equity_m is None:
        return [_tie_result(
            check_id="statement_bs_equation",
            check_type="statement_bs_equation",
            scope="report", note_no="",
            title="재무상태표 기본등식",
            expected=None, actual=None, difference=None, tolerance=tolerance,
            status=PARSE_UNCERTAIN,
            reason="자산총계·부채총계·자본총계 중 하나 이상 미발견",
            evidence=[],
            parse_uncertain_reason=LABEL_NOT_FOUND,
        )]

    _uncertain = _low_confidence_any(asset_m, liab_m, equity_m)

    asset_val = _current_amount(table, asset_m.row)
    liab_val = _current_amount(table, liab_m.row)
    equity_val = _current_amount(table, equity_m.row)
    if asset_val is None or liab_val is None or equity_val is None:
        return []

    expected = liab_val + equity_val
    actual = asset_val
    difference = actual - expected

    if _uncertain:
        status = PARSE_UNCERTAIN
        reason = f"BS equation — 신뢰도 낮은 행 사용 ({_uncertain})"
        uncertain_reason = LOW_CONFIDENCE_MATCH
    else:
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        reason = "BS equation 성립" if status == MATCHED else "BS equation 불일치"
        uncertain_reason = None

    return [_tie_result(
        check_id="statement_bs_equation:current",
        check_type="statement_bs_equation",
        title="재무상태표 BS equation: 자산총계 = 부채총계 + 자본총계",
        expected=expected, actual=actual, difference=difference,
        tolerance=tolerance, status=status, reason=reason,
        evidence=[
            CheckEvidence(asset_m.row[0], asset_val, _row_source(table, asset_m.row, "bs")),
            CheckEvidence(liab_m.row[0], liab_val, _row_source(table, liab_m.row, "bs")),
            CheckEvidence(equity_m.row[0], equity_val, _row_source(table, equity_m.row, "bs")),
        ],
        note_no="bs",
        parse_uncertain_reason=uncertain_reason,
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

    bs_m = LabelResolver.find_row(bs_table, AccountRole.CASH_END)
    cf_m = LabelResolver.find_row(cf_table, AccountRole.CASH_END)
    if bs_m is None or cf_m is None:
        return []

    bs_val = _current_amount(bs_table, bs_m.row)
    cf_val = _current_amount(cf_table, cf_m.row)
    if bs_val is None or cf_val is None:
        return []

    _uncertain = _low_confidence_any(bs_m, cf_m)
    difference = bs_val - cf_val
    if _uncertain:
        status = PARSE_UNCERTAIN
        reason = f"현금 대사 — 신뢰도 낮은 행 사용 ({_uncertain})"
        uncertain_reason = LOW_CONFIDENCE_MATCH
    else:
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        reason = "BS 현금 = CF 기말 현금" if status == MATCHED else "BS 현금 ≠ CF 기말 현금"
        uncertain_reason = None

    return [_tie_result(
        check_id="statement_cash_tie:current",
        check_type="statement_cash_tie",
        title="재무상태표 현금 ↔ 현금흐름표 기말 현금 대사",
        expected=cf_val, actual=bs_val, difference=difference,
        tolerance=tolerance, status=status, reason=reason,
        evidence=[
            CheckEvidence(bs_m.row[0], bs_val, _row_source(bs_table, bs_m.row, "bs")),
            CheckEvidence(cf_m.row[0], cf_val, _row_source(cf_table, cf_m.row, "cf")),
        ],
        note_no="cross_statement",
        parse_uncertain_reason=uncertain_reason,
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

    bs_m = LabelResolver.find_row(bs_table, AccountRole.EQUITY_TOTAL)
    sce_m = _find_sce_equity_end_row(sce_table)
    if bs_m is None or sce_m is None:
        return []

    bs_val = _current_amount(bs_table, bs_m.row)
    # SCE 기말자본 행은 (자본금, 자본잉여금, …, 자본총계) 매트릭스이고 헤더가
    # 퇴화('자본' 반복)인 경우가 많아 leftmost(첫 셀)는 자본금을 집는다. 기말 매트릭스
    # 행은 마지막 자본총계 컬럼을 쓰고, 단일값 '자본총계' 라벨 행은 기존 동작을 유지한다.
    if "기말" in _compact(sce_m.row[0]):
        sce_val = _rightmost_amount(sce_table, sce_m.row)
    else:
        sce_val = _current_amount(sce_table, sce_m.row)
    if bs_val is None or sce_val is None:
        return []

    difference = bs_val - sce_val
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    return [_tie_result(
        check_id="statement_equity_tie:current",
        check_type="statement_equity_tie",
        title="재무상태표 자본총계 ↔ 자본변동표 기말 자본 대사",
        expected=sce_val, actual=bs_val, difference=difference,
        tolerance=tolerance,
        status=status,
        reason="BS 자본총계 = SCE 기말 자본총계" if status == MATCHED else "BS 자본총계 ≠ SCE 기말 자본총계",
        evidence=[
            CheckEvidence(bs_m.row[0], bs_val, _row_source(bs_table, bs_m.row, "bs")),
            CheckEvidence(sce_m.row[0], sce_val, _row_source(sce_table, sce_m.row, "sce")),
        ],
        note_no="cross_statement",
    )]


# ── SCE equity end row (preserved — still label-based, returns RowMatch) ────

_EQUITY_SCE_END_LABELS = frozenset(["자본총계", "자본합계", "총자본"])
_EQUITY_SCE_END_FRAGMENTS = ("기말자본", "기말의자본")

def _find_sce_equity_end_row(table: ReportTable) -> RowMatch | None:
    from dart_footing_reconciler.label_resolver import MatchTier, RowMatch
    candidate = None
    for row in table.rows:
        if not row:
            continue
        from dart_footing_reconciler.label_resolver import _compact
        label = _compact(row[0])
        if label in _EQUITY_SCE_END_LABELS or any(frag in label for frag in _EQUITY_SCE_END_FRAGMENTS):
            candidate = row
    if candidate is None:
        return None
    return RowMatch(
        row=candidate, confidence=1.0, match_tier=MatchTier.EXACT,
        matched_label=candidate[0], candidates=[],
        reason=f"SCE 기말 자본 행: '{candidate[0]}'",
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _low_confidence_any(*matches: RowMatch) -> str | None:
    """Return label of first low-confidence match, or None if all are high confidence."""
    for m in matches:
        if m.confidence < 0.70:
            return m.matched_label
    return None


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


def _current_amount(table: ReportTable, row: list[str]) -> int | None:
    for cell in row[1:]:
        val = parse_amount(cell)
        if val is not None:
            return val * table.unit_multiplier
    return None


def _rightmost_amount(table: ReportTable, row: list[str]) -> int | None:
    """Rightmost parseable amount in a row (the SCE 자본총계 column for a 기말
    matrix row, where the leftmost cell is 자본금)."""
    for cell in reversed(row[1:]):
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
    check_id: str, check_type: str, scope: str = "report", title: str,
    expected: int | None, actual: int | None, difference: int | None,
    tolerance: int, status: str, reason: str, evidence: list[CheckEvidence],
    note_no: str, parse_uncertain_reason: str | None = None,
) -> CheckResult:
    return CheckResult(
        check_id=check_id, check_type=check_type, status=status,
        scope=scope, note_no=note_no, title=title,
        expected=expected, actual=actual, difference=difference,
        tolerance=tolerance, reason=reason, evidence=evidence,
        parse_uncertain_reason=parse_uncertain_reason,
    )
