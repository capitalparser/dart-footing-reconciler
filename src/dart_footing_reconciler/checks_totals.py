"""Generic row and column total checks."""

from __future__ import annotations

import re

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
from dart_footing_reconciler.validation_relevance import classify_validation_relevance

TOTAL_LABELS = ("소계", "합계", "계", "총계", "자산총계", "부채총계", "자본총계")


def check_table_totals(table: ReportTable, *, note_no: str, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    seen_targets: set[str] = set()
    for batch in (
        _row_total_results(table, note_no=note_no, tolerance=tolerance),
        _section_total_results(table, note_no=note_no, tolerance=tolerance),
        _column_total_results(table, note_no=note_no, tolerance=tolerance),
    ):
        for result in batch:
            target = _result_target(result)
            if target and target in seen_targets:
                continue
            if target:
                seen_targets.add(target)
            results.append(result)
    if not results:
        status = PARSE_UNCERTAIN if _requires_total_check(table) else NOT_TESTED
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
    rows = table.rows or []
    if _data_start_row(rows) <= 1:
        # 단일 헤더: 합계 컬럼이 정확히 1개·최우측이고 구성요소 라벨이 서로 다를
        # 때만 신뢰한다. (그룹 구조[보통|우선|합계]x2 등은 보류.)
        header_segments: list[tuple[int, int]] = (
            _single_header_segments(rows[0]) if rows else []
        )
    else:
        # 다단 헤더 표는 leaf 라벨 배타성 가드를 통과한 합계 구간만 신뢰한다.
        # (측정 요약 표처럼 토지/건물 그룹이 섞인 헤더의 무조건 합산을 막는다.)
        # 가드가 보류하면 최우측 합계로의 무조건 fallback은 하지 않는다 —
        # 중간 소계까지 합산해 거짓 차이를 만든다(배당주식수·공정가치 FP).
        header_segments = _header_block_total_segments(rows)
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if row and _is_total_label(row[0]):
            continue
        if header_segments:
            segments = header_segments
        else:
            row_total_col = _total_column(row)
            segments = [(1, row_total_col)] if row_total_col is not None else []
        for start_col, total_col in segments:
            if total_col is None or total_col - start_col < 2:
                continue
            values = [_parse_amount_cell(cell) for cell in row[start_col:total_col]]
            actual = _parse_amount_cell(row[total_col]) if total_col < len(row) else None
            if actual is None or any(value is None for value in values):
                continue
            expected = sum(value for value in values if value is not None)
            results.append(
                _result(
                    check_id=f"total:{note_no}:table{table.index}:row{row_idx}:col{total_col}",
                    note_no=note_no,
                    title=f"{row[0]} 행 합계",
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


def _section_total_results(table: ReportTable, *, note_no: str, tolerance: int) -> list[CheckResult]:
    rows = table.rows or []
    data_start = _data_start_row(rows)
    if len(rows) < 4 or data_start >= len(rows):
        return []
    subtotal_rows = [
        idx
        for idx in range(data_start, len(rows))
        if rows[idx] and _is_total_label(rows[idx][0]) and not _is_grand_total_label(rows[idx][0])
    ]
    if len(subtotal_rows) <= 1:
        return []

    results: list[CheckResult] = []
    component_rows: list[tuple[int, list[str]]] = []
    subtotal_snapshots: list[tuple[int, list[str]]] = []
    for row_idx in range(data_start, len(rows)):
        row = rows[row_idx]
        if not row:
            continue
        if _is_total_label(row[0]):
            if _is_grand_total_label(row[0]):
                results.extend(
                    _grand_total_results(
                        table,
                        subtotal_snapshots,
                        row_idx,
                        row,
                        note_no=note_no,
                        tolerance=tolerance,
                    )
                )
                component_rows = []
                subtotal_snapshots = []
                continue
            subtotal_results = _subtotal_results(
                table,
                component_rows,
                row_idx,
                row,
                note_no=note_no,
                tolerance=tolerance,
            )
            if subtotal_results:
                results.extend(subtotal_results)
                subtotal_snapshots.append((row_idx, row))
            component_rows = []
            continue
        if _component_row_has_amount(row):
            component_rows.append((row_idx, row))
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


def _subtotal_results(
    table: ReportTable,
    component_rows: list[tuple[int, list[str]]],
    subtotal_row_idx: int,
    subtotal_row: list[str],
    *,
    note_no: str,
    tolerance: int,
) -> list[CheckResult]:
    if len(component_rows) < 2:
        return []
    results: list[CheckResult] = []
    for col_idx in range(1, len(subtotal_row)):
        actual = _parse_amount_cell(subtotal_row[col_idx])
        values = [
            _parse_amount_cell(row[col_idx]) if col_idx < len(row) else None
            for _, row in component_rows
        ]
        if actual is None or not values or any(value is None for value in values):
            continue
        expected = sum(value for value in values if value is not None)
        results.append(
            _result(
                check_id=(
                    f"total:{note_no}:table{table.index}:section"
                    f"{subtotal_row_idx}:col{col_idx}"
                ),
                note_no=note_no,
                title=f"{subtotal_row[0]} 소계",
                expected=expected,
                actual=actual,
                tolerance=tolerance,
                reason_ok="section subtotal agrees",
                reason_gap="section subtotal does not agree",
                evidence=[
                    CheckEvidence(
                        subtotal_row[0],
                        actual,
                        (
                            f"note:{note_no}/table:{table.index}/row:"
                            f"{subtotal_row_idx}/col:{col_idx}"
                        ),
                    )
                ],
            )
        )
    return results


def _grand_total_results(
    table: ReportTable,
    subtotal_rows: list[tuple[int, list[str]]],
    total_row_idx: int,
    total_row: list[str],
    *,
    note_no: str,
    tolerance: int,
) -> list[CheckResult]:
    if len(subtotal_rows) < 2:
        return []
    results: list[CheckResult] = []
    for col_idx in range(1, len(total_row)):
        actual = _parse_amount_cell(total_row[col_idx])
        values = [
            _parse_amount_cell(row[col_idx]) if col_idx < len(row) else None
            for _, row in subtotal_rows
        ]
        if actual is None or not values or any(value is None for value in values):
            continue
        expected = sum(value for value in values if value is not None)
        results.append(
            _result(
                check_id=f"total:{note_no}:table{table.index}:grand:col{col_idx}",
                note_no=note_no,
                title=f"{total_row[0]} 총계",
                expected=expected,
                actual=actual,
                tolerance=tolerance,
                reason_ok="grand total agrees",
                reason_gap="grand total does not agree",
                evidence=[
                    CheckEvidence(
                        total_row[0],
                        actual,
                        (
                            f"note:{note_no}/table:{table.index}/row:"
                            f"{total_row_idx}/col:{col_idx}"
                        ),
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


def _result_target(result: CheckResult) -> str | None:
    if not result.evidence:
        return None
    return result.evidence[0].source


def _total_column(row: list[str]) -> int | None:
    for idx in range(len(row) - 1, -1, -1):
        cell = row[idx]
        if _is_total_label(cell):
            return idx
    return None


def _total_row(rows: list[list[str]]) -> int | None:
    for idx in range(len(rows) - 1, 0, -1):
        if rows[idx] and _is_total_label(rows[idx][0]):
            return idx
    return None


def _is_total_label(value: str) -> bool:
    compact = value.replace(" ", "")
    return any(label == compact or compact.endswith(label) for label in TOTAL_LABELS)


def _is_grand_total_label(value: str) -> bool:
    compact = value.replace(" ", "")
    return compact in {"총계", "자산총계", "부채총계", "자본총계"}


def _has_amounts(table: ReportTable) -> bool:
    return any(parse_amount(cell) is not None for row in table.rows for cell in row)


def _amount_cell(value: str) -> bool:
    """금액 형태의 셀만 True.

    비율(0.0610), 내용연수(5~40년), 기간(30일 미만) 등 숫자가 섞인 서술
    셀은 제외한다. 괄호/쉼표/부호 표기만 허용하고 코어가 전부 숫자여야 한다.
    """
    core = re.sub(r"[,\s()\-−△]", "", value)
    if not core:
        return False
    return core.isdigit() and parse_amount(value) is not None


def _parse_amount_cell(value: str) -> int | None:
    if not _amount_cell(value):
        return None
    return parse_amount(value)


def _component_row_has_amount(row: list[str]) -> bool:
    return any(_amount_cell(cell) for cell in row[1:])


def _summable_structure(table: ReportTable) -> bool:
    """합계 검증이 의미를 가지려면 합산할 구성요소 묶음이 있어야 한다.

    행 방향(구성요소 2개 이상 + 합계)이나 열 방향(3개 이상 금액 행) 중
    하나라도 없으면 footing 대상 표가 아니므로 parse_uncertain으로
    분류하지 않는다(내용연수·할인율·가정 공시 표 등).
    """
    rows = table.rows or []
    for row in rows:
        if sum(1 for cell in row[1:] if _amount_cell(cell)) >= 3:
            return True
    width = max((len(row) for row in rows), default=0)
    for col in range(1, width):
        count = sum(1 for row in rows if col < len(row) and _amount_cell(row[col]))
        if count >= 3:
            return True
    return False


def _data_start_row(rows: list[list[str]]) -> int:
    """첫 금액 데이터 행 인덱스(그 앞까지가 헤더 블록)."""
    return next(
        (
            idx
            for idx, row in enumerate(rows)
            if any(_amount_cell(cell) for cell in row[1:])
        ),
        len(rows),
    )


def _header_block_total_segments(rows: list[list[str]]) -> list[tuple[int, int]]:
    """다단 헤더 표의 '합계' 열들을 (구간 시작열, 합계열) 세그먼트로 찾는다.

    선행 헤더 블록(금액 셀이 없는 연속 행) 안에서 합계/총계로 끝나는 헤더
    텍스트의 열을 모으고, colspan 반복을 같은 텍스트의 인접 열 그룹으로
    접는다. 각 합계 열의 합산 구간은 직전 합계 열 다음부터 자기 직전
    열까지로 본다(당기/전기 구간별 합계 패턴 지원). 구간 안의 유효 leaf
    라벨(헤더 블록 아래→위 첫 비공백 텍스트)이 모두 존재하고 서로 다를
    때만 배타적 구성요소 합산으로 채택한다. (토지/건물 그룹이 섞인 측정
    요약 표처럼 leaf 라벨이 반복되면 보류해 parse_uncertain을 유지한다.)
    """
    data_start = _data_start_row(rows)
    if data_start < 2:
        return []
    # 컬럼 단위로 모은다. 합계 헤더가 여러 헤더 행에 걸쳐 반복돼도 한 컬럼은
    # 한 번만 센다(같은 합계 열을 그룹 여러 개로 오판하지 않도록).
    col_text: dict[int, str] = {}
    for row in rows[:data_start]:
        for col, cell in enumerate(row[1:], start=1):
            text = "".join(cell.split())
            if text.endswith(("합계", "총계")):
                col_text.setdefault(col, text)
    candidates = sorted(col_text.items())
    if not candidates:
        return []
    groups: list[tuple[str, int]] = []  # (text, last_col)
    for col, text in sorted(candidates):
        if groups and groups[-1][0] == text and col == groups[-1][1] + 1:
            groups[-1] = (text, col)
        else:
            groups.append((text, col))

    def effective_leaf_label(col: int) -> str:
        for row in reversed(rows[:data_start]):
            if col < len(row):
                text = "".join(row[col].split())
                if text:
                    return text
        return ""

    # 합계 그룹이 둘 이상이면(중간 소계·구간 합계 혼합 구조) 구성요소
    # 배타성이 보장되지 않아 거짓 차이를 만들기 쉬우므로 보류한다.
    if len(groups) != 1:
        return []
    total_col = groups[0][1]
    start_col = 1
    if total_col - start_col < 2:
        return []
    component_labels = [
        effective_leaf_label(col) for col in range(start_col, total_col)
    ]
    if any(not label for label in component_labels):
        return []
    if len(set(component_labels)) != len(component_labels):
        return []
    return [(start_col, total_col)]


def _single_header_segments(header_row: list[str]) -> list[tuple[int, int]]:
    """단일 헤더 행에서 신뢰 가능한 (시작열, 합계열) 세그먼트를 1개만 돌려준다.

    합계/소계/계 컬럼이 정확히 1개이고 최우측이며, 그 앞 구성요소 헤더가 모두
    비어있지 않고 서로 다를 때만 채택한다. 합계 컬럼이 둘 이상이면(그룹 구조
    [보통|우선|합계]x2 등) 그룹을 가로질러 합산할 위험이 있어 보류한다.
    """
    total_cols = [
        col for col, cell in enumerate(header_row) if col >= 1 and _is_total_label(cell)
    ]
    if len(total_cols) != 1:
        return []
    total_col = total_cols[0]
    if total_col != len(header_row) - 1 or total_col < 3:
        return []
    components = ["".join(header_row[col].split()) for col in range(1, total_col)]
    if any(not label for label in components):
        return []
    if len(set(components)) != len(components):
        return []
    return [(1, total_col)]


def _requires_total_check(table: ReportTable) -> bool:
    if not _has_amounts(table):
        return False
    if not _summable_structure(table):
        return False
    rows = table.rows or []
    headers = tuple(rows[0]) if rows else ()
    row_labels = tuple(row[0] for row in rows[1:] if row)
    relevance = classify_validation_relevance(
        title=table.heading,
        headers=headers,
        row_labels=row_labels,
    )
    return relevance.validation_relevant
