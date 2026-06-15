"""Small helpers shared by first-pass validation rules."""

from __future__ import annotations

import re
from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import FullReport, ReportSection
from dart_footing_reconciler.table_semantics import row_amount_prefer_current


@dataclass(frozen=True)
class AmountHit:
    amount: int
    note_no: str
    section_title: str
    label: str
    source: str


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", "", value)


def find_amounts(
    sections: list[ReportSection],
    *,
    section_keyword: str | None = None,
    row_keyword: str,
    prefer_column: str | None = None,
) -> list[AmountHit]:
    section_key = normalize_label(section_keyword or "")
    row_key = normalize_label(row_keyword)
    prefer_key = normalize_label(prefer_column or "")
    hits: list[AmountHit] = []
    for section in sections:
        if section_key and section_key not in normalize_label(section.title):
            continue
        for block in section.blocks:
            table = block.table
            if table is None:
                continue
            if _is_prior_period_table(table.heading):
                continue
            rows = table.rows
            if not rows:
                continue
            headers = rows[0]
            for row_idx, row in enumerate(rows[1:], start=1):
                if not row or row_key not in normalize_label(row[0]):
                    continue
                amount, col_idx = _row_amount(row, headers, prefer_key)
                if amount is None or col_idx is None:
                    continue
                amount *= table.unit_multiplier
                hits.append(
                    AmountHit(
                        amount=amount,
                        note_no=section.note_no,
                        section_title=section.title,
                        label=row[0],
                        source=f"{section.section_id}/table:{table.index}/row:{row_idx}/col:{col_idx}",
                    )
                )
    return hits


def find_statement_amounts(report: FullReport, row_keyword: str) -> list[AmountHit]:
    return find_amounts(report.statements, row_keyword=row_keyword)


def find_note_amounts(report: FullReport, section_keyword: str, row_keyword: str) -> list[AmountHit]:
    return find_amounts(report.notes, section_keyword=section_keyword, row_keyword=row_keyword)


def unique_or_none(hits: list[AmountHit]) -> AmountHit | None:
    return hits[0] if len(hits) == 1 else None


def _row_amount(row: list[str], headers: list[str], prefer_key: str) -> tuple[int | None, int | None]:
    if prefer_key:
        for col_idx, header in enumerate(headers):
            if col_idx < len(row) and prefer_key in normalize_label(header):
                amount = parse_amount(row[col_idx])
                if amount is not None:
                    return amount, col_idx
    return row_amount_prefer_current(row, headers)


def _is_prior_period_table(heading: str) -> bool:
    normalized = normalize_label(heading)
    if any(alias in normalized for alias in ("전기", "전기말", "전년도")):
        return not any(alias in normalized for alias in ("당기", "당기말", "당년도"))
    return False
