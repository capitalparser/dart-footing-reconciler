"""Semantic validation report placement over existing CheckResult rows."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.semantic_attempts import SemanticAttemptSpec, attempts_for_signatures
from dart_footing_reconciler.semantic_layer import SemanticDataset, SemanticTable, build_semantic_dataset


@dataclass(frozen=True)
class SemanticCheckPlacement:
    check: CheckResult
    table: SemanticTable | None
    order: int | None


@dataclass(frozen=True)
class SemanticValidationCandidate:
    candidate_id: str
    layer: str
    attempt_id: str
    check_type: str
    table_source: str
    evidence_sources: tuple[str, ...]
    confidence: float
    block_reason: str | None = None


@dataclass(frozen=True)
class SemanticValidationReport:
    dataset: SemanticDataset
    candidates: tuple[SemanticValidationCandidate, ...]
    placements: tuple[SemanticCheckPlacement, ...]
    attempts_by_source: dict[str, tuple[SemanticAttemptSpec, ...]]


def run_semantic_validation(
    report: FullReport,
    prior_report: FullReport | None,
    *,
    tolerance: int,
) -> SemanticValidationReport:
    from dart_footing_reconciler.check_pipeline import assemble_report_checks

    checks = assemble_report_checks(report, prior_report, tolerance=tolerance)
    return build_semantic_validation_report(report, checks)


def build_semantic_validation_report(
    report: FullReport,
    checks: list[CheckResult],
) -> SemanticValidationReport:
    dataset = build_semantic_dataset(report)
    attempts_by_source = {
        table.source: attempts_for_signatures(table.signatures)
        for table in dataset.tables
    }
    candidates = tuple(
        candidate
        for table in dataset.tables
        for candidate in _candidates_for_table(dataset, table, attempts_by_source.get(table.source, ()))
    )
    placements = tuple(sorted(
        (_placement(dataset, check) for check in checks),
        key=_placement_sort_key,
    ))
    return SemanticValidationReport(
        dataset=dataset,
        candidates=candidates,
        placements=placements,
        attempts_by_source=attempts_by_source,
    )


def _candidates_for_table(
    dataset: SemanticDataset,
    table: SemanticTable,
    attempts: tuple[SemanticAttemptSpec, ...],
) -> tuple[SemanticValidationCandidate, ...]:
    facts = dataset.amount_facts_for_table(table.source)
    evidence_sources = tuple(fact.cell_source for fact in facts)
    candidates: list[SemanticValidationCandidate] = []
    for attempt in attempts:
        confidences = [
            signature.confidence
            for signature in table.signatures
            if signature.signature in attempt.required_signatures
        ]
        confidence = min(confidences) if confidences else 0.0
        candidates.append(
            SemanticValidationCandidate(
                candidate_id=f"{table.source}:{attempt.attempt_id}",
                layer=attempt.layer,
                attempt_id=attempt.attempt_id,
                check_type=attempt.check_type,
                table_source=table.source,
                evidence_sources=evidence_sources,
                confidence=confidence,
                block_reason=None if evidence_sources else "no amount facts",
            )
        )
    return tuple(candidates)


def _placement(dataset: SemanticDataset, check: CheckResult) -> SemanticCheckPlacement:
    for evidence in check.evidence:
        table = dataset.table_for_source(evidence.source)
        if table is not None:
            return SemanticCheckPlacement(check=check, table=table, order=table.order)
    return SemanticCheckPlacement(check=check, table=None, order=None)


def _placement_sort_key(placement: SemanticCheckPlacement) -> tuple[int, int, str]:
    if placement.order is None:
        return (1, 999_999_999, placement.check.check_id)
    return (0, placement.order, placement.check.check_id)
