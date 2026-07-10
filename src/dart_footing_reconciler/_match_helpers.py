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


#: Row-label keywords that signal a disclosed non-cash / bridge adjustment.
#: Used only for *residual explanation* lookups: the amount must ALSO match the
#: residual exactly and the hit must come from a related note (same note or a
#: cash-flow disclosure note), so a keyword alone never explains a gap.
NON_CASH_EXPLANATION_KEYWORDS = (
    "비현금",
    "미지급",
    "미수금",
    "리스",
    "대체",
    "환율",
    "외화",
    "사업결합",
    "정부보조금",
)


def find_residual_non_cash_explanation(
    report: FullReport,
    residual: int,
    *,
    note_no: str,
    exclude_sources: frozenset[str] = frozenset(),
) -> AmountHit | None:
    """Return evidence for a residual gap, or ``None`` when it stays unexplained.

    An ``explainable_gap`` classification must be backed by a disclosed line
    item, not by keyword coincidence anywhere in the filing. A hit qualifies
    only when all of the following hold:

    - its amount equals ``abs(residual)`` exactly (display precision is the
      caller's job, this helper never loosens the match), and
    - its row label carries a non-cash adjustment keyword, and
    - it is disclosed in the *same note* as the reconciled movement, or in a
      cash-flow / non-cash-transaction disclosure note (Korean filings disclose
      비현금거래 in a separate 현금흐름표 관련 주석).
    """
    if residual == 0:
        return None
    target = abs(residual)
    best: AmountHit | None = None
    for keyword in NON_CASH_EXPLANATION_KEYWORDS:
        for hit in find_note_amounts(report, "", keyword):
            if abs(hit.amount) != target:
                continue
            if hit.source in exclude_sources:
                continue
            if not _is_related_explanation_section(hit, note_no):
                continue
            # Prefer a same-note hit over a cash-flow-note hit.
            if best is None or (hit.note_no == note_no and best.note_no != note_no):
                best = hit
    return best


def _is_related_explanation_section(hit: AmountHit, note_no: str) -> bool:
    if note_no and hit.note_no == note_no:
        return True
    normalized_title = normalize_label(hit.section_title)
    return "현금흐름" in normalized_title or "비현금" in normalized_title


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
    if any(alias in normalized for alias in ("당기및전기", "당기와전기", "당분기및전분기", "당분기와전분기")):
        return False
    prior_tail = (
        "전기",
        "전기말",
        "전년도",
        "전분기",
        "전분기말",
        "전반기",
        "전반기말",
    )
    if re.search(rf"({'|'.join(prior_tail)})(?:\(단위[:：]?.*\))?$", normalized):
        return True
    if any(alias in normalized for alias in prior_tail):
        return not any(alias in normalized for alias in ("당기", "당기말", "당년도", "당분기", "당분기말", "당반기", "당반기말"))
    return False
