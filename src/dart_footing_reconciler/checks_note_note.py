"""Note to note relationship checks."""

from __future__ import annotations

from dart_footing_reconciler._match_helpers import AmountHit, find_note_amounts
from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport

NOTE_NOTE_RULES = [
    ("depreciation_expense", ("유형자산", "감가상각비"), ("비용", "감가상각비")),
    ("amortization_expense", ("무형자산", "상각비"), ("비용", "상각비")),
    ("lease_liability_current_noncurrent", ("리스부채", "유동"), ("리스부채", "비유동")),
    ("tax_temporary_difference", ("이연법인세", "일시적차이"), ("법인세", "일시적차이")),
]


def check_note_note_matches(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    for rule_id, left_rule, right_rule in NOTE_NOTE_RULES:
        left_hits = find_note_amounts(report, left_rule[0], left_rule[1])
        right_hits = find_note_amounts(report, right_rule[0], right_rule[1])
        if not left_hits or not right_hits:
            continue
        if len(left_hits) != 1 or len(right_hits) != 1:
            results.append(_uncertain(rule_id, left_hits + right_hits, tolerance))
            continue
        left_hit, right_hit = left_hits[0], right_hits[0]
        difference = right_hit.amount - left_hit.amount
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        results.append(
            CheckResult(
                check_id=f"note_note:{rule_id}:{left_hit.note_no}:{right_hit.note_no}",
                check_type="note_note_match",
                status=status,
                scope="report",
                note_no=left_hit.note_no,
                title=f"{rule_id} note to note match",
                expected=left_hit.amount,
                actual=right_hit.amount,
                difference=difference,
                tolerance=tolerance,
                reason="related note amounts agree"
                if status == MATCHED
                else "related note amounts do not agree",
                evidence=[
                    CheckEvidence(left_hit.label, left_hit.amount, left_hit.source),
                    CheckEvidence(right_hit.label, right_hit.amount, right_hit.source),
                ],
            )
        )
    return results


def _uncertain(rule_id: str, hits: list[AmountHit], tolerance: int) -> CheckResult:
    return CheckResult(
        check_id=f"note_note:{rule_id}:parse_uncertain",
        check_type="note_note_match",
        status=PARSE_UNCERTAIN,
        scope="report",
        note_no=hits[0].note_no if hits else "",
        title=f"{rule_id} note to note match",
        expected=None,
        actual=None,
        difference=None,
        tolerance=tolerance,
        reason="multiple candidate note amounts found",
        evidence=[CheckEvidence(hit.label, hit.amount, hit.source) for hit in hits],
    )
