"""Verification signature extraction from note/statement tables (ADR-0003 v0)."""

from __future__ import annotations

from dataclasses import dataclass, field

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import ReportTable
from dart_footing_reconciler.table_semantics import compact
from dart_footing_reconciler.taxonomy import TAXONOMY

_ROLLFORWARD_ROW_TOKENS = frozenset([
    "기초장부금액", "기초잔액", "기초금액", "전기말",
    "기말장부금액", "기말잔액", "기말금액", "당기말",
])
_ROLLFORWARD_COL_TOKENS = frozenset(["기초", "기말", "취득", "처분", "상각"])

_CLOSURE_LABELS = frozenset(["합계", "소계", "계", "총계", "자산총계", "부채총계", "자본총계"])

_TAXONOMY_CORE_LABELS: frozenset[str] = frozenset(
    compact(alias)
    for entry in TAXONOMY
    for alias in (
        *entry.statement_aliases,
        *entry.note_title_aliases,
        *entry.note_amount_aliases,
    )
)


@dataclass(frozen=True)
class SignatureMatch:
    signature: str
    confidence: float
    meta: dict = field(default_factory=dict)


def emit_signatures(table: ReportTable) -> list[SignatureMatch]:
    """Return all matched signatures for a table (empty list = no signatures)."""
    results: list[SignatureMatch] = []

    rollforward = _rollforward_axis(table)
    if rollforward is not None:
        results.append(rollforward)

    closure = _internal_closure(table)
    if closure is not None:
        results.append(closure)

    core_match = _statement_core_match(table)
    if core_match is not None:
        results.append(core_match)

    return results


def _rollforward_axis(table: ReportTable) -> SignatureMatch | None:
    if not table.rows:
        return None
    row_labels = {compact(row[0]) for row in table.rows if row}
    col_labels = {compact(cell) for cell in (table.rows[0] if table.rows else [])}

    row_hits = sum(1 for lbl in row_labels if lbl in _ROLLFORWARD_ROW_TOKENS)
    col_hits = sum(1 for lbl in col_labels if lbl in _ROLLFORWARD_COL_TOKENS)

    has_beginning = any(
        compact(row[0]).startswith("기초") or compact(row[0]) == "전기말"
        for row in table.rows if row
    )
    has_ending = any(
        compact(row[0]).startswith("기말") or compact(row[0]) == "당기말"
        for row in table.rows if row
    )

    if has_beginning and has_ending:
        confidence = min(0.9, 0.6 + row_hits * 0.1)
        return SignatureMatch("rollforward_axis", confidence, {"row_hits": row_hits})
    if col_hits >= 2:
        confidence = 0.65
        return SignatureMatch("rollforward_axis", confidence, {"col_hits": col_hits})
    return None


def _internal_closure(table: ReportTable) -> SignatureMatch | None:
    if not table.rows:
        return None
    header = table.rows[0] if table.rows else []
    col_closure = any(compact(cell) in _CLOSURE_LABELS for cell in header)
    row_closure = any(
        compact(row[0]) in _CLOSURE_LABELS
        for row in table.rows[1:]
        if row
    )
    if col_closure:
        return SignatureMatch("internal_closure", 0.85, {"level": "grand_total", "axis": "column"})
    if row_closure:
        return SignatureMatch("internal_closure", 0.75, {"level": "subtotal", "axis": "row"})
    return None


def _statement_core_match(table: ReportTable) -> SignatureMatch | None:
    if not table.rows:
        return None
    matched_labels = [
        compact(row[0])
        for row in table.rows
        if row and compact(row[0]) in _TAXONOMY_CORE_LABELS
        and (parse_amount(row[1]) is not None if len(row) > 1 else False)
    ]
    if matched_labels:
        confidence = min(0.9, 0.6 + len(matched_labels) * 0.05)
        return SignatureMatch("statement_core_match", confidence, {"matched": matched_labels[:3]})
    return None
