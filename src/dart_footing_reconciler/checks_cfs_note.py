"""Cash flow statement to note movement checks."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler._match_helpers import (
    AmountHit,
    find_note_amounts,
    find_statement_amounts,
    normalize_label,
)
from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    EXPLAINABLE_GAP,
    MATCHED,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.checks_fs_note import _is_non_amount_field_label, _plausible_amount
from dart_footing_reconciler.document import FullReport

@dataclass(frozen=True)
class CashFlowNoteRule:
    activity: str
    statement_label: str
    note_section: str
    note_movement: str
    account_key: str


CFS_NOTE_RULES = (
    CashFlowNoteRule("operating", "감가상각비", "유형자산", "감가상각비", "depreciation_expense"),
    CashFlowNoteRule("investing", "유형자산의취득", "유형자산", "취득", "property_plant_equipment"),
    CashFlowNoteRule("investing", "유형자산의처분", "유형자산", "처분", "property_plant_equipment"),
    CashFlowNoteRule("investing", "무형자산의취득", "무형자산", "취득", "intangible_assets"),
    CashFlowNoteRule("investing", "무형자산의처분", "무형자산", "처분", "intangible_assets"),
    CashFlowNoteRule("investing", "투자부동산의취득", "투자부동산", "취득", "investment_property"),
    CashFlowNoteRule("investing", "투자부동산의처분", "투자부동산", "처분", "investment_property"),
    CashFlowNoteRule("financing", "차입금의차입", "차입금", "차입", "borrowings"),
    CashFlowNoteRule("financing", "차입금의상환", "차입금", "상환", "borrowings"),
    CashFlowNoteRule("financing", "사채의발행", "사채", "발행", "bonds"),
    CashFlowNoteRule("financing", "사채의상환", "사채", "상환", "bonds"),
    CashFlowNoteRule("financing", "리스부채의상환", "리스부채", "상환", "lease_liabilities"),
)


def check_cfs_note_matches(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    for rule in CFS_NOTE_RULES:
        cfs_hits = find_statement_amounts(report, rule.statement_label)
        note_hits = find_note_amounts(report, rule.note_section, rule.note_movement)
        note_hits = [
            hit
            for hit in note_hits
            if _plausible_amount(hit.amount) and not _is_non_amount_field_label(hit.label)
        ]
        if not cfs_hits or not note_hits:
            continue
        cfs_hit = cfs_hits[0]
        note_hit = _select_note_hit_by_keyword(
            note_hits,
            rule.statement_label,
            rule.note_movement,
        )
        if note_hit is None:
            # 라벨 순위 없이 첫 행으로 페어링하면 텍스트/조건표 파싱 잔재가 gap을 만든다.
            continue
        expected = abs(cfs_hit.amount)
        actual = abs(note_hit.amount)
        difference = actual - expected
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        reason = (
            "cash flow statement amount agrees to note movement"
            if status == MATCHED
            else "cash flow statement amount does not agree to note movement"
        )
        if status != MATCHED and _has_exact_non_cash_adjustment(report, abs(difference)):
            status = EXPLAINABLE_GAP
            reason = "separately disclosed non-cash adjustment explains the gap"
        results.append(
            CheckResult(
                check_id=f"cfs_note:{rule.activity}:{rule.statement_label}:{note_hit.note_no}",
                check_type="cfs_note_match",
                status=status,
                scope=rule.activity,
                note_no=note_hit.note_no,
                title=f"{rule.statement_label} CFS to note match",
                expected=expected,
                actual=actual,
                difference=difference,
                tolerance=tolerance,
                reason=reason,
                evidence=[
                    CheckEvidence(cfs_hit.label, cfs_hit.amount, cfs_hit.source),
                    CheckEvidence(note_hit.label, note_hit.amount, note_hit.source),
                ],
                account_key=rule.account_key,
            )
        )
    return results


def _has_exact_non_cash_adjustment(report: FullReport, amount: int) -> bool:
    keywords = ("비현금", "미지급", "리스", "대체", "환율", "외화")
    for keyword in keywords:
        for hit in find_note_amounts(report, "", keyword):
            if abs(hit.amount) == amount:
                return True
    return False


def _select_note_hit_by_keyword(
    note_hits: list[AmountHit], cfs_label: str, row_keyword: str
) -> AmountHit | None:
    targets = tuple(
        dict.fromkeys(
            target
            for target in (normalize_label(cfs_label), normalize_label(row_keyword))
            if target
        )
    )
    ranked = [
        (rank, index, hit)
        for index, hit in enumerate(note_hits)
        if not _is_non_amount_field_label(hit.label)
        and (rank := _keyword_rank(hit.label, targets)) is not None
    ]
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1]))
    best_rank = ranked[0][0]
    if sum(rank == best_rank for rank, _index, _hit in ranked) != 1:
        return None
    return ranked[0][2]


def _keyword_rank(label: str, targets: tuple[str, ...]) -> int | None:
    normalized = normalize_label(label)
    for target_index, target in enumerate(targets):
        base = target_index * 3
        if normalized == target:
            return base
        if normalized.startswith(target):
            return base + 1
        if target in normalized:
            return base + 2
    return None
