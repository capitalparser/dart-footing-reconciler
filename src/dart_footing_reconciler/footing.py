"""Footing checks for movement tables."""

from __future__ import annotations

import re
from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.html_tables import ParsedTable

MATCHED = "matched"
UNEXPLAINED_GAP = "unexplained_gap"
PARSE_UNCERTAIN = "parse_uncertain"

_BEGINNING_LABELS = (
    "기초장부금액",
    "기초금액",
    "기초잔액",
    "기초",
    "전기초",
    "당기초",
)
_ENDING_LABELS = (
    "기말장부금액",
    "기말금액",
    "기말잔액",
    "기말",
    "전기말",
    "당기말",
)
_CONTRA_KEYWORDS = (
    "감가상각",
    "상각",
    "처분",
    "폐기",
    "손상",
    "감소",
    "제거",
)
_INCREASE_KEYWORDS = (
    "취득",
    "증가",
    "대체",
    "연결범위",
    "사업결합",
)
_DISPLAY_SIGN_KEYWORDS = (
    "증가(감소)",
    "증가/감소",
    "증감",
    "대체",
    "재평가",
    "외환",
    "환율",
    "환산",
)
_NON_CARRYING_COLUMN_KEYWORDS = (
    "총장부금액",
    "취득원가",
    "상각누계",
    "감가상각누계",
    "손상누계",
    "손상차손누계",
)
_LIABILITY_CONTEXT_KEYWORDS = (
    "사채",
    "차입금",
    "리스부채",
    "부채",
)

# Row labels that represent intermediate subtotals or grand totals.
# Rows matching these (exact, after whitespace normalisation) are EXCLUDED
# from rollforward movement sums to prevent double-counting.
# The ending row is identified separately by _find_row() and is NOT affected.
_SUBTOTAL_LABELS: frozenset[str] = frozenset({
    "소계",
    "합계",
    "소합계",
    "자산총계",
    "부채총계",
    "자본총계",
    "부채및자본총계",
})


@dataclass(frozen=True)
class FootingEvidence:
    role: str
    label: str
    amount: int
    source: str


@dataclass(frozen=True)
class FootingColumnResult:
    label: str
    expected: int
    actual: int
    difference: int
    status: str
    evidence: list[FootingEvidence]


@dataclass(frozen=True)
class FootingResult:
    table_index: int
    heading: str
    status: str
    columns: list[FootingColumnResult]
    reason: str


def foot_table(table: ParsedTable, tolerance: int = 0) -> FootingResult:
    """Foot a single movement table.

    The first non-empty column is treated as the row label column. Numeric
    columns after that are checked independently.
    """
    label_col = _find_label_column(table)
    if label_col is None:
        return _uncertain(table, "could not find label column")

    beginning_idx = _find_row(table, label_col, _BEGINNING_LABELS)
    ending_idx = _find_row(table, label_col, _ENDING_LABELS)
    if beginning_idx is None or ending_idx is None:
        return _uncertain(table, "could not find beginning or ending row")

    data_columns = _numeric_columns(table, label_col, beginning_idx, ending_idx)
    if not data_columns:
        return _uncertain(table, "could not find numeric columns")

    header = _header_labels(table, label_col)
    table_context = _table_context(table)
    data_columns = [
        col for col in data_columns if not _is_non_carrying_column(header.get(col, ""))
    ]
    if not data_columns:
        return _uncertain(table, "could not find carrying amount columns")

    results: list[FootingColumnResult] = []

    for col in data_columns:
        beginning = parse_amount(_cell(table, beginning_idx, col))
        actual = parse_amount(_cell(table, ending_idx, col))
        if beginning is None or actual is None:
            continue

        expected = beginning
        evidence: list[FootingEvidence] = [
            FootingEvidence(
                role="beginning",
                label=_cell(table, beginning_idx, label_col),
                amount=beginning,
                source=_cell_source(table, beginning_idx, col),
            )
        ]
        movement_start = min(beginning_idx, ending_idx) + 1
        movement_end = max(beginning_idx, ending_idx)
        for row_idx in range(movement_start, movement_end):
            label = _cell(table, row_idx, label_col)
            if _is_beginning_or_ending_detail(label):
                continue
            if _is_subtotal_row(label):
                continue
            amount = parse_amount(_cell(table, row_idx, col))
            if amount is None:
                continue
            column_context = " ".join([table_context, header.get(col, "")])
            movement_amount = _movement_amount(label, amount, column_context)
            expected += movement_amount
            evidence.append(
                FootingEvidence(
                    role="movement",
                    label=label,
                    amount=movement_amount,
                    source=_cell_source(table, row_idx, col),
                )
            )

        difference = actual - expected
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        evidence.append(
            FootingEvidence(
                role="ending",
                label=_cell(table, ending_idx, label_col),
                amount=actual,
                source=_cell_source(table, ending_idx, col),
            )
        )
        results.append(
            FootingColumnResult(
                label=header.get(col, f"column_{col}"),
                expected=expected,
                actual=actual,
                difference=difference,
                status=status,
                evidence=evidence,
            )
        )

    if not results:
        return _uncertain(table, "numeric columns had no comparable amounts")

    status = MATCHED if all(col.status == MATCHED for col in results) else UNEXPLAINED_GAP
    reason = "all columns foot within tolerance" if status == MATCHED else "one or more columns do not foot"
    return FootingResult(
        table_index=table.index,
        heading=table.heading,
        status=status,
        columns=results,
        reason=reason,
    )


def _find_label_column(table: ParsedTable) -> int | None:
    max_cols = max((len(row.cells) for row in table.rows), default=0)
    for col in range(max_cols):
        labels = [_cell(table, idx, col) for idx in range(len(table.rows))]
        if any(_matches(label, _BEGINNING_LABELS) for label in labels) and any(
            _matches(label, _ENDING_LABELS) for label in labels
        ):
            return col
    return None


def _find_row(table: ParsedTable, label_col: int, aliases: tuple[str, ...]) -> int | None:
    fallback: int | None = None
    for index, row in enumerate(table.rows):
        label = _safe_cell(row.cells, label_col)
        if _matches(label, aliases):
            if not _is_beginning_or_ending_detail(label):
                return index
            if fallback is None:
                fallback = index
    return fallback


def _numeric_columns(
    table: ParsedTable,
    label_col: int,
    beginning_idx: int,
    ending_idx: int,
) -> list[int]:
    max_cols = max((len(row.cells) for row in table.rows), default=0)
    columns: list[int] = []
    for col in range(max_cols):
        if col == label_col:
            continue
        if parse_amount(_cell(table, beginning_idx, col)) is not None and parse_amount(
            _cell(table, ending_idx, col)
        ) is not None:
            columns.append(col)
    return columns


def _header_labels(table: ParsedTable, label_col: int) -> dict[int, str]:
    first_data_idx = _first_data_row_index(table, label_col)
    header_rows = table.rows[:first_data_idx]
    labels: dict[int, str] = {}
    for row in header_rows:
        for col, value in enumerate(row.cells):
            if col == label_col or not value:
                continue
            labels[col] = value
    return labels


def _first_data_row_index(table: ParsedTable, label_col: int) -> int:
    for index, row in enumerate(table.rows):
        label = _safe_cell(row.cells, label_col)
        if _matches(label, _BEGINNING_LABELS):
            return index
    return 0


def _movement_amount(label: str, amount: int, context: str = "") -> int:
    normalized = _normalize_label(label)
    normalized_context = _normalize_label(context)
    if amount < 0:
        return amount
    if any(keyword in normalized for keyword in _DISPLAY_SIGN_KEYWORDS):
        return amount
    if "상각" in normalized and any(
        keyword in normalized_context for keyword in _LIABILITY_CONTEXT_KEYWORDS
    ):
        return amount
    if any(keyword in normalized for keyword in _CONTRA_KEYWORDS):
        return -amount
    if any(keyword in normalized for keyword in _INCREASE_KEYWORDS):
        return amount
    return amount


def _is_non_carrying_column(label: str) -> bool:
    normalized = _normalize_label(label)
    if "장부금액합계" in normalized:
        return False
    return any(keyword in normalized for keyword in _NON_CARRYING_COLUMN_KEYWORDS)


def _table_context(table: ParsedTable) -> str:
    return " ".join([table.heading, _table_text(table)])


def _table_text(table: ParsedTable) -> str:
    return " ".join(" ".join(row.cells) for row in table.rows)


def _is_subtotal_row(label: str) -> bool:
    """Return True if *label* is a subtotal/total row that must be excluded
    from the rollforward movement sum to prevent double-counting.

    Uses exact match (after whitespace collapse) so that valid movement
    labels like '취득합계' or '장부금액합계' are NOT excluded.
    """
    normalized = re.sub(r"\s+", "", label.replace("\xa0", " ").strip())
    return normalized in _SUBTOTAL_LABELS


def _is_beginning_or_ending_detail(label: str) -> bool:
    normalized = _normalize_label(label)
    if not ("기초" in normalized or "기말" in normalized):
        return False
    return any(keyword in normalized for keyword in ("취득원가", "상각누계", "손상누계", "손상차손누계"))


def _matches(label: str, aliases: tuple[str, ...]) -> bool:
    normalized = _normalize_label(label)
    return any(alias in normalized for alias in aliases)


def _normalize_label(label: str) -> str:
    return "".join(label.replace("\xa0", " ").split())


def _cell(table: ParsedTable, row_idx: int, col_idx: int) -> str:
    if row_idx >= len(table.rows):
        return ""
    return _safe_cell(table.rows[row_idx].cells, col_idx)


def _cell_source(table: ParsedTable, row_idx: int, col_idx: int) -> str:
    return f"table:{table.index} row:{row_idx} col:{col_idx}"


def _safe_cell(cells: list[str], col_idx: int) -> str:
    if col_idx >= len(cells):
        return ""
    return cells[col_idx]


def _uncertain(table: ParsedTable, reason: str) -> FootingResult:
    return FootingResult(
        table_index=table.index,
        heading=table.heading,
        status=PARSE_UNCERTAIN,
        columns=[],
        reason=reason,
    )
