"""Shared validation result model."""

from __future__ import annotations

from dataclasses import dataclass

MATCHED = "matched"
EXPLAINABLE_GAP = "explainable_gap"
UNEXPLAINED_GAP = "unexplained_gap"
PARSE_UNCERTAIN = "parse_uncertain"
NOT_TESTED = "not_tested"


@dataclass(frozen=True)
class CheckEvidence:
    label: str
    amount: int | None
    source: str


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    check_type: str
    status: str
    scope: str
    note_no: str
    title: str
    expected: int | None
    actual: int | None
    difference: int | None
    tolerance: int
    reason: str
    evidence: list[CheckEvidence]
