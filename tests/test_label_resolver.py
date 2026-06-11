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
