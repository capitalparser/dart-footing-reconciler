"""High-level document scanning helpers."""

from __future__ import annotations

import re

from dart_footing_reconciler.footing import PARSE_UNCERTAIN, FootingResult, foot_table
from dart_footing_reconciler.html_tables import ParsedTable, extract_tables

_TARGET_KEYWORDS = (
    "유형자산",
    "무형자산",
    "투자부동산",
    "차입금",
    "사채",
    "리스",
)
_CAPITAL_TABLE_KEYWORDS = (
    "자본금",
    "자본잉여금",
    "주식발행초과금",
)


def scan_html(html: str, tolerance: int = 1, include_all: bool = False) -> list[FootingResult]:
    """Find and foot movement-like tables in a DART HTML document."""
    results: list[FootingResult] = []
    for table in extract_tables(html):
        if not include_all and not _is_target_table(table):
            continue
        result = foot_table(table, tolerance=tolerance)
        if result.status == PARSE_UNCERTAIN:
            continue
        results.append(result)
    return results


def _is_target_table(table: ParsedTable) -> bool:
    header_text = _normalize(_header_text(table))
    current_heading_text = _normalize(_current_heading(table.heading))
    candidate_text = _normalize(" ".join([current_heading_text, header_text]))
    full_text = _normalize(" ".join([table.heading, _table_text(table)]))
    if any(keyword in full_text for keyword in _CAPITAL_TABLE_KEYWORDS):
        return False
    if not any(keyword in candidate_text for keyword in _TARGET_KEYWORDS):
        return False
    return "변동" in full_text or _has_beginning_and_ending_rows(table)


def _table_text(table: ParsedTable) -> str:
    return " ".join(" ".join(row.cells) for row in table.rows)


def _header_text(table: ParsedTable) -> str:
    return " ".join(" ".join(row.cells) for row in table.rows[:2])


def _normalize(value: str) -> str:
    return "".join(value.replace("\xa0", " ").split())


def _current_heading(heading: str) -> str:
    matches = list(re.finditer(r"\d+\.\s*", heading))
    if not matches:
        return heading
    return heading[matches[-1].start() :]


def _has_beginning_and_ending_rows(table: ParsedTable) -> bool:
    labels = [_normalize(row.cells[0]) for row in table.rows if row.cells]
    has_beginning = any("기초" in label for label in labels)
    has_ending = any("기말" in label for label in labels)
    return has_beginning and has_ending
