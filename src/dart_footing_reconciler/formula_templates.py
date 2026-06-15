"""Non-cash adjustment formula templates for CFS ↔ note reconciliation.

Provides FORMULA_TEMPLATES with known Korean note patterns and
match_formula_template() to retry formula_template_missing checks
by scanning raw note label-amount pairs instead of relying on
pre-tagged movement_role classification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from dart_footing_reconciler.amounts import parse_amount

# ---------------------------------------------------------------------------
# Subtotal row detection (shared with footing.py rollforward logic)
# ---------------------------------------------------------------------------

_SUBTOTAL_LABELS: frozenset[str] = frozenset({
    "소계",
    "합계",
    "소합계",
    "자산총계",
    "부채총계",
    "자본총계",
    "부채및자본총계",
})


def _normalize_ws(text: str) -> str:
    """Remove all whitespace and non-breaking spaces."""
    return re.sub(r"\s+", "", text.replace("\xa0", " ").strip())


def is_subtotal_row_label(label: str) -> bool:
    """Return True if *label* is a subtotal / grand-total row that should be
    excluded from rollforward movement sums.

    Uses exact match after whitespace normalisation so that labels like
    '취득합계' (취득 subtotal heading) are NOT incorrectly excluded.
    """
    return _normalize_ws(label) in _SUBTOTAL_LABELS


# ---------------------------------------------------------------------------
# Formula template registry
# ---------------------------------------------------------------------------

#: Mapping of template_key → template spec.
#:
#: ``note_items``   – label keywords whose amounts are summed as the primary total (abs value)
#: ``contra_items`` – label keywords whose amounts are subtracted (abs value) from primary
#: ``adjustments``  – optional signed adjustments; each is tried independently; sign applied to abs(amount)
#: ``tolerance``    – rounding tolerance in smallest currency unit (원)
FORMULA_TEMPLATES: dict[str, dict] = {
    # ------------------------------------------------------------------
    # 유형자산 취득 (PPE acquisition)
    # 현금 지급 취득 = 주석 취득 - 미지급금 증가 + 미지급금 감소 - 대체 취득 - 교환 취득
    # ------------------------------------------------------------------
    "ppe_acquisition": {
        "description": (
            "유형자산 취득 현금흐름 = 주석 취득 - 비현금(미지급금 증가)"
            " + 비현금(미지급금 감소) - 대체 - 교환취득"
        ),
        "note_items": ["취득"],
        "contra_items": [],
        "adjustments": [
            {"label": "미지급금증가", "sign": -1, "optional": True},
            {"label": "미지급금감소", "sign": +1, "optional": True},
            {"label": "대체", "sign": -1, "optional": True},
            {"label": "교환취득", "sign": -1, "optional": True},
            {"label": "사업결합", "sign": -1, "optional": True},
        ],
        "tolerance": 1_000,
    },
    # ------------------------------------------------------------------
    # 무형자산 취득 (intangible acquisition)
    # ------------------------------------------------------------------
    "intangible_acquisition": {
        "description": (
            "무형자산 취득 현금흐름 = 주석 취득 - 비현금(미지급금 증가) - 상각전환"
        ),
        "note_items": ["취득"],
        "contra_items": [],
        "adjustments": [
            {"label": "미지급금증가", "sign": -1, "optional": True},
            {"label": "미지급금감소", "sign": +1, "optional": True},
            {"label": "상각전환", "sign": -1, "optional": True},
            {"label": "대체", "sign": -1, "optional": True},
        ],
        "tolerance": 1_000,
    },
    # ------------------------------------------------------------------
    # 차입금 순현금흐름 (borrowing net)
    # CFS = Σ차입 - Σ상환
    # ------------------------------------------------------------------
    "borrowing_net": {
        "description": "차입금 CFS = Σ차입 - Σ상환 (rounding 허용)",
        "note_items": ["차입", "사채발행"],
        "contra_items": ["상환", "사채상환"],
        "adjustments": [],
        "tolerance": 5_000,
    },
    # ------------------------------------------------------------------
    # 리스부채 상환 (lease payment)
    # CFS = 주석 상환 - 이자지급(조정)
    # ------------------------------------------------------------------
    "lease_payment": {
        "description": "리스부채 상환 CFS = 주석 상환 - 이자지급",
        "note_items": ["상환"],
        "contra_items": [],
        "adjustments": [
            {"label": "이자지급", "sign": -1, "optional": True},
            {"label": "이자비용", "sign": -1, "optional": True},
        ],
        "tolerance": 1_000,
    },
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FormulaMatchResult:
    """Outcome of a single formula template matching attempt."""

    matched: bool
    """True if the residual is within the template tolerance."""

    formula_applied: str = ""
    """Template key that succeeded (empty when matched=False)."""

    tried_template: str = ""
    """Template key that was attempted."""

    formula_total: int = 0
    """Computed formula total (before comparing to cfs_amount)."""

    residual: int = 0
    """abs(formula_total - cfs_amount)."""

    matched_labels: tuple[str, ...] = field(default_factory=tuple)
    """Row labels that contributed to formula_total."""


# ---------------------------------------------------------------------------
# Core matching function
# ---------------------------------------------------------------------------


def match_formula_template(
    cfs_amount: int,
    note_rows: list[tuple[str, int]],
    template_key: str,
    tolerance: int | None = None,
) -> FormulaMatchResult:
    """Try to reconcile *cfs_amount* against *note_rows* using a known template.

    Args:
        cfs_amount:   Absolute CFS amount to match (positive integer).
        note_rows:    ``[(label, amount), ...]`` pairs from the relevant note table.
                      Amounts should already be scaled by the table unit_multiplier.
        template_key: Key in :data:`FORMULA_TEMPLATES`.
        tolerance:    Override tolerance in 원 (uses template default when None).

    Returns:
        :class:`FormulaMatchResult` – ``matched=True`` when residual ≤ tolerance.
    """
    template = FORMULA_TEMPLATES.get(template_key)
    if template is None:
        return FormulaMatchResult(matched=False, tried_template=template_key)

    effective_tolerance = tolerance if tolerance is not None else template["tolerance"]

    # Strip subtotal rows so they don't distort primary sums.
    rows = [
        (label, amount)
        for label, amount in note_rows
        if not is_subtotal_row_label(label)
    ]

    note_item_patterns: list[str] = template.get("note_items", [])
    contra_item_patterns: list[str] = template.get("contra_items", [])
    adjustment_specs: list[dict] = template.get("adjustments", [])

    # ------------------------------------------------------------------
    # Contra total  (Σ matched contra_items, subtracted from primary)
    # Computed FIRST so contra rows are excluded from the primary sum.
    # ------------------------------------------------------------------
    contra_total = 0
    contra_labels: list[str] = []
    contra_row_indices: set[int] = set()
    for idx, (label, amount) in enumerate(rows):
        norm = _normalize_ws(label)
        if any(_normalize_ws(pat) in norm for pat in contra_item_patterns):
            contra_total += abs(amount)
            contra_labels.append(label)
            contra_row_indices.add(idx)

    # ------------------------------------------------------------------
    # Primary total  (Σ matched note_items, excluding contra rows)
    # ------------------------------------------------------------------
    primary_total = 0
    primary_labels: list[str] = []
    for idx, (label, amount) in enumerate(rows):
        if idx in contra_row_indices:
            continue  # already counted as contra
        norm = _normalize_ws(label)
        if any(_normalize_ws(pat) in norm for pat in note_item_patterns):
            primary_total += abs(amount)
            primary_labels.append(label)

    if primary_total == 0:
        return FormulaMatchResult(matched=False, tried_template=template_key)

    base_total = primary_total - contra_total

    # ------------------------------------------------------------------
    # Optional adjustments – try all 2^n subsets, pick best
    # ------------------------------------------------------------------
    best_residual = abs(base_total - cfs_amount)
    best_adj_labels: list[str] = []
    best_formula_total = base_total

    n = len(adjustment_specs)
    for mask in range(0, 1 << n):
        adj_total = base_total
        adj_labels: list[str] = []
        for bit, spec in enumerate(adjustment_specs):
            if not (mask & (1 << bit)):
                continue
            for label, amount in rows:
                norm = _normalize_ws(label)
                if _normalize_ws(spec["label"]) in norm:
                    adj_total += spec["sign"] * abs(amount)
                    adj_labels.append(label)
                    break  # use only the first matching row per adjustment
        residual = abs(adj_total - cfs_amount)
        if residual < best_residual:
            best_residual = residual
            best_adj_labels = list(adj_labels)
            best_formula_total = adj_total

    matched = best_residual <= effective_tolerance
    all_labels = tuple(primary_labels + contra_labels + best_adj_labels)
    return FormulaMatchResult(
        matched=matched,
        formula_applied=template_key if matched else "",
        tried_template=template_key,
        formula_total=best_formula_total,
        residual=best_residual,
        matched_labels=all_labels,
    )


# ---------------------------------------------------------------------------
# Utilities for callers
# ---------------------------------------------------------------------------


def extract_note_label_amount_pairs(
    section_rows: list[list[str]],
    unit_multiplier: int = 1,
) -> list[tuple[str, int]]:
    """Convert raw note table rows to ``[(label, amount)]`` pairs.

    Only rows with a non-empty first cell AND at least one parseable amount
    in the remaining cells are included.  The LAST parseable numeric cell
    in each row is used as the amount (handles multi-column rollforward tables
    where the current-period amount is typically the rightmost column).

    Args:
        section_rows:    Raw rows from :attr:`ReportTable.rows`.
        unit_multiplier: Scale factor from the table (e.g. 1000 for 천원).

    Returns:
        List of ``(label, amount)`` tuples, amounts already scaled.
    """
    pairs: list[tuple[str, int]] = []
    for row in section_rows:
        if not row or not row[0].strip():
            continue
        label = row[0].strip()
        amount: int | None = None
        # Scan right-to-left to prefer current-period column
        for cell in reversed(row[1:]):
            parsed = parse_amount(cell)
            if parsed is not None:
                amount = parsed
                break
        if amount is not None:
            pairs.append((label, amount * unit_multiplier))
    return pairs
