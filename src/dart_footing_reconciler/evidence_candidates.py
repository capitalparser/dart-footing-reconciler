"""Candidate evidence selection helpers for reconciliation formulas."""

from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations


@dataclass(frozen=True)
class CandidateEvidence:
    account_key: str
    role: str
    label: str
    amount: int
    source: str
    note_no: str
    table_class: str
    period_role: str = "current"
    unit_multiplier: int = 1
    score: int = 0
    included: bool = False
    exclusion_reason: str = ""


def select_best_subset(
    candidates: list[CandidateEvidence],
    *,
    target_amount: int,
    tolerance: int,
    max_terms: int,
) -> tuple[list[CandidateEvidence], list[CandidateEvidence]]:
    compatible = [candidate for candidate in candidates if candidate.period_role == "current"]
    best_subset: tuple[CandidateEvidence, ...] | None = None
    best_key: tuple[int, int, int] | None = None
    for size in range(1, min(max_terms, len(compatible)) + 1):
        for subset in combinations(compatible, size):
            total = sum(candidate.amount for candidate in subset)
            difference = abs(total - target_amount)
            key = (difference, size, -sum(candidate.score for candidate in subset))
            if best_key is None or key < best_key:
                best_key = key
                best_subset = subset
    if best_subset is None or best_key is None or best_key[0] > tolerance:
        return [], [
            replace(candidate, included=False, exclusion_reason=candidate.exclusion_reason or "no_formula_match")
            for candidate in candidates
        ]
    selected_ids = {candidate.source for candidate in best_subset}
    selected = [replace(candidate, included=True, exclusion_reason="") for candidate in best_subset]
    rejected = [
        replace(candidate, included=False, exclusion_reason=candidate.exclusion_reason or "not_needed_for_best_formula")
        for candidate in candidates
        if candidate.source not in selected_ids
    ]
    return selected, rejected
