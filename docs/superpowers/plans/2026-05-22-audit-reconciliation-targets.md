# Audit Reconciliation Targets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reframe the project from table-local footing toward audit reconciliation assertions that connect financial statement lines, note disclosures, cash flow statement lines, total checks, and prior-period roll-forward checks.

**Architecture:** Add an explicit reconciliation target registry and input extraction layer before rule execution. Keep table-local total checks and movement-table arithmetic as supporting checks, while making BS-note, CFS-note, expense/adjustment, and prior-year beginning balance reconciliations the primary audit outputs.

**Tech Stack:** Python 3.11+, dataclasses, current DART HTML parser, existing `CheckResult` model, `pytest`, `openpyxl` for existing workbook rendering.

---

## Current Correction

The current `foot_table()` behavior is a supporting arithmetic check only:

```text
note movement table: beginning + movements = ending
```

The audit feature must instead produce assertion-level reconciliations:

```text
financial statement line <-> note amount
cash flow statement line <-> cash movement in note
expense or CFS adjustment <-> depreciation/amortization/interest/tax note evidence
prior-year ending balance <-> current-year beginning balance
note table row/column totals <-> displayed total
```

## File Structure

- Create `src/dart_footing_reconciler/reconciliation_targets.py`
  - Owns canonical reconciliation target definitions and assertion metadata.
- Create `src/dart_footing_reconciler/reconciliation_inputs.py`
  - Extracts statement lines, note balances, note movements, CFS lines, and supporting amounts from `FullReport`.
- Create `src/dart_footing_reconciler/checks_reconciliation.py`
  - Executes target assertions and returns `CheckResult` objects.
- Modify `src/dart_footing_reconciler/taxonomy.py`
  - Expose canonical account keys and polarity-aware alias matching for target extraction.
- Modify `src/dart_footing_reconciler/checks_fs_note.py`
  - Delegate to `checks_reconciliation.py` or become a compatibility wrapper.
- Modify `src/dart_footing_reconciler/checks_cfs_note.py`
  - Delegate to target-driven CFS assertions or become a compatibility wrapper.
- Modify `src/dart_footing_reconciler/checks_prior_year.py`
  - Add current-year beginning to prior-year ending reconciliation.
- Modify `src/dart_footing_reconciler/cli.py`
  - Run target-driven reconciliation in `workpaper-excel`.
- Modify `src/dart_footing_reconciler/audit_workbook.py`
  - Label primary reconciliation vs supporting checks.
- Add tests:
  - `tests/test_reconciliation_targets.py`
  - `tests/test_reconciliation_inputs.py`
  - `tests/test_checks_reconciliation.py`
  - Extend `tests/test_checks_prior_year.py`
  - Extend `tests/test_cli_workpaper.py`

## Target List

### Primary Balance Assertions

| Target | Assertion | Source A | Source B | Status |
|---|---|---|---|---|
| `property_plant_equipment` | BS ending balance to note ending carrying amount | BS PPE | PPE note ending carrying amount | Required |
| `intangible_assets` | BS ending balance to note ending carrying amount | BS intangibles | Intangibles note ending carrying amount | Required |
| `investment_property` | BS ending balance to note ending carrying amount | BS investment property | Investment property note ending carrying amount | Required |
| `right_of_use_assets` | BS ending balance to note ending carrying amount | BS ROU assets or note-only if not separately presented | ROU asset note ending carrying amount | Required |
| `lease_liabilities` | BS current + non-current lease liabilities to note ending balance | BS lease liabilities | Lease liability note ending balance | Required |
| `borrowings` | BS current + non-current borrowings to note ending balance | BS borrowings | Borrowing note ending balance | Required |
| `bonds` | BS bonds to note ending balance | BS bonds | Bond note ending balance | Required |

### Primary Cash Flow Assertions

| Target | Assertion | Source A | Source B | Required Adjustments |
|---|---|---|---|---|
| PPE acquisitions | CFS PPE acquisition cash outflow to cash-like note acquisitions | CFS investing line | PPE note acquisition rows | unpaid acquisitions, leases, business combinations, transfers |
| PPE disposals | CFS PPE disposal cash inflow to disposal cash proceeds evidence | CFS investing line | PPE disposal proceeds or disposal note evidence | disposal carrying amount and gain/loss are not cash proceeds |
| Intangible acquisitions | CFS intangible acquisition cash outflow to cash-like note acquisitions | CFS investing line | Intangible note acquisition rows | unpaid acquisitions, internal development capitalization, transfers |
| Intangible disposals | CFS intangible disposal cash inflow to disposal proceeds evidence | CFS investing line | Intangible disposal proceeds evidence | carrying amount/gain/loss bridge needed |
| Investment property acquisitions/disposals | CFS investment property cash flows to note cash movements | CFS investing line | Investment property note movement/proceeds evidence | transfers from PPE, fair value changes |
| Borrowing proceeds | CFS borrowing proceeds to cash borrowing increases | CFS financing line | Borrowings note cash increase rows | FX, reclassification, amortized cost |
| Borrowing repayments | CFS borrowing repayments to cash borrowing decreases | CFS financing line | Borrowings note repayment rows | current/non-current reclassification |
| Bond issuance/redemption | CFS bond issuance/redemption to note cash movements | CFS financing line | Bond note issue/redemption rows | conversion, discount amortization, transaction costs |
| Lease principal payments | CFS lease principal repayment to lease liability cash repayments | CFS financing line | Lease liability note repayment rows | interest, new lease additions, modifications |

### Expense And Non-Cash Assertions

| Target | Assertion | Source A | Source B |
|---|---|---|---|
| PPE depreciation | CFS operating adjustment or expense note to PPE depreciation | CFS adjustment / expense by nature | PPE note depreciation row |
| ROU depreciation | CFS operating adjustment or expense note to ROU depreciation | CFS adjustment / lease note | ROU asset depreciation row |
| Intangible amortization | CFS operating adjustment or expense note to intangible amortization | CFS adjustment / expense note | Intangible note amortization row |
| Lease interest | Finance cost / CFS interest paid to lease interest evidence | CFS/PL interest | Lease note finance cost |

### Supporting Checks

| Check | Assertion | Current Code | Required Change |
|---|---|---|---|
| Total check | Row/column displayed totals agree to components | `check_table_totals()` | Keep as supporting check and scope to relevant note tables |
| Movement table arithmetic | Beginning + movements = ending | `foot_table()` | Keep as supporting check, renamed in reports as movement arithmetic |
| Prior-year comparative | Current comparative amount equals prior current amount | `check_prior_year_reconciliation()` | Keep |
| Prior ending to current beginning | Prior-year ending balance equals current-year beginning balance | Missing | Add explicit assertion |

---

### Task 1: Reconciliation Target Registry

**Files:**
- Create: `src/dart_footing_reconciler/reconciliation_targets.py`
- Test: `tests/test_reconciliation_targets.py`

- [ ] **Step 1: Write the failing test**

```python
from dart_footing_reconciler.reconciliation_targets import RECONCILIATION_TARGETS


def test_reconciliation_targets_include_primary_balance_and_cashflow_assertions():
    keys = {target.key for target in RECONCILIATION_TARGETS}

    assert "property_plant_equipment.balance" in keys
    assert "property_plant_equipment.acquisitions_cashflow" in keys
    assert "property_plant_equipment.disposals_cashflow" in keys
    assert "intangible_assets.balance" in keys
    assert "lease_liabilities.principal_payments_cashflow" in keys
    assert "borrowings.proceeds_cashflow" in keys
    assert "borrowings.repayments_cashflow" in keys
    assert "bonds.issuance_redemption_cashflow" in keys
    assert "prior_year.ending_to_current_beginning" in keys
    assert "supporting.table_totals" in keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reconciliation_targets.py::test_reconciliation_targets_include_primary_balance_and_cashflow_assertions -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'dart_footing_reconciler.reconciliation_targets'`.

- [ ] **Step 3: Implement target registry**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReconciliationTarget:
    key: str
    account_key: str
    assertion_type: str
    statement_source: str
    note_source: str
    required_adjustments: tuple[str, ...] = ()
    supporting: bool = False


RECONCILIATION_TARGETS: tuple[ReconciliationTarget, ...] = (
    ReconciliationTarget(
        "property_plant_equipment.balance",
        "property_plant_equipment",
        "balance",
        "statement_financial_position",
        "note_ending_carrying_amount",
    ),
    ReconciliationTarget(
        "property_plant_equipment.acquisitions_cashflow",
        "property_plant_equipment",
        "cashflow_acquisition",
        "statement_cash_flows",
        "note_cash_like_acquisitions",
        ("unpaid_acquisitions", "leases", "business_combinations", "transfers"),
    ),
    ReconciliationTarget(
        "property_plant_equipment.disposals_cashflow",
        "property_plant_equipment",
        "cashflow_disposal",
        "statement_cash_flows",
        "note_disposal_proceeds_evidence",
        ("carrying_amount", "disposal_gain_loss"),
    ),
    ReconciliationTarget(
        "intangible_assets.balance",
        "intangible_assets",
        "balance",
        "statement_financial_position",
        "note_ending_carrying_amount",
    ),
    ReconciliationTarget(
        "lease_liabilities.principal_payments_cashflow",
        "lease_liabilities",
        "cashflow_repayment",
        "statement_cash_flows",
        "note_cash_repayments",
        ("interest", "new_leases", "modifications"),
    ),
    ReconciliationTarget(
        "borrowings.proceeds_cashflow",
        "borrowings",
        "cashflow_proceeds",
        "statement_cash_flows",
        "note_cash_increases",
        ("foreign_exchange", "reclassification", "amortized_cost"),
    ),
    ReconciliationTarget(
        "borrowings.repayments_cashflow",
        "borrowings",
        "cashflow_repayment",
        "statement_cash_flows",
        "note_cash_repayments",
        ("current_noncurrent_reclassification",),
    ),
    ReconciliationTarget(
        "bonds.issuance_redemption_cashflow",
        "bonds",
        "cashflow_issue_redemption",
        "statement_cash_flows",
        "note_cash_issue_redemption",
        ("conversion", "discount_amortization", "transaction_costs"),
    ),
    ReconciliationTarget(
        "prior_year.ending_to_current_beginning",
        "all_movement_accounts",
        "prior_ending_to_current_beginning",
        "prior_year_note_ending",
        "current_year_note_beginning",
    ),
    ReconciliationTarget(
        "supporting.table_totals",
        "all_note_tables",
        "table_total",
        "note_components",
        "note_displayed_total",
        supporting=True,
    ),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_reconciliation_targets.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/reconciliation_targets.py tests/test_reconciliation_targets.py
git commit -m "feat: define audit reconciliation targets"
```

### Task 2: Reconciliation Input Extraction Model

**Files:**
- Create: `src/dart_footing_reconciler/reconciliation_inputs.py`
- Test: `tests/test_reconciliation_inputs.py`

- [ ] **Step 1: Write the failing test**

```python
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.reconciliation_inputs import extract_reconciliation_inputs


def _section(section_id, title, kind, note_no, rows):
    table = ReportTable(0, rows, title, SourceLocation(section_id, 0, 0))
    return ReportSection(section_id, title, kind, note_no, [ReportBlock("table", "", table, table.location)])


def test_extract_reconciliation_inputs_separates_statement_note_and_cfs_sources():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [
            _section("statement:bs", "재무상태표", "statement", "", [["구분", "당기"], ["유형자산", "1,000"]]),
            _section("statement:cf", "현금흐름표", "statement", "", [["구분", "당기"], ["유형자산의 취득", "(300)"]]),
        ],
        [
            _section("note:11", "유형자산", "note", "11", [["구분", "합계"], ["기초", "800"], ["취득", "300"], ["기말", "1,000"]]),
        ],
    )

    inputs = extract_reconciliation_inputs(report)

    assert inputs.statement_lines[0].account_key == "property_plant_equipment"
    assert inputs.cfs_lines[0].account_key == "property_plant_equipment"
    assert inputs.cfs_lines[0].movement_role == "acquisition"
    assert inputs.note_balances[0].balance_role == "ending"
    assert inputs.note_movements[0].movement_role == "acquisition"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_reconciliation_inputs.py::test_extract_reconciliation_inputs_separates_statement_note_and_cfs_sources -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement input dataclasses and extraction**

```python
from __future__ import annotations

from dataclasses import dataclass

from dart_footing_reconciler.amounts import parse_amount
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.taxonomy import classify_report


@dataclass(frozen=True)
class StatementLineInput:
    account_key: str
    label: str
    amount: int
    source: str


@dataclass(frozen=True)
class CfsLineInput:
    account_key: str
    movement_role: str
    label: str
    amount: int
    source: str


@dataclass(frozen=True)
class NoteBalanceInput:
    account_key: str
    balance_role: str
    note_no: str
    label: str
    amount: int
    source: str


@dataclass(frozen=True)
class NoteMovementInput:
    account_key: str
    movement_role: str
    note_no: str
    label: str
    amount: int
    source: str


@dataclass(frozen=True)
class ReconciliationInputs:
    statement_lines: list[StatementLineInput]
    cfs_lines: list[CfsLineInput]
    note_balances: list[NoteBalanceInput]
    note_movements: list[NoteMovementInput]


def extract_reconciliation_inputs(report: FullReport) -> ReconciliationInputs:
    classified = classify_report(report)
    return ReconciliationInputs(
        statement_lines=[
            StatementLineInput(line.account_key, line.label, line.amount, line.source)
            for line in classified.statement_lines
            if line.statement_title != "현금흐름표"
        ],
        cfs_lines=_extract_cfs_lines(report),
        note_balances=_extract_note_balances(classified),
        note_movements=_extract_note_movements(report),
    )


def _extract_cfs_lines(report: FullReport) -> list[CfsLineInput]:
    lines: list[CfsLineInput] = []
    for section in report.statements:
        if section.title != "현금흐름표":
            continue
        for block in section.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row:
                    continue
                account_key, movement_role = _classify_cfs_label(row[0])
                if account_key == "":
                    continue
                amount = _rightmost_amount(row)
                if amount is None:
                    continue
                lines.append(CfsLineInput(account_key, movement_role, row[0], amount, f"{section.section_id}/table:{table.index}/row:{row_idx}"))
    return lines


def _extract_note_balances(classified) -> list[NoteBalanceInput]:
    balances: list[NoteBalanceInput] = []
    for amount in classified.note_amounts:
        if "기말" in amount.label or "장부금액" in amount.label:
            balances.append(NoteBalanceInput(amount.account_key, "ending", amount.note_no, amount.label, amount.amount, amount.source))
        elif "기초" in amount.label:
            balances.append(NoteBalanceInput(amount.account_key, "beginning", amount.note_no, amount.label, amount.amount, amount.source))
    return balances


def _extract_note_movements(report: FullReport) -> list[NoteMovementInput]:
    movements: list[NoteMovementInput] = []
    classified = classify_report(report)
    topic_by_note_no = {topic.note_no: topic.topic_key for topic in classified.note_topics}
    for note in report.notes:
        account_key = topic_by_note_no.get(note.note_no)
        if account_key is None:
            continue
        for block in note.blocks:
            table = block.table
            if table is None or not table.rows:
                continue
            for row_idx, row in enumerate(table.rows[1:], start=1):
                if not row:
                    continue
                movement_role = _classify_movement_label(row[0])
                if movement_role == "":
                    continue
                amount = _rightmost_amount(row)
                if amount is None:
                    continue
                movements.append(NoteMovementInput(account_key, movement_role, note.note_no, row[0], amount, f"{note.section_id}/table:{table.index}/row:{row_idx}"))
    return movements


def _classify_cfs_label(label: str) -> tuple[str, str]:
    compact = "".join(label.split())
    if "유형자산" in compact and "취득" in compact:
        return "property_plant_equipment", "acquisition"
    if "유형자산" in compact and "처분" in compact:
        return "property_plant_equipment", "disposal"
    if "무형자산" in compact and "취득" in compact:
        return "intangible_assets", "acquisition"
    if "차입금" in compact and "차입" in compact:
        return "borrowings", "proceeds"
    if "차입금" in compact and "상환" in compact:
        return "borrowings", "repayment"
    if "리스부채" in compact and "상환" in compact:
        return "lease_liabilities", "repayment"
    return "", ""


def _classify_movement_label(label: str) -> str:
    compact = "".join(label.split())
    if "취득" in compact or "증가" in compact:
        return "acquisition"
    if "처분" in compact:
        return "disposal"
    if "상환" in compact:
        return "repayment"
    if "차입" in compact:
        return "proceeds"
    if "감가상각" in compact:
        return "depreciation"
    if "상각" in compact:
        return "amortization"
    if "기초" in compact:
        return "beginning"
    if "기말" in compact:
        return "ending"
    return ""


def _rightmost_amount(row: list[str]) -> int | None:
    for cell in reversed(row[1:]):
        amount = parse_amount(cell)
        if amount is not None:
            return amount
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_reconciliation_inputs.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/reconciliation_inputs.py tests/test_reconciliation_inputs.py
git commit -m "feat: extract reconciliation inputs"
```

### Task 3: Primary Balance Reconciliation

**Files:**
- Create: `src/dart_footing_reconciler/checks_reconciliation.py`
- Test: `tests/test_checks_reconciliation.py`

- [ ] **Step 1: Write the failing test**

```python
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.checks_reconciliation import check_reconciliation_targets


def _section(section_id, title, kind, note_no, rows):
    table = ReportTable(0, rows, title, SourceLocation(section_id, 0, 0))
    return ReportSection(section_id, title, kind, note_no, [ReportBlock("table", "", table, table.location)])


def test_check_reconciliation_targets_matches_bs_to_note_ending_balance():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:bs", "재무상태표", "statement", "", [["구분", "당기"], ["유형자산", "1,000"]])],
        [_section("note:11", "유형자산", "note", "11", [["구분", "합계"], ["기말 장부금액", "1,000"]])],
    )

    results = check_reconciliation_targets(report, tolerance=0)

    assert results[0].check_type == "primary_balance_reconciliation"
    assert results[0].check_id == "reconciliation:property_plant_equipment.balance"
    assert results[0].status == "matched"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_matches_bs_to_note_ending_balance -v`

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement minimal balance reconciliation**

```python
from __future__ import annotations

from dart_footing_reconciler.checks import CheckEvidence, CheckResult, MATCHED, UNEXPLAINED_GAP
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.reconciliation_inputs import extract_reconciliation_inputs
from dart_footing_reconciler.reconciliation_targets import RECONCILIATION_TARGETS


def check_reconciliation_targets(report: FullReport, *, tolerance: int = 1) -> list[CheckResult]:
    inputs = extract_reconciliation_inputs(report)
    results: list[CheckResult] = []
    for target in RECONCILIATION_TARGETS:
        if target.assertion_type != "balance":
            continue
        statement = _first([line for line in inputs.statement_lines if line.account_key == target.account_key])
        note = _first([balance for balance in inputs.note_balances if balance.account_key == target.account_key and balance.balance_role == "ending"])
        if statement is None or note is None:
            continue
        difference = note.amount - statement.amount
        status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
        results.append(
            CheckResult(
                f"reconciliation:{target.key}",
                "primary_balance_reconciliation",
                status,
                "report",
                note.note_no,
                target.key,
                statement.amount,
                note.amount,
                difference,
                tolerance,
                "statement ending balance agrees to note ending balance" if status == MATCHED else "statement ending balance does not agree to note ending balance",
                [
                    CheckEvidence(statement.label, statement.amount, statement.source),
                    CheckEvidence(note.label, note.amount, note.source),
                ],
            )
        )
    return results


def _first(values):
    return values[0] if values else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_checks_reconciliation.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/checks_reconciliation.py tests/test_checks_reconciliation.py
git commit -m "feat: reconcile statement balances to note balances"
```

### Task 4: Cash Flow To Note Movement Reconciliation

**Files:**
- Modify: `src/dart_footing_reconciler/checks_reconciliation.py`
- Test: `tests/test_checks_reconciliation.py`

- [ ] **Step 1: Add failing cashflow test**

```python
def test_check_reconciliation_targets_matches_cfs_acquisition_to_note_cash_movement():
    report = FullReport(
        "sample.html",
        "Sample Co",
        [_section("statement:cf", "현금흐름표", "statement", "", [["구분", "당기"], ["유형자산의 취득", "(300)"]])],
        [_section("note:11", "유형자산", "note", "11", [["구분", "합계"], ["취득", "300"]])],
    )

    results = check_reconciliation_targets(report, tolerance=0)
    acquisition = [result for result in results if result.check_id == "reconciliation:property_plant_equipment.acquisitions_cashflow"]

    assert acquisition[0].check_type == "primary_cashflow_reconciliation"
    assert acquisition[0].status == "matched"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_checks_reconciliation.py::test_check_reconciliation_targets_matches_cfs_acquisition_to_note_cash_movement -v`

Expected: FAIL because no `primary_cashflow_reconciliation` result exists.

- [ ] **Step 3: Add cashflow assertion execution**

Add this branch inside `check_reconciliation_targets()`:

```python
        if target.assertion_type.startswith("cashflow_"):
            cfs_role = _role_for_target(target.assertion_type)
            cfs = _first([line for line in inputs.cfs_lines if line.account_key == target.account_key and line.movement_role == cfs_role])
            note = _first([movement for movement in inputs.note_movements if movement.account_key == target.account_key and movement.movement_role == cfs_role])
            if cfs is None or note is None:
                continue
            expected = abs(cfs.amount)
            actual = abs(note.amount)
            difference = actual - expected
            status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
            results.append(
                CheckResult(
                    f"reconciliation:{target.key}",
                    "primary_cashflow_reconciliation",
                    status,
                    "report",
                    note.note_no,
                    target.key,
                    expected,
                    actual,
                    difference,
                    tolerance,
                    "cash flow statement line agrees to note cash movement" if status == MATCHED else "cash flow statement line does not agree to note cash movement",
                    [
                        CheckEvidence(cfs.label, cfs.amount, cfs.source),
                        CheckEvidence(note.label, note.amount, note.source),
                    ],
                )
            )
            continue
```

Add this helper:

```python
def _role_for_target(assertion_type: str) -> str:
    if assertion_type == "cashflow_acquisition":
        return "acquisition"
    if assertion_type == "cashflow_disposal":
        return "disposal"
    if assertion_type == "cashflow_repayment":
        return "repayment"
    if assertion_type == "cashflow_proceeds":
        return "proceeds"
    if assertion_type == "cashflow_issue_redemption":
        return "proceeds"
    return ""
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_checks_reconciliation.py tests/test_reconciliation_inputs.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/checks_reconciliation.py tests/test_checks_reconciliation.py
git commit -m "feat: reconcile cash flow lines to note movements"
```

### Task 5: Supporting Total Checks And Movement Arithmetic Classification

**Files:**
- Modify: `src/dart_footing_reconciler/audit_workbook.py`
- Modify: `src/dart_footing_reconciler/cli.py`
- Test: `tests/test_audit_workbook.py`

- [ ] **Step 1: Write failing workbook label test**

```python
def test_audit_workbook_labels_total_checks_as_supporting_checks(tmp_path):
    table = ReportTable(0, [["구분", "토지", "건물", "합계"], ["기초", "100", "200", "300"]], "11. 유형자산", SourceLocation("note:11", 0, 0))
    note = ReportSection("note:11", "유형자산", "note", "11", [ReportBlock("table", "", table, table.location)])
    report = FullReport("sample.html", "Sample Co", [], [note])
    checks = check_table_totals(table, note_no="11", tolerance=0)
    output = tmp_path / "workpaper.xlsx"

    export_audit_workbook(report, checks, output)

    ws = load_workbook(output)["Note 11"]
    assert ws["A7"].value == "보조 검증"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_audit_workbook.py::test_audit_workbook_labels_total_checks_as_supporting_checks -v`

Expected: FAIL because the workbook currently labels the row as `합계 검증 결과`.

- [ ] **Step 3: Update label mapping**

Change `_check_type_label()` in `audit_workbook.py`:

```python
def _check_type_label(check_type: str) -> str:
    labels = {
        "primary_balance_reconciliation": "주요 대사",
        "primary_cashflow_reconciliation": "현금흐름 대사",
        "total_check": "보조 검증",
        "movement_arithmetic": "보조 검증",
        "fs_note_match": "재무제표-주석 대사",
        "note_note_match": "주석 간 대사",
        "cfs_note_match": "현금흐름표-주석 직접 대사",
        "prior_year_amount_match": "전기-당기 대사",
        "prior_year_beginning_balance_match": "전기말-당기초 대사",
        "prior_year_structure_change": "전기 공시 구조 변화",
    }
    return labels.get(check_type, check_type)
```

- [ ] **Step 4: Run workbook tests**

Run: `uv run pytest tests/test_audit_workbook.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/audit_workbook.py tests/test_audit_workbook.py
git commit -m "feat: label footing as supporting validation"
```

### Task 6: Prior-Year Ending To Current-Year Beginning Check

**Files:**
- Modify: `src/dart_footing_reconciler/checks_prior_year.py`
- Test: `tests/test_checks_prior_year.py`

- [ ] **Step 1: Write failing prior ending/current beginning test**

```python
def test_prior_year_reconciles_prior_ending_to_current_beginning_balance():
    current_note = _note("11", "유형자산", [["구분", "당기"], ["기초", "1,000"], ["기말", "1,200"]])
    prior_note = _note("11", "유형자산", [["구분", "당기"], ["기초", "700"], ["기말", "1,000"]])

    results = check_prior_year_reconciliation(
        FullReport("current.html", "Sample Co", [], [current_note]),
        FullReport("prior.html", "Sample Co", [], [prior_note]),
        tolerance=0,
    )

    beginning_results = [result for result in results if result.check_type == "prior_year_beginning_balance_match"]
    assert beginning_results[0].status == "matched"
    assert beginning_results[0].expected == 1000
    assert beginning_results[0].actual == 1000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_checks_prior_year.py::test_prior_year_reconciles_prior_ending_to_current_beginning_balance -v`

Expected: FAIL because `prior_year_beginning_balance_match` is not emitted.

- [ ] **Step 3: Add beginning balance comparison**

Add to `_compare_note_tables()` before comparative-column matching:

```python
        current_beginning = _label_amount_by_role(current_table, "beginning")
        prior_ending = _label_amount_by_role(prior_table, "ending")
        if current_beginning is not None and prior_ending is not None:
            difference = current_beginning - prior_ending
            status = MATCHED if abs(difference) <= tolerance else UNEXPLAINED_GAP
            results.append(
                CheckResult(
                    f"prior_beginning:{current_note.note_no}:{current_table.index}",
                    "prior_year_beginning_balance_match",
                    status,
                    "prior_year",
                    current_note.note_no,
                    current_note.title,
                    prior_ending,
                    current_beginning,
                    difference,
                    tolerance,
                    "prior-year ending balance agrees to current-year beginning balance" if status == MATCHED else "prior-year ending balance does not agree to current-year beginning balance",
                    [
                        CheckEvidence("prior ending", prior_ending, f"note:{prior_note.note_no}/ending"),
                        CheckEvidence("current beginning", current_beginning, f"note:{current_note.note_no}/beginning"),
                    ],
                )
            )
```

Add helper:

```python
def _label_amount_by_role(table: ReportTable, role: str) -> int | None:
    labels = ("기초", "기초장부금액", "기초금액") if role == "beginning" else ("기말", "기말장부금액", "기말금액")
    for row in table.rows[1:]:
        if not row:
            continue
        key = normalize_label(row[0])
        if any(normalize_label(label) in key for label in labels):
            return _rightmost_amount(row)
    return None
```

- [ ] **Step 4: Run prior-year tests**

Run: `uv run pytest tests/test_checks_prior_year.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/checks_prior_year.py tests/test_checks_prior_year.py
git commit -m "feat: reconcile prior ending to current beginning"
```

### Task 7: CLI Workpaper Uses Target-Driven Reconciliation

**Files:**
- Modify: `src/dart_footing_reconciler/cli.py`
- Test: `tests/test_cli_workpaper.py`

- [ ] **Step 1: Write failing CLI integration test**

```python
def test_workpaper_excel_runs_target_reconciliation(tmp_path):
    source = tmp_path / "report.html"
    source.write_text(
        """
        <p>재무상태표</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>유형자산</td><td>1,000</td></tr></table>
        <p>현금흐름표</p><table><tr><th>구분</th><th>당기</th></tr><tr><td>유형자산의 취득</td><td>(300)</td></tr></table>
        <p>재무제표 주석</p>
        <p>11. 유형자산</p><table><tr><th>구분</th><th>합계</th></tr><tr><td>기초</td><td>700</td></tr><tr><td>취득</td><td>300</td></tr><tr><td>기말 장부금액</td><td>1,000</td></tr></table>
        """,
        encoding="utf-8",
    )
    output = tmp_path / "workpaper.xlsx"

    result = runner.invoke(app, ["workpaper-excel", str(source), str(output), "--company", "Sample Co"])

    assert result.exit_code == 0
    ws = load_workbook(output)["Note 11"]
    values = [cell.value for row in ws.iter_rows() for cell in row]
    assert "주요 대사" in values
    assert "현금흐름 대사" in values
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_workpaper.py::test_workpaper_excel_runs_target_reconciliation -v`

Expected: FAIL because `workpaper-excel` still uses legacy `check_fs_note_matches()` and `check_cfs_note_matches()`.

- [ ] **Step 3: Update CLI**

In `workpaper_excel()` replace:

```python
    checks.extend(check_fs_note_matches(report, tolerance=tolerance))
    checks.extend(check_note_note_matches(report, tolerance=tolerance))
    checks.extend(check_cfs_note_matches(report, tolerance=tolerance))
```

with:

```python
    checks.extend(check_reconciliation_targets(report, tolerance=tolerance))
    checks.extend(check_note_note_matches(report, tolerance=tolerance))
```

Add import:

```python
from dart_footing_reconciler.checks_reconciliation import check_reconciliation_targets
```

- [ ] **Step 4: Run CLI tests**

Run: `uv run pytest tests/test_cli_workpaper.py tests/test_checks_reconciliation.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dart_footing_reconciler/cli.py tests/test_cli_workpaper.py
git commit -m "feat: run target reconciliation in workpaper export"
```

### Task 8: Real DART Smoke Classification Report

**Files:**
- Create: `docs/validation/2026-05-22-cj-reconciliation-target-smoke.md`

- [ ] **Step 1: Run CJ target smoke**

Run:

```bash
uv run python -c "from collections import Counter; from pathlib import Path; from dart_footing_reconciler.document import parse_full_report; from dart_footing_reconciler.checks_reconciliation import check_reconciliation_targets; report=parse_full_report('/private/tmp/cj_financial_section.html', company='CJ제일제당'); results=check_reconciliation_targets(report, tolerance=1); print(len(results)); print(Counter(r.check_type for r in results)); print(Counter(r.status for r in results)); [print(r.status, r.check_type, r.check_id, r.expected, r.actual, r.difference) for r in results[:30]]"
```

Expected: command completes and prints primary balance/cashflow reconciliation counts.

- [ ] **Step 2: Add validation note**

Create `docs/validation/2026-05-22-cj-reconciliation-target-smoke.md` with this structure:

```markdown
# CJ Reconciliation Target Smoke

Date: 2026-05-22

Source: CJ제일제당 2025.03.17 DART business report, `III. 재무에 관한 사항` viewer HTML.

## Purpose

Validate whether the target-driven reconciliation engine identifies primary audit assertions separately from supporting note arithmetic checks.

## Summary

The smoke command printed four count lines:

```text
total_results=<integer from command output>
check_type_counts=<Counter printed by command output>
status_counts=<Counter printed by command output>
first_results=<first result rows printed by command output>
```

Copy the exact values from the command output into this section when executing the task.

## Observations

- Balance assertions are expected for PPE, intangible assets, investment property, lease liabilities, borrowings, and bonds when both statement and note evidence are found.
- Cashflow assertions are expected only when CFS lines and note cash movement rows are both found.
- Unexplained gaps should be reviewed by source evidence before rule changes.
```

- [ ] **Step 3: Commit**

```bash
git add docs/validation/2026-05-22-cj-reconciliation-target-smoke.md
git commit -m "docs: record CJ reconciliation target smoke"
```

### Task 9: Final Regression

**Files:**
- No new files.

- [ ] **Step 1: Run full tests**

Run: `uv run pytest`

Expected: all tests pass.

- [ ] **Step 2: Check worktree**

Run: `git status --short`

Expected: only intentional files changed or clean after commits.

- [ ] **Step 3: Summarize implementation status**

Report these counts in the final handoff:

```text
Primary target definitions:
Primary balance checks implemented:
Primary cashflow checks implemented:
Supporting total checks implemented:
Prior ending to current beginning implemented:
Full test result:
Real DART smoke result:
```

## Self-Review

Spec coverage:
- User requested reconciliation target list: covered in `Target List`.
- User requested total checks: covered in supporting checks and Task 5.
- User requested prior ending to current beginning: covered in Task 6.
- User corrected footing vs reconciliation distinction: reflected in `Current Correction` and target architecture.
- User requested implementation plan: this file is the implementation plan.

Placeholder scan:
- The plan contains no empty implementation slots.
- The validation note template records command output fields explicitly after Task 8 runs.

Type consistency:
- `ReconciliationTarget`, `ReconciliationInputs`, and `CheckResult` names are consistent across tasks.
- `primary_balance_reconciliation`, `primary_cashflow_reconciliation`, and `prior_year_beginning_balance_match` are used consistently in tests and workbook labels.
