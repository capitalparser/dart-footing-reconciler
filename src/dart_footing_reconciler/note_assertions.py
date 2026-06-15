"""Note-level audit assertion checks."""

from __future__ import annotations

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.scope import primary_note_sections

_BEGINNING_LABELS = ("기초", "기초장부금액", "기초금액", "전기말")
_ENDING_LABELS = ("기말", "기말장부금액", "기말금액", "당기말")
_ASSET_NOTE_TOKENS = ("유형자산", "무형자산", "투자부동산")
_DECREASE_LABELS = (
    "감가상각",
    "상각",
    "처분",
    "손상",
    "감소",
    "상환",
    "제각",
)


def check_note_assertions(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    scoped_notes = primary_note_sections(report.notes)
    for section in scoped_notes:
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            results.extend(_asset_rollforward_results(section, table, tolerance))
    return results


def _asset_rollforward_results(
    section: ReportSection, table: ReportTable, tolerance: int
) -> list[CheckResult]:
    if not _is_asset_rollforward(section.title, table.heading):
        return []
    beginning_idx = _find_row(table, _BEGINNING_LABELS)
    ending_idx = _find_row(table, _ENDING_LABELS)
    if beginning_idx is None or ending_idx is None:
        return []
    account_label = _account_label(section.title, table.heading)
    results: list[CheckResult] = []
    for col_idx in _rollforward_amount_columns(table, beginning_idx, ending_idx):
        beginning = _amount_at(table, beginning_idx, col_idx, blank_as_zero=True)
        ending = _amount_at(table, ending_idx, col_idx, blank_as_zero=True)
        if beginning is None or ending is None:
            continue
        expected = beginning
        for row_idx in range(min(beginning_idx, ending_idx) + 1, max(beginning_idx, ending_idx)):
            movement = _amount_at(table, row_idx, col_idx, blank_as_zero=True)
            if movement is None:
                continue
            expected += _movement_amount(table.rows[row_idx][0], movement)
        difference = ending - expected
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        column_label = _column_label(table, col_idx)
        results.append(
            CheckResult(
                check_id=f"note_assertion:{section.note_no}:table{table.index}:rollforward:col{col_idx}",
                check_type="note_rollforward_check",
                status=status,
                scope="note",
                note_no=section.note_no,
                title=f"{account_label} 증감표 검산 - {column_label}",
                expected=expected,
                actual=ending,
                difference=difference,
                tolerance=tolerance,
                reason="기초와 변동내역이 기말 장부금액과 일치"
                if status == MATCHED
                else "기초와 변동내역이 기말 장부금액과 불일치",
                evidence=[
                    CheckEvidence(
                        f"{table.rows[beginning_idx][0]} {column_label}",
                        beginning,
                        f"note:{section.note_no}/table:{table.index}/row:{beginning_idx}/col:{col_idx}",
                    ),
                    CheckEvidence(
                        f"{table.rows[ending_idx][0]} {column_label}",
                        ending,
                        f"note:{section.note_no}/table:{table.index}/row:{ending_idx}/col:{col_idx}",
                    ),
                ],
            )
        )
    return results


def _is_asset_rollforward(section_title: str, heading: str) -> bool:
    text = _compact(f"{section_title} {heading}")
    return any(token in text for token in _ASSET_NOTE_TOKENS) and any(
        token in text for token in ("변동내역", "증감", "장부금액")
    )


def _find_row(table: ReportTable, labels: tuple[str, ...]) -> int | None:
    for idx, row in enumerate(table.rows):
        if row and any(_compact(row[0]).startswith(_compact(label)) for label in labels):
            return idx
    return None


def _find_total_column(table: ReportTable) -> int | None:
    headers = table.rows[0]
    for idx in range(len(headers) - 1, 0, -1):
        if _compact(headers[idx]) in {"합계", "계", "총계", "장부금액"}:
            return idx
    return len(headers) - 1 if len(headers) > 1 else None


def _rollforward_amount_columns(table: ReportTable, beginning_idx: int, ending_idx: int) -> list[int]:
    max_cols = max(len(row) for row in table.rows)
    columns: list[int] = []
    for col_idx in range(1, max_cols):
        # 빈칸을 0으로 보지 않고 실제 금액 유무로 판단한다. 기초·기말이 모두
        # 빈칸인 열은 (값이 합계 열에 있는) 그룹 하위 열이므로, 0/0을 movement와
        # 비교해 거짓 차이를 내지 않도록 rollforward 열에서 제외한다.
        beginning = _amount_at(table, beginning_idx, col_idx, blank_as_zero=False)
        ending = _amount_at(table, ending_idx, col_idx, blank_as_zero=False)
        if beginning is None and ending is None:
            continue
        columns.append(col_idx)
    total_col = _find_total_column(table)
    if total_col is not None and total_col not in columns:
        b = _amount_at(table, beginning_idx, total_col, blank_as_zero=False)
        e = _amount_at(table, ending_idx, total_col, blank_as_zero=False)
        if b is not None or e is not None:
            columns.append(total_col)
    return columns


def _column_label(table: ReportTable, col_idx: int) -> str:
    if table.rows and col_idx < len(table.rows[0]) and table.rows[0][col_idx].strip():
        return table.rows[0][col_idx].strip()
    return f"열 {col_idx}"


def _amount_at(table: ReportTable, row_idx: int, col_idx: int, *, blank_as_zero: bool) -> int | None:
    if row_idx >= len(table.rows) or col_idx >= len(table.rows[row_idx]):
        return 0 if blank_as_zero else None
    cell = table.rows[row_idx][col_idx]
    if not cell.strip() and blank_as_zero:
        return 0
    amount = parse_amount(cell)
    return amount * table.unit_multiplier if amount is not None else None


def _movement_amount(label: str, amount: int) -> int:
    normalized = _compact(label)
    if amount > 0 and any(token in normalized for token in _DECREASE_LABELS):
        return -amount
    return amount


def _account_label(section_title: str, heading: str) -> str:
    text = f"{section_title} {heading}"
    for token in _ASSET_NOTE_TOKENS:
        if token in text:
            return token
    return "주석"


def _compact(value: str) -> str:
    return value.replace(" ", "").replace("\n", "")
