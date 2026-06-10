"""Semantic verification attempt registry selected from signatures."""

from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.signatures import SignatureMatch


@dataclass(frozen=True)
class SemanticAttemptSpec:
    attempt_id: str
    layer: str
    check_type: str
    axis: str
    handler_key: str
    required_signatures: tuple[str, ...]
    check_group: str
    attempt_minimum: float = 0.40
    matched_minimum: float = 0.70


SEMANTIC_ATTEMPTS: tuple[SemanticAttemptSpec, ...] = (
    SemanticAttemptSpec(
        attempt_id="statement_cross_ties",
        layer="statement_cross",
        check_type="statement_bs_equation",
        axis="statement_to_statement",
        handler_key="check_statement_ties",
        required_signatures=("statement_core_match",),
        check_group="재무제표 교차 검증",
        matched_minimum=0.90,
    ),
    SemanticAttemptSpec(
        attempt_id="internal_table_total",
        layer="note_internal",
        check_type="total_check",
        axis="internal",
        handler_key="check_table_totals",
        required_signatures=("internal_closure",),
        check_group="합계 검증",
    ),
    SemanticAttemptSpec(
        attempt_id="rollforward_internal_formula",
        layer="note_internal",
        check_type="note_layout_formula_check",
        axis="internal",
        handler_key="check_layout_formula_assertions",
        required_signatures=("rollforward_axis",),
        check_group="주석 내부/공식 검증",
    ),
    SemanticAttemptSpec(
        attempt_id="note_statement_balance",
        layer="statement_note",
        check_type="fs_note_match",
        axis="note_to_bs",
        handler_key="check_fs_note_matches",
        required_signatures=("statement_core_match",),
        check_group="재무제표-주석 대사",
    ),
    SemanticAttemptSpec(
        attempt_id="note_cashflow_bridge",
        layer="statement_note",
        check_type="cfs_note_match",
        axis="note_to_cf",
        handler_key="check_cfs_note_matches",
        required_signatures=("rollforward_axis", "statement_core_match"),
        check_group="현금흐름표-주석 대사",
        attempt_minimum=0.35,
    ),
)


def attempts_for_signatures(signatures: tuple[SignatureMatch, ...]) -> tuple[SemanticAttemptSpec, ...]:
    confidence_by_signature: dict[str, float] = {}
    for signature in signatures:
        confidence_by_signature[signature.signature] = max(
            confidence_by_signature.get(signature.signature, 0.0),
            signature.confidence,
        )

    selected: list[SemanticAttemptSpec] = []
    for attempt in SEMANTIC_ATTEMPTS:
        confidences = [
            confidence_by_signature.get(signature_name, 0.0)
            for signature_name in attempt.required_signatures
        ]
        if confidences and min(confidences) >= attempt.attempt_minimum:
            selected.append(attempt)
    return tuple(selected)
