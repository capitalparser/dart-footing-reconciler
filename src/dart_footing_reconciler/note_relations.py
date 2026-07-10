"""Structural candidate resolution for note-to-note relations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dart_footing_reconciler._match_helpers import (
    AmountHit,
    find_note_amounts,
    normalize_label,
)
from dart_footing_reconciler.document import FullReport

BalanceLevel = Literal["current", "noncurrent"]
_BALANCE_MOVEMENT_KEYWORDS = ("대체", "재분류")


@dataclass(frozen=True)
class NoteRelationTerm:
    section_keyword: str
    row_keyword: str
    balance_level: BalanceLevel | None = None
    excluded_section_keywords: tuple[str, ...] = ()


@dataclass(frozen=True)
class NoteRelationRule:
    rule_id: str
    left: NoteRelationTerm
    right: NoteRelationTerm


@dataclass(frozen=True)
class NoteRelationCandidates:
    left_hits: tuple[AmountHit, ...]
    right_hits: tuple[AmountHit, ...]
    pairs: tuple[tuple[AmountHit, AmountHit], ...]

    @property
    def evidence_hits(self) -> tuple[AmountHit, ...]:
        return _unique_sources((*self.left_hits, *self.right_hits))


NOTE_RELATION_RULES = (
    NoteRelationRule(
        "depreciation_expense",
        NoteRelationTerm("유형자산", "감가상각비"),
        NoteRelationTerm("비용", "감가상각비"),
    ),
    NoteRelationRule(
        "depreciation_expense_nature",
        NoteRelationTerm("유형자산", "감가상각비"),
        NoteRelationTerm("비용의성격별분류", "감가상각"),
    ),
    NoteRelationRule(
        "amortization_expense",
        NoteRelationTerm("무형자산", "상각비"),
        NoteRelationTerm("비용", "상각비"),
    ),
    NoteRelationRule(
        "lease_liability_current_noncurrent",
        NoteRelationTerm("리스부채", "유동", balance_level="current"),
        NoteRelationTerm("리스부채", "비유동", balance_level="noncurrent"),
    ),
    NoteRelationRule(
        "tax_temporary_difference",
        NoteRelationTerm("이연법인세", "일시적차이"),
        NoteRelationTerm(
            "법인세",
            "일시적차이",
            excluded_section_keywords=("이연법인세",),
        ),
    ),
)


def resolve_note_relation(
    report: FullReport,
    rule: NoteRelationRule,
) -> NoteRelationCandidates | None:
    """Return only candidates that can form a distinct-source relation."""
    left_hits = _eligible_hits(report, rule.left)
    right_hits = _eligible_hits(report, rule.right)
    pairs = tuple(
        (left, right)
        for left in left_hits
        for right in right_hits
        if left.source != right.source
    )
    if not pairs:
        return None

    paired_left_sources = {left.source for left, _right in pairs}
    paired_right_sources = {right.source for _left, right in pairs}
    return NoteRelationCandidates(
        left_hits=tuple(hit for hit in left_hits if hit.source in paired_left_sources),
        right_hits=tuple(hit for hit in right_hits if hit.source in paired_right_sources),
        pairs=pairs,
    )


def _eligible_hits(report: FullReport, term: NoteRelationTerm) -> tuple[AmountHit, ...]:
    hits = find_note_amounts(report, term.section_keyword, term.row_keyword)
    return tuple(hit for hit in hits if _term_accepts_hit(term, hit))


def _term_accepts_hit(term: NoteRelationTerm, hit: AmountHit) -> bool:
    section_title = normalize_label(hit.section_title)
    if any(
        normalize_label(keyword) in section_title
        for keyword in term.excluded_section_keywords
    ):
        return False
    if term.balance_level is None:
        return True
    return _balance_level(hit.label) == term.balance_level


def _balance_level(label: str) -> BalanceLevel | None:
    compact = normalize_label(label)
    if any(keyword in compact for keyword in _BALANCE_MOVEMENT_KEYWORDS):
        return None
    has_noncurrent = "비유동" in compact
    has_current = "유동" in compact.replace("비유동", "")
    if has_current == has_noncurrent:
        return None
    return "current" if has_current else "noncurrent"


def _unique_sources(hits: tuple[AmountHit, ...]) -> tuple[AmountHit, ...]:
    seen: set[str] = set()
    unique: list[AmountHit] = []
    for hit in hits:
        if hit.source in seen:
            continue
        seen.add(hit.source)
        unique.append(hit)
    return tuple(unique)
