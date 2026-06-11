"""Tests for LabelResolver — confidence-tiered row finder."""
import pytest
from dart_footing_reconciler.document import ReportTable, SourceLocation
from dart_footing_reconciler.label_resolver import (
    AccountRole, LabelResolver, MatchTier, RowMatch,
)


def _table(rows: list[list[str]]) -> ReportTable:
    return ReportTable(
        index=0,
        rows=rows,
        heading="테스트",
        location=SourceLocation("s", 0, 0),
    )


# ── EXACT ──────────────────────────────────────────────────────────────────

def test_exact_match_asset_total():
    table = _table([["구분", "당기"], ["자산총계", "1,000"], ["부채총계", "600"]])
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    assert match is not None
    assert match.match_tier == MatchTier.EXACT
    assert match.confidence == 1.0
    assert match.row[0] == "자산총계"

def test_exact_match_asset_alias_합계():
    table = _table([["구분", "당기"], ["자산합계", "1,000"]])
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    assert match is not None
    assert match.match_tier == MatchTier.EXACT
    assert match.row[0] == "자산합계"

def test_exact_match_liability_total():
    table = _table([["구분", "당기"], ["부채총계", "600"]])
    match = LabelResolver.find_row(table, AccountRole.LIABILITY_TOTAL)
    assert match is not None
    assert match.row[0] == "부채총계"

def test_exact_match_equity_total():
    table = _table([["구분", "당기"], ["자본총계", "400"]])
    match = LabelResolver.find_row(table, AccountRole.EQUITY_TOTAL)
    assert match is not None
    assert match.row[0] == "자본총계"

def test_exact_match_cash_end():
    table = _table([["구분", "당기"], ["기말현금및현금성자산", "500"]])
    match = LabelResolver.find_row(table, AccountRole.CASH_END)
    assert match is not None
    assert match.row[0] == "기말현금및현금성자산"

def test_no_match_returns_none():
    table = _table([["구분", "당기"], ["매출채권", "300"]])
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    assert match is None

# ── PREFIX ─────────────────────────────────────────────────────────────────

def test_prefix_match_자산총계합계():
    """Label starts with a canonical alias."""
    table = _table([["구분", "당기"], ["자산총계(합산)", "1,000"]])
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    assert match is not None
    assert match.match_tier == MatchTier.PREFIX
    assert match.confidence == pytest.approx(0.85)

def test_prefix_not_triggered_by_partial_interior():
    """'당기자산총계' should NOT match PREFIX (자산총계 is not a prefix of the label)."""
    table = _table([["구분", "당기"], ["당기자산총계", "1,000"]])
    # Should fall through to CONTAINS, not PREFIX
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    if match is not None:
        assert match.match_tier != MatchTier.PREFIX

# ── CONTAINS ───────────────────────────────────────────────────────────────

def test_contains_match_당기자산총계():
    table = _table([["구분", "당기"], ["당기자산총계", "1,000"]])
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    assert match is not None
    assert match.match_tier == MatchTier.CONTAINS
    assert match.confidence == pytest.approx(0.70)

# ── POSITION ───────────────────────────────────────────────────────────────

def test_position_match_last_total_row_when_no_label_match():
    """When no label matches, fall back to last row with a total-indicator char."""
    table = _table([
        ["구분", "당기"],
        ["유동자산", "300"],
        ["비유동자산", "700"],
        ["자산합계액", "1,000"],
    ])
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    # CONTAINS might fire ("자산합계" is in aliases and "자산합계액" contains it)
    # Either CONTAINS or POSITION is acceptable; confidence must be >= 0.40
    assert match is not None
    assert match.confidence >= 0.40

def test_position_no_total_indicator_returns_none():
    """Last row without total indicator char → no POSITION match → None."""
    table = _table([
        ["구분", "당기"],
        ["유동자산", "300"],
        ["매출채권", "700"],
    ])
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    assert match is None

# ── FUZZY ──────────────────────────────────────────────────────────────────

def test_fuzzy_match_자산계():
    """'자산계' is in the alias list, so it matches as EXACT (not fuzzy)."""
    table = _table([["구분", "당기"], ["자산계", "1,000"]])
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    assert match is not None
    assert match.match_tier == MatchTier.EXACT
    assert match.confidence == pytest.approx(1.0)

# ── Tie-breaking ───────────────────────────────────────────────────────────

def test_exact_beats_prefix_when_both_present():
    """If two rows match — one EXACT one PREFIX — EXACT wins."""
    table = _table([
        ["구분", "당기"],
        ["자산총계(보조)", "900"],    # PREFIX
        ["자산총계", "1,000"],        # EXACT
    ])
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    assert match is not None
    assert match.match_tier == MatchTier.EXACT
    assert match.row[0] == "자산총계"

def test_role_cash_end_현금및현금성자산():
    """현금및현금성자산 on BS maps to CASH_END role (it's in the alias list)."""
    table = _table([["구분", "당기"], ["현금및현금성자산", "500"]])
    match = LabelResolver.find_row(table, AccountRole.CASH_END)
    assert match is not None
    assert match.match_tier == MatchTier.EXACT
