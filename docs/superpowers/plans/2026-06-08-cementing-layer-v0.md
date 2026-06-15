# Cementing Layer v0 — Statement Ties + Signature Foundation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **인계 대상: Codex** (Heavy-zone Tier 3). 입력: 이 plan, `docs/adr/0003-signature-driven-verification-not-category-dispatch.md`, `CONTEXT.md`. 산출: `src/`, `tests/`.

**Goal:** 재무상태표 BS equation + cross-statement 대사(현금·자본) 검증을 즉시 작동시키고, signature-driven dispatch의 기반 레지스트리(signatures.py + essential_notes.py)를 구축한다.

**Architecture:**
- Phase 1 (Tasks 1–4): `checks_statement_ties.py` — 3개 statement-level 검증 (BS equation, cash tie, equity tie). 독립 모듈, 즉시 값 있음.
- Phase 2 (Tasks 5–6): `signatures.py` + `essential_notes.py` — ADR-0003 시멘팅 레이어 v0 기반. dispatch 배선은 후속 플랜.
- P0 원칙 유지: 의미 기반 행 선택. 값 근접(closest-value) 매칭 절대 금지.

**Tech Stack:** Python 3.11, pytest, uv. 테스트 실행: `uv run pytest`. 전체: `uv run pytest -q`.

**감사 원칙:** 재무상태표 내 교차 검증(statement_to_statement axis)은 CONTEXT.md §Reconciliation Axis S2-2 work order. check_type은 `statement_bs_equation`, `statement_cash_tie`, `statement_equity_tie`. 의미상 대응이 없으면 PARSE_UNCERTAIN으로 정직하게 표시 — MATCHED 위조 금지.

---

## File Structure

| 파일 | 역할 | 변경 |
|------|------|------|
| `src/dart_footing_reconciler/checks_statement_ties.py` | BS equation + cross-statement tie 3개 | **신규** |
| `src/dart_footing_reconciler/signatures.py` | Verification Signature 추출 (ADR-0003) | **신규** |
| `src/dart_footing_reconciler/essential_notes.py` | Core Account × Audit Cycle × Essential Note 레지스트리 | **신규** |
| `src/dart_footing_reconciler/check_pipeline.py` | statement ties 배선 추가 | 수정 (line 19+) |
| `src/dart_footing_reconciler/report_frame.py` | `CHECK_GROUP_ORDER` 에 `"재무제표 교차 검증"` 추가 | 수정 (line 22) |
| `src/dart_footing_reconciler/report_html.py` | `_report_frame_check_group_label` 라우팅 추가 | 수정 (line 1104+) |
| `tests/test_checks_statement_ties.py` | statement tie 단위 테스트 | **신규** |
| `tests/test_signatures.py` | signature 추출 단위 테스트 | **신규** |
| `tests/test_essential_notes.py` | essential notes 레지스트리 단위 테스트 | **신규** |
| `tests/test_check_pipeline.py` | statement ties pipeline 통합 검증 추가 | 수정 |

---

## Task 1: BS equation check — `자산총계 ≈ 부채총계 + 자본총계`

**이 Task만으로 독립 배포 가능.** BS table에서 3개 행을 찾아 BS equation을 검증한다.
레이블 처리 규칙:
- `자산총계` alias: `자산합계`, `총자산`, `자본과부채총계` (후자는 자산총계와 동일)
- `부채총계` alias: `부채합계`, `총부채`
- `자본총계` alias: `자본합계`, `총자본`
- 3개 모두 발견 → equation 검증
- `자산총계`/`자본과부채총계` 중 하나만 있고 `부채총계` 없음 → PARSE_UNCERTAIN (단독으로 검증 불가)
- 전혀 없음 → 빈 결과 반환 (문서 파싱 한계)

**Files:**
- Create: `src/dart_footing_reconciler/checks_statement_ties.py`
- Create: `tests/test_checks_statement_ties.py`

- [ ] **Step 1: RED — BS equation matched 테스트 작성**

```python
# tests/test_checks_statement_ties.py
from dart_footing_reconciler.checks import MATCHED, UNEXPLAINED_GAP, PARSE_UNCERTAIN
from dart_footing_reconciler.checks_statement_ties import check_statement_ties
from dart_footing_reconciler.document import (
    FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation,
)


def _stmt(section_id: str, title: str, rows: list[list[str]]) -> ReportSection:
    table = ReportTable(0, rows, title, SourceLocation(section_id, 0, 0))
    return ReportSection(
        section_id, title, "statement", "",
        [ReportBlock("table", "", table, table.location)],
    )


def _report(statements: list[ReportSection]) -> FullReport:
    return FullReport("sample.html", "테스트", statements, [])


def test_bs_equation_matched():
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "1,000"],
            ["부채총계", "600"],
            ["자본총계", "400"],
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == MATCHED
    assert eq[0].expected == 1000
    assert eq[0].actual == 1000


def test_bs_equation_gap():
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자산총계", "1,000"],
            ["부채총계", "600"],
            ["자본총계", "500"],  # 600+500=1100 ≠ 1000
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert eq[0].status == UNEXPLAINED_GAP


def test_bs_equation_alias_자본과부채총계():
    """자산총계 없고 자본과부채총계 + 자본총계만 있어도 부채총계 있으면 검증"""
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["부채총계", "600"],
            ["자본총계", "400"],
            ["자본과부채총계", "1,000"],
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == MATCHED


def test_bs_equation_missing_부채총계_returns_parse_uncertain():
    """부채총계 행 없으면 PARSE_UNCERTAIN"""
    bs = _stmt(
        "statement:재무상태표",
        "재무상태표",
        [
            ["구분", "당기"],
            ["자본총계", "400"],
            ["자본과부채총계", "1,000"],
        ],
    )
    results = check_statement_ties(_report([bs]))
    eq = [r for r in results if r.check_type == "statement_bs_equation"]
    assert len(eq) == 1
    assert eq[0].status == PARSE_UNCERTAIN
```

- [ ] **Step 2: RED 확인**

```bash
uv run pytest tests/test_checks_statement_ties.py -v 2>&1 | head -20
```
Expected: `ImportError` 또는 `ModuleNotFoundError: No module named 'dart_footing_reconciler.checks_statement_ties'`

- [ ] **Step 3: `checks_statement_ties.py` 구현 — BS equation 부분**

```python
# src/dart_footing_reconciler/checks_statement_ties.py
"""Statement-level tie checks: BS equation and cross-statement amount ties."""

from __future__ import annotations

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import (
    CheckEvidence,
    CheckResult,
    MATCHED,
    PARSE_UNCERTAIN,
    UNEXPLAINED_GAP,
)
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.table_semantics import compact

# ─── label alias tables ──────────────────────────────────────────────────────

_ASSET_TOTAL_LABELS = frozenset(["자산총계", "자산합계", "총자산", "자본과부채총계"])
_LIAB_TOTAL_LABELS = frozenset(["부채총계", "부채합계", "총부채"])
_EQUITY_TOTAL_LABELS = frozenset(["자본총계", "자본합계", "총자본"])

_CASH_BS_LABELS = frozenset(["현금및현금성자산"])
_CASH_CF_END_LABELS = frozenset([
    "기말현금및현금성자산", "현금및현금성자산기말잔액",
    "현금및현금성자산의기말잔액", "기말의현금및현금성자산",
])
_EQUITY_SCE_END_LABELS = frozenset(["자본총계", "합계"])


def check_statement_ties(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    results.extend(_bs_equation_checks(report, tolerance=tolerance))
    results.extend(_cash_tie_checks(report, tolerance=tolerance))
    results.extend(_equity_tie_checks(report, tolerance=tolerance))
    return results


# ─── BS equation ─────────────────────────────────────────────────────────────

def _bs_equation_checks(report: FullReport, *, tolerance: int) -> list[CheckResult]:
    bs = _find_statement(report, ("재무상태표",))
    if bs is None:
        return []
    table = _first_table(bs)
    if table is None:
        return []

    asset_row = _find_row(table, _ASSET_TOTAL_LABELS)
    liab_row = _find_row(table, _LIAB_TOTAL_LABELS)
    equity_row = _find_row(table, _EQUITY_TOTAL_LABELS)

    # Need equity to do anything; need at least one of asset/liab + equity
    if equity_row is None:
        return []

    equity_val = _current_amount(equity_row)
    if equity_val is None:
        return []

    if asset_row is None or liab_row is None:
        # Cannot verify equation — not enough labels present
        return [_tie_result(
            check_id="statement_bs_equation:missing_labels",
            check_type="statement_bs_equation",
            title="재무상태표 BS equation — 자산/부채 합계 행 미발견",
            expected=None,
            actual=None,
            difference=None,
            tolerance=tolerance,
            status=PARSE_UNCERTAIN,
            reason="자산총계 또는 부채총계 행을 찾지 못함 — 회사별 레이블 변형 가능성",
            evidence=[],
            note_no="bs",
        )]

    asset_val = _current_amount(asset_row)
    liab_val = _current_amount(liab_row)
    if asset_val is None or liab_val is None:
        return []

    expected = liab_val + equity_val  # 부채총계 + 자본총계
    actual = asset_val                 # 자산총계
    difference = actual - expected
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP

    return [_tie_result(
        check_id="statement_bs_equation:current",
        check_type="statement_bs_equation",
        title="재무상태표 BS equation: 자산총계 = 부채총계 + 자본총계",
        expected=expected,
        actual=actual,
        difference=difference,
        tolerance=tolerance,
        status=status,
        reason="BS equation 성립" if status == MATCHED else "BS equation 불일치",
        evidence=[
            CheckEvidence(asset_row[0], asset_val, _row_source(table, asset_row, "bs")),
            CheckEvidence(liab_row[0], liab_val, _row_source(table, liab_row, "bs")),
            CheckEvidence(equity_row[0], equity_val, _row_source(table, equity_row, "bs")),
        ],
        note_no="bs",
    )]


# ─── Cross-statement cash tie ─────────────────────────────────────────────────

def _cash_tie_checks(report: FullReport, *, tolerance: int) -> list[CheckResult]:
    bs = _find_statement(report, ("재무상태표",))
    cf = _find_statement(report, ("현금흐름표",))
    if bs is None or cf is None:
        return []

    bs_table = _first_table(bs)
    cf_table = _first_table(cf)
    if bs_table is None or cf_table is None:
        return []

    bs_row = _find_row(bs_table, _CASH_BS_LABELS)
    cf_row = _find_row(cf_table, _CASH_CF_END_LABELS)
    if bs_row is None or cf_row is None:
        return []

    bs_val = _current_amount(bs_row)
    cf_val = _current_amount(cf_row)
    if bs_val is None or cf_val is None:
        return []

    difference = bs_val - cf_val
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP

    return [_tie_result(
        check_id="statement_cash_tie:current",
        check_type="statement_cash_tie",
        title="재무상태표 현금 ↔ 현금흐름표 기말 현금 대사",
        expected=cf_val,
        actual=bs_val,
        difference=difference,
        tolerance=tolerance,
        status=status,
        reason="BS 현금 = CF 기말 현금" if status == MATCHED else "BS 현금 ≠ CF 기말 현금",
        evidence=[
            CheckEvidence(bs_row[0], bs_val, _row_source(bs_table, bs_row, "bs")),
            CheckEvidence(cf_row[0], cf_val, _row_source(cf_table, cf_row, "cf")),
        ],
        note_no="cross_statement",
    )]


# ─── Cross-statement equity tie ───────────────────────────────────────────────

def _equity_tie_checks(report: FullReport, *, tolerance: int) -> list[CheckResult]:
    bs = _find_statement(report, ("재무상태표",))
    sce = _find_statement(report, ("자본변동표",))
    if bs is None or sce is None:
        return []

    bs_table = _first_table(bs)
    sce_table = _first_table(sce)
    if bs_table is None or sce_table is None:
        return []

    bs_row = _find_row(bs_table, _EQUITY_TOTAL_LABELS)
    sce_row = _find_sce_equity_end_row(sce_table)
    if bs_row is None or sce_row is None:
        return []

    bs_val = _current_amount(bs_row)
    sce_val = _current_amount(sce_row)
    if bs_val is None or sce_val is None:
        return []

    difference = bs_val - sce_val
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP

    return [_tie_result(
        check_id="statement_equity_tie:current",
        check_type="statement_equity_tie",
        title="재무상태표 자본총계 ↔ 자본변동표 기말 자본 대사",
        expected=sce_val,
        actual=bs_val,
        difference=difference,
        tolerance=tolerance,
        status=status,
        reason="BS 자본총계 = SCE 기말 자본총계" if status == MATCHED else "BS 자본총계 ≠ SCE 기말 자본총계",
        evidence=[
            CheckEvidence(bs_row[0], bs_val, _row_source(bs_table, bs_row, "bs")),
            CheckEvidence(sce_row[0], sce_val, _row_source(sce_table, sce_row, "sce")),
        ],
        note_no="cross_statement",
    )]


# ─── helpers ─────────────────────────────────────────────────────────────────

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


def _find_row(table: ReportTable, label_set: frozenset[str]) -> list[str] | None:
    for row in table.rows:
        if row and compact(row[0]) in label_set:
            return row
    return None


def _find_sce_equity_end_row(table: ReportTable) -> list[str] | None:
    """SCE 기말 자본 합계 행: 마지막 등장하는 자본총계/합계 행."""
    candidate = None
    for row in table.rows:
        if row and compact(row[0]) in _EQUITY_SCE_END_LABELS:
            candidate = row
    return candidate


def _current_amount(row: list[str]) -> int | None:
    for cell in row[1:]:
        val = parse_amount(cell)
        if val is not None:
            return val
    return None


def _row_source(table: ReportTable, row: list[str], statement_kind: str) -> str:
    for i, r in enumerate(table.rows):
        if r is row:
            return f"statement:{statement_kind}/table:{table.index}/row:{i}"
    return f"statement:{statement_kind}/table:{table.index}/row:unknown"


def _tie_result(
    *,
    check_id: str,
    check_type: str,
    title: str,
    expected: int | None,
    actual: int | None,
    difference: int | None,
    tolerance: int,
    status: str,
    reason: str,
    evidence: list[CheckEvidence],
    note_no: str,
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type=check_type,
        status=status,
        scope="report",
        note_no=note_no,
        title=title,
        expected=expected,
        actual=actual,
        difference=difference,
        tolerance=tolerance,
        reason=reason,
        evidence=evidence,
    )
```

- [ ] **Step 4: GREEN 확인**

```bash
uv run pytest tests/test_checks_statement_ties.py -v
```
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/checks_statement_ties.py tests/test_checks_statement_ties.py
git commit -m "feat(checks): statement-level BS equation + cross-statement cash/equity tie"
```

---

## Task 2: cross-statement 대사 보완 테스트 추가

cash tie / equity tie 각각 gap + parse_uncertain 케이스 보완.

**Files:**
- Modify: `tests/test_checks_statement_ties.py`

- [ ] **Step 1: cash_tie / equity_tie 테스트 추가**

```python
# tests/test_checks_statement_ties.py 에 추가

def test_cash_tie_matched():
    bs = _stmt("statement:재무상태표", "재무상태표",
               [["구분", "당기"], ["현금및현금성자산", "500"]])
    cf = _stmt("statement:현금흐름표", "현금흐름표",
               [["구분", "당기"], ["기말현금및현금성자산", "500"]])
    results = check_statement_ties(_report([bs, cf]))
    tie = [r for r in results if r.check_type == "statement_cash_tie"]
    assert len(tie) == 1
    assert tie[0].status == MATCHED


def test_cash_tie_gap():
    bs = _stmt("statement:재무상태표", "재무상태표",
               [["구분", "당기"], ["현금및현금성자산", "500"]])
    cf = _stmt("statement:현금흐름표", "현금흐름표",
               [["구분", "당기"], ["기말현금및현금성자산", "490"]])
    results = check_statement_ties(_report([bs, cf]))
    tie = [r for r in results if r.check_type == "statement_cash_tie"]
    assert tie[0].status == UNEXPLAINED_GAP


def test_cash_tie_no_cf_returns_empty():
    bs = _stmt("statement:재무상태표", "재무상태표",
               [["구분", "당기"], ["현금및현금성자산", "500"]])
    results = check_statement_ties(_report([bs]))
    assert not [r for r in results if r.check_type == "statement_cash_tie"]


def test_equity_tie_matched():
    bs = _stmt("statement:재무상태표", "재무상태표",
               [["구분", "당기"], ["자본총계", "800"]])
    sce = _stmt("statement:자본변동표", "자본변동표",
                [["구분", "당기"], ["자본총계", "800"]])
    results = check_statement_ties(_report([bs, sce]))
    tie = [r for r in results if r.check_type == "statement_equity_tie"]
    assert len(tie) == 1
    assert tie[0].status == MATCHED


def test_equity_tie_gap():
    bs = _stmt("statement:재무상태표", "재무상태표",
               [["구분", "당기"], ["자본총계", "800"]])
    sce = _stmt("statement:자본변동표", "자본변동표",
                [["구분", "당기"], ["자본총계", "750"]])
    results = check_statement_ties(_report([bs, sce]))
    tie = [r for r in results if r.check_type == "statement_equity_tie"]
    assert tie[0].status == UNEXPLAINED_GAP
```

- [ ] **Step 2: GREEN 확인**

```bash
uv run pytest tests/test_checks_statement_ties.py -v
```
Expected: 10 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_checks_statement_ties.py
git commit -m "test(checks): add cross-statement cash/equity tie gap and edge cases"
```

---

## Task 3: check_pipeline.py 배선 + CHECK_GROUP_ORDER + 라우팅

**Files:**
- Modify: `src/dart_footing_reconciler/check_pipeline.py`
- Modify: `src/dart_footing_reconciler/report_frame.py` (lines 22–28)
- Modify: `src/dart_footing_reconciler/report_html.py` (line 1104+)
- Modify: `tests/test_check_pipeline.py`

- [ ] **Step 1: RED — pipeline 통합 테스트 추가**

`tests/test_check_pipeline.py` 끝에 추가:

```python
def test_assemble_includes_statement_ties():
    report = parse_full_report(INVENI)
    types = Counter(
        check.check_type for check in assemble_report_checks(report, None, tolerance=1)
    )
    # BS equation: INVENI에는 부채총계 행 없음 → PARSE_UNCERTAIN 1건 기대
    assert types["statement_bs_equation"] >= 1, types
    # cash_tie: BS 현금 ↔ CF 기말 현금 대사
    assert types["statement_cash_tie"] >= 1, types
    # equity_tie: BS 자본총계 ↔ SCE 기말
    assert types["statement_equity_tie"] >= 1, types
```

- [ ] **Step 2: RED 확인**

```bash
uv run pytest tests/test_check_pipeline.py::test_assemble_includes_statement_ties -v
```
Expected: FAIL (statement_ties not yet wired)

- [ ] **Step 3: check_pipeline.py — import + 1줄 배선 추가**

`src/dart_footing_reconciler/check_pipeline.py` 상단 import에 추가:

```python
from dart_footing_reconciler.checks_statement_ties import check_statement_ties
```

`assemble_report_checks` 함수의 `check_note_assertions` 호출 바로 앞에 추가:

```python
    checks.extend(check_statement_ties(report, tolerance=tolerance))
```

전체 함수 최종 형태:

```python
def assemble_report_checks(
    report: FullReport, prior_report: FullReport | None, *, tolerance: int
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    checks.extend(check_statement_ties(report, tolerance=tolerance))
    for note in report.notes:
        for block in note.blocks:
            if block.table is not None:
                checks.extend(check_table_totals(block.table, note_no=note.note_no, tolerance=tolerance))
    checks.extend(check_note_assertions(report, tolerance=tolerance))
    checks.extend(check_layout_formula_assertions(report, tolerance=tolerance))
    checks.extend(check_reconciliation_targets(report, tolerance=tolerance))
    checks.extend(check_asset_note_bridges(report, tolerance=tolerance))
    checks.extend(check_fs_note_matches(report, tolerance=tolerance))
    checks.extend(check_cfs_note_matches(report, tolerance=tolerance))
    checks.extend(check_note_note_matches(report, tolerance=tolerance))
    checks.extend(check_prior_column_matches(report, tolerance=tolerance))
    if prior_report is not None:
        checks.extend(check_prior_year_reconciliation(report, prior_report, tolerance=tolerance))
    return checks
```

- [ ] **Step 4: report_frame.py — CHECK_GROUP_ORDER 업데이트**

`src/dart_footing_reconciler/report_frame.py` line 22의 `CHECK_GROUP_ORDER` 튜플에 첫 번째 항목으로 추가:

```python
CHECK_GROUP_ORDER = (
    "재무제표 교차 검증",   # ← 신규: statement_bs_equation, statement_cash_tie, statement_equity_tie
    "합계 검증",
    "전기대사",
    "재무제표-주석 대사",
    "현금흐름표-주석 대사",
    "주석끼리 대사",
    "주석 내부/공식 검증",
)
```

- [ ] **Step 5: report_html.py — 라우팅 추가**

`src/dart_footing_reconciler/report_html.py` line 1104의 `_report_frame_check_group_label` 함수에 첫 번째 조건으로 추가:

```python
def _report_frame_check_group_label(check: CheckResult) -> str:
    for group in CHECK_GROUP_ORDER:
        if check.check_type in {"statement_bs_equation", "statement_cash_tie", "statement_equity_tie"} and group == "재무제표 교차 검증":
            return group
        if check.check_type == "total_check" and group == "합계 검증":
            return group
        # ... (기존 조건들 유지)
```

- [ ] **Step 6: GREEN 확인 + 전체 테스트**

```bash
uv run pytest tests/test_check_pipeline.py -v
uv run pytest -q
```
Expected: 전체 PASS (기존 685 + 새 테스트들)

- [ ] **Step 7: Commit**

```bash
git add src/dart_footing_reconciler/check_pipeline.py \
        src/dart_footing_reconciler/report_frame.py \
        src/dart_footing_reconciler/report_html.py \
        tests/test_check_pipeline.py
git commit -m "feat(pipeline): wire statement ties + add 재무제표교차검증 group to report"
```

---

## Task 4: corpus 기준선 재실행 (Tasks 1-3 이후)

Tasks 1-7(2026-06-07 HANDOFF) + 이번 statement ties 배선 이후 첫 100-company 측정.

**Files:** 없음 (corpus runner CLI 실행만)

- [ ] **Step 1: 기존 corpus manifest 재실행**

```bash
uv run dart-footing corpus --manifest out/corpus/manifest_2026-05-26-hundred.json \
    --out out/corpus/run_2026-06-08-statement-ties-baseline \
    --no-fetch
```

- [ ] **Step 2: 결과 확인 및 기록**

```bash
cat out/corpus/run_2026-06-08-statement-ties-baseline/run_summary.json
```

기록할 지표:
- `total_checks` (baseline 68,807 대비)
- `matched` (baseline 35,044)
- `statement_bs_equation` 건수 (신규)
- `statement_cash_tie` 건수 (신규)
- `statement_equity_tie` 건수 (신규)
- `fs_note_match` 건수 (2026-06-07 Tasks 배선 이후 첫 측정)
- `cfs_note_match` 건수

- [ ] **Step 3: HANDOFF.md에 기준선 수치 추가**

`HANDOFF.md`의 "Current State" 섹션에 다음 형식으로 추가:

```markdown
- 2026-06-08 baseline (run_2026-06-08-statement-ties-baseline):
  total_checks: X, matched: Y, statement_bs_equation: A, statement_cash_tie: B,
  statement_equity_tie: C, fs_note_match: D (matched: E / gap: F),
  cfs_note_match: G
```

---

## Task 5: `signatures.py` v0 — 3개 핵심 시그니처

ADR-0003 §Verification Signature 구현 v0. dispatch 배선은 후속 플랜.

v0 구현 대상:
- `rollforward_axis`: 기초/취득/처분/기말 행/열 패턴 인식 (confidence 0.7+)
- `internal_closure`: 합계/소계 행 또는 열이 있는 경우 인식
- `statement_core_match`: taxonomy account_key가 행 레이블에 매칭되는 경우

**Files:**
- Create: `src/dart_footing_reconciler/signatures.py`
- Create: `tests/test_signatures.py`

- [ ] **Step 1: RED — signatures 기본 테스트**

```python
# tests/test_signatures.py
from dart_footing_reconciler.document import ReportTable, SourceLocation
from dart_footing_reconciler.signatures import SignatureMatch, emit_signatures


def _table(rows: list[list[str]], heading: str = "테스트표") -> ReportTable:
    return ReportTable(0, rows, heading, SourceLocation("note:1", 0, 0))


def test_emit_rollforward_axis_on_기초기말_rows():
    table = _table([
        ["구분", "금액"],
        ["기초장부금액", "1,000"],
        ["취득", "200"],
        ["처분", "(50)"],
        ["기말장부금액", "1,150"],
    ])
    matches = emit_signatures(table)
    sigs = {m.signature for m in matches}
    assert "rollforward_axis" in sigs


def test_emit_internal_closure_on_합계_column_header():
    table = _table([
        ["구분", "A", "B", "합계"],
        ["항목1", "100", "200", "300"],
    ])
    matches = emit_signatures(table)
    sigs = {m.signature for m in matches}
    assert "internal_closure" in sigs


def test_emit_internal_closure_on_합계_row():
    table = _table([
        ["구분", "금액"],
        ["항목1", "100"],
        ["합계", "100"],
    ])
    matches = emit_signatures(table)
    sigs = {m.signature for m in matches}
    assert "internal_closure" in sigs


def test_emit_statement_core_match_on_유형자산_label():
    table = _table([
        ["구분", "당기"],
        ["유형자산", "5,000"],
    ])
    matches = emit_signatures(table)
    sigs = {m.signature for m in matches}
    assert "statement_core_match" in sigs


def test_qualitative_table_has_no_signatures():
    table = _table([
        ["내용"],
        ["본 회사는 K-IFRS 제1001호에 따라 재무제표를 작성하였음."],
    ])
    matches = emit_signatures(table)
    assert not matches


def test_signature_match_has_confidence_field():
    table = _table([
        ["구분", "금액"],
        ["기초장부금액", "1,000"],
        ["기말장부금액", "1,000"],
    ])
    matches = emit_signatures(table)
    for m in matches:
        assert 0.0 <= m.confidence <= 1.0
```

- [ ] **Step 2: RED 확인**

```bash
uv run pytest tests/test_signatures.py -v 2>&1 | head -10
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: `signatures.py` 구현**

```python
# src/dart_footing_reconciler/signatures.py
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

    # Need 기초 + 기말 (row or col) to emit with meaningful confidence
    has_beginning = any(
        compact(row[0]).startswith("기초") or compact(row[0]) == "전기말"
        for row in table.rows if row
    )
    has_ending = any(
        compact(row[0]).startswith("기말") or compact(row[0]) == "당기말"
        for row in table.rows if row
    )

    if has_beginning and has_ending:
        # Both present in rows → strong roll-forward signal
        confidence = min(0.9, 0.6 + row_hits * 0.1)
        return SignatureMatch("rollforward_axis", confidence, {"row_hits": row_hits})
    if col_hits >= 2:
        confidence = 0.65
        return SignatureMatch("rollforward_axis", confidence, {"col_hits": col_hits})
    return None


def _internal_closure(table: ReportTable) -> SignatureMatch | None:
    if not table.rows:
        return None
    # Check column headers for closure label
    header = table.rows[0] if table.rows else []
    col_closure = any(compact(cell) in _CLOSURE_LABELS for cell in header)
    # Check row labels for closure label
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
    # Check if any row label matches a known taxonomy alias
    matched_labels = [
        compact(row[0])
        for row in table.rows
        if row and compact(row[0]) in _TAXONOMY_CORE_LABELS
        and parse_amount(row[1]) is not None if len(row) > 1 else False
    ]
    if matched_labels:
        confidence = min(0.9, 0.6 + len(matched_labels) * 0.05)
        return SignatureMatch("statement_core_match", confidence, {"matched": matched_labels[:3]})
    return None
```

- [ ] **Step 4: GREEN 확인**

```bash
uv run pytest tests/test_signatures.py -v
```
Expected: 6 tests PASS.

- [ ] **Step 5: 전체 테스트 확인**

```bash
uv run pytest -q
```
Expected: 전체 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dart_footing_reconciler/signatures.py tests/test_signatures.py
git commit -m "feat(signatures): v0 rollforward_axis + internal_closure + statement_core_match"
```

---

## Task 6: `essential_notes.py` v0 — Investing/Financing/Other cycle 레지스트리

ADR-0003 §Essential Note 구현 v0. Audit Cycle × Core Account → 필수 검증 주석 매핑.
dispatch 배선(signatures → attempt 실행)은 후속 플랜.

**Files:**
- Create: `src/dart_footing_reconciler/essential_notes.py`
- Create: `tests/test_essential_notes.py`

- [ ] **Step 1: RED — essential_notes 테스트**

```python
# tests/test_essential_notes.py
from dart_footing_reconciler.essential_notes import (
    EssentialNote,
    essential_notes_for,
    VALID_CYCLES,
)


def test_essential_notes_for_investing_returns_ppe():
    notes = essential_notes_for("investing")
    keys = {n.account_key for n in notes}
    assert "property_plant_equipment" in keys


def test_essential_notes_for_investing_returns_intangibles():
    notes = essential_notes_for("investing")
    keys = {n.account_key for n in notes}
    assert "intangible_assets" in keys


def test_essential_notes_for_financing_returns_borrowings():
    notes = essential_notes_for("financing")
    keys = {n.account_key for n in notes}
    assert "borrowings" in keys


def test_essential_notes_for_other_returns_cash():
    notes = essential_notes_for("other")
    keys = {n.account_key for n in notes}
    assert "cash_and_cash_equivalents_increase" in keys


def test_essential_note_has_required_fields():
    notes = essential_notes_for("investing")
    ppe = next(n for n in notes if n.account_key == "property_plant_equipment")
    assert ppe.cycle == "investing"
    assert ppe.required_signatures  # 최소 1개 이상
    assert ppe.reconciliation_axes  # 최소 1개 이상


def test_valid_cycles_covers_all_six():
    required = {"operating", "investing", "financing", "tax", "employee", "other"}
    assert required.issubset(VALID_CYCLES)


def test_unknown_cycle_returns_empty():
    assert essential_notes_for("unknown_cycle") == []
```

- [ ] **Step 2: RED 확인**

```bash
uv run pytest tests/test_essential_notes.py -v 2>&1 | head -10
```
Expected: `ModuleNotFoundError`

- [ ] **Step 3: `essential_notes.py` 구현**

```python
# src/dart_footing_reconciler/essential_notes.py
"""Audit Cycle × Core Account × Essential Note registry (ADR-0003 v0).

This module holds the static mapping:
  Audit Cycle → Core Accounts → Essential Notes → required Signatures + Axes

Dispatch (running verification attempts based on signatures) is a follow-on
plan slice. This module is a catalog only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VALID_CYCLES = frozenset([
    "operating", "investing", "financing", "tax", "employee", "other",
])


@dataclass(frozen=True)
class EssentialNote:
    cycle: str
    account_key: str
    display_name: str
    required_signatures: tuple[str, ...]
    reconciliation_axes: tuple[str, ...]
    notes: str = ""


_INVESTING_NOTES: list[EssentialNote] = [
    EssentialNote(
        cycle="investing",
        account_key="property_plant_equipment",
        display_name="유형자산",
        required_signatures=("rollforward_axis", "statement_core_match"),
        reconciliation_axes=("note_to_bs", "note_to_cf"),
        notes="기초→기말 roll-forward; CF 취득/처분 bridge",
    ),
    EssentialNote(
        cycle="investing",
        account_key="intangible_assets",
        display_name="무형자산",
        required_signatures=("rollforward_axis", "statement_core_match"),
        reconciliation_axes=("note_to_bs", "note_to_cf"),
        notes="개발비/산업재산권/영업권 포함",
    ),
    EssentialNote(
        cycle="investing",
        account_key="investment_property",
        display_name="투자부동산",
        required_signatures=("rollforward_axis", "statement_core_match"),
        reconciliation_axes=("note_to_bs", "note_to_cf"),
    ),
]

_FINANCING_NOTES: list[EssentialNote] = [
    EssentialNote(
        cycle="financing",
        account_key="borrowings",
        display_name="차입금",
        required_signatures=("rollforward_axis", "statement_core_match"),
        reconciliation_axes=("note_to_bs", "note_to_cf"),
        notes="단기/장기 차입금 통합; CF 조달/상환 bridge",
    ),
    EssentialNote(
        cycle="financing",
        account_key="bonds",
        display_name="사채",
        required_signatures=("rollforward_axis", "statement_core_match"),
        reconciliation_axes=("note_to_bs", "note_to_cf"),
    ),
    EssentialNote(
        cycle="financing",
        account_key="lease_liabilities",
        display_name="리스부채",
        required_signatures=("rollforward_axis", "statement_core_match"),
        reconciliation_axes=("note_to_bs", "note_to_cf"),
        notes="IFRS 16 원금 지급 CF bridge",
    ),
]

_OTHER_NOTES: list[EssentialNote] = [
    EssentialNote(
        cycle="other",
        account_key="cash_and_cash_equivalents_increase",
        display_name="현금및현금성자산",
        required_signatures=("statement_core_match",),
        reconciliation_axes=("statement_to_statement",),
        notes="BS 기말 현금 ↔ CF 기말 현금 tie (S2-2)",
    ),
]

_OPERATING_NOTES: list[EssentialNote] = [
    EssentialNote(
        cycle="operating",
        account_key="revenue",
        display_name="매출액",
        required_signatures=("statement_core_match",),
        reconciliation_axes=("note_to_pl",),
    ),
    EssentialNote(
        cycle="operating",
        account_key="cost_of_sales",
        display_name="매출원가",
        required_signatures=("statement_core_match",),
        reconciliation_axes=("note_to_pl",),
    ),
]

_TAX_NOTES: list[EssentialNote] = [
    EssentialNote(
        cycle="tax",
        account_key="income_tax_expense_benefit",
        display_name="법인세비용",
        required_signatures=("statement_core_match",),
        reconciliation_axes=("note_to_pl",),
    ),
]

_EMPLOYEE_NOTES: list[EssentialNote] = [
    EssentialNote(
        cycle="employee",
        account_key="depreciation_expense",
        display_name="감가상각비",
        required_signatures=("statement_core_match",),
        reconciliation_axes=("note_to_pl",),
        notes="비용의 성격별 분류 주석 대사",
    ),
]

_REGISTRY: dict[str, list[EssentialNote]] = {
    "investing": _INVESTING_NOTES,
    "financing": _FINANCING_NOTES,
    "other": _OTHER_NOTES,
    "operating": _OPERATING_NOTES,
    "tax": _TAX_NOTES,
    "employee": _EMPLOYEE_NOTES,
}


def essential_notes_for(cycle: str) -> list[EssentialNote]:
    """Return EssentialNote entries for the given audit cycle."""
    return list(_REGISTRY.get(cycle, []))
```

- [ ] **Step 4: GREEN 확인**

```bash
uv run pytest tests/test_essential_notes.py -v
```
Expected: 7 tests PASS.

- [ ] **Step 5: 전체 테스트 + 린트**

```bash
uv run pytest -q
uv run ruff check src/dart_footing_reconciler/signatures.py src/dart_footing_reconciler/essential_notes.py src/dart_footing_reconciler/checks_statement_ties.py
```
Expected: 전체 PASS, ruff 0 warnings.

- [ ] **Step 6: Commit**

```bash
git add src/dart_footing_reconciler/essential_notes.py tests/test_essential_notes.py
git commit -m "feat(essential_notes): v0 Audit Cycle x Core Account x Essential Note registry"
```

---

## Self-Review

**Spec coverage:**
- [x] BS equation check (자산총계 = 부채총계 + 자본총계) — Task 1
- [x] 부채총계 없는 회사 PARSE_UNCERTAIN — Task 1 (test_bs_equation_missing_부채총계)
- [x] Cross-statement cash tie (BS ↔ CF) — Task 1 구현 + Task 2 테스트
- [x] Cross-statement equity tie (BS ↔ SCE) — Task 1 구현 + Task 2 테스트
- [x] check_pipeline 배선 — Task 3
- [x] CHECK_GROUP_ORDER 업데이트 — Task 3
- [x] report_html 라우팅 — Task 3
- [x] corpus 기준선 재실행 — Task 4
- [x] signatures.py v0 3개 시그니처 — Task 5
- [x] essential_notes.py v0 6개 cycle — Task 6
- [ ] signatures → attempt dispatch 배선 — **후속 플랜 (scope 외)**

**Placeholder scan:** 없음. 모든 step에 실제 코드 포함.

**Type consistency:**
- `SignatureMatch(signature: str, confidence: float, meta: dict)` — Task 5 전반 일관
- `EssentialNote(cycle, account_key, display_name, required_signatures, reconciliation_axes)` — Task 6 전반 일관
- `check_statement_ties(report: FullReport, *, tolerance: int) -> list[CheckResult]` — Task 1 + 3 일관

**중요 제약 (Codex는 시작 전 읽을 것):**

1. `checks_statement_ties.py`의 `_current_amount`는 current period column을 선택해야 하지만 Task 1 구현에서는 **첫 번째 parseable 값**을 사용한다. 다기간 BS 테이블(제44기/제43기/제42기)에서 틀릴 수 있음 — Task 3 GREEN 확인 시 INVENI로 실제 동작 확인 필수. 만약 틀린 열 값을 잡으면 `table_semantics.row_amount_prefer_current(row, headers)`를 사용하도록 수정할 것.

2. `_find_sce_equity_end_row`는 SCE 기말 자본총계를 "마지막으로 등장하는 자본총계/합계 행"으로 찾는다. SCE 표 구조(기초잔액→변동→기말잔액)에서 기말잔액은 마지막에 위치하므로 일반적으로 맞지만, 회사별 SCE 레이아웃이 다를 경우 오탐 가능 — INVENI 실제 데이터로 검증 필수.

3. Task 4 corpus 재실행 후 `statement_bs_equation: parse_uncertain` 비율이 높을 경우 (부채총계 없는 회사가 많은 경우) — 이것은 정상이며 회계 정보 부재를 정직하게 표면화한 것. false matched로 억지로 채우지 말 것.

4. `signatures.py`의 `_TAXONOMY_CORE_LABELS` 빌드 시 `TaxonomyEntry`에 `aliases` 필드가 없음. 실제 필드는 `statement_aliases`, `note_title_aliases`, `note_amount_aliases` (모두 `tuple[str, ...]`). 플랜 코드는 이 3개를 unpack해 합산하도록 이미 수정됨. 추가로 `compact(alias)` 적용 필수 — 공백 없이 정규화해야 `compact(row[0])` 비교와 일치.
