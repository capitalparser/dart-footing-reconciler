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
from dart_footing_reconciler.scope import primary_note_sections

NOTE_NOTE_RULES = [
    ("depreciation_expense", ("유형자산", "감가상각비"), ("비용", "감가상각비")),
    ("depreciation_expense_nature", ("유형자산", "감가상각비"), ("비용의성격별분류", "감가상각")),
    ("amortization_expense", ("무형자산", "상각비"), ("비용", "상각비")),
    ("lease_liability_current_noncurrent", ("리스부채", "유동"), ("리스부채", "비유동")),
    ("tax_temporary_difference", ("이연법인세", "일시적차이"), ("법인세", "일시적차이")),
]


def check_note_note_matches(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    scoped_report = FullReport(
        report.source,
        report.company,
        report.statements,
        primary_note_sections(report.notes),
    )
    for rule_id, left_rule, right_rule in NOTE_NOTE_RULES:
        left_hits = find_note_amounts(scoped_report, left_rule[0], left_rule[1])
        right_hits = find_note_amounts(scoped_report, right_rule[0], right_rule[1])
        if not left_hits or not right_hits:
            continue
        match = _candidate_match(rule_id, left_hits, right_hits, tolerance)
        if match is None:
            results.append(_uncertain(rule_id, left_hits + right_hits, tolerance))
            continue
        left_hit, right_hit, evidence_hits = match
        expected = _comparable_amount(rule_id, left_hit.amount)
        actual = _comparable_amount(rule_id, right_hit.amount)
        difference = actual - expected
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        results.append(
            CheckResult(
                check_id=f"note_note:{rule_id}:{left_hit.note_no}:{right_hit.note_no}",
                check_type="note_note_match",
                status=status,
                scope="report",
                note_no=left_hit.note_no,
                title=f"{rule_id} note to note match",
                expected=expected,
                actual=actual,
                difference=difference,
                tolerance=tolerance,
                reason="related note amounts agree"
                if status == MATCHED
                else "related note amounts do not agree",
                evidence=[CheckEvidence(hit.label, hit.amount, hit.source) for hit in evidence_hits],
            )
        )
    return results


def _candidate_match(
    rule_id: str, left_hits: list[AmountHit], right_hits: list[AmountHit], tolerance: int
) -> tuple[AmountHit, AmountHit, list[AmountHit]] | None:
    if len(left_hits) == 1 and len(right_hits) == 1:
        return left_hits[0], right_hits[0], [left_hits[0], right_hits[0]]
    all_hits = [*left_hits, *right_hits]
    if not _all_candidates_agree(rule_id, all_hits, tolerance):
        return None
    return left_hits[0], right_hits[0], all_hits


def _all_candidates_agree(rule_id: str, hits: list[AmountHit], tolerance: int) -> bool:
    if not hits:
        return False
    baseline = _comparable_amount(rule_id, hits[0].amount)
    return all(abs(_comparable_amount(rule_id, hit.amount) - baseline) <= tolerance for hit in hits)


def _comparable_amount(rule_id: str, amount: int) -> int:
    if rule_id in {"depreciation_expense", "amortization_expense"}:
        return abs(amount)
    return amount


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
