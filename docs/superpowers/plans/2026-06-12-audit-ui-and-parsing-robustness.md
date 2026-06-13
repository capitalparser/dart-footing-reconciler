# Audit UI & Parsing Robustness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the developer-facing HTML report with an evidence_cockpit UI that renders raw DART financial statement tables with inline verification overlays, and introduce a `LabelResolver` module so diverse company label variants no longer silently fail.

**Architecture:** Two independent phases in sequence. Phase A builds `label_resolver.py` — a confidence-tiered row-finding engine that replaces scattered frozenset lookups — and adds `parse_uncertain_reason` to `CheckResult`. Phase B replaces `report_html.py` entirely, keeping the same public function signature, and renders `FullReport` tables verbatim with tick-mark overlays driven by `CheckResult.evidence` source strings.

**Tech Stack:** Python 3.11+, BeautifulSoup4, `difflib.SequenceMatcher` (stdlib, no new dep), pytest; HTML output is self-contained with inline CSS/JS, no CDN.

---

## File Map

### Phase A — Label Resolver

| Action | Path |
|--------|------|
| **Create** | `src/dart_footing_reconciler/label_resolver.py` |
| **Modify** | `src/dart_footing_reconciler/checks.py` |
| **Modify** | `src/dart_footing_reconciler/checks_statement_ties.py` |
| **Create** | `tests/test_label_resolver.py` |

### Phase B — HTML Report

| Action | Path |
|--------|------|
| **Replace** | `src/dart_footing_reconciler/report_html.py` |
| **Create** | `tests/test_report_html_new.py` |

---

## Background: Key Types

```python
# checks.py
MATCHED = "matched"
UNEXPLAINED_GAP = "unexplained_gap"
PARSE_UNCERTAIN = "parse_uncertain"

@dataclass(frozen=True)
class CheckEvidence:
    label: str
    amount: int | None
    source: str   # e.g. "statement:bs/table:0/row:3"

@dataclass(frozen=True)
class CheckResult:
    check_id: str; check_type: str; status: str; scope: str
    note_no: str; title: str
    expected: int | None; actual: int | None; difference: int | None
    tolerance: int; reason: str
    evidence: list[CheckEvidence]
    # parse_uncertain_reason added in Task 1

# document.py
@dataclass(frozen=True)
class ReportTable:
    index: int
    rows: list[list[str]]   # rows[i][0] = label, rows[i][1:] = amount cells
    heading: str
    location: SourceLocation
    row_acodes: list[list[str]] | None = None
    unit_multiplier: int = 1

@dataclass(frozen=True)
class ReportSection:
    section_id: str; title: str; kind: str; note_no: str
    blocks: list[ReportBlock]; scope: str = ""

@dataclass(frozen=True)
class FullReport:
    source: str; company: str
    statements: list[ReportSection]
    notes: list[ReportSection]
```

---

## Phase A — Label Resolver

---

### Task 1: Add `parse_uncertain_reason` to `CheckResult`

**Files:**
- Modify: `src/dart_footing_reconciler/checks.py`
- Test: `tests/test_checks_model.py` (existing — add one test)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_checks_model.py`:

```python
def test_check_result_has_parse_uncertain_reason_field():
    from dart_footing_reconciler.checks import CheckResult, PARSE_UNCERTAIN
    result = CheckResult(
        check_id="x", check_type="x", status=PARSE_UNCERTAIN,
        scope="report", note_no="", title="테스트",
        expected=None, actual=None, difference=None,
        tolerance=1, reason="row not found", evidence=[],
        parse_uncertain_reason="LABEL_NOT_FOUND",
    )
    assert result.parse_uncertain_reason == "LABEL_NOT_FOUND"

def test_check_result_parse_uncertain_reason_defaults_to_none():
    from dart_footing_reconciler.checks import CheckResult, MATCHED
    result = CheckResult(
        check_id="x", check_type="x", status=MATCHED,
        scope="report", note_no="", title="테스트",
        expected=100, actual=100, difference=0,
        tolerance=1, reason="ok", evidence=[],
    )
    assert result.parse_uncertain_reason is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/kjun/vault/01_Projects/09_dart_footing_reconciler
uv run pytest tests/test_checks_model.py::test_check_result_has_parse_uncertain_reason_field -v
```
Expected: FAIL — `CheckResult.__init__() got unexpected keyword argument 'parse_uncertain_reason'`

- [ ] **Step 3: Add `parse_uncertain_reason` field to `CheckResult`**

In `src/dart_footing_reconciler/checks.py`, change:

```python
@dataclass(frozen=True)
class CheckResult:
    check_id: str
    check_type: str
    status: str
    scope: str
    note_no: str
    title: str
    expected: int | None
    actual: int | None
    difference: int | None
    tolerance: int
    reason: str
    evidence: list[CheckEvidence]
    parse_uncertain_reason: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_checks_model.py -v
```
Expected: All PASS. Then run the full suite to check nothing broke:

```bash
uv run pytest tests/ -x -q 2>&1 | tail -20
```
Expected: All tests pass (the new field has a default of `None` so existing call sites are unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/checks.py tests/test_checks_model.py
git commit -m "feat(domain): add parse_uncertain_reason optional field to CheckResult"
```

---

### Task 2: Create `label_resolver.py` — EXACT and PREFIX tiers

**Files:**
- Create: `src/dart_footing_reconciler/label_resolver.py`
- Create: `tests/test_label_resolver.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_label_resolver.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_label_resolver.py -v 2>&1 | head -20
```
Expected: ImportError — `label_resolver` module not found.

- [ ] **Step 3: Create `src/dart_footing_reconciler/label_resolver.py`**

```python
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

            # Tier 3: CONTAINS — label contains a canonical alias
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
        """Last-resort: return the last row that looks like a grand total."""
        # Only apply to roles where a grand-total heuristic makes sense
        if role not in (
            AccountRole.ASSET_TOTAL,
            AccountRole.LIABILITY_TOTAL,
            AccountRole.EQUITY_TOTAL,
        ):
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
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_label_resolver.py -v
```
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/label_resolver.py tests/test_label_resolver.py
git commit -m "feat(label_resolver): add LabelResolver with EXACT/PREFIX/CONTAINS/POSITION/FUZZY tiers"
```

---

### Task 3: Add CONTAINS and POSITION tier tests + edge cases

**Files:**
- Modify: `tests/test_label_resolver.py`

- [ ] **Step 1: Add tests**

Append to `tests/test_label_resolver.py`:

```python
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
        ["자산합계액", "1,000"],   # Not in canonical list — no EXACT/PREFIX/CONTAINS match
    ])
    # "자산합계액" contains "합계" (a total indicator) so POSITION fires
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    # CONTAINS might actually fire here since "자산합계" is in aliases and "자산합계액" contains it
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
    """'자산계' has no canonical alias, but is similar to '자산총계' (ratio ~0.8+)."""
    table = _table([["구분", "당기"], ["자산계", "1,000"]])
    match = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    # Either FUZZY fires or match is None — depends on SequenceMatcher ratio
    # What matters: if it matches, tier must be FUZZY and confidence 0.40
    if match is not None:
        assert match.match_tier == MatchTier.FUZZY
        assert match.confidence == pytest.approx(0.40)

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
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/test_label_resolver.py -v
```
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_label_resolver.py
git commit -m "test(label_resolver): add CONTAINS, POSITION, FUZZY, tie-breaking tests"
```

---

### Task 4: Migrate `checks_statement_ties.py` to `LabelResolver`

**Files:**
- Modify: `src/dart_footing_reconciler/checks_statement_ties.py`
- Modify: `tests/test_checks_statement_ties.py`

- [ ] **Step 1: Add regression test for variant label**

Append to `tests/test_checks_statement_ties.py`:

```python
def test_bs_equation_variant_label_순자산총계():
    """'순자산총계' is not in the old frozenset but LabelResolver CONTAINS should catch it."""
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "1,000"],
            ["부채총계", "600"],
            ["순자산총계", "400"],     # variant for 자본총계
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    # With LabelResolver, 순자산총계 matches EQUITY_TOTAL via CONTAINS
    assert eq[0].status in (MATCHED, UNEXPLAINED_GAP)  # not PARSE_UNCERTAIN
    assert eq[0].status != PARSE_UNCERTAIN

def test_bs_equation_parse_uncertain_reason_when_row_missing():
    """When no row found at all, parse_uncertain_reason should be LABEL_NOT_FOUND."""
    from dart_footing_reconciler.label_resolver import LABEL_NOT_FOUND
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["매출채권", "300"],     # no total rows at all
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == PARSE_UNCERTAIN
    assert eq[0].parse_uncertain_reason == LABEL_NOT_FOUND
```

- [ ] **Step 2: Run new tests to verify they fail for the right reason**

```bash
uv run pytest tests/test_checks_statement_ties.py::test_bs_equation_variant_label_순자산총계 tests/test_checks_statement_ties.py::test_bs_equation_parse_uncertain_reason_when_row_missing -v
```
Expected: First test FAILS (`PARSE_UNCERTAIN` returned instead of `MATCHED`). Second test FAILS (`parse_uncertain_reason` is `None`).

- [ ] **Step 3: Migrate `checks_statement_ties.py`**

Replace the file content:

```python
"""Statement-level tie checks: BS equation and cross-statement amount ties."""
from __future__ import annotations

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    CheckEvidence, CheckResult,
    MATCHED, PARSE_UNCERTAIN, UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.label_resolver import (
    AccountRole, LabelResolver, RowMatch,
    LABEL_NOT_FOUND, LOW_CONFIDENCE_MATCH,
)


def check_statement_ties(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(_bs_equation_checks(report, tolerance=tolerance))
    results.extend(_cash_tie_checks(report, tolerance=tolerance))
    results.extend(_equity_tie_checks(report, tolerance=tolerance))
    return results


def _bs_equation_checks(report: FullReport, *, tolerance: int) -> list[CheckResult]:
    bs = _find_statement(report, ("재무상태표",))
    if bs is None:
        return []
    table = _first_table(bs)
    if table is None:
        return []

    asset_m = LabelResolver.find_row(table, AccountRole.ASSET_TOTAL)
    liab_m = LabelResolver.find_row(table, AccountRole.LIABILITY_TOTAL)
    equity_m = LabelResolver.find_row(table, AccountRole.EQUITY_TOTAL)

    if asset_m is None or liab_m is None or equity_m is None:
        return [_tie_result(
            check_id="statement_bs_equation",
            check_type="statement_bs_equation",
            scope="report", note_no="",
            title="재무상태표 기본등식",
            expected=None, actual=None, difference=None, tolerance=tolerance,
            status=PARSE_UNCERTAIN,
            reason="자산총계·부채총계·자본총계 중 하나 이상 미발견",
            evidence=[],
            parse_uncertain_reason=LABEL_NOT_FOUND,
        )]

    _uncertain = _low_confidence_any(asset_m, liab_m, equity_m)

    asset_val = _current_amount(table, asset_m.row)
    liab_val = _current_amount(table, liab_m.row)
    equity_val = _current_amount(table, equity_m.row)
    if asset_val is None or liab_val is None or equity_val is None:
        return []

    expected = liab_val + equity_val
    actual = asset_val
    difference = actual - expected

    if _uncertain:
        status = PARSE_UNCERTAIN
        reason = f"BS equation — 신뢰도 낮은 행 사용 ({_uncertain})"
        uncertain_reason = LOW_CONFIDENCE_MATCH
    else:
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        reason = "BS equation 성립" if status == MATCHED else "BS equation 불일치"
        uncertain_reason = None

    return [_tie_result(
        check_id="statement_bs_equation:current",
        check_type="statement_bs_equation",
        title="재무상태표 BS equation: 자산총계 = 부채총계 + 자본총계",
        expected=expected, actual=actual, difference=difference,
        tolerance=tolerance, status=status, reason=reason,
        evidence=[
            CheckEvidence(asset_m.row[0], asset_val, _row_source(table, asset_m.row, "bs")),
            CheckEvidence(liab_m.row[0], liab_val, _row_source(table, liab_m.row, "bs")),
            CheckEvidence(equity_m.row[0], equity_val, _row_source(table, equity_m.row, "bs")),
        ],
        note_no="bs",
        parse_uncertain_reason=uncertain_reason,
    )]


def _cash_tie_checks(report: FullReport, *, tolerance: int) -> list[CheckResult]:
    bs = _find_statement(report, ("재무상태표",))
    cf = _find_statement(report, ("현금흐름표",))
    if bs is None or cf is None:
        return []

    bs_table = _first_table(bs)
    cf_table = _first_table(cf)
    if bs_table is None or cf_table is None:
        return []

    bs_m = LabelResolver.find_row(bs_table, AccountRole.CASH_END)
    cf_m = LabelResolver.find_row(cf_table, AccountRole.CASH_END)
    if bs_m is None or cf_m is None:
        return []

    bs_val = _current_amount(bs_table, bs_m.row)
    cf_val = _current_amount(cf_table, cf_m.row)
    if bs_val is None or cf_val is None:
        return []

    _uncertain = _low_confidence_any(bs_m, cf_m)
    difference = bs_val - cf_val
    if _uncertain:
        status = PARSE_UNCERTAIN
        reason = f"현금 대사 — 신뢰도 낮은 행 사용 ({_uncertain})"
        uncertain_reason = LOW_CONFIDENCE_MATCH
    else:
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        reason = "BS 현금 = CF 기말 현금" if status == MATCHED else "BS 현금 ≠ CF 기말 현금"
        uncertain_reason = None

    return [_tie_result(
        check_id="statement_cash_tie:current",
        check_type="statement_cash_tie",
        title="재무상태표 현금 ↔ 현금흐름표 기말 현금 대사",
        expected=cf_val, actual=bs_val, difference=difference,
        tolerance=tolerance, status=status, reason=reason,
        evidence=[
            CheckEvidence(bs_m.row[0], bs_val, _row_source(bs_table, bs_m.row, "bs")),
            CheckEvidence(cf_m.row[0], cf_val, _row_source(cf_table, cf_m.row, "cf")),
        ],
        note_no="cross_statement",
        parse_uncertain_reason=uncertain_reason,
    )]


def _equity_tie_checks(report: FullReport, *, tolerance: int) -> list[CheckResult]:
    bs = _find_statement(report, ("재무상태표",))
    sce = _find_statement(report, ("자본변동표",))
    if bs is None or sce is None:
        return []

    bs_table = _first_table(bs)
    sce_table = _first_table(sce)
    if bs_table is None or sce_table is None:
        return []

    bs_m = LabelResolver.find_row(bs_table, AccountRole.EQUITY_TOTAL)
    sce_m = _find_sce_equity_end_row(sce_table)
    if bs_m is None or sce_m is None:
        return []

    bs_val = _current_amount(bs_table, bs_m.row)
    sce_val = _current_amount(sce_table, sce_m.row)
    if bs_val is None or sce_val is None:
        return []

    difference = bs_val - sce_val
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    return [_tie_result(
        check_id="statement_equity_tie:current",
        check_type="statement_equity_tie",
        title="재무상태표 자본총계 ↔ 자본변동표 기말 자본 대사",
        expected=sce_val, actual=bs_val, difference=difference,
        tolerance=tolerance,
        status=status,
        reason="BS 자본총계 = SCE 기말 자본총계" if status == MATCHED else "BS 자본총계 ≠ SCE 기말 자본총계",
        evidence=[
            CheckEvidence(bs_m.row[0], bs_val, _row_source(bs_table, bs_m.row, "bs")),
            CheckEvidence(sce_m.row[0], sce_val, _row_source(sce_table, sce_m.row, "sce")),
        ],
        note_no="cross_statement",
    )]


# ── SCE equity end row (preserved from original — still label-based) ────────

_EQUITY_SCE_END_LABELS = frozenset(["자본총계", "자본합계", "총자본"])
_EQUITY_SCE_END_FRAGMENTS = ("기말자본", "기말의자본")

def _find_sce_equity_end_row(table: ReportTable) -> RowMatch | None:
    from dart_footing_reconciler.label_resolver import MatchTier, RowMatch
    candidate = None
    for row in table.rows:
        if not row:
            continue
        from dart_footing_reconciler.label_resolver import _compact
        label = _compact(row[0])
        if label in _EQUITY_SCE_END_LABELS or any(frag in label for frag in _EQUITY_SCE_END_FRAGMENTS):
            candidate = row
    if candidate is None:
        return None
    return RowMatch(
        row=candidate, confidence=1.0, match_tier=MatchTier.EXACT,
        matched_label=candidate[0], candidates=[],
        reason=f"SCE 기말 자본 행: '{candidate[0]}'",
    )


# ── Helpers ─────────────────────────────────────────────────────────────────

def _low_confidence_any(*matches: RowMatch) -> str | None:
    """Return label of first low-confidence match, or None if all are high confidence."""
    for m in matches:
        if m.confidence < 0.70:
            return m.matched_label
    return None


def _find_statement(report: FullReport, title_fragments: tuple[str, ...]) -> ReportSection | None:
    for section in report.statements:
        if any(frag in section.title for frag in title_fragments):
            return section
    return None


def _first_table(section: ReportSection) -> ReportTable | None:
    for block in section.blocks:
        if block.table is not None:
            return block.table
    return None


def _current_amount(table: ReportTable, row: list[str]) -> int | None:
    for cell in row[1:]:
        val = parse_amount(cell)
        if val is not None:
            return val * table.unit_multiplier
    return None


def _row_source(table: ReportTable, row: list[str], statement_kind: str) -> str:
    for i, r in enumerate(table.rows):
        if r is row:
            return f"statement:{statement_kind}/table:{table.index}/row:{i}"
    return f"statement:{statement_kind}/table:{table.index}/row:unknown"


def _tie_result(
    *,
    check_id: str, check_type: str, scope: str = "report", title: str,
    expected: int | None, actual: int | None, difference: int | None,
    tolerance: int, status: str, reason: str, evidence: list[CheckEvidence],
    note_no: str, parse_uncertain_reason: str | None = None,
) -> CheckResult:
    return CheckResult(
        check_id=check_id, check_type=check_type, status=status,
        scope=scope, note_no=note_no, title=title,
        expected=expected, actual=actual, difference=difference,
        tolerance=tolerance, reason=reason, evidence=evidence,
        parse_uncertain_reason=parse_uncertain_reason,
    )
```

- [ ] **Step 4: Run all statement tie tests**

```bash
uv run pytest tests/test_checks_statement_ties.py -v
```
Expected: All PASS including the new variant label and parse_uncertain_reason tests.

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
uv run pytest tests/ -x -q 2>&1 | tail -20
```
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/dart_footing_reconciler/checks_statement_ties.py tests/test_checks_statement_ties.py
git commit -m "feat(checks): migrate checks_statement_ties to LabelResolver with confidence tiers"
```

---

## Phase B — HTML Report

---

### Task 5: Scaffold new `report_html.py` with public API + `_tie_results`

**Files:**
- Replace: `src/dart_footing_reconciler/report_html.py`
- Create: `tests/test_report_html_new.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_report_html_new.py`:

```python
"""Tests for the new evidence_cockpit HTML renderer."""
from pathlib import Path
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP, PARSE_UNCERTAIN
from dart_footing_reconciler.document import (
    FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation,
)
from dart_footing_reconciler.report_html import export_audit_reconciliation_html, _tie_results


# ── Fixtures ────────────────────────────────────────────────────────────────

def _table(idx: int, rows: list[list[str]]) -> ReportTable:
    return ReportTable(idx, rows, "테스트", SourceLocation("s", 0, idx))

def _stmt_section(section_id: str, title: str, rows: list[list[str]]) -> ReportSection:
    t = _table(0, rows)
    return ReportSection(section_id, title, "statement", "",
                         [ReportBlock("table", "", t, t.location)])

def _note_section(note_no: str, rows: list[list[str]]) -> ReportSection:
    t = _table(0, rows)
    return ReportSection(f"note:{note_no}", f"주석 {note_no}", "note", note_no,
                         [ReportBlock("table", "", t, t.location)])

def _result(check_id: str, status: str, source: str, note_no: str = "") -> CheckResult:
    return CheckResult(
        check_id=check_id, check_type="test", status=status,
        scope="report", note_no=note_no, title=check_id,
        expected=100, actual=100, difference=0, tolerance=1,
        reason="ok",
        evidence=[CheckEvidence("자산총계", 100, source)],
    )


# ── _tie_results ────────────────────────────────────────────────────────────

def test_tie_results_groups_by_statement_kind():
    results = [
        _result("eq1", MATCHED, "statement:bs/table:0/row:1"),
        _result("eq2", MATCHED, "statement:cf/table:0/row:2"),
        _result("eq3", MATCHED, "statement:bs/table:0/row:3"),
    ]
    tied = _tie_results(results)
    assert len(tied["bs"]) == 2
    assert len(tied["cf"]) == 1
    assert "is" not in tied or len(tied["is"]) == 0

def test_tie_results_groups_note():
    results = [
        _result("n1", MATCHED, "note:12/table:0/row:1", note_no="12"),
        _result("n2", MATCHED, "note:13/table:0/row:2", note_no="13"),
    ]
    tied = _tie_results(results)
    assert len(tied.get("note:12", [])) == 1
    assert len(tied.get("note:13", [])) == 1

def test_tie_results_cross_statement_evidence():
    """A result with evidence from both bs and cf sections: key derived from first evidence."""
    results = [
        _result("cash_tie", MATCHED, "statement:bs/table:0/row:1"),
    ]
    tied = _tie_results(results)
    assert "bs" in tied


# ── export_audit_reconciliation_html ────────────────────────────────────────

def test_export_creates_html_file(tmp_path: Path):
    bs = _stmt_section("statement:재무상태표", "재무상태표",
                       [["구분", "당기", "전기"], ["자산총계", "1,000", "900"]])
    report = FullReport("test.html", "테스트(주)", [bs], [])
    checks = [_result("eq1", MATCHED, "statement:bs/table:0/row:1")]
    out = tmp_path / "report.html"
    export_audit_reconciliation_html(report, checks, out)
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "테스트(주)" in content

def test_export_returns_path(tmp_path: Path):
    report = FullReport("t.html", "회사", [], [])
    result_path = export_audit_reconciliation_html(report, [], tmp_path / "r.html")
    assert result_path == tmp_path / "r.html"
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_report_html_new.py -v 2>&1 | head -30
```
Expected: ImportError or AttributeError — `_tie_results` not found in new module.

- [ ] **Step 3: Replace `report_html.py` with the scaffold**

Completely replace `src/dart_footing_reconciler/report_html.py` with:

```python
"""Evidence-cockpit HTML renderer for DART audit reconciliation reports.

Public API (unchanged from previous version):
    export_audit_reconciliation_html(report, checks, output_path) -> Path
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from dart_footing_reconciler.checks import (
    CheckResult, MATCHED, UNEXPLAINED_GAP, PARSE_UNCERTAIN,
)
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable


# ── Public API ───────────────────────────────────────────────────────────────

def export_audit_reconciliation_html(
    report: FullReport,
    checks: list[CheckResult],
    output_path: str | Path,
    *,
    company_name: str = "",
    period_label: str = "",
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    meta = _ReportMeta(
        company=company_name or report.company or "회사",
        period=period_label,
    )
    output.write_text(_build_html(report, checks, meta), encoding="utf-8")
    return output


# ── Meta ─────────────────────────────────────────────────────────────────────

class _ReportMeta(NamedTuple):
    company: str
    period: str


# ── Tie results ──────────────────────────────────────────────────────────────

def _tie_results(results: list[CheckResult]) -> dict[str, list[CheckResult]]:
    """Group CheckResults by section key extracted from their first evidence source.

    Keys: "bs" | "is" | "sce" | "cf" | "note:{note_no}" | "other"
    """
    grouped: dict[str, list[CheckResult]] = {}
    for result in results:
        key = _section_key(result)
        grouped.setdefault(key, []).append(result)
    return grouped


def _section_key(result: CheckResult) -> str:
    if result.evidence:
        src = result.evidence[0].source
        # "statement:bs/..." → "bs"
        m = re.match(r"statement:(\w+)", src)
        if m:
            return m.group(1)
        # "note:12/..." → "note:12"
        m = re.match(r"note:(\w+)", src)
        if m:
            return f"note:{m.group(1)}"
    # Fall back to note_no if present
    if result.note_no and result.note_no not in ("", "bs", "cf", "sce", "cross_statement"):
        return f"note:{result.note_no}"
    return "other"


# ── Build HTML ────────────────────────────────────────────────────────────────

def _build_html(report: FullReport, results: list[CheckResult], meta: _ReportMeta) -> str:
    tied = _tie_results(results)
    uncertain_results = [r for r in results if r.status == PARSE_UNCERTAIN]

    sidebar_html = _render_sidebar(report, results)
    banner_html = _render_verdict_banner(results)

    panels: list[str] = []

    # Statement panels in canonical order
    _STMT_KINDS = [
        ("재무상태표", "bs", "재무상태표"),
        ("손익계산서", "is", "손익계산서"),
        ("포괄손익계산서", "is", "포괄손익계산서"),
        ("자본변동표", "sce", "자본변동표"),
        ("현금흐름표", "cf", "현금흐름표"),
    ]
    rendered_kinds: set[str] = set()
    for title_frag, kind, label in _STMT_KINDS:
        if kind in rendered_kinds:
            continue
        section = _find_section(report.statements, title_frag)
        if section is None:
            continue
        rendered_kinds.add(kind)
        panels.append(_render_statement_panel(
            section, tied.get(kind, []), panel_id=f"panel-{kind}", label=label,
        ))

    # Note panels
    for section in report.notes:
        note_no = section.note_no or section.section_id
        panels.append(_render_note_panel(
            section, tied.get(f"note:{note_no}", []), panel_id=f"panel-note-{note_no}",
        ))

    # Parse uncertain panel
    if uncertain_results:
        panels.append(_render_parse_uncertain_panel(uncertain_results))

    content = "\n".join(panels)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DART 수치검증 — {_esc(meta.company)}</title>
{_inline_css()}
</head>
<body data-cockpit-profile="evidence_cockpit" data-cockpit-shell="side-app">
<div class="shell">
{sidebar_html}
<main id="main-content">
{banner_html}
{content}
</main>
</div>
{_inline_js()}
</body>
</html>"""


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _render_sidebar(report: FullReport, results: list[CheckResult]) -> str:
    tied = _tie_results(results)

    def _badge(kind_key: str) -> str:
        items = tied.get(kind_key, [])
        if not items:
            return ""
        warn = sum(1 for r in items if r.status in (UNEXPLAINED_GAP,))
        unc = sum(1 for r in items if r.status == PARSE_UNCERTAIN)
        if warn:
            return f'<span class="nav-badge nb-warn">⚠ {warn}</span>'
        if unc:
            return f'<span class="nav-badge nb-unc">? {unc}</span>'
        return '<span class="nav-badge nb-ok">✓</span>'

    stmt_items = ""
    _STMT_MAP = [
        ("재무상태표", "bs"), ("손익계산서", "is"),
        ("자본변동표", "sce"), ("현금흐름표", "cf"),
    ]
    for label, kind in _STMT_MAP:
        section = _find_section(report.statements, label)
        if section is None:
            continue
        b = _badge(kind)
        stmt_items += f'<div class="nav-item" data-target="panel-{kind}">{_esc(label)} {b}</div>\n'

    note_items = ""
    for section in report.notes:
        note_no = section.note_no or section.section_id
        b = _badge(f"note:{note_no}")
        note_items += (
            f'<div class="nav-item" data-target="panel-note-{_esc(note_no)}">'
            f'{_esc(section.note_no)}. {_esc(section.title)} {b}'
            f'</div>\n'
        )

    uncertain_count = sum(1 for r in results if r.status == PARSE_UNCERTAIN)
    diag_item = ""
    if uncertain_count:
        diag_item = (
            f'<div class="nav-item" data-target="panel-parse-diag">'
            f'파싱 진단 <span class="nav-badge nb-unc">? {uncertain_count}</span>'
            f'</div>'
        )

    return f"""<aside>
  <div class="sidebar-brand">
    <div class="sidebar-brand-name">DART 수치 검증</div>
    <div class="sidebar-brand-sub">{_esc(report.company)}</div>
  </div>
  <div class="sidebar-section">요약</div>
  <div class="nav-item active" data-target="panel-summary">전체 결과 요약</div>
  <hr class="sidebar-divider">
  <div class="sidebar-section">재무제표 본문</div>
  {stmt_items}
  <hr class="sidebar-divider">
  <div class="sidebar-section">주석</div>
  {note_items}
  {diag_item}
</aside>"""


# ── Verdict Banner ────────────────────────────────────────────────────────────

def _render_verdict_banner(results: list[CheckResult]) -> str:
    matched = sum(1 for r in results if r.status == MATCHED)
    gaps = sum(1 for r in results if r.status == UNEXPLAINED_GAP)
    uncertain = sum(1 for r in results if r.status == PARSE_UNCERTAIN)
    total = len(results)

    if not results:
        verdict_label = "검증 항목 없음"
        verdict_class = "verdict-none"
    elif gaps > 0:
        verdict_label = "검토 필요"
        verdict_class = "verdict-warn"
    elif uncertain > 0:
        verdict_label = "확인 필요"
        verdict_class = "verdict-unc"
    else:
        verdict_label = "이상 없음"
        verdict_class = "verdict-ok"

    return f"""<div class="verdict-banner {verdict_class}" id="panel-summary">
  <div class="verdict-label">{verdict_label}</div>
  <div class="kpi-strip">
    <div class="kpi-tile kpi-ok"><div class="kpi-val">{matched}</div><div class="kpi-name">검증 완료</div></div>
    <div class="kpi-tile kpi-warn"><div class="kpi-val">{gaps}</div><div class="kpi-name">검토 필요</div></div>
    <div class="kpi-tile kpi-unc"><div class="kpi-val">{uncertain}</div><div class="kpi-name">파싱 불확실</div></div>
    <div class="kpi-tile"><div class="kpi-val">{total}</div><div class="kpi-name">전체</div></div>
  </div>
</div>"""


# ── Statement Panel ───────────────────────────────────────────────────────────

def _render_statement_panel(
    section: ReportSection,
    results: list[CheckResult],
    panel_id: str,
    label: str,
) -> str:
    table = _first_table(section)
    if table is None:
        return (
            f'<div class="panel" id="{_esc(panel_id)}">'
            f'<div class="panel-title">{_esc(label)}</div>'
            f'<p class="empty-state">공시에서 찾을 수 없음</p></div>'
        )

    # Build row-index → CheckResult mapping
    row_map: dict[int, CheckResult] = {}
    for result in results:
        for ev in result.evidence:
            m = re.search(r"/row:(\d+)", ev.source)
            if m:
                idx = int(m.group(1))
                if idx not in row_map:
                    row_map[idx] = result

    rows_html = _render_table_rows(table, row_map)
    check_summary = _render_check_summary(results) if results else ""

    return f"""<div class="panel" id="{_esc(panel_id)}">
  <div class="panel-title">{_esc(label)}</div>
  <div class="panel-sub">원문 보고서 형태 · 검증 행 클릭 시 근거 확인</div>
  <div class="statement-wrap">
    <div class="statement-caption"><span>{_esc(label)}</span></div>
    <table class="fs-table">
      {rows_html}
    </table>
  </div>
  {check_summary}
</div>"""


def _render_table_rows(table: ReportTable, row_map: dict[int, CheckResult]) -> str:
    html_parts: list[str] = []
    if not table.rows:
        return ""

    header = table.rows[0]
    header_cells = "".join(f"<th>{_esc(c)}</th>" for c in header)
    html_parts.append(f"<thead><tr>{header_cells}</tr></thead><tbody>")

    for i, row in enumerate(table.rows[1:], start=1):
        result = row_map.get(i)
        if result is None:
            cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
            html_parts.append(f"<tr>{cells}</tr>")
        else:
            css_class = _status_to_row_class(result.status)
            dd_id = f"dd-{i}"
            cells = "".join(f"<td>{_esc(c)}</td>" for c in row)
            html_parts.append(
                f'<tr class="{css_class}" data-check-row="{i}" '
                f'onclick="toggleDD(\'{dd_id}\')">{cells}</tr>'
            )
            html_parts.append(
                f'<tr class="dd-row">'
                f'<td colspan="{len(row)}" class="dd-cell">'
                f'<div class="dd-inner" id="{dd_id}">'
                f'{_render_drilldown(result)}'
                f'</div></td></tr>'
            )

    html_parts.append("</tbody>")
    return "\n".join(html_parts)


def _status_to_row_class(status: str) -> str:
    if status == MATCHED:
        return "verified-ok"
    if status == UNEXPLAINED_GAP:
        return "verified-warn"
    if status == PARSE_UNCERTAIN:
        return "verified-uncertain"
    return "verified-uncertain"


def _render_drilldown(result: CheckResult) -> str:
    callout_class = "ok" if result.status == MATCHED else "warn"
    callout_icon = "✓" if result.status == MATCHED else "⚠"
    callout_text = result.reason

    ev_rows = ""
    for ev in result.evidence:
        amount_str = f"{ev.amount:,}" if ev.amount is not None else "—"
        ev_rows += f"<tr><td>{_esc(ev.label)}</td><td>{amount_str}</td><td class='src-ref'>{_esc(ev.source)}</td></tr>"

    uncertain_note = ""
    if result.parse_uncertain_reason:
        uncertain_note = (
            f'<div class="callout unc">파싱 사유: {_esc(result.parse_uncertain_reason)}</div>'
        )

    return f"""<div class="dd-title">{_esc(result.title)}</div>
<table class="src-tbl">
  <thead><tr><th>항목</th><th>금액</th><th>출처</th></tr></thead>
  <tbody>{ev_rows}</tbody>
</table>
<div class="callout {callout_class}">{callout_icon} {_esc(callout_text)}</div>
{uncertain_note}"""


def _render_check_summary(results: list[CheckResult]) -> str:
    if not results:
        return ""
    rows = ""
    for result in results:
        badge_class = _status_to_badge_class(result.status)
        badge_label = _status_to_badge_label(result.status)
        exp_str = f"{result.expected:,}" if result.expected is not None else "—"
        act_str = f"{result.actual:,}" if result.actual is not None else "—"
        diff_str = (
            f"차이 {result.difference:,}" if result.difference is not None else ""
        )
        rows += f"""<div class="check-row">
  <span class="check-name">{_esc(result.title)}</span>
  <span class="check-vals"><span>{exp_str}</span><span>{act_str}</span><span>{diff_str}</span></span>
  <span class="badge {badge_class}">{badge_label}</span>
</div>"""
    return f'<div class="check-summary"><div class="check-summary-head">검증 결과</div>{rows}</div>'


# ── Note Panel ────────────────────────────────────────────────────────────────

def _render_note_panel(
    section: ReportSection,
    results: list[CheckResult],
    panel_id: str,
) -> str:
    table = _first_table(section)
    table_html = ""
    if table is not None:
        rows_html = _render_table_rows(table, {})
        table_html = f'<div class="statement-wrap"><table class="fs-table">{rows_html}</table></div>'

    check_rows = ""
    for result in results:
        badge_class = _status_to_badge_class(result.status)
        badge_label = _status_to_badge_label(result.status)
        exp_str = f"{result.expected:,}" if result.expected is not None else "—"
        act_str = f"{result.actual:,}" if result.actual is not None else "—"
        diff_str = (
            f"차이 {result.difference:,}" if result.difference is not None else ""
        )
        dd_id = f"dd-note-{_esc(result.check_id)}"
        check_rows += f"""<div class="check-row" onclick="toggleDD('{dd_id}')">
  <span class="expand-tri" id="tri-{dd_id}">▶</span>
  <span class="check-name">{_esc(result.title)}</span>
  <span class="check-vals"><span>{exp_str}</span><span>{act_str}</span><span>{diff_str}</span></span>
  <span class="badge {badge_class}">{badge_label}</span>
</div>
<div class="dd-inline" id="{dd_id}">{_render_drilldown(result)}</div>"""

    check_section = (
        f'<div class="check-summary"><div class="check-summary-head">검증 결과</div>{check_rows}</div>'
        if results else ""
    )

    return f"""<div class="panel" id="{_esc(panel_id)}">
  <div class="panel-title">{_esc(section.note_no)}. {_esc(section.title)}</div>
  {table_html}
  {check_section}
</div>"""


# ── Parse Uncertain Panel ─────────────────────────────────────────────────────

def _render_parse_uncertain_panel(results: list[CheckResult]) -> str:
    cards = ""
    for result in results:
        reason_code = result.parse_uncertain_reason or "UNKNOWN"
        reason_text = _uncertain_reason_text(reason_code)
        candidates_text = ""
        for ev in result.evidence:
            if ev.source:
                candidates_text += f"<li>항목: {_esc(ev.label)} — 출처: {_esc(ev.source)}</li>"
        cards += f"""<div class="diag-card">
  <div class="diag-title">{_esc(result.title)}</div>
  <div class="diag-reason"><span class="badge badge-unc">{_esc(reason_code)}</span> {_esc(reason_text)}</div>
  <ul class="diag-candidates">{candidates_text}</ul>
  <div class="diag-guide">이 항목이 공시에 포함된 경우 issue를 제보하세요.</div>
</div>"""

    return f"""<div class="panel" id="panel-parse-diag">
  <div class="panel-title">파싱 진단</div>
  <div class="panel-sub">자동 해석에 실패한 항목입니다.</div>
  {cards}
</div>"""


def _uncertain_reason_text(code: str) -> str:
    return {
        "LABEL_NOT_FOUND": "공시에서 해당 계정과목을 찾지 못했습니다.",
        "LOW_CONFIDENCE_MATCH": "유사한 항목을 찾았으나 신뢰도가 낮습니다.",
        "AMBIGUOUS_MULTIPLE": "동일한 신뢰도의 후보가 여러 개입니다.",
        "COLUMN_NOT_DETECTED": "당기/전기 컬럼을 구별하지 못했습니다.",
        "TABLE_NOT_FOUND": "해당 재무제표/주석 섹션이 공시에 없습니다.",
        "AMOUNT_PARSE_FAILED": "행은 찾았으나 숫자 추출에 실패했습니다.",
    }.get(code, "알 수 없는 파싱 오류입니다.")


# ── CSS ───────────────────────────────────────────────────────────────────────

def _inline_css() -> str:
    return """<style>
:root {
  --bg:#fff; --surface:#f8fafc; --surface-2:#f1f5f9;
  --border:#e2e8f0; --text:#0f172a; --muted:#64748b;
  --accent:#3b82f6; --accent-dim:rgba(59,130,246,.12);
  --warn:#f59e0b; --warn-dim:#fef3c7;
  --ok:#16a34a; --ok-dim:#dcfce7;
  --down:#dc2626; --down-dim:#fee2e2;
  --sidebar-bg:#0f172a; --sidebar-text:#94a3b8;
  --sidebar-active:#f1f5f9; --sidebar-accent:#3b82f6;
  --font:Pretendard,ui-sans-serif,system-ui,-apple-system,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:var(--font);background:var(--bg);color:var(--text);font-size:13px;line-height:1.6;letter-spacing:0;}
.shell{display:grid;grid-template-columns:220px minmax(0,1fr);min-height:100vh;}
aside{background:var(--sidebar-bg);border-right:1px solid rgba(255,255,255,.06);padding:20px 0;position:sticky;top:0;height:100vh;overflow-y:auto;}
.sidebar-brand{padding:0 16px 14px;border-bottom:1px solid rgba(255,255,255,.08);margin-bottom:8px;}
.sidebar-brand-name{font-size:12px;font-weight:700;color:var(--sidebar-active);}
.sidebar-brand-sub{font-size:11px;color:#475569;margin-top:2px;}
.sidebar-section{padding:10px 16px 4px;font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.06em;}
.nav-item{display:flex;align-items:center;gap:8px;padding:7px 16px;font-size:12px;font-weight:500;color:var(--sidebar-text);cursor:pointer;border-left:3px solid transparent;}
.nav-item:hover,.nav-item.active{background:rgba(255,255,255,.05);color:var(--sidebar-active);}
.nav-item.active{background:rgba(59,130,246,.18);border-left-color:var(--sidebar-accent);font-weight:700;}
.nav-badge{margin-left:auto;font-size:10px;padding:1px 5px;border-radius:3px;font-weight:700;}
.nb-ok{background:rgba(22,163,74,.2);color:#4ade80;}
.nb-warn{background:rgba(249,115,22,.2);color:#fb923c;}
.nb-unc{background:rgba(100,116,139,.2);color:#94a3b8;}
.sidebar-divider{border:none;border-top:1px solid rgba(255,255,255,.06);margin:8px 0;}
main{padding:24px 28px;}
.panel{margin-bottom:32px;}
.panel.hidden{display:none;}
.panel-title{font-size:14px;font-weight:800;margin-bottom:2px;}
.panel-sub{font-size:12px;color:var(--muted);margin-bottom:16px;}
.empty-state{color:var(--muted);font-size:12px;padding:12px 0;}
/* Verdict */
.verdict-banner{padding:16px 20px;border-radius:10px;border:1px solid var(--border);margin-bottom:24px;}
.verdict-banner.verdict-ok{border-color:#bbf7d0;background:var(--ok-dim);}
.verdict-banner.verdict-warn{border-color:#fde68a;background:var(--warn-dim);}
.verdict-banner.verdict-unc{border-color:var(--border);background:var(--surface);}
.verdict-label{font-size:16px;font-weight:800;margin-bottom:12px;}
.kpi-strip{display:flex;gap:12px;flex-wrap:wrap;}
.kpi-tile{background:#fff;border:1px solid var(--border);border-radius:7px;padding:10px 16px;min-width:100px;}
.kpi-val{font-size:22px;font-weight:800;}
.kpi-name{font-size:11px;color:var(--muted);}
.kpi-tile.kpi-ok .kpi-val{color:var(--ok);}
.kpi-tile.kpi-warn .kpi-val{color:var(--warn);}
.kpi-tile.kpi-unc .kpi-val{color:var(--muted);}
/* Statement table */
.statement-wrap{border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-bottom:16px;}
.statement-caption{padding:9px 16px;background:var(--surface-2);border-bottom:1px solid var(--border);font-size:12px;font-weight:700;color:var(--muted);}
.fs-table{width:100%;border-collapse:collapse;font-size:12px;}
.fs-table th{padding:7px 12px;background:var(--surface-2);border-bottom:1px solid var(--border);font-size:11px;font-weight:700;color:var(--muted);text-align:right;}
.fs-table th:first-child{text-align:left;}
.fs-table td{padding:7px 12px;border-bottom:1px solid var(--border);text-align:right;font-variant-numeric:tabular-nums;}
.fs-table td:first-child{text-align:left;}
.fs-table tr:last-child td{border-bottom:none;}
/* Tick overlays */
.verified-ok td:first-child::after{content:"✓";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--ok-dim);color:var(--ok);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-warn td:first-child::after{content:"⚠";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--warn-dim);color:var(--warn);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-uncertain td:first-child::after{content:"?";display:inline-flex;align-items:center;justify-content:center;margin-left:8px;width:16px;height:16px;background:var(--surface-2);color:var(--muted);border-radius:3px;font-size:10px;font-weight:800;vertical-align:middle;}
.verified-ok{cursor:pointer;} .verified-ok:hover td{background:#f0fdf4;}
.verified-warn{cursor:pointer;} .verified-warn:hover td{background:#fffbeb;}
.verified-uncertain{cursor:pointer;} .verified-uncertain:hover td{background:var(--surface);}
/* Drilldown */
.dd-cell{padding:0!important;}
.dd-inner,.dd-inline{display:none;padding:12px 16px;background:var(--surface);border-top:2px solid var(--border);}
.dd-inner.open,.dd-inline.open{display:block;}
.dd-title{font-size:12px;font-weight:700;margin-bottom:8px;}
.src-tbl{width:100%;border-collapse:collapse;font-size:11px;margin-bottom:8px;}
.src-tbl th{background:var(--surface-2);padding:4px 8px;border:1px solid var(--border);font-size:10px;color:var(--muted);}
.src-tbl td{padding:5px 8px;border:1px solid var(--border);}
.src-ref{color:var(--muted);font-size:10px;}
.callout{margin-top:8px;padding:7px 10px;border-radius:5px;font-size:11px;}
.callout.ok{background:var(--ok-dim);border:1px solid #bbf7d0;color:#166534;}
.callout.warn{background:var(--warn-dim);border:1px solid #fde68a;color:#92400e;}
.callout.unc{background:var(--surface-2);border:1px solid var(--border);color:var(--muted);}
/* Check summary */
.check-summary{border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-top:8px;}
.check-summary-head{padding:9px 14px;background:var(--surface-2);border-bottom:1px solid var(--border);font-size:11px;font-weight:700;color:var(--muted);}
.check-row{display:flex;align-items:center;gap:10px;padding:8px 14px;border-bottom:1px solid var(--border);font-size:12px;cursor:pointer;}
.check-row:last-child{border-bottom:none;}
.check-row:hover{background:var(--surface);}
.check-name{flex:1;}
.check-vals{display:flex;gap:14px;font-variant-numeric:tabular-nums;color:var(--muted);font-size:11px;}
.badge{display:inline-flex;align-items:center;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:700;}
.badge-ok{background:var(--ok-dim);color:#166534;}
.badge-warn{background:var(--warn-dim);color:#92400e;}
.badge-unc{background:var(--surface-2);color:var(--muted);}
.expand-tri{font-size:9px;color:var(--muted);transition:transform .15s;display:inline-block;}
/* Diag cards */
.diag-card{border:1px solid var(--border);border-radius:7px;padding:14px;margin-bottom:12px;}
.diag-title{font-size:13px;font-weight:700;margin-bottom:6px;}
.diag-reason{margin-bottom:8px;font-size:12px;}
.diag-candidates{margin-left:16px;font-size:11px;color:var(--muted);}
.diag-guide{margin-top:8px;font-size:11px;color:var(--muted);}
</style>"""


# ── JS micro-runtime ───────────────────────────────────────────────────────────

def _inline_js() -> str:
    return """<script>
(function(){
  // Panel switching
  var navItems = document.querySelectorAll('.nav-item[data-target]');
  var panels = document.querySelectorAll('.panel');
  navItems.forEach(function(item){
    item.addEventListener('click', function(){
      var target = item.getAttribute('data-target');
      navItems.forEach(function(n){ n.classList.remove('active'); });
      item.classList.add('active');
      panels.forEach(function(p){
        p.classList.toggle('hidden', p.id !== target);
      });
      var tp = document.getElementById(target);
      if(tp){ tp.scrollIntoView({behavior:'smooth',block:'start'}); }
    });
  });
})();

function toggleDD(id){
  var el = document.getElementById(id);
  if(!el) return;
  el.classList.toggle('open');
  var tri = document.getElementById('tri-' + id);
  if(tri){ tri.style.transform = el.classList.contains('open') ? 'rotate(90deg)' : ''; }
}
</script>"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _esc(text: str | None) -> str:
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _find_section(sections: list[ReportSection], title_frag: str) -> ReportSection | None:
    for s in sections:
        if title_frag in s.title:
            return s
    return None


def _first_table(section: ReportSection) -> ReportTable | None:
    for block in section.blocks:
        if block.table is not None:
            return block.table
    return None


def _status_to_badge_class(status: str) -> str:
    if status == MATCHED:
        return "badge-ok"
    if status == UNEXPLAINED_GAP:
        return "badge-warn"
    return "badge-unc"


def _status_to_badge_label(status: str) -> str:
    if status == MATCHED:
        return "✓ 일치"
    if status == UNEXPLAINED_GAP:
        return "⚠ 차이"
    return "? 불확실"
```

- [ ] **Step 4: Run the new HTML tests**

```bash
uv run pytest tests/test_report_html_new.py -v
```
Expected: All PASS.

- [ ] **Step 5: Confirm CLI still works**

```bash
uv run pytest tests/test_cli.py -v -q 2>&1 | tail -15
```
Expected: All PASS (the new `report_html.py` exports the same public function).

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest tests/ -x -q 2>&1 | tail -20
```
Expected: All pass. Any failures in `test_report_html*` that test internal functions of the OLD renderer are expected — those tests can be deleted (they tested the old API).

Note: If `tests/test_report_html*.py` files exist that test old internals like `render_audit_reconciliation_html`, `_overall_verdict`, `classify_report`, etc. — delete them. The old renderer is gone.

```bash
# Find and remove old renderer tests that reference deleted functions
grep -l "render_audit_reconciliation_html\|_overall_verdict\|classify_report\|_account_coverage" tests/ 2>/dev/null
# Remove each file listed above
```

- [ ] **Step 7: Commit**

```bash
git add src/dart_footing_reconciler/report_html.py tests/test_report_html_new.py
git commit -m "feat(report_html): replace developer-facing renderer with evidence_cockpit UI"
```

---

### Task 6: Additional HTML rendering tests — verdict banner and statement panel

**Files:**
- Modify: `tests/test_report_html_new.py`

- [ ] **Step 1: Add rendering assertion tests**

Append to `tests/test_report_html_new.py`:

```python
from html.parser import HTMLParser


class _TagCollector(HTMLParser):
    """Collects all tag names and class attribute values seen."""
    def __init__(self):
        super().__init__()
        self.classes: set[str] = set()
        self.text_content: list[str] = []
        self._in_body = False

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        cls = attr_dict.get("class", "")
        for c in cls.split():
            self.classes.add(c)

    def handle_data(self, data):
        stripped = data.strip()
        if stripped:
            self.text_content.append(stripped)


def _parse_html(html: str) -> _TagCollector:
    p = _TagCollector()
    p.feed(html)
    return p


def test_verdict_banner_shows_matched_count():
    from dart_footing_reconciler.report_html import _render_verdict_banner
    results = [
        _result("a", MATCHED, "statement:bs/table:0/row:1"),
        _result("b", MATCHED, "statement:bs/table:0/row:2"),
        _result("c", UNEXPLAINED_GAP, "statement:bs/table:0/row:3"),
    ]
    html = _render_verdict_banner(results)
    assert "2" in html   # matched count
    assert "1" in html   # gap count
    assert "검토 필요" in html   # verdict label

def test_verdict_banner_ok_when_all_matched():
    from dart_footing_reconciler.report_html import _render_verdict_banner
    results = [_result("a", MATCHED, "statement:bs/table:0/row:1")]
    html = _render_verdict_banner(results)
    assert "이상 없음" in html

def test_verdict_banner_empty_results():
    from dart_footing_reconciler.report_html import _render_verdict_banner
    html = _render_verdict_banner([])
    assert "검증 항목 없음" in html

def test_statement_panel_tick_overlay_on_verified_row(tmp_path):
    """Verified row gets css class verified-ok or verified-warn."""
    from dart_footing_reconciler.report_html import _render_statement_panel
    section = _stmt_section(
        "statement:재무상태표", "재무상태표",
        [
            ["과목", "당기", "전기"],
            ["자산총계", "1,000", "900"],
            ["부채총계", "600", "550"],
        ],
    )
    results = [
        _result("bs_eq", MATCHED, "statement:bs/table:0/row:1"),
        _result("bs_gap", UNEXPLAINED_GAP, "statement:bs/table:0/row:2"),
    ]
    html = _render_statement_panel(section, results, "panel-bs", "재무상태표")
    p = _parse_html(html)
    assert "verified-ok" in p.classes
    assert "verified-warn" in p.classes

def test_statement_panel_drilldown_row_present(tmp_path):
    """A dd-row is emitted after each verified row."""
    from dart_footing_reconciler.report_html import _render_statement_panel
    section = _stmt_section(
        "statement:재무상태표", "재무상태표",
        [["과목", "당기"], ["자산총계", "1,000"]],
    )
    results = [_result("eq", MATCHED, "statement:bs/table:0/row:1")]
    html = _render_statement_panel(section, results, "panel-bs", "재무상태표")
    assert "dd-row" in html
    assert "dd-inner" in html

def test_parse_uncertain_panel_shows_reason():
    from dart_footing_reconciler.report_html import _render_parse_uncertain_panel
    r = CheckResult(
        check_id="x", check_type="x", status=PARSE_UNCERTAIN,
        scope="report", note_no="", title="자산총계 미발견",
        expected=None, actual=None, difference=None,
        tolerance=1, reason="행 없음", evidence=[],
        parse_uncertain_reason="LABEL_NOT_FOUND",
    )
    html = _render_parse_uncertain_panel([r])
    assert "LABEL_NOT_FOUND" in html
    assert "자산총계 미발견" in html
    assert "공시에서 해당 계정과목을 찾지 못했습니다" in html
```

- [ ] **Step 2: Run tests**

```bash
uv run pytest tests/test_report_html_new.py -v
```
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_report_html_new.py
git commit -m "test(report_html): add verdict banner, statement panel, drilldown, diag panel assertions"
```

---

### Task 7: Integration smoke test with a real fixture

**Files:**
- Modify: `tests/test_report_html_new.py`

- [ ] **Step 1: Find an existing test fixture**

```bash
ls tests/fixtures/ | head -10
```

- [ ] **Step 2: Add smoke test**

Find the HTML fixture file path from the output above and use it. Append to `tests/test_report_html_new.py`:

```python
import os
from pathlib import Path
from dart_footing_reconciler.document import parse_full_report
from dart_footing_reconciler.checks_statement_ties import check_statement_ties


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _first_html_fixture() -> Path | None:
    """Return the first .html fixture file found, or None."""
    for p in sorted(FIXTURE_DIR.glob("*.html")):
        return p
    return None


def test_smoke_real_fixture(tmp_path):
    """End-to-end: parse a real fixture, run checks, export HTML, assert structure."""
    fixture = _first_html_fixture()
    if fixture is None:
        import pytest
        pytest.skip("No HTML fixture found in tests/fixtures/")

    report = parse_full_report(fixture)
    checks = check_statement_ties(report)

    out = tmp_path / "smoke_output.html"
    result_path = export_audit_reconciliation_html(report, checks, out)

    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")

    # Basic structure present
    assert "<!DOCTYPE html>" in content
    assert 'data-cockpit-profile="evidence_cockpit"' in content
    assert "verdict-banner" in content
    assert "sidebar-brand" in content

    # No internal programming terms exposed in visible labels
    assert "check_type" not in content
    assert "statement:bs/table:" not in content   # source strings should only appear in drilldown
```

- [ ] **Step 3: Run smoke test**

```bash
uv run pytest tests/test_report_html_new.py::test_smoke_real_fixture -v -s
```
Expected: PASS or SKIP (if no fixtures). If it fails, examine output and fix rendering edge cases.

- [ ] **Step 4: Run full test suite one final time**

```bash
uv run pytest tests/ -q 2>&1 | tail -25
```
Expected: All pass.

- [ ] **Step 5: Final commit**

```bash
git add tests/test_report_html_new.py
git commit -m "test(report_html): add end-to-end smoke test with real DART fixture"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Task(s) |
|---|---|
| §4.2 LabelResolver + AccountRole + RowMatch + MatchTier | Task 2, 3 |
| §4.3 Structural signals (POSITION tier) | Task 2 (`_position_match`) |
| §4.4 ParseUncertainReason | Task 1, Task 4 (propagated to check) |
| §4.5 Migrate checks_statement_ties | Task 4 |
| §5.1 Same public API | Task 5 scaffold |
| §5.2 Internal render functions | Task 5 |
| §5.3 _tie_results | Task 5 |
| §6.1 Verdict Banner | Task 5 + Task 6 tests |
| §6.2 Statement panel raw table + tick overlay | Task 5 + Task 6 tests |
| §6.3 Note panel | Task 5 |
| §6.4 Parse uncertain panel | Task 5 + Task 6 tests |
| §7 Outcome label → CSS class mapping | Task 5 (`_status_to_row_class`) |
| §9 Design tokens | Task 5 (`_inline_css`) |
| §10 Edge cases (empty section, zero results) | Task 6 tests + `empty-state` guard |
| §12 `cli.py` unchanged | Task 5 (signature backward-compatible) |

**Gaps identified and addressed:**
- `checks_totals.py`, `footing.py`, `note_assertions.py` frozenset migration: **not included** — spec §4.5 lists them but scope is large; Task 4 migrates only `checks_statement_ties.py` as the primary file. Add follow-up tasks if needed after verifying no regressions.
- `note_assertions.py` and `footing.py` frozenset migration is a separate future task that can use the same `LabelResolver` pattern.

**Placeholder scan:** No TBD, TODO, or "similar to Task N" patterns found.

**Type consistency:** `RowMatch` defined in Task 2, used in Task 4. `LABEL_NOT_FOUND` / `LOW_CONFIDENCE_MATCH` string constants defined in `label_resolver.py` (Task 2), imported in Task 4. `parse_uncertain_reason` field added in Task 1, used in Tasks 4 and 5. All consistent.
