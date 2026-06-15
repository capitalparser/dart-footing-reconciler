# Note Assertions And Cash Flow Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the report from table-total checks plus statement-note matching into a note-level audit assertion engine that validates note roll-forwards, note-to-note consistency, and cash-flow investing/financing formulas with visible included/excluded evidence.

**Architecture:** Add a typed note assertion layer and a reusable evidence-candidate layer above the existing parser and below `CheckResult`. Keep existing `check_table_totals()` as a supporting arithmetic check, integrate `foot_table()` movement arithmetic into workpaper checks, and extend the cash-flow reconciliation engine so every matched or unresolved investing/financing line can show a reproducible formula, source rows, and rejected candidate reasons.

**Tech Stack:** Python 3.11+, dataclasses, existing `FullReport` / `ReportTable` parser model, existing `CheckResult` evidence model, `pytest`, current HTML report renderer.

---

## Verdict

Conditional.

The current system already handles primary financial-statement-to-note and many cash-flow targets, but the "주석별 검증" surface is not audit-grade yet. Current note-level logic is mainly:

- row/column total checks where `합계`, `소계`, `계`, `총계` labels are present
- four hard-coded note-to-note rules
- selected note balance/movement extraction used by statement or cash-flow reconciliation

It does not yet systematically validate note-specific assertions such as:

- beginning + movement rows = ending for each account family in note roll-forward tables
- note movement rows reconcile to related note balances
- cash and non-cash movement rows are separately classified
- investing/financing cash-flow lines match the best available note evidence with excluded-candidate explanations
- zero/blank cells are interpreted consistently for arithmetic, not only display

## Required Outcome

After this plan, a reviewer opening the HTML report should be able to answer:

1. **해당 주석 자체가 맞는가?**  
   Example: 유형자산 주석의 `기초 + 취득 - 처분 - 감가상각 ± 대체 ± 환산 = 기말`이 열별/합계별로 맞는지.

2. **그 주석의 주요 금액이 다른 주석과 맞는가?**  
   Example: 유형자산 감가상각비가 비용의 성격별 분류 또는 현금흐름표 조정과 맞는지.

3. **현금흐름표 투자/재무활동 금액이 주석에서 재현 가능한가?**  
   Example: CFS `유형자산의 처분`이 주석의 처분 장부금액 + 처분손익 조합 또는 처분대금 표로 재현되는지.

4. **왜 후보가 제외되었는가?**  
   Example: `전기표`, `공정가치표`, `약정표`, `정책표`, `scope 불일치`, `non-cash movement`, `prior-period only`.

## Current Gap Classification

### Required Gaps

| Gap | Current State | Required State |
|---|---|---|
| 주석별 roll-forward 검증 | `foot_table()` exists but is not part of `workpaper-html` checks | movement tables in notes emit `note_rollforward_check` results |
| 주석별 assertion registry | Missing | account-family note assertions registered and tested |
| 빈칸/0 arithmetic policy | display layer normalizes some 0s to `-`; arithmetic still skips blanks in many places | note arithmetic treats blank amount cells as zero only in amount grids, with explicit parse policy |
| 투자활동 CFS formula matching | selected cases covered through `NoteMovementInput`; candidate visibility limited | all investing targets use candidate pool + formula search + excluded reasons |
| 재무활동 CFS formula matching | financing net improved, but candidate diagnostics still thin | financing candidates include role, sign, source table class, period, and exclusion reason |
| HTML reviewer surface | formulas shown for selected checks; note-level checks are mostly totals | separate sections for `주석별 검증`, `후보 증거`, `제외 후보`, `현금흐름 대사 공식` |

### Recommended Gaps

| Gap | Recommended Improvement |
|---|---|
| false-positive control | add "conservative unresolved > false matched" guard tests for every new formula family |
| corpus metrics | report note assertion pass rates separately from primary reconciliation no-difference rate |
| reviewer labels | replace engine names with Korean labels: `주석 증감표 검산`, `주석 간 대사`, `현금흐름 후보 제외` |

## File Structure

- Create `src/dart_footing_reconciler/note_assertions.py`
  - Owns note-level assertion extraction and execution.
  - Emits `CheckResult` with `check_type` values such as `note_rollforward_check`, `note_balance_bridge_check`, and `note_internal_consistency_check`.

- Create `src/dart_footing_reconciler/evidence_candidates.py`
  - Owns typed candidate records used by cash-flow matching and note assertion diagnostics.
  - Records included and excluded candidates with source, role, amount, score, and exclusion reason.

- Modify `src/dart_footing_reconciler/reconciliation_inputs.py`
  - Attach table-class and candidate-role metadata to `NoteMovementInput` where needed.
  - Keep the public dataclass compatible by adding optional fields with defaults.

- Modify `src/dart_footing_reconciler/checks_reconciliation.py`
  - Use the candidate pool for investing and financing matching.
  - Preserve existing passing behavior while adding excluded evidence details for unresolved cases.

- Modify `src/dart_footing_reconciler/cli.py`
  - Add note assertion checks to `_run_workpaper_checks()` after total checks and before primary reconciliation.

- Modify `src/dart_footing_reconciler/report_html.py`
  - Render note assertion checks in a separate `주석별 검증` section.
  - Show candidate inclusion/exclusion details in hover panels and review queues.

- Modify `src/dart_footing_reconciler/audit_workbook.py`
  - Label new check types in Korean and include candidate diagnostics.

- Add tests:
  - `tests/test_note_assertions.py`
  - `tests/test_evidence_candidates.py`
  - extend `tests/test_reconciliation_inputs.py`
  - extend `tests/test_checks_reconciliation.py`
  - extend `tests/test_cli_workpaper.py`

## Data Contracts

### NoteAssertionResult Contract

Use existing `CheckResult`; do not create a parallel result model. Required conventions:

```text
check_type:
  note_rollforward_check
  note_balance_bridge_check
  note_internal_consistency_check

scope:
  note

title:
  Korean-first reviewer label, e.g. "유형자산 증감표 검산"

reason:
  short Korean reviewer-facing judgment

evidence:
  every material source amount used in the formula
```

### CandidateEvidence Contract

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateEvidence:
    account_key: str
    role: str
    label: str
    amount: int
    source: str
    note_no: str
    table_class: str
    period_role: str = "current"
    unit_multiplier: int = 1
    score: int = 0
    included: bool = False
    exclusion_reason: str = ""
```

Allowed `role` values:

```text
beginning_balance
ending_balance
acquisition
disposal
disposal_proceeds
disposal_gain_loss
disposal_loss
depreciation
amortization
transfer
foreign_exchange
noncash_acquisition
right_of_use_noncash_acquisition
government_grant_disposal
financing_cashflow
proceeds
repayment
transaction_cost
interest
```

Allowed `table_class` values for this phase:

```text
asset_rollforward
intangible_rollforward
investment_property_rollforward
financing_liability_rollforward
financing_cashflow_reconciliation
expense_by_nature
income_expense_detail
tax_detail
fair_value_detail
commitment_detail
policy_only
unsupported
```

Allowed `exclusion_reason` examples:

```text
scope_mismatch
prior_period_only
policy_only
fair_value_table
commitment_table
not_cash_movement
duplicate_candidate
amount_direction_mismatch
formula_term_limit
weak_label_match
```

---

### Task 1: Note Assertion Test Harness

**Files:**
- Create: `tests/test_note_assertions.py`
- Create: `src/dart_footing_reconciler/note_assertions.py`

- [ ] **Step 1: Write the failing test**

```python
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.note_assertions import check_note_assertions


def _note(note_no: str, title: str, table: ReportTable) -> ReportSection:
    return ReportSection(
        f"note:{note_no}",
        title,
        "note",
        note_no,
        [ReportBlock("table", "", table, table.location)],
    )


def test_check_note_assertions_foots_asset_rollforward_table():
    table = ReportTable(
        0,
        [
            ["구분", "토지", "건물", "합계"],
            ["기초장부금액", "100", "200", "300"],
            ["취득", "10", "20", "30"],
            ["처분", "", "(5)", "(5)"],
            ["감가상각비", "", "(15)", "(15)"],
            ["기말장부금액", "110", "200", "310"],
        ],
        "유형자산의 변동내역 당기",
        SourceLocation("note:11", 0, 0),
    )
    report = FullReport("sample.html", "Sample Co", [], [_note("11", "유형자산", table)])

    results = check_note_assertions(report, tolerance=0)

    assert [(result.check_type, result.status, result.title) for result in results] == [
        ("note_rollforward_check", "matched", "유형자산 증감표 검산")
    ]
    assert results[0].expected == 310
    assert results[0].actual == 310
    assert any(evidence.label == "기초장부금액 합계" for evidence in results[0].evidence)
    assert any(evidence.label == "기말장부금액 합계" for evidence in results[0].evidence)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_note_assertions.py::test_check_note_assertions_foots_asset_rollforward_table -v
```

Expected: FAIL with `ModuleNotFoundError` or missing `check_note_assertions`.

- [ ] **Step 3: Create minimal note assertion module**

Create `src/dart_footing_reconciler/note_assertions.py`:

```python
from __future__ import annotations

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import FullReport, ReportSection, ReportTable
from dart_footing_reconciler.scope import primary_note_sections


_BEGINNING_LABELS = ("기초", "기초장부금액", "기초금액", "전기말")
_ENDING_LABELS = ("기말", "기말장부금액", "기말금액", "당기말")
_ASSET_NOTE_TOKENS = ("유형자산", "무형자산", "투자부동산")


def check_note_assertions(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    results: list[CheckResult] = []
    scoped_notes = primary_note_sections(report.notes)
    for section in scoped_notes:
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            result = _asset_rollforward_result(section, table, tolerance)
            if result is not None:
                results.append(result)
    return results


def _asset_rollforward_result(
    section: ReportSection, table: ReportTable, tolerance: int
) -> CheckResult | None:
    if not _is_asset_rollforward(section.title, table.heading):
        return None
    beginning_idx = _find_row(table, _BEGINNING_LABELS)
    ending_idx = _find_row(table, _ENDING_LABELS)
    if beginning_idx is None or ending_idx is None:
        return None
    total_col = _find_total_column(table)
    if total_col is None:
        return None
    beginning = _amount_at(table, beginning_idx, total_col, blank_as_zero=True)
    ending = _amount_at(table, ending_idx, total_col, blank_as_zero=True)
    if beginning is None or ending is None:
        return None
    expected = beginning
    for row_idx in range(min(beginning_idx, ending_idx) + 1, max(beginning_idx, ending_idx)):
        movement = _amount_at(table, row_idx, total_col, blank_as_zero=True)
        if movement is None:
            continue
        expected += movement
    difference = ending - expected
    status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
    account_label = _account_label(section.title, table.heading)
    return CheckResult(
        check_id=f"note_assertion:{section.note_no}:table{table.index}:rollforward",
        check_type="note_rollforward_check",
        status=status,
        scope="note",
        note_no=section.note_no,
        title=f"{account_label} 증감표 검산",
        expected=expected,
        actual=ending,
        difference=difference,
        tolerance=tolerance,
        reason="기초와 변동내역이 기말 장부금액과 일치"
        if status == MATCHED
        else "기초와 변동내역이 기말 장부금액과 불일치",
        evidence=[
            CheckEvidence(
                f"{table.rows[beginning_idx][0]} 합계",
                beginning,
                f"note:{section.note_no}/table:{table.index}/row:{beginning_idx}/col:{total_col}",
            ),
            CheckEvidence(
                f"{table.rows[ending_idx][0]} 합계",
                ending,
                f"note:{section.note_no}/table:{table.index}/row:{ending_idx}/col:{total_col}",
            ),
        ],
    )


def _is_asset_rollforward(section_title: str, heading: str) -> bool:
    text = _compact(f"{section_title} {heading}")
    return any(token in text for token in _ASSET_NOTE_TOKENS) and any(
        token in text for token in ("변동내역", "증감", "장부금액")
    )


def _find_row(table: ReportTable, labels: tuple[str, ...]) -> int | None:
    for idx, row in enumerate(table.rows):
        if row and any(_compact(row[0]).startswith(_compact(label)) for label in labels):
            return idx
    return None


def _find_total_column(table: ReportTable) -> int | None:
    headers = table.rows[0]
    for idx in range(len(headers) - 1, 0, -1):
        if _compact(headers[idx]) in {"합계", "계", "총계", "장부금액"}:
            return idx
    return len(headers) - 1 if len(headers) > 1 else None


def _amount_at(table: ReportTable, row_idx: int, col_idx: int, *, blank_as_zero: bool) -> int | None:
    if row_idx >= len(table.rows) or col_idx >= len(table.rows[row_idx]):
        return 0 if blank_as_zero else None
    cell = table.rows[row_idx][col_idx]
    if not cell.strip() and blank_as_zero:
        return 0
    amount = parse_amount(cell)
    return amount * table.unit_multiplier if amount is not None else None


def _account_label(section_title: str, heading: str) -> str:
    text = f"{section_title} {heading}"
    for token in _ASSET_NOTE_TOKENS:
        if token in text:
            return token
    return "주석"


def _compact(value: str) -> str:
    return value.replace(" ", "").replace("\n", "")
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_note_assertions.py::test_check_note_assertions_foots_asset_rollforward_table -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/note_assertions.py tests/test_note_assertions.py
git commit -m "feat: add note rollforward assertion checks"
```

---

### Task 2: Integrate Existing Footing Semantics Into Note Assertions

**Files:**
- Modify: `src/dart_footing_reconciler/note_assertions.py`
- Test: `tests/test_note_assertions.py`

- [ ] **Step 1: Write failing tests for sign-sensitive roll-forward**

Append to `tests/test_note_assertions.py`:

```python
def test_check_note_assertions_treats_positive_depreciation_as_decrease():
    table = ReportTable(
        0,
        [
            ["구분", "건물", "합계"],
            ["기초장부금액", "200", "200"],
            ["취득", "20", "20"],
            ["감가상각비", "15", "15"],
            ["기말장부금액", "205", "205"],
        ],
        "유형자산의 변동내역 당기",
        SourceLocation("note:11", 0, 0),
    )
    report = FullReport("sample.html", "Sample Co", [], [_note("11", "유형자산", table)])

    result = check_note_assertions(report, tolerance=0)[0]

    assert result.status == "matched"
    assert result.expected == 205
    assert result.actual == 205
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_note_assertions.py::test_check_note_assertions_treats_positive_depreciation_as_decrease -v
```

Expected: FAIL because current minimal implementation adds positive depreciation.

- [ ] **Step 3: Reuse movement polarity logic**

Modify `src/dart_footing_reconciler/note_assertions.py`:

```python
_DECREASE_LABELS = (
    "감가상각",
    "상각",
    "처분",
    "손상",
    "감소",
    "상환",
    "제각",
)


def _movement_amount(label: str, amount: int) -> int:
    normalized = _compact(label)
    if amount > 0 and any(token in normalized for token in _DECREASE_LABELS):
        return -amount
    return amount
```

Change the movement loop:

```python
    for row_idx in range(min(beginning_idx, ending_idx) + 1, max(beginning_idx, ending_idx)):
        movement = _amount_at(table, row_idx, total_col, blank_as_zero=True)
        if movement is None:
            continue
        expected += _movement_amount(table.rows[row_idx][0], movement)
```

- [ ] **Step 4: Run note assertion tests**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_note_assertions.py -q
```

Expected: all note assertion tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/note_assertions.py tests/test_note_assertions.py
git commit -m "feat: apply movement polarity to note rollforward checks"
```

---

### Task 3: Add Evidence Candidate Model

**Files:**
- Create: `src/dart_footing_reconciler/evidence_candidates.py`
- Create: `tests/test_evidence_candidates.py`

- [ ] **Step 1: Write failing tests**

```python
from dart_footing_reconciler.evidence_candidates import CandidateEvidence, select_best_subset


def test_select_best_subset_returns_exact_cashflow_formula_candidates():
    candidates = [
        CandidateEvidence("borrowings", "proceeds", "차입", 100, "note:1/table:0/row:1/col:1", "1", "financing_liability_rollforward", score=5),
        CandidateEvidence("borrowings", "repayment", "상환", -40, "note:1/table:0/row:2/col:1", "1", "financing_liability_rollforward", score=5),
        CandidateEvidence("borrowings", "foreign_exchange", "환산", 3, "note:1/table:0/row:3/col:1", "1", "financing_liability_rollforward", score=1),
    ]

    selected, rejected = select_best_subset(candidates, target_amount=60, tolerance=0, max_terms=3)

    assert [candidate.label for candidate in selected] == ["차입", "상환"]
    assert rejected[0].exclusion_reason == "not_needed_for_best_formula"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_evidence_candidates.py::test_select_best_subset_returns_exact_cashflow_formula_candidates -v
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement model and subset selection**

Create `src/dart_footing_reconciler/evidence_candidates.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import combinations


@dataclass(frozen=True)
class CandidateEvidence:
    account_key: str
    role: str
    label: str
    amount: int
    source: str
    note_no: str
    table_class: str
    period_role: str = "current"
    unit_multiplier: int = 1
    score: int = 0
    included: bool = False
    exclusion_reason: str = ""


def select_best_subset(
    candidates: list[CandidateEvidence],
    *,
    target_amount: int,
    tolerance: int,
    max_terms: int,
) -> tuple[list[CandidateEvidence], list[CandidateEvidence]]:
    compatible = [candidate for candidate in candidates if candidate.period_role == "current"]
    best_subset: tuple[CandidateEvidence, ...] | None = None
    best_key: tuple[int, int, int] | None = None
    for size in range(1, min(max_terms, len(compatible)) + 1):
        for subset in combinations(compatible, size):
            total = sum(candidate.amount for candidate in subset)
            difference = abs(total - target_amount)
            key = (difference, size, -sum(candidate.score for candidate in subset))
            if best_key is None or key < best_key:
                best_key = key
                best_subset = subset
    if best_subset is None or best_key is None or best_key[0] > tolerance:
        return [], [
            replace(candidate, included=False, exclusion_reason=candidate.exclusion_reason or "no_formula_match")
            for candidate in candidates
        ]
    selected_ids = {candidate.source for candidate in best_subset}
    selected = [replace(candidate, included=True, exclusion_reason="") for candidate in best_subset]
    rejected = [
        replace(candidate, included=False, exclusion_reason=candidate.exclusion_reason or "not_needed_for_best_formula")
        for candidate in candidates
        if candidate.source not in selected_ids
    ]
    return selected, rejected
```

- [ ] **Step 4: Run tests**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_evidence_candidates.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/evidence_candidates.py tests/test_evidence_candidates.py
git commit -m "feat: add reconciliation evidence candidate model"
```

---

### Task 4: Enrich NoteMovementInput With Candidate Metadata

**Files:**
- Modify: `src/dart_footing_reconciler/reconciliation_inputs.py`
- Test: `tests/test_reconciliation_inputs.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_reconciliation_inputs.py`:

```python
def test_extract_reconciliation_inputs_marks_financing_cashflow_table_class():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            ReportSection(
                "note:20",
                "차입금",
                "note",
                "20",
                [
                    ReportBlock(
                        "table",
                        "",
                        ReportTable(
                            0,
                            [
                                ["구분", "당기"],
                                ["차입", "100"],
                                ["상환", "(40)"],
                            ],
                            "재무활동에서 생기는 부채의 변동",
                            SourceLocation("note:20", 0, 0),
                        ),
                        SourceLocation("note:20", 0, 0),
                    )
                ],
            )
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    movements = [movement for movement in inputs.note_movements if movement.movement_role == "financing_cashflow"]
    assert movements
    assert {movement.table_class for movement in movements} == {"financing_cashflow_reconciliation"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_marks_financing_cashflow_table_class -v
```

Expected: FAIL with `AttributeError: 'NoteMovementInput' object has no attribute 'table_class'`.

- [ ] **Step 3: Add optional metadata fields**

Modify `NoteMovementInput` in `src/dart_footing_reconciler/reconciliation_inputs.py`:

```python
@dataclass(frozen=True)
class NoteMovementInput:
    account_key: str
    movement_role: str
    note_no: str
    label: str
    amount: int
    source: str
    unit_multiplier: int = 1
    table_class: str = "unsupported"
    period_role: str = "current"
    exclusion_reason: str = ""
```

Update every constructor call for financing cash-flow extraction to pass:

```python
table_class="financing_cashflow_reconciliation"
```

Update asset roll-forward movement constructor calls to pass one of:

```python
table_class="asset_rollforward"
table_class="intangible_rollforward"
table_class="investment_property_rollforward"
```

If a constructor is intentionally generic, leave defaults.

- [ ] **Step 4: Run focused tests**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_reconciliation_inputs.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/reconciliation_inputs.py tests/test_reconciliation_inputs.py
git commit -m "feat: preserve table class metadata on note movements"
```

---

### Task 5: Candidate Pool For Investing Cash Flows

**Files:**
- Modify: `src/dart_footing_reconciler/checks_reconciliation.py`
- Test: `tests/test_checks_reconciliation.py`

- [ ] **Step 1: Write failing test for excluded non-cash candidate**

Append to `tests/test_checks_reconciliation.py`:

```python
def test_check_reconciliation_targets_reports_excluded_investing_candidates():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            ReportSection(
                "statement:cfs",
                "현금흐름표",
                "statement",
                "",
                [
                    ReportBlock(
                        "table",
                        "",
                        ReportTable(
                            0,
                            [["구분", "당기"], ["유형자산의 취득", "(80)"]],
                            "현금흐름표",
                            SourceLocation("statement:cfs", 0, 0),
                        ),
                        SourceLocation("statement:cfs", 0, 0),
                    )
                ],
            )
        ],
        [
            ReportSection(
                "note:11",
                "유형자산",
                "note",
                "11",
                [
                    ReportBlock(
                        "table",
                        "",
                        ReportTable(
                            1,
                            [
                                ["구분", "합계"],
                                ["취득", "100"],
                                ["미지급금 증가", "20"],
                            ],
                            "유형자산 변동내역 당기",
                            SourceLocation("note:11", 0, 1),
                        ),
                        SourceLocation("note:11", 0, 1),
                    )
                ],
            )
        ],
    )

    result = next(
        check for check in check_reconciliation_targets(report, tolerance=0)
        if check.title == "property_plant_equipment.acquisitions_cashflow"
    )

    assert result.status == "matched"
    assert "후보 제외" in result.reason
    assert any(evidence.label == "note 11 미지급금 증가" for evidence in result.evidence)
```

- [ ] **Step 2: Run test to verify current behavior**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_reports_excluded_investing_candidates -v
```

Expected: FAIL because excluded candidate details are not yet surfaced in reason/evidence.

- [ ] **Step 3: Build candidate diagnostics in cash-flow result**

In `checks_reconciliation.py`, add helper:

```python
def _excluded_candidate_evidence(note_movements: list[NoteMovementInput]) -> list[CheckEvidence]:
    return [
        CheckEvidence(
            f"excluded note {movement.note_no} {movement.label} ({movement.exclusion_reason})",
            movement.amount,
            movement.source,
        )
        for movement in note_movements
        if movement.exclusion_reason
    ]
```

When candidate selection excludes movements because they are non-cash, set:

```python
movement.exclusion_reason = "not_cash_movement"
```

Because `NoteMovementInput` is frozen, use `dataclasses.replace()`:

```python
from dataclasses import replace
```

Append excluded candidate evidence to the `evidence` list for cash-flow results. Update `_cashflow_bridge_reason()` so matched results with excluded candidates include:

```text
후보 제외: non-cash movement 후보는 현금흐름 산식에서 제외
```

- [ ] **Step 4: Run focused reconciliation tests**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_checks_reconciliation.py -q
```

Expected: PASS with no regression.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/checks_reconciliation.py tests/test_checks_reconciliation.py
git commit -m "feat: surface excluded investing cashflow candidates"
```

---

### Task 6: Formula Subset Search For Financing Cash Flows

**Files:**
- Modify: `src/dart_footing_reconciler/checks_reconciliation.py`
- Test: `tests/test_checks_reconciliation.py`

- [ ] **Step 1: Write failing test for financing subset formula**

Append to `tests/test_checks_reconciliation.py`:

```python
def test_check_reconciliation_targets_selects_financing_subset_and_rejects_fx():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            ReportSection(
                "statement:cfs",
                "현금흐름표",
                "statement",
                "",
                [
                    ReportBlock(
                        "table",
                        "",
                        ReportTable(
                            0,
                            [["구분", "당기"], ["차입금의 차입", "100"], ["차입금의 상환", "(40)"]],
                            "현금흐름표",
                            SourceLocation("statement:cfs", 0, 0),
                        ),
                        SourceLocation("statement:cfs", 0, 0),
                    )
                ],
            )
        ],
        [
            ReportSection(
                "note:20",
                "차입금",
                "note",
                "20",
                [
                    ReportBlock(
                        "table",
                        "",
                        ReportTable(
                            1,
                            [
                                ["구분", "당기"],
                                ["차입", "100"],
                                ["상환", "(40)"],
                                ["환율변동효과", "3"],
                            ],
                            "재무활동에서 생기는 부채의 변동",
                            SourceLocation("note:20", 0, 1),
                        ),
                        SourceLocation("note:20", 0, 1),
                    )
                ],
            )
        ],
    )

    result = next(
        check for check in check_reconciliation_targets(report, tolerance=0)
        if check.title == "borrowings.financing_cashflow"
    )

    assert result.status == "matched"
    assert result.actual == 60
    assert "환율변동효과" in " ".join(evidence.label for evidence in result.evidence)
    assert "후보 제외" in result.reason
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_selects_financing_subset_and_rejects_fx -v
```

Expected: FAIL if excluded FX candidate is not visible.

- [ ] **Step 3: Use `select_best_subset()` for financing net**

In `checks_reconciliation.py`, convert note movements to candidates:

```python
from dart_footing_reconciler.evidence_candidates import CandidateEvidence, select_best_subset


def _movement_candidate(movement: NoteMovementInput, score: int = 0) -> CandidateEvidence:
    return CandidateEvidence(
        account_key=movement.account_key,
        role=movement.movement_role,
        label=movement.label,
        amount=movement.amount,
        source=movement.source,
        note_no=movement.note_no,
        table_class=movement.table_class,
        period_role=movement.period_role,
        unit_multiplier=movement.unit_multiplier,
        score=score,
        exclusion_reason=movement.exclusion_reason,
    )
```

Replace financing net selection internals so the selected candidates drive `actual`, while rejected candidates are appended as evidence with labels:

```text
excluded note 20 환율변동효과 (not_needed_for_best_formula)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_evidence_candidates.py tests/test_checks_reconciliation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/evidence_candidates.py src/dart_footing_reconciler/checks_reconciliation.py tests/test_evidence_candidates.py tests/test_checks_reconciliation.py
git commit -m "feat: apply candidate subset search to financing cashflows"
```

---

### Task 7: Integrate Note Assertions Into Workpaper Checks

**Files:**
- Modify: `src/dart_footing_reconciler/cli.py`
- Test: `tests/test_cli_workpaper.py`

- [ ] **Step 1: Write failing integration test**

Append to `tests/test_cli_workpaper.py`:

```python
def test_workpaper_checks_include_note_rollforward_assertions():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [],
        [
            _section(
                "note:11",
                "유형자산",
                "note",
                "11",
                ReportTable(
                    0,
                    [
                        ["구분", "합계"],
                        ["기초장부금액", "100"],
                        ["취득", "10"],
                        ["기말장부금액", "110"],
                    ],
                    "유형자산의 변동내역 당기",
                    SourceLocation("note:11", 0, 0),
                ),
            )
        ],
    )

    checks = _run_workpaper_checks(report, None, tolerance=0)

    assert any(check.check_type == "note_rollforward_check" for check in checks)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_cli_workpaper.py::test_workpaper_checks_include_note_rollforward_assertions -v
```

Expected: FAIL because `_run_workpaper_checks()` does not call `check_note_assertions()`.

- [ ] **Step 3: Wire note assertions into CLI**

Modify imports in `src/dart_footing_reconciler/cli.py`:

```python
from dart_footing_reconciler.note_assertions import check_note_assertions
```

Modify `_run_workpaper_checks()`:

```python
def _run_workpaper_checks(
    report: FullReport, prior_report: FullReport | None, tolerance: int
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    checks.extend(_run_total_checks(report, tolerance))
    checks.extend(check_note_assertions(report, tolerance=tolerance))
    checks.extend(check_reconciliation_targets(report, tolerance=tolerance))
    checks.extend(check_note_note_matches(report, tolerance=tolerance))
    if prior_report is not None:
        checks.extend(check_prior_year_reconciliation(report, prior_report, tolerance=tolerance))
    return checks
```

- [ ] **Step 4: Run integration tests**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_cli_workpaper.py tests/test_note_assertions.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/cli.py tests/test_cli_workpaper.py
git commit -m "feat: include note assertions in workpaper checks"
```

---

### Task 8: Render Note Assertion And Candidate Diagnostics In HTML

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Test: `tests/test_cli_workpaper.py`

- [ ] **Step 1: Write failing HTML test**

Append to `tests/test_cli_workpaper.py`:

```python
def test_html_report_renders_note_assertion_section():
    report = FullReport("sample.html", "Sample Co", [], [])
    checks = [
        CheckResult(
            "note_assertion:11:table0:rollforward",
            "note_rollforward_check",
            "matched",
            "note",
            "11",
            "유형자산 증감표 검산",
            110,
            110,
            0,
            0,
            "기초와 변동내역이 기말 장부금액과 일치",
            [
                CheckEvidence("기초장부금액 합계", 100, "note:11/table:0/row:1/col:1"),
                CheckEvidence("기말장부금액 합계", 110, "note:11/table:0/row:3/col:1"),
            ],
        )
    ]

    html = render_audit_reconciliation_html(report, checks)

    assert "주석별 검증" in html
    assert "유형자산 증감표 검산" in html
    assert "기초와 변동내역이 기말 장부금액과 일치" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_cli_workpaper.py::test_html_report_renders_note_assertion_section -v
```

Expected: FAIL if the HTML does not render this check family.

- [ ] **Step 3: Add note assertion section**

In `report_html.py`, add:

```python
NOTE_ASSERTION_CHECK_TYPES = {
    "note_rollforward_check",
    "note_balance_bridge_check",
    "note_internal_consistency_check",
}
```

Add section renderer:

```python
def _note_assertion_section(checks: list[CheckResult]) -> str:
    note_checks = [check for check in checks if check.check_type in NOTE_ASSERTION_CHECK_TYPES]
    if not note_checks:
        return ""
    rows = []
    for check in note_checks:
        rows.append(
            "<tr>"
            f"<td>{escape(check.note_no)}</td>"
            f"<td>{escape(check.title)}</td>"
            f"<td>{_status_badge(check.status)}</td>"
            f"<td>{_amount(check.expected)}</td>"
            f"<td>{_amount(check.actual)}</td>"
            f"<td>{_amount(check.difference)}</td>"
            f"<td>{escape(check.reason)}</td>"
            "</tr>"
        )
    return (
        '<section class="report-section" id="note-assertions">'
        "<h2>주석별 검증</h2>"
        '<p class="term-note"><strong>주석별 검증</strong>: 주석 표 내부의 증감표, 합계, 관련 주석 간 대사가 재현 가능한지 확인합니다.</p>'
        '<div class="table-wrap"><table class="evidence-table">'
        "<thead><tr><th>주석</th><th>검증 항목</th><th>상태</th><th>기대값</th><th>원문값</th><th>차이</th><th>판단</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        "</section>"
    )
```

Insert the section after the reviewer summary and before statement source sections.

- [ ] **Step 4: Run HTML tests**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_cli_workpaper.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/report_html.py tests/test_cli_workpaper.py
git commit -m "feat: render note assertion checks in HTML report"
```

---

### Task 9: Corpus Metrics For Note Assertions

**Files:**
- Modify: `src/dart_footing_reconciler/corpus.py`
- Test: `tests/test_corpus.py`

- [ ] **Step 1: Write failing corpus metric test**

Append to `tests/test_corpus.py`:

```python
def test_corpus_summary_counts_note_assertion_checks(monkeypatch, tmp_path):
    def fake_checks(report, prior_report=None, tolerance=1):
        return [
            CheckResult(
                "note_assertion:11:table0:rollforward",
                "note_rollforward_check",
                "matched",
                "note",
                "11",
                "유형자산 증감표 검산",
                100,
                100,
                0,
                1,
                "matched",
                [],
            )
        ]

    monkeypatch.setattr("dart_footing_reconciler.corpus._run_checks", fake_checks)

    # Use the smallest existing corpus fixture helper in this file.
    # The assertion below is the required new behavior.
    payload = _run_one_sample_corpus(tmp_path)

    assert payload["summary"]["note_assertion_checks"] == 1
    assert payload["summary"]["note_assertion_matched"] == 1
```

If `_run_one_sample_corpus()` does not exist, create a local helper in the test using the same sample setup already used in existing corpus tests.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_corpus.py::test_corpus_summary_counts_note_assertion_checks -v
```

Expected: FAIL because summary keys do not exist.

- [ ] **Step 3: Add summary counters**

In `corpus.py`, add:

```python
def _note_assertion_summary(checks: list[CheckResult]) -> dict[str, int]:
    note_checks = [check for check in checks if check.check_type.startswith("note_")]
    return {
        "note_assertion_checks": len(note_checks),
        "note_assertion_matched": sum(1 for check in note_checks if check.status == MATCHED),
        "note_assertion_unresolved": sum(1 for check in note_checks if check.status == UNEXPLAINED_GAP),
    }
```

Merge these counters into the top-level corpus summary and per-sample diagnostic payload.

- [ ] **Step 4: Run corpus tests**

Run:

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest tests/test_corpus.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/corpus.py tests/test_corpus.py
git commit -m "feat: report note assertion corpus metrics"
```

---

### Task 10: Regenerate SeAH Steel Sample And Visual Check

**Files:**
- Output: `out/corpus/run_2026-05-27-hundred-v82/reports/세아제강_2024.html`
- Output: `out/corpus/run_2026-05-27-hundred-v82/reports/세아제강_2024_note_assertions.png`

- [ ] **Step 1: Run focused tests**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest \
  tests/test_note_assertions.py \
  tests/test_evidence_candidates.py \
  tests/test_reconciliation_inputs.py \
  tests/test_checks_reconciliation.py \
  tests/test_cli_workpaper.py \
  -q
```

Expected: all selected tests PASS.

- [ ] **Step 2: Run full tests**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/pytest -q
```

Expected: all tests PASS.

- [ ] **Step 3: Regenerate sample HTML**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache .venv/bin/dart-footing workpaper-html \
  out/corpus/run_2026-05-27-hundred-v82/raw/세아제강_2024_20250312000987.html \
  out/corpus/run_2026-05-27-hundred-v82/reports/세아제강_2024.html \
  --company 세아제강
```

Expected:

```text
Wrote out/corpus/run_2026-05-27-hundred-v82/reports/세아제강_2024.html
```

- [ ] **Step 4: Run browser render inspection**

Use project-local Playwright through Node:

```bash
node - <<'NODE'
const { chromium } = require('playwright');
(async () => {
  const reportPath = '/Users/kjun/vault/01_Projects/09_dart_footing_reconciler/out/corpus/run_2026-05-27-hundred-v82/reports/세아제강_2024.html';
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto('file://' + reportPath, { waitUntil: 'load' });
  const checks = await page.evaluate(() => {
    const html = document.documentElement.innerHTML;
    return {
      hasNoteAssertions: html.includes('주석별 검증'),
      hasRollforwardCheck: html.includes('증감표 검산'),
      hasCandidateExclusion: html.includes('후보 제외'),
      hasFormulaTable: document.querySelectorAll('.formula-table').length > 0,
      rawZeroCells: [...document.querySelectorAll('.raw-note-table td')].filter(td => td.textContent.trim() === '0').length,
    };
  });
  await page.screenshot({
    path: '/Users/kjun/vault/01_Projects/09_dart_footing_reconciler/out/corpus/run_2026-05-27-hundred-v82/reports/세아제강_2024_note_assertions.png',
    fullPage: false
  });
  await browser.close();
  console.log(JSON.stringify(checks, null, 2));
})();
NODE
```

Expected:

```json
{
  "hasNoteAssertions": true,
  "hasRollforwardCheck": true,
  "hasCandidateExclusion": true,
  "hasFormulaTable": true,
  "rawZeroCells": 0
}
```

- [ ] **Step 5: Run Harness verification**

```bash
UV_CACHE_DIR=/private/tmp/uv-cache ./Harness/verify.sh
```

Expected: `harness verify ok`.

- [ ] **Step 6: Update handoff docs**

Update:

- `HANDOFF.md`
- `/Users/kjun/vault/Harness/progress.md`
- `/Users/kjun/vault/Harness/session-handoff.md`

Record:

```text
- note assertion checks added
- investing/financing candidate diagnostics added
- focused and full test counts
- sample report path and screenshot path
- remaining unresolved cash-flow families, if any
```

- [ ] **Step 7: Commit**

```bash
git add \
  src/dart_footing_reconciler \
  tests \
  HANDOFF.md \
  /Users/kjun/vault/Harness/progress.md \
  /Users/kjun/vault/Harness/session-handoff.md
git commit -m "feat: add note assertions and cashflow candidate diagnostics"
```

---

## Implementation Order

1. Task 1-2: note assertion engine minimum viable behavior.
2. Task 3-4: candidate evidence model and metadata plumbing.
3. Task 5-6: investing/financing cash-flow matching diagnostics.
4. Task 7-8: workpaper and HTML integration.
5. Task 9-10: corpus metrics, sample regeneration, verification.

## Acceptance Criteria

Required:

- `workpaper-html` includes `note_rollforward_check` results.
- At least asset roll-forward note tables validate `beginning + movements = ending`.
- Blank amount cells in note arithmetic are treated as zero only inside numeric amount grids.
- Investing CFS matches show included and excluded candidate rows.
- Financing CFS matches use subset search and show excluded non-cash/FX/reclassification rows.
- HTML report has a `주석별 검증` section.
- Full pytest passes.
- Root Harness verify passes.

Recommended:

- Corpus summary separates note assertion pass rate from primary reconciliation no-difference rate.
- Sample SeAH Steel HTML includes note assertion and candidate exclusion evidence.
- Candidate exclusion labels are Korean-facing in the HTML surface.

## Non-Goals

- Do not make audit conclusions such as "오류 있음" or "부정 징후".
- Do not use LLM-only parsing or MCP-only matching.
- Do not hardcode company names, note numbers, or one-off DART layouts.
- Do not replace existing conservative unresolved classification with loose matching.
- Do not broaden to all note types in this phase; income tax, fair value, commitments, and EPS can be later phases unless required for visible false positives.

## Risk Controls

- Every new `matched` case must show a reproducible formula.
- Every formula term must have a source location.
- Excluded candidates must be visible when the result would otherwise look mysterious.
- Candidate subset search must cap terms with `max_terms`; if no exact or tolerance-bound formula exists, keep `unexplained_gap` or `parse_uncertain`.
- Existing corpus baseline must not be replaced unless the same sample set is fully regenerated without source-access gaps.

## Self-Review

- Spec coverage: covers the user-identified note validation gap and cash-flow investing/financing matching gap through note assertions, candidate evidence, HTML surfacing, and corpus metrics.
- Placeholder scan: no placeholder markers or open-ended "add appropriate handling" tasks; each implementation task contains concrete tests, files, commands, and expected outcomes.
- Type consistency: `CandidateEvidence`, `NoteMovementInput.table_class`, `note_rollforward_check`, and `check_note_assertions()` are introduced before later tasks reference them.
