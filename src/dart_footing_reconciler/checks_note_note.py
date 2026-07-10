"""Note to note relationship checks."""

from __future__ import annotations

from dart_footing_reconciler._match_helpers import AmountHit
from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.label_resolver import AMBIGUOUS_MULTIPLE
from dart_footing_reconciler.note_relations import (
    NOTE_RELATION_RULES,
    NoteRelationCandidates,
    resolve_note_relation,
)
from dart_footing_reconciler.scope import primary_note_sections


def check_note_note_matches(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    scoped_report = FullReport(
        report.source,
        report.company,
        report.statements,
        primary_note_sections(report.notes),
    )
    for rule in NOTE_RELATION_RULES:
        candidates = resolve_note_relation(scoped_report, rule)
        if candidates is None:
            continue
        rule_id = rule.rule_id
        match = _candidate_match(rule_id, candidates, tolerance)
        if match is None:
            results.append(
                _uncertain(rule_id, list(candidates.evidence_hits), tolerance)
            )
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
    rule_id: str,
    candidates: NoteRelationCandidates,
    tolerance: int,
) -> tuple[AmountHit, AmountHit, list[AmountHit]] | None:
    left_hits = candidates.left_hits
    right_hits = candidates.right_hits
    if len(left_hits) == 1 and len(right_hits) == 1:
        left_hit, right_hit = candidates.pairs[0]
        return left_hit, right_hit, [left_hit, right_hit]
    all_hits = list(candidates.evidence_hits)
    if not _all_candidates_agree(rule_id, all_hits, tolerance):
        return None
    left_hit, right_hit = candidates.pairs[0]
    return left_hit, right_hit, all_hits


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
        parse_uncertain_reason=AMBIGUOUS_MULTIPLE,
    )
