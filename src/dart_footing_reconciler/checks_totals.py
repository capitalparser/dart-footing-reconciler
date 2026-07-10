"""Generic row and column total checks."""

from __future__ import annotations

import re

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    NOT_TESTED,
    NOT_TESTED_NO_APPLICABLE_CHECK,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import ReportTable
from dart_footing_reconciler.label_resolver import AMOUNT_PARSE_FAILED
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
                parse_uncertain_reason=AMOUNT_PARSE_FAILED if status == PARSE_UNCERTAIN else None,
                not_tested_reason=NOT_TESTED_NO_APPLICABLE_CHECK if status == NOT_TESTED else None,
            )
        )
    return results


def _row_total_results(table: ReportTable, *, note_no: str, tolerance: int) -> list[CheckResult]:
    results: list[CheckResult] = []
    rows = table.rows or []
    if _data_start_row(rows) <= 1:
        # 단일 헤더: 합계 컬럼이 정확히 1개·최우측이고 구성요소 라벨이 서로 다를
        # 때만 신뢰한다. (그룹 구조[보통|우선|합계]x2 등은 보류.)
        header_groups: list[tuple[list[int], int]] = (
            [(list(range(start_col, total_col)), total_col)
             for start_col, total_col in _single_header_segments(rows[0])]
            if rows else []
        )
    else:
        # 다단 헤더 표는 헤더 경로상 직접 자식인 leaf/소계만 합산한다.
        # 최우측 합계로 단순 fallback하지 않아 중간 소계를 중복 합산하지 않는다.
        header_groups = _header_block_total_groups(rows)
    for row_idx, row in enumerate(table.rows[1:], start=1):
        if row and _is_total_label(row[0]):
            continue
        if header_groups:
            groups = header_groups
        else:
            row_total_col = _total_column(row)
            groups = (
                [(list(range(1, row_total_col)), row_total_col)]
                if row_total_col is not None else []
            )
        for component_cols, total_col in groups:
            if total_col is None or len(component_cols) < 2:
                continue
            actual = _parse_amount_cell(row[total_col]) if total_col < len(row) else None
            parsed_components = [
                (col, _parse_amount_cell(row[col]) if col < len(row) else None)
                for col in component_cols
            ]
            if actual is None or _has_non_blank_unparsed_component(row, parsed_components):
                continue
            numeric_components = [
                (col, amount) for col, amount in parsed_components if amount is not None
            ]
            if len(numeric_components) < 2:
                continue
            expected = sum(amount for _, amount in numeric_components)
            row_components = [
                CheckEvidence(
                    row[0],
                    amount,
                    f"note:{note_no}/table:{table.index}/row:{row_idx}/col:{col}",
                    role="component",
                )
                for col, amount in numeric_components
            ]
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
                        ),
                        *row_components,
                    ],
                )
            )
    return results


def _has_non_blank_unparsed_component(
    row: list[str],
    parsed_components: list[tuple[int, int | None]],
) -> bool:
    for col, amount in parsed_components:
        if amount is not None:
            continue
        if col < len(row) and row[col].strip():
            return True
    return False


def _section_total_results(table: ReportTable, *, note_no: str, tolerance: int) -> list[CheckResult]:
    rows = table.rows or []
    data_start = _data_start_row(rows)
    if len(rows) < 4 or data_start >= len(rows):
        return []
    # 금액이 있는 소계 행만 센다. 비율-only '합계'(예: 평균유효세율 합계)는
    # 실제 소계가 아니므로, 단일 조정표(법인세 등)를 다중섹션으로 오인해
    # 비가산 base 행(세전이익 등)을 합산하는 FP를 막는다.
    subtotal_rows = [
        idx
        for idx in range(data_start, len(rows))
        if rows[idx]
        and _is_total_label(rows[idx][0])
        and not _is_grand_total_label(rows[idx][0])
        and _component_row_has_amount(rows[idx])
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
            if _is_grand_total_label(row[0]) or _is_trailing_total_over_subtotals(
                rows,
                row_idx,
                subtotal_snapshots,
            ):
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
            if _component_row_has_amount(row):
                subtotal_snapshots.append((row_idx, row))
            component_rows = []
            continue
        if _component_row_has_amount(row):
            component_rows.append((row_idx, row))
    return results


def _is_trailing_total_over_subtotals(
    rows: list[list[str]],
    row_idx: int,
    subtotal_snapshots: list[tuple[int, list[str]]],
) -> bool:
    if len(subtotal_snapshots) < 2:
        return False
    if not rows[row_idx] or _compact_label(rows[row_idx][0]) not in {"합계", "총계"}:
        return False
    amount_rows = [
        idx for idx, row in enumerate(rows)
        if row and _component_row_has_amount(row)
    ]
    return bool(amount_rows and row_idx == amount_rows[-1])


def _column_total_results(table: ReportTable, *, note_no: str, tolerance: int) -> list[CheckResult]:
    if len(table.rows) < 3:
        return []
    total_row_idx = _total_row(table.rows)
    if total_row_idx is None:
        return []
    total_row = table.rows[total_row_idx]
    results: list[CheckResult] = []
    for col_idx in range(1, min(len(total_row), max(len(row) for row in table.rows[:total_row_idx]))):
        if _column_total_has_omitted_component_risk(table.rows, total_row_idx, col_idx):
            continue
        actual = _parse_amount_cell(total_row[col_idx])
        component_rows = [
            (ri, row, amount)
            for ri, row in _column_component_rows(table.rows, total_row_idx, col_idx, total_row[0])
            if (amount := _parse_amount_cell(row[col_idx])) is not None
        ]
        # 구성요소가 2개 미만이면 '합계 = 단일 항목'이라 footing 의미가 없고,
        # 무관한 단일 행(계약수익 등)을 합계 구성요소로 오인하기 쉽다 → 보류.
        if actual is None or len(component_rows) < 2:
            continue
        expected = sum(amount for _, _, amount in component_rows)
        components = [
            CheckEvidence(
                row[0],
                amount,
                f"note:{note_no}/table:{table.index}/row:{ri}/col:{col_idx}",
                role="component",
            )
            for ri, row, amount in component_rows
        ]
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
                    ),
                    *components,
                ],
            )
        )
    return results


def _column_component_rows(
    rows: list[list[str]],
    total_row_idx: int,
    col_idx: int,
    total_label: str,
) -> list[tuple[int, list[str]]]:
    component_rows: list[tuple[int, list[str]]] = []
    for ri in range(1, total_row_idx):
        row = rows[ri]
        if col_idx >= len(row) or _is_total_label(row[0]):
            continue
        if _is_non_additive_column_component(total_label, row[0]):
            continue
        component_rows.append((ri, row))
    return component_rows


def _column_total_has_omitted_component_risk(
    rows: list[list[str]],
    total_row_idx: int,
    col_idx: int,
) -> bool:
    if not any(rows[ri] and _is_total_label(rows[ri][0]) for ri in range(1, total_row_idx)):
        return False
    total_row = rows[total_row_idx]
    numeric_cols = [
        idx for idx in range(1, len(total_row))
        if _parse_amount_cell(total_row[idx]) is not None
    ]
    return numeric_cols == [col_idx]


def _is_non_additive_column_component(total_label: str, row_label: str) -> bool:
    total = _compact_label(total_label)
    row = _compact_label(row_label)
    if not total or not row:
        return False
    if "법인세비용" in total and "차감전순이익" in row:
        return True
    if "손익으로인식된" in total and row.startswith("기초"):
        return True
    if "증가감소합계" in total and row.startswith("기초"):
        return True
    return False


def _compact_label(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "")


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
    if not _subtotal_scope_matches_components(subtotal_row[0], [row for _, row in component_rows]):
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
        subtotal_components = [
            CheckEvidence(
                comp_row[0],
                _parse_amount_cell(comp_row[col_idx]) if col_idx < len(comp_row) else None,
                f"note:{note_no}/table:{table.index}/row:{comp_row_idx}/col:{col_idx}",
                role="component",
            )
            for comp_row_idx, comp_row in component_rows
            if col_idx < len(comp_row) and _parse_amount_cell(comp_row[col_idx]) is not None
        ]
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
                    ),
                    *subtotal_components,
                ],
            )
        )
    return results


def _subtotal_scope_matches_components(
    subtotal_label: str,
    component_rows: list[list[str]],
) -> bool:
    scope_tokens = _subtotal_scope_tokens(subtotal_label)
    if scope_tokens is None:
        return True
    return all(any(scope in _compact_label(row[0]) for scope in scope_tokens) for row in component_rows if row)


def _subtotal_scope_tokens(label: str) -> tuple[str, ...] | None:
    compact = _compact_label(label)
    if "비유동" in compact:
        return ("비유동", "장기")
    if "유동" in compact:
        return ("유동", "단기")
    return None


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
        components = [
            CheckEvidence(
                row[0],
                _parse_amount_cell(row[col_idx]) if col_idx < len(row) else None,
                f"note:{note_no}/table:{table.index}/row:{subtotal_row_idx}/col:{col_idx}",
                role="component",
            )
            for subtotal_row_idx, row in subtotal_rows
            if col_idx < len(row) and _parse_amount_cell(row[col_idx]) is not None
        ]
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
                        role="total",
                    ),
                    *components,
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
    # 합계 행으로 인정하려면 금액이 있어야 한다. 비율-only '합계'(평균유효세율
    # 합계 등)를 총계로 잡아 거짓 차이를 내는 것을 막는다.
    for idx in range(len(rows) - 1, 0, -1):
        if rows[idx] and _is_total_label(rows[idx][0]) and _component_row_has_amount(rows[idx]):
            return idx
    return None


def _is_total_label(value: str) -> bool:
    compact = _compact_label(value)
    if any(label == compact or compact.endswith(label) for label in TOTAL_LABELS):
        return True
    return any(
        compact.endswith(f"{label}{descriptor}")
        for label in ("합계", "총계")
        for descriptor in ("공정가치", "장부금액", "장부가액", "금액")
    )


def _is_grand_total_label(value: str) -> bool:
    compact = _compact_label(value)
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


def _header_block_total_groups(rows: list[list[str]]) -> list[tuple[list[int], int]]:
    """다단 헤더 표의 총계 컬럼별 직접 구성요소 컬럼을 찾는다.

    DART 병합헤더는 같은 상위 라벨을 여러 열에 반복한다. 따라서 leaf 라벨
    하나만 보지 않고 헤더 전체 경로를 만든 뒤, 각 합계 컬럼의 직접 자식
    소계 컬럼 또는 leaf 컬럼만 합산한다. 이 방식이면 리스 만기분석의
    자산별 소계와 영업부문 수익의 nested subtotal을 중복 없이 검증할 수
    있다.
    """
    data_start = _data_start_row(rows)
    if data_start < 2:
        return []
    header_rows = rows[:data_start]
    width = max((len(row) for row in header_rows), default=0)
    total_cols = [
        col for col in range(1, width)
        if any(
            _is_total_header_candidate(_compact_label(row[col]))
            for row in header_rows
            if col < len(row)
        )
    ]
    if not total_cols:
        return []
    column_paths = {
        col: _header_column_path(header_rows, col)
        for col in range(1, width)
    }
    total_paths = {
        col: _header_total_node_path(header_rows, col)
        for col in total_cols
    }
    groups: list[tuple[list[int], int]] = []
    for total_col in total_cols:
        total_path = total_paths[total_col]
        if not total_path:
            continue
        component_total_cols = _direct_child_total_cols(total_col, total_paths)
        if len(component_total_cols) >= 2:
            groups.append((component_total_cols, total_col))
            continue
        leaf_cols = _leaf_cols_for_total_path(total_col, total_path, column_paths, total_cols)
        if len(leaf_cols) < 2:
            continue
        if _paths_are_unique(column_paths[col] for col in leaf_cols):
            groups.append((leaf_cols, total_col))
    return groups


def _is_total_header_candidate(text: str) -> bool:
    return text.endswith("합계") or text in {"총계", "자산총계", "부채총계", "자본총계"}


def _header_column_path(header_rows: list[list[str]], col: int) -> tuple[str, ...]:
    labels: list[str] = []
    for row in header_rows:
        if col >= len(row):
            continue
        text = _compact_label(row[col])
        if not text:
            continue
        if labels and labels[-1] == text:
            continue
        labels.append(text)
    return tuple(labels)


def _header_total_node_path(header_rows: list[list[str]], col: int) -> tuple[str, ...]:
    deepest_total_row = None
    for row_idx, row in enumerate(header_rows):
        if col < len(row) and _is_total_header_candidate(_compact_label(row[col])):
            deepest_total_row = row_idx
    if deepest_total_row is None:
        return ()
    labels: list[str] = []
    for row in header_rows[: deepest_total_row + 1]:
        if col >= len(row):
            continue
        text = _compact_label(row[col])
        if not text:
            continue
        if _is_total_header_candidate(text):
            text = _strip_total_suffix(text)
        if not text:
            continue
        if labels and labels[-1] == text:
            continue
        labels.append(text)
    return tuple(labels)


def _direct_child_total_cols(
    total_col: int,
    total_paths: dict[int, tuple[str, ...]],
) -> list[int]:
    parent_path = total_paths[total_col]
    child_cols: list[int] = []
    for candidate_col, candidate_path in total_paths.items():
        if candidate_col >= total_col:
            continue
        if not _path_is_strict_prefix(parent_path, candidate_path):
            continue
        if any(
            other_col != candidate_col
            and other_col < total_col
            and _path_is_strict_prefix(parent_path, other_path)
            and _path_is_strict_prefix(other_path, candidate_path)
            for other_col, other_path in total_paths.items()
        ):
            continue
        child_cols.append(candidate_col)
    return sorted(child_cols)


def _leaf_cols_for_total_path(
    total_col: int,
    total_path: tuple[str, ...],
    column_paths: dict[int, tuple[str, ...]],
    total_cols: list[int],
) -> list[int]:
    leaf_cols = _leaf_cols_with_prefix(total_col, total_path, column_paths, total_cols)
    if len(leaf_cols) >= 2 or len(total_path) <= 1:
        return leaf_cols
    return _leaf_cols_with_prefix(total_col, total_path[:-1], column_paths, total_cols)


def _leaf_cols_with_prefix(
    total_col: int,
    prefix: tuple[str, ...],
    column_paths: dict[int, tuple[str, ...]],
    total_cols: list[int],
) -> list[int]:
    return [
        col for col, path in column_paths.items()
        if col < total_col
        and col not in total_cols
        and _path_is_strict_prefix(prefix, path)
    ]


def _path_is_strict_prefix(parent: tuple[str, ...], child: tuple[str, ...]) -> bool:
    return len(parent) < len(child) and child[: len(parent)] == parent


def _paths_are_unique(paths) -> bool:
    paths = list(paths)
    return all(paths) and len(set(paths)) == len(paths)


def _has_period_group_header(
    header_rows: list[list[str]],
    start_col: int,
    total_col: int,
) -> bool:
    for row in header_rows:
        labels = [
            _strip_total_suffix("".join(row[col].split()))
            for col in range(start_col, total_col + 1)
            if col < len(row) and "".join(row[col].split())
        ]
        if labels and len(set(labels)) == 1 and _is_period_group_label(labels[0]):
            return True
    return False


def _strip_total_suffix(value: str) -> str:
    for suffix in ("합계", "총계"):
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def _is_period_group_label(value: str) -> bool:
    normalized = value.replace("(", "").replace(")", "")
    if normalized in {
        "당기",
        "전기",
        "전전기",
        "당기말",
        "전기말",
        "전전기말",
        "당분기",
        "전분기",
        "당분기말",
        "전분기말",
        "당반기",
        "전반기",
        "당반기말",
        "전반기말",
    }:
        return True
    return bool(
        re.fullmatch(r"제?\d+(당|전)?기(말|현재|말현재)?", normalized)
        or re.fullmatch(r"\d{4}년(말|현재|말현재)?", normalized)
    )


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
