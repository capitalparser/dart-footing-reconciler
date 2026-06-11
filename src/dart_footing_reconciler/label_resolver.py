"""Confidence-tiered row finder for DART financial statement tables.

Replaces scattered frozenset lookups in check modules with a single,
testable entry point that returns a RowMatch with a confidence score.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum

from dart_footing_reconciler.document import ReportTable


class AccountRole(Enum):
    ASSET_TOTAL = "asset_total"
    LIABILITY_TOTAL = "liability_total"
    EQUITY_TOTAL = "equity_total"
    CASH_END = "cash_end"
    CASH_BEGIN = "cash_begin"
    PROFIT_LOSS = "profit_loss"
    REVENUE = "revenue"


class MatchTier(Enum):
    EXACT = "exact"
    PREFIX = "prefix"
    CONTAINS = "contains"
    POSITION = "position"
    FUZZY = "fuzzy"


# ParseUncertainReason constants (strings, consistent with MATCHED / PARSE_UNCERTAIN pattern)
LABEL_NOT_FOUND = "LABEL_NOT_FOUND"
LOW_CONFIDENCE_MATCH = "LOW_CONFIDENCE_MATCH"
AMBIGUOUS_MULTIPLE = "AMBIGUOUS_MULTIPLE"
COLUMN_NOT_DETECTED = "COLUMN_NOT_DETECTED"
TABLE_NOT_FOUND = "TABLE_NOT_FOUND"
AMOUNT_PARSE_FAILED = "AMOUNT_PARSE_FAILED"


@dataclass(frozen=True)
class RowMatch:
    row: list[str]
    confidence: float
    match_tier: MatchTier
    matched_label: str
    candidates: list[str]
    reason: str


# ── Canonical label registry ────────────────────────────────────────────────

_CANONICAL_LABELS: dict[AccountRole, tuple[str, ...]] = {
    AccountRole.ASSET_TOTAL: (
        "자산총계", "자산합계", "총자산", "자본과부채총계",
        "자산계", "총자산계",
    ),
    AccountRole.LIABILITY_TOTAL: (
        "부채총계", "부채합계", "총부채", "부채계",
    ),
    AccountRole.EQUITY_TOTAL: (
        "자본총계", "자본합계", "총자본", "자본계", "순자산총계",
    ),
    AccountRole.CASH_END: (
        "기말현금및현금성자산", "현금및현금성자산기말잔액",
        "현금및현금성자산의기말잔액", "기말의현금및현금성자산",
        "기말현금성자산", "현금및현금성자산",
    ),
    AccountRole.CASH_BEGIN: (
        "기초현금및현금성자산", "현금및현금성자산기초잔액",
        "현금및현금성자산의기초잔액", "기초의현금및현금성자산",
    ),
    AccountRole.PROFIT_LOSS: (
        "당기순이익", "당기순손익", "당기순손실",
        "당기순이익(손실)", "당기순손실(이익)",
    ),
    AccountRole.REVENUE: (
        "매출액", "영업수익", "수익", "매출",
    ),
}

_TOTAL_INDICATOR_CHARS = frozenset("총합계")


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


class LabelResolver:
    """Stateless row finder. All methods are class-level."""

    @classmethod
    def find_row(cls, table: ReportTable, role: AccountRole) -> RowMatch | None:
        """Return the best-matching row for *role*, or None if confidence < 0.40."""
        aliases = _CANONICAL_LABELS.get(role, ())
        if not aliases:
            return None

        candidates: list[tuple[float, MatchTier, list[str], str, str]] = []
        # (confidence, tier, row, matched_label, reason)

        for row in table.rows:
            if not row:
                continue
            label = _compact(row[0])
            if not label:
                continue

            # Tier 1: EXACT
            for alias in aliases:
                if label == _compact(alias):
                    candidates.append((
                        1.0, MatchTier.EXACT, row, row[0],
                        f"완전 일치: '{row[0]}' = '{alias}'",
                    ))

            # Tier 2: PREFIX — label starts with a canonical alias
            for alias in aliases:
                ca = _compact(alias)
                if label.startswith(ca) and label != ca:
                    candidates.append((
                        0.85, MatchTier.PREFIX, row, row[0],
                        f"접두 일치: '{row[0]}' → '{alias}'",
                    ))

            # Tier 3: CONTAINS — label contains a canonical alias (not a prefix)
            for alias in aliases:
                ca = _compact(alias)
                if ca in label and not label.startswith(ca):
                    candidates.append((
                        0.70, MatchTier.CONTAINS, row, row[0],
                        f"포함 일치: '{row[0]}' ⊇ '{alias}'",
                    ))

            # Tier 4: FUZZY — SequenceMatcher ratio >= 0.80
            for alias in aliases:
                ratio = SequenceMatcher(None, label, _compact(alias)).ratio()
                if ratio >= 0.80:
                    candidates.append((
                        0.40, MatchTier.FUZZY, row, row[0],
                        f"유사 일치: '{row[0]}' ≈ '{alias}' (유사도 {ratio:.0%})",
                    ))

        if not candidates:
            # Tier 5: POSITION — last non-empty row in the table (grand-total heuristic)
            position_match = cls._position_match(table, role)
            if position_match:
                return position_match
            return None

        # Pick the best: highest confidence, then earliest tier enum order, then first in table
        candidates.sort(key=lambda c: (-c[0], list(MatchTier).index(c[1])))
        best_conf, best_tier, best_row, best_label, best_reason = candidates[0]

        if best_conf < 0.40:
            return None

        other_candidate_labels = [
            c[3] for c in candidates[1:]
            if c[0] >= 0.30 and c[2] is not best_row
        ]

        return RowMatch(
            row=best_row,
            confidence=best_conf,
            match_tier=best_tier,
            matched_label=best_label,
            candidates=other_candidate_labels[:3],
            reason=best_reason,
        )

    @classmethod
    def _position_match(cls, table: ReportTable, role: AccountRole) -> RowMatch | None:
        """Last-resort: return the last row that looks like a grand total.

        Restricted to ASSET_TOTAL only.  For ASSET_TOTAL the last grand-total
        row in a BS table is almost always the right one (assets always appear
        before liabilities/equity, so the last '계' row is the asset total).
        For LIABILITY_TOTAL and EQUITY_TOTAL the last-row heuristic fires on
        the wrong row too often (grand asset total, equity sub-components),
        producing misleading PARSE_UNCERTAIN evidence.
        """
        # POSITION heuristic is only defensible for ASSET_TOTAL.
        if role not in (AccountRole.ASSET_TOTAL,):
            return None

        last_row = None
        for row in reversed(table.rows):
            if row and row[0].strip():
                last_row = row
                break

        if last_row is None:
            return None

        label = _compact(last_row[0])
        # Must contain at least one total indicator character
        if not any(ch in label for ch in _TOTAL_INDICATOR_CHARS):
            return None

        return RowMatch(
            row=last_row,
            confidence=0.55,
            match_tier=MatchTier.POSITION,
            matched_label=last_row[0],
            candidates=[],
            reason=f"위치 추정: 테이블 마지막 합계 행 '{last_row[0]}'",
        )
