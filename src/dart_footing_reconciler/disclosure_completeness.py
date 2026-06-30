"""Reviewer-lens disclosure completeness prompts.

This module is intentionally outside ``CheckResult``. It produces reviewer
follow-up memos and parser/layout backlog evidence, not numeric verdicts.
"""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import FullReport, ReportTable, SourceLocation
from dart_footing_reconciler.layout_variants import classify_layout
from dart_footing_reconciler.note_inventory import NoteTableInventoryItem, build_note_inventory
from dart_footing_reconciler.orientation import detect_orientation
from dart_footing_reconciler.table_semantics import compact
from dart_footing_reconciler.verification_candidates import extract_verification_candidates


@dataclass(frozen=True)
class ObservedAmountEvidence:
    label: str
    raw_value: str
    amount: int
    scaled_amount: int
    unit_multiplier: int
    location: SourceLocation


@dataclass(frozen=True)
class ReviewerMemo:
    finding_class: str
    status: str
    priority: str
    observed_item: str
    expected_disclosure: str
    message: str
    observed_evidence: tuple[ObservedAmountEvidence, ...]
    false_positive_risks: tuple[str, ...]


@dataclass(frozen=True)
class InterpretationBacklogItem:
    topic: str
    reason: str
    source: str


@dataclass(frozen=True)
class DisclosureCompletenessReview:
    reviewer_memos: tuple[ReviewerMemo, ...]
    interpretation_backlog: tuple[InterpretationBacklogItem, ...]


FALSE_POSITIVE_RISKS = (
    "다른 명칭의 표 가능",
    "서술형 공시 가능",
    "중요성 판단 가능",
    "기간·기준 표시 차이 가능",
)


def review_disclosure_completeness(report: FullReport) -> DisclosureCompletenessReview:
    lease_evidence = _lease_liability_amount_evidence(report)
    if not lease_evidence:
        return DisclosureCompletenessReview((), ())

    disclosure_state = _lease_maturity_disclosure_state(report)
    if disclosure_state.found:
        return DisclosureCompletenessReview((), ())
    if disclosure_state.backlog:
        return DisclosureCompletenessReview((), tuple(disclosure_state.backlog))

    memo = ReviewerMemo(
        finding_class="disclosure_omission_candidate",
        status="needs_review",
        priority="low",
        observed_item="리스부채 금액",
        expected_disclosure="리스부채 만기분석",
        message=(
            "리스부채 금액은 문서 내에서 확인되나, 리스부채 만기분석 공시는 "
            "확인되지 않았습니다. 후속 확인이 필요합니다."
        ),
        observed_evidence=tuple(lease_evidence),
        false_positive_risks=FALSE_POSITIVE_RISKS,
    )
    return DisclosureCompletenessReview((memo,), ())


@dataclass(frozen=True)
class _DisclosureSearchState:
    found: bool
    backlog: tuple[InterpretationBacklogItem, ...]


def _lease_liability_amount_evidence(report: FullReport) -> list[ObservedAmountEvidence]:
    evidence: list[ObservedAmountEvidence] = []
    for section in [*report.statements, *report.notes]:
        if section.kind == "statement" and compact(section.title) != "재무상태표":
            continue
        for block_idx, block in enumerate(section.blocks):
            table = block.table
            if table is None or not table.rows:
                continue
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row or not _is_explicit_lease_liability_amount_label(row[0]):
                    continue
                amount_cell = _first_amount_cell(row)
                if amount_cell is None:
                    continue
                amount_col, raw_value, amount = amount_cell
                evidence.append(
                    ObservedAmountEvidence(
                        label=row[0],
                        raw_value=raw_value,
                        amount=amount,
                        scaled_amount=amount * table.unit_multiplier,
                        unit_multiplier=table.unit_multiplier,
                        location=SourceLocation(
                            section.section_id,
                            block.location.block_index if block.location else block_idx,
                            table.index,
                            row_idx,
                            amount_col,
                        ),
                    )
                )
    return evidence


def _lease_maturity_disclosure_state(report: FullReport) -> _DisclosureSearchState:
    table_lookup = _table_lookup(report)
    backlog: list[InterpretationBacklogItem] = []

    for item in build_note_inventory(report).tables:
        table = table_lookup.get(item.source)
        if table is None:
            continue
        layout = classify_layout(item)
        orientation = detect_orientation(headers=item.headers, row_labels=item.row_labels)

        if layout.key == "lease_liability_maturity_summary":
            return _DisclosureSearchState(True, ())

        if layout.key == "liquidity_maturity_analysis":
            candidates = extract_verification_candidates(
                note_no=item.note_no,
                title=item.title,
                table=table,
                layout=layout,
                orientation=orientation,
            )
            if any(
                candidate.account_key == "lease_liabilities"
                and candidate.role.startswith("maturity_")
                for candidate in candidates
            ):
                return _DisclosureSearchState(True, ())

        if _is_lease_maturity_like_table(item, table):
            backlog.append(
                InterpretationBacklogItem(
                    topic="리스부채 만기분석",
                    reason="만기분석 유사 표가 있으나 현재 표 해석 로직이 확신 있게 읽지 못함",
                    source=item.source,
                )
            )

    if _has_lease_maturity_narrative(report):
        return _DisclosureSearchState(True, ())

    return _DisclosureSearchState(False, tuple(backlog))


def _table_lookup(report: FullReport):
    lookup = {}
    for section in report.notes:
        for block in section.blocks:
            table = block.table
            if table is None:
                continue
            lookup[f"note:{section.note_no}/table:{table.index}"] = table
    return lookup


def _is_explicit_lease_liability_amount_label(label: str) -> bool:
    normalized = compact(label).lower()
    if "리스부채" not in normalized:
        return False
    if any(
        token in normalized
        for token in (
            "감소",
            "증가",
            "증감",
            "상환",
            "지급",
            "현금흐름",
            "이자",
            "비용",
            "리스료",
            "변동리스",
            "사용권자산",
            "측정에포함되지",
        )
    ):
        return False
    if normalized in {"리스부채", "리스부채합계", "총리스부채", "leaseliabilities"}:
        return True
    return any(
        token in normalized
        for token in (
            "유동리스부채",
            "유동성리스부채",
            "비유동리스부채",
            "단기리스부채",
            "장기리스부채",
            "리스부채장부금액",
            "leaseliability",
        )
    )


def _first_amount_cell(row: list[str]) -> tuple[int, str, int] | None:
    for col_idx, cell in enumerate(row[1:], start=1):
        amount = parse_amount(cell)
        if amount is not None and amount != 0:
            return col_idx, cell, amount
    return None


def _is_lease_maturity_like_table(item: NoteTableInventoryItem, table: ReportTable) -> bool:
    values = (
        item.title,
        item.heading,
        *item.headers,
        *item.row_labels,
        *[cell for row in table.rows for cell in row],
    )
    joined = compact(" ".join(values))
    title_heading = compact(f"{item.title} {item.heading}")
    if "리스부채" not in joined:
        return False
    if any(token in title_heading for token in ("만기분석", "계약상만기", "잔존만기", "만기별")):
        return True
    if "유동성위험" in title_heading:
        return True
    if _count_maturity_bucket_labels(tuple(cell for row in table.rows for cell in row)) >= 2:
        return True
    return _count_annual_maturity_columns(table.rows) >= 3


def _count_maturity_bucket_labels(values: tuple[str, ...]) -> int:
    return sum(1 for value in values if _is_maturity_bucket_label(value))


def _is_maturity_bucket_label(value: str) -> bool:
    normalized = compact(value).lower()
    if any(token in normalized for token in ("withinoneyear", "lessthanoneyear", "overoneyear")):
        return True
    if "년" not in normalized and "개월" not in normalized:
        return False
    return any(token in normalized for token in ("이내", "초과", "미만", "이상", "~"))


def _count_annual_maturity_columns(rows: list[list[str]]) -> int:
    if not rows:
        return 0
    return max(
        (sum(1 for cell in row[1:] if _is_annual_maturity_column(cell)) for row in rows),
        default=0,
    )


def _is_annual_maturity_column(value: str) -> bool:
    normalized = compact(value)
    if "년" not in normalized:
        return False
    if any(token in normalized for token in ("이내", "초과", "미만", "이상")):
        return False
    return any(char.isdigit() for char in normalized)


def _has_lease_maturity_narrative(report: FullReport) -> bool:
    for section in report.notes:
        for block in section.blocks:
            if not block.text:
                continue
            text = compact(block.text).lower()
            if (
                "리스부채" in text
                and any(token in text for token in ("만기", "잔존만기", "계약상만기", "maturity"))
                and _has_period_language(text)
            ):
                return True
    return False


def _has_period_language(text: str) -> bool:
    return any(
        token in text
        for token in (
            "1년이내",
            "1년초과",
            "5년초과",
            "년이내",
            "년초과",
            "withinoneyear",
            "overoneyear",
            "fiveyears",
        )
    )
