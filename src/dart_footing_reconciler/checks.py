"""Shared validation result model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Output schema version for machine-consumable JSON payloads. Bump on any
#: breaking change to serialized field names/shapes so archived workpaper
#: evidence can be read back against the contract that produced it.
SCHEMA_VERSION = "1.0"

MATCHED = "matched"
EXPLAINABLE_GAP = "explainable_gap"
UNEXPLAINED_GAP = "unexplained_gap"
PARSE_UNCERTAIN = "parse_uncertain"
NOT_TESTED = "not_tested"

#: Canonical status set, ordered for display. Single source of truth so every
#: summary/aggregation surfaces all five statuses (no hidden explainable_gap /
#: not_tested coverage).
ALL_STATUSES = (
    MATCHED,
    EXPLAINABLE_GAP,
    UNEXPLAINED_GAP,
    PARSE_UNCERTAIN,
    NOT_TESTED,
)


def status_summary(results: list[Any]) -> dict[str, int]:
    """Count every canonical status (plus total) for a result list.

    Results may be CheckResult or FootingResult — anything with a ``.status``
    string. Statuses outside :data:`ALL_STATUSES` are ignored.
    """
    counts = {status: 0 for status in ALL_STATUSES}
    for result in results:
        if result.status in counts:
            counts[result.status] += 1
    return {"total": len(results), **counts}


@dataclass(frozen=True)
class CheckEvidence:
    label: str
    amount: int | None
    source: str
    role: str = ""


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
    parse_uncertain_reason: str | None = None
    account_key: str = "unknown"
    consolidation_basis: str = "unknown"
    report_period: str = "unknown"
    balance_level: str = "unknown"
