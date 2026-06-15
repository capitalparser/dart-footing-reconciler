# Verification Harness Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 재무제표 본문(재무상태표, 손익계산서, 자본변동표, 현금흐름표) ↔ 주석 검증과 주석 내부 검증을 별도 하네스 레이어로 분리하되, 기존 `CheckResult` 출력과 CLI/corpus/report 동작은 보존한다.

**Architecture:** Add an internal verification harness runner around existing check modules. `statement_note` is the key layer for financial-statement-body-to-note checks, with cash-flow checks as a separate strategy inside that layer. `note_internal` is the key layer for note table arithmetic, roll-forward, formula, and note-to-note checks. Existing statement-to-statement and prior-report checks remain as supporting harnesses so the current behavior does not disappear during migration.

**Tech Stack:** Python 3.11, dataclasses, Protocol, pytest, uv, existing `dart_footing_reconciler` package modules.

---

## Current State

- `src/dart_footing_reconciler/check_pipeline.py` is a flat assembly function. It directly calls all check functions in one list.
- Existing callers are `src/dart_footing_reconciler/corpus.py::_run_checks` and `src/dart_footing_reconciler/cli.py::_run_workpaper_checks`; both call `assemble_report_checks`.
- Existing tests normalize check output in `tests/test_check_pipeline.py`, so migration can preserve result content without preserving every internal call site.
- `src/dart_footing_reconciler/report_frame.py` groups rendered checks from `check_type`, not from explicit layer metadata.
- `CheckResult` is the stable output contract. Do not change its dataclass fields in this plan.
- `signatures.py` exists but is not yet a full attempt registry. This plan does not require completing the semantic-attempt layer.
- Focused baseline before writing this plan:

```bash
uv run pytest tests/test_check_pipeline.py tests/test_report_frame.py tests/test_signatures.py -q
```

Expected baseline: `25 passed`.

## Boundary Decision

Two domains are primary:

| Domain | Meaning | Existing checks moved under it |
|---|---|---|
| `statement_note` | Financial statement body ↔ note validation | `check_reconciliation_targets`, `check_asset_note_bridges`, `check_fs_note_matches`, `check_cfs_note_matches`, same-file prior-column FS-note checks |
| `note_internal` | Validation inside note contents | `check_table_totals`, `check_note_assertions`, `check_layout_formula_assertions`, `check_note_note_matches` |

Supporting domains remain explicit:

| Domain | Meaning | Existing checks |
|---|---|---|
| `statement_cross` | Financial statement body ↔ financial statement body | `check_statement_ties` |
| `prior_report` | Current filing ↔ prior filing when `prior_report` exists | `check_prior_year_reconciliation` |

Cash-flow statement validation belongs in `statement_note`, but it must be a separate strategy from BS/PL/SCE note matching because it uses cash-like movement, non-cash movement, and bridge adjustment logic.

## Semantic Candidate Bridge

The harness layer starts as a wrapper around existing check functions, but it
must not become a parallel routing system separate from the semantic layer.
`SemanticValidationCandidate` is the bridge contract:

- `statement_note` harnesses consume candidates whose layer is
  `statement_note`.
- `note_internal` harnesses consume candidates whose layer is `note_internal`.
- V1 keeps candidate consumption optional so existing CLI/corpus behavior stays
  stable, but the harness context must be able to carry semantic candidates.
- A harness may still call the existing check function directly when no
  semantic candidates are supplied.

## UI And Accuracy Decisions

- Do not create a new cockpit profile for this work. DART audit reports already use the shared `evidence_cockpit` profile, so the design-kit change must be additive inside that profile and the `cockpit-app-shell` DART section.
- User-facing UI labels should say `검증 범위`, not `harness` or `layer`. Internal Python metadata can still use `layer` values.
- Render validation results in actual company report order: 재무상태표, 손익계산서, 자본변동표, 현금흐름표, 주석.
- Add row-level validation scope labels so reviewers can distinguish `재무제표 본문-주석`, `주석 내부`, `재무제표 본문 간`, and `전기 보고서`.
- More test reports help coverage and layout discovery, but raw report count is not an accuracy metric. Accuracy must be measured with reviewed labels, false-match review, and stratified holdout sets.
- Optimization priority is false-match minimization first, then coverage improvement. A higher match rate is not accepted if it hides mismatched evidence.

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `src/dart_footing_reconciler/verification_harness.py` | Harness protocol, context, layer constants, run result, executor | Create |
| `src/dart_footing_reconciler/statement_note_harness.py` | 재무제표 본문 ↔ 주석 checks, with separate CF strategy | Create |
| `src/dart_footing_reconciler/note_internal_harness.py` | 주석 내부 checks | Create |
| `src/dart_footing_reconciler/supporting_harnesses.py` | Statement-cross and prior-report supporting harnesses | Create |
| `src/dart_footing_reconciler/semantic_validation.py` | Provides optional `SemanticValidationCandidate` rows for harness context | Read |
| `src/dart_footing_reconciler/check_pipeline.py` | Replace flat assembly with harness runner while preserving public API | Modify |
| `src/dart_footing_reconciler/report_frame.py` | Add layer-aware classification helper without changing output groups | Modify |
| `tests/test_verification_harness.py` | Core harness executor tests | Create |
| `tests/test_statement_note_harness.py` | Statement-note harness routing tests | Create |
| `tests/test_note_internal_harness.py` | Note-internal harness routing tests | Create |
| `tests/test_check_pipeline.py` | Pipeline equivalence and harness-run exposure tests | Modify |
| `tests/test_report_frame.py` | Check grouping still maps statement-note and note-internal results | Modify only if needed |
| `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/dashboard-cockpit-kit.md` | Shared evidence cockpit DART verification report guidance | Modify |
| `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/cockpit-app-shell-kit.md` | Shared DART app-shell guidance | Modify |
| `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript/src/cockpitProfiles.ts` | Additive optional tab labels for evidence cockpit | Modify |
| `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript/tests/validateArtifact.test.ts` | Design-kit adapter regression for evidence cockpit options | Modify |
| `src/dart_footing_reconciler/report_html.py` | Reader-facing validation scope label in report tables | Modify |
| `tests/test_cli_workpaper.py` | HTML report validation-scope regression | Modify |
| `docs/validation/verification-accuracy-strategy.md` | Accuracy set design and metric policy | Create |
| `tests/test_validation_docs.py` | Doc contract regression for the accuracy strategy | Create |

---

### Task 1: Core Harness Contract

**Files:**
- Create: `src/dart_footing_reconciler/verification_harness.py`
- Create: `tests/test_verification_harness.py`

- [x] **Step 1: Write failing tests**

Create `tests/test_verification_harness.py`:

```python
from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.verification_harness import (
    LAYER_NOTE_INTERNAL,
    VerificationContext,
    VerificationHarness,
    run_harnesses,
)


def _check(check_id: str) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type="total_check",
        status="matched",
        scope="report",
        note_no="1",
        title=check_id,
        expected=100,
        actual=100,
        difference=0,
        tolerance=1,
        reason="matched",
        evidence=[CheckEvidence("합계", 100, "note:1/table:0/row:1/col:1")],
    )


class FakeHarness:
    harness_id = "fake"
    layer = LAYER_NOTE_INTERNAL

    def run(self, context: VerificationContext) -> list[CheckResult]:
        assert context.tolerance == 1
        return [_check("fake-check")]


def test_run_harnesses_preserves_harness_metadata_and_checks():
    context = VerificationContext(
        report=FullReport("sample.html", "Sample Co", [], []),
        prior_report=None,
        tolerance=1,
    )

    runs = run_harnesses([FakeHarness()], context)

    assert len(runs) == 1
    assert runs[0].harness_id == "fake"
    assert runs[0].layer == LAYER_NOTE_INTERNAL
    assert [check.check_id for check in runs[0].checks] == ["fake-check"]


def test_fake_harness_satisfies_protocol_shape():
    harness: VerificationHarness = FakeHarness()

    assert harness.harness_id == "fake"
    assert harness.layer == LAYER_NOTE_INTERNAL
```

- [x] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_verification_harness.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'dart_footing_reconciler.verification_harness'`.

- [x] **Step 3: Implement core contract**

Create `src/dart_footing_reconciler/verification_harness.py`:

```python
"""Internal verification harness contracts and runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.document import FullReport

LAYER_STATEMENT_NOTE = "statement_note"
LAYER_NOTE_INTERNAL = "note_internal"
LAYER_STATEMENT_CROSS = "statement_cross"
LAYER_PRIOR_REPORT = "prior_report"


@dataclass(frozen=True)
class VerificationContext:
    report: FullReport
    prior_report: FullReport | None
    tolerance: int


class VerificationHarness(Protocol):
    harness_id: str
    layer: str

    def run(self, context: VerificationContext) -> list[CheckResult]:
        """Return CheckResult rows for this harness."""


@dataclass(frozen=True)
class HarnessRun:
    harness_id: str
    layer: str
    checks: tuple[CheckResult, ...]


def run_harnesses(
    harnesses: list[VerificationHarness],
    context: VerificationContext,
) -> list[HarnessRun]:
    runs: list[HarnessRun] = []
    for harness in harnesses:
        checks = tuple(harness.run(context))
        runs.append(
            HarnessRun(
                harness_id=harness.harness_id,
                layer=harness.layer,
                checks=checks,
            )
        )
    return runs


def flatten_harness_runs(runs: list[HarnessRun]) -> list[CheckResult]:
    return [check for run in runs for check in run.checks]
```

- [x] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_verification_harness.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/verification_harness.py tests/test_verification_harness.py
git commit -m "feat: add verification harness contract"
```

---

### Task 2: Statement-Note Harness

**Files:**
- Create: `src/dart_footing_reconciler/statement_note_harness.py`
- Create: `tests/test_statement_note_harness.py`

- [x] **Step 1: Write failing tests**

Create `tests/test_statement_note_harness.py`:

```python
from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.statement_note_harness import StatementNoteHarness
from dart_footing_reconciler.verification_harness import LAYER_STATEMENT_NOTE, VerificationContext


def _check(check_id: str, check_type: str) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type=check_type,
        status="matched",
        scope="report",
        note_no="1",
        title=check_id,
        expected=100,
        actual=100,
        difference=0,
        tolerance=1,
        reason="matched",
        evidence=[
            CheckEvidence("재무상태표", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석", 100, "note:1/table:0/row:1/col:1"),
        ],
    )


def test_statement_note_harness_exposes_layer_identity():
    harness = StatementNoteHarness()

    assert harness.harness_id == "statement_note"
    assert harness.layer == LAYER_STATEMENT_NOTE


def test_statement_note_harness_routes_cashflow_as_separate_strategy(monkeypatch):
    calls: list[str] = []

    def fake_reconciliation(report, *, tolerance):
        calls.append("reconciliation")
        return [
            _check("balance", "primary_balance_reconciliation"),
            _check("cashflow", "cashflow_reconciliation"),
            _check("expense", "expense_allocation"),
        ]

    def fake_bridges(report, *, tolerance):
        calls.append("bridges")
        return [_check("asset-bridge", "asset_note_bridge_check")]

    def fake_fs(report, *, tolerance):
        calls.append("fs")
        return [_check("fs-note", "fs_note_match")]

    def fake_cfs(report, *, tolerance):
        calls.append("cfs")
        return [_check("cfs-note", "cfs_note_match")]

    def fake_prior_column(report, *, tolerance):
        calls.append("prior-column")
        return [_check("prior-column", "prior_column_fs_note")]

    monkeypatch.setattr(
        "dart_footing_reconciler.statement_note_harness.check_reconciliation_targets",
        fake_reconciliation,
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.statement_note_harness.check_asset_note_bridges",
        fake_bridges,
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.statement_note_harness.check_fs_note_matches",
        fake_fs,
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.statement_note_harness.check_cfs_note_matches",
        fake_cfs,
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.statement_note_harness.check_prior_column_matches",
        fake_prior_column,
    )

    context = VerificationContext(FullReport("sample.html", "Sample", [], []), None, tolerance=1)
    checks = StatementNoteHarness().run(context)

    assert calls == ["reconciliation", "bridges", "fs", "cfs", "prior-column"]
    assert [check.check_type for check in checks] == [
        "primary_balance_reconciliation",
        "expense_allocation",
        "asset_note_bridge_check",
        "fs_note_match",
        "cashflow_reconciliation",
        "cfs_note_match",
        "prior_column_fs_note",
    ]
```

- [x] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_statement_note_harness.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'dart_footing_reconciler.statement_note_harness'`.

- [x] **Step 3: Implement statement-note harness**

Create `src/dart_footing_reconciler/statement_note_harness.py`:

```python
"""Financial statement body to note verification harness."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.checks_cfs_note import check_cfs_note_matches
from dart_footing_reconciler.checks_fs_note import check_fs_note_matches
from dart_footing_reconciler.checks_note_bridges import check_asset_note_bridges
from dart_footing_reconciler.checks_prior_column import check_prior_column_matches
from dart_footing_reconciler.checks_reconciliation import check_reconciliation_targets
from dart_footing_reconciler.verification_harness import LAYER_STATEMENT_NOTE, VerificationContext


class StatementNoteHarness:
    """Run checks that compare financial statement body lines to note content."""

    harness_id = "statement_note"
    layer = LAYER_STATEMENT_NOTE

    def run(self, context: VerificationContext) -> list[CheckResult]:
        reconciliation = check_reconciliation_targets(
            context.report,
            tolerance=context.tolerance,
        )
        results: list[CheckResult] = []
        results.extend(_non_cashflow_statement_note_checks(reconciliation))
        results.extend(check_asset_note_bridges(context.report, tolerance=context.tolerance))
        results.extend(check_fs_note_matches(context.report, tolerance=context.tolerance))
        results.extend(_cashflow_statement_note_checks(reconciliation))
        results.extend(check_cfs_note_matches(context.report, tolerance=context.tolerance))
        results.extend(check_prior_column_matches(context.report, tolerance=context.tolerance))
        return results


def _non_cashflow_statement_note_checks(checks: list[CheckResult]) -> list[CheckResult]:
    return [
        check
        for check in checks
        if check.check_type != "cashflow_reconciliation"
    ]


def _cashflow_statement_note_checks(checks: list[CheckResult]) -> list[CheckResult]:
    return [
        check
        for check in checks
        if check.check_type == "cashflow_reconciliation"
    ]
```

- [x] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_statement_note_harness.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/statement_note_harness.py tests/test_statement_note_harness.py
git commit -m "feat: add statement-note verification harness"
```

---

### Task 3: Note-Internal Harness

**Files:**
- Create: `src/dart_footing_reconciler/note_internal_harness.py`
- Create: `tests/test_note_internal_harness.py`

- [x] **Step 1: Write failing tests**

Create `tests/test_note_internal_harness.py`:

```python
from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport, ReportBlock, ReportSection, ReportTable, SourceLocation
from dart_footing_reconciler.note_internal_harness import NoteInternalHarness
from dart_footing_reconciler.verification_harness import LAYER_NOTE_INTERNAL, VerificationContext


def _check(check_id: str, check_type: str) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type=check_type,
        status="matched",
        scope="report",
        note_no="1",
        title=check_id,
        expected=100,
        actual=100,
        difference=0,
        tolerance=1,
        reason="matched",
        evidence=[CheckEvidence("주석", 100, "note:1/table:0/row:1/col:1")],
    )


def _report_with_note_table() -> FullReport:
    table = ReportTable(
        0,
        [["구분", "당기"], ["합계", "100"]],
        "1. 테스트 주석",
        SourceLocation("note:1", 0, 0),
    )
    note = ReportSection(
        "note:1",
        "테스트 주석",
        "note",
        "1",
        [ReportBlock("table", "", table, table.location)],
    )
    return FullReport("sample.html", "Sample", [], [note])


def test_note_internal_harness_exposes_layer_identity():
    harness = NoteInternalHarness()

    assert harness.harness_id == "note_internal"
    assert harness.layer == LAYER_NOTE_INTERNAL


def test_note_internal_harness_runs_note_content_checks(monkeypatch):
    calls: list[str] = []

    def fake_totals(table, *, note_no, tolerance):
        calls.append(f"totals:{note_no}")
        return [_check("total", "total_check")]

    def fake_assertions(report, *, tolerance):
        calls.append("assertions")
        return [_check("assertion", "note_rollforward_check")]

    def fake_formulas(report, *, tolerance):
        calls.append("formulas")
        return [_check("formula", "note_layout_formula_check")]

    def fake_note_note(report, *, tolerance):
        calls.append("note-note")
        return [_check("note-note", "note_note_match")]

    monkeypatch.setattr(
        "dart_footing_reconciler.note_internal_harness.check_table_totals",
        fake_totals,
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.note_internal_harness.check_note_assertions",
        fake_assertions,
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.note_internal_harness.check_layout_formula_assertions",
        fake_formulas,
    )
    monkeypatch.setattr(
        "dart_footing_reconciler.note_internal_harness.check_note_note_matches",
        fake_note_note,
    )

    context = VerificationContext(_report_with_note_table(), None, tolerance=1)
    checks = NoteInternalHarness().run(context)

    assert calls == ["totals:1", "assertions", "formulas", "note-note"]
    assert [check.check_type for check in checks] == [
        "total_check",
        "note_rollforward_check",
        "note_layout_formula_check",
        "note_note_match",
    ]
```

- [x] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_note_internal_harness.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'dart_footing_reconciler.note_internal_harness'`.

- [x] **Step 3: Implement note-internal harness**

Create `src/dart_footing_reconciler/note_internal_harness.py`:

```python
"""Note-content internal verification harness."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.checks_note_note import check_note_note_matches
from dart_footing_reconciler.checks_totals import check_table_totals
from dart_footing_reconciler.layout_formula_assertions import check_layout_formula_assertions
from dart_footing_reconciler.note_assertions import check_note_assertions
from dart_footing_reconciler.verification_harness import LAYER_NOTE_INTERNAL, VerificationContext


class NoteInternalHarness:
    """Run checks whose evidence and arithmetic live inside note contents."""

    harness_id = "note_internal"
    layer = LAYER_NOTE_INTERNAL

    def run(self, context: VerificationContext) -> list[CheckResult]:
        results: list[CheckResult] = []
        for note in context.report.notes:
            for block in note.blocks:
                if block.table is not None:
                    results.extend(
                        check_table_totals(
                            block.table,
                            note_no=note.note_no,
                            tolerance=context.tolerance,
                        )
                    )
        results.extend(check_note_assertions(context.report, tolerance=context.tolerance))
        results.extend(check_layout_formula_assertions(context.report, tolerance=context.tolerance))
        results.extend(check_note_note_matches(context.report, tolerance=context.tolerance))
        return results
```

- [x] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_note_internal_harness.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/note_internal_harness.py tests/test_note_internal_harness.py
git commit -m "feat: add note-internal verification harness"
```

---

### Task 4: Supporting Harnesses

**Files:**
- Create: `src/dart_footing_reconciler/supporting_harnesses.py`
- Create: `tests/test_supporting_harnesses.py`

- [x] **Step 1: Write failing tests**

Create `tests/test_supporting_harnesses.py`:

```python
from dart_footing_reconciler.checks import CheckEvidence, CheckResult
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.supporting_harnesses import PriorReportHarness, StatementCrossHarness
from dart_footing_reconciler.verification_harness import (
    LAYER_PRIOR_REPORT,
    LAYER_STATEMENT_CROSS,
    VerificationContext,
)


def _check(check_id: str, check_type: str) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        check_type=check_type,
        status="matched",
        scope="report",
        note_no="",
        title=check_id,
        expected=100,
        actual=100,
        difference=0,
        tolerance=1,
        reason="matched",
        evidence=[CheckEvidence("본문", 100, "statement:bs/table:0/row:1/col:1")],
    )


def test_statement_cross_harness_wraps_statement_ties(monkeypatch):
    def fake_statement_ties(report, *, tolerance):
        return [_check("bs-equation", "statement_bs_equation")]

    monkeypatch.setattr(
        "dart_footing_reconciler.supporting_harnesses.check_statement_ties",
        fake_statement_ties,
    )

    context = VerificationContext(FullReport("sample.html", "Sample", [], []), None, tolerance=1)
    harness = StatementCrossHarness()

    assert harness.harness_id == "statement_cross"
    assert harness.layer == LAYER_STATEMENT_CROSS
    assert [check.check_type for check in harness.run(context)] == ["statement_bs_equation"]


def test_prior_report_harness_skips_when_prior_report_is_missing(monkeypatch):
    called = False

    def fake_prior(current_report, prior_report, *, tolerance):
        nonlocal called
        called = True
        return [_check("prior", "prior_year_beginning_balance_match")]

    monkeypatch.setattr(
        "dart_footing_reconciler.supporting_harnesses.check_prior_year_reconciliation",
        fake_prior,
    )

    context = VerificationContext(FullReport("sample.html", "Sample", [], []), None, tolerance=1)
    harness = PriorReportHarness()

    assert harness.harness_id == "prior_report"
    assert harness.layer == LAYER_PRIOR_REPORT
    assert harness.run(context) == []
    assert called is False


def test_prior_report_harness_runs_when_prior_report_exists(monkeypatch):
    def fake_prior(current_report, prior_report, *, tolerance):
        return [_check("prior", "prior_year_beginning_balance_match")]

    monkeypatch.setattr(
        "dart_footing_reconciler.supporting_harnesses.check_prior_year_reconciliation",
        fake_prior,
    )

    current = FullReport("current.html", "Sample", [], [])
    prior = FullReport("prior.html", "Sample", [], [])
    context = VerificationContext(current, prior, tolerance=1)

    assert [check.check_type for check in PriorReportHarness().run(context)] == [
        "prior_year_beginning_balance_match"
    ]
```

- [x] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_supporting_harnesses.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'dart_footing_reconciler.supporting_harnesses'`.

- [x] **Step 3: Implement supporting harnesses**

Create `src/dart_footing_reconciler/supporting_harnesses.py`:

```python
"""Supporting verification harnesses outside the two primary note domains."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.checks_prior_year import check_prior_year_reconciliation
from dart_footing_reconciler.checks_statement_ties import check_statement_ties
from dart_footing_reconciler.verification_harness import (
    LAYER_PRIOR_REPORT,
    LAYER_STATEMENT_CROSS,
    VerificationContext,
)


class StatementCrossHarness:
    """Run financial statement body to financial statement body checks."""

    harness_id = "statement_cross"
    layer = LAYER_STATEMENT_CROSS

    def run(self, context: VerificationContext) -> list[CheckResult]:
        return check_statement_ties(context.report, tolerance=context.tolerance)


class PriorReportHarness:
    """Run current filing to prior filing checks only when a prior report exists."""

    harness_id = "prior_report"
    layer = LAYER_PRIOR_REPORT

    def run(self, context: VerificationContext) -> list[CheckResult]:
        if context.prior_report is None:
            return []
        return check_prior_year_reconciliation(
            context.report,
            context.prior_report,
            tolerance=context.tolerance,
        )
```

- [x] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_supporting_harnesses.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/supporting_harnesses.py tests/test_supporting_harnesses.py
git commit -m "feat: add supporting verification harnesses"
```

---

### Task 5: Migrate Check Pipeline To Harness Runner

**Files:**
- Modify: `src/dart_footing_reconciler/check_pipeline.py`
- Modify: `tests/test_check_pipeline.py`

- [x] **Step 1: Add failing pipeline harness tests**

Append to `tests/test_check_pipeline.py`:

```python
from dart_footing_reconciler.check_pipeline import assemble_report_harness_runs


def test_assemble_report_harness_runs_exposes_primary_layers():
    report = parse_full_report(INVENI)
    runs = assemble_report_harness_runs(report, None, tolerance=1)

    layer_by_id = {run.harness_id: run.layer for run in runs}
    assert layer_by_id["statement_note"] == "statement_note"
    assert layer_by_id["note_internal"] == "note_internal"
    assert layer_by_id["statement_cross"] == "statement_cross"
    assert layer_by_id["prior_report"] == "prior_report"


def test_assemble_report_checks_flattens_harness_runs():
    report = parse_full_report(INVENI)
    flattened = _norm(assemble_report_checks(report, None, tolerance=1))
    from_runs = _norm(
        [
            check
            for run in assemble_report_harness_runs(report, None, tolerance=1)
            for check in run.checks
        ]
    )

    assert flattened == from_runs
```

- [x] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_check_pipeline.py::test_assemble_report_harness_runs_exposes_primary_layers tests/test_check_pipeline.py::test_assemble_report_checks_flattens_harness_runs -q
```

Expected: fails with `ImportError` for `assemble_report_harness_runs`.

- [x] **Step 3: Replace flat pipeline with harness assembly**

Replace `src/dart_footing_reconciler/check_pipeline.py` with:

```python
"""Shared report check assembly through verification harnesses."""

from __future__ import annotations

from dart_footing_reconciler.checks import CheckResult
from dart_footing_reconciler.document import FullReport
from dart_footing_reconciler.note_internal_harness import NoteInternalHarness
from dart_footing_reconciler.statement_note_harness import StatementNoteHarness
from dart_footing_reconciler.supporting_harnesses import PriorReportHarness, StatementCrossHarness
from dart_footing_reconciler.verification_harness import (
    HarnessRun,
    VerificationContext,
    VerificationHarness,
    flatten_harness_runs,
    run_harnesses,
)


def default_report_harnesses() -> list[VerificationHarness]:
    return [
        StatementCrossHarness(),
        NoteInternalHarness(),
        StatementNoteHarness(),
        PriorReportHarness(),
    ]


def assemble_report_harness_runs(
    report: FullReport,
    prior_report: FullReport | None,
    *,
    tolerance: int,
) -> list[HarnessRun]:
    context = VerificationContext(
        report=report,
        prior_report=prior_report,
        tolerance=tolerance,
    )
    return run_harnesses(default_report_harnesses(), context)


def assemble_report_checks(
    report: FullReport,
    prior_report: FullReport | None,
    *,
    tolerance: int,
) -> list[CheckResult]:
    return flatten_harness_runs(
        assemble_report_harness_runs(
            report,
            prior_report,
            tolerance=tolerance,
        )
    )
```

- [x] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_check_pipeline.py -q
```

Expected: all `test_check_pipeline.py` tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/check_pipeline.py tests/test_check_pipeline.py
git commit -m "refactor: assemble checks through verification harnesses"
```

---

### Task 6: Layer-Aware Report Classification Helper

**Files:**
- Modify: `src/dart_footing_reconciler/report_frame.py`
- Modify: `tests/test_report_frame.py`

- [x] **Step 1: Add report-frame regression tests**

Append to `tests/test_report_frame.py`:

```python
from dart_footing_reconciler.report_frame import check_layer


def test_report_frame_classifies_statement_note_layer():
    check = CheckResult(
        "fs-note",
        "fs_note_match",
        "matched",
        "report",
        "11",
        "FS-note match",
        100,
        100,
        0,
        1,
        "matched",
        [
            CheckEvidence("재무상태표", 100, "statement:bs/table:0/row:1/col:1"),
            CheckEvidence("주석", 100, "note:11/table:0/row:1/col:1"),
        ],
    )

    assert check_layer(check) == "statement_note"


def test_report_frame_classifies_note_internal_layer():
    check = CheckResult(
        "total",
        "total_check",
        "matched",
        "table",
        "11",
        "주석 합계 검증",
        100,
        100,
        0,
        1,
        "matched",
        [CheckEvidence("합계", 100, "note:11/table:0/row:1/col:1")],
    )

    assert check_layer(check) == "note_internal"
```

- [x] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_report_frame.py::test_report_frame_classifies_statement_note_layer tests/test_report_frame.py::test_report_frame_classifies_note_internal_layer -q
```

Expected: fails with `ImportError` for `check_layer`.

- [x] **Step 3: Add layer helper to `report_frame.py`**

Add this function above `check_group` in `src/dart_footing_reconciler/report_frame.py`:

```python
def check_layer(check: CheckResult) -> str:
    if check.check_type in {
        "primary_balance_reconciliation",
        "cashflow_reconciliation",
        "fs_note_match",
        "cfs_note_match",
        "asset_note_bridge_check",
        "expense_allocation",
        "prior_column_fs_note",
    }:
        return "statement_note"
    if check.check_type in {
        "total_check",
        "note_rollforward_check",
        "note_balance_bridge_check",
        "note_internal_consistency_check",
        "note_layout_formula_check",
        "note_note_match",
        "note_note_reconciliation",
        "prior_column_rollforward",
    }:
        return "note_internal"
    if check.check_type in {
        "statement_bs_equation",
        "statement_cash_tie",
        "statement_equity_tie",
    }:
        return "statement_cross"
    if check.check_type == "prior_year_beginning_balance_match":
        return "prior_report"
    sources = [evidence.source for evidence in check.evidence]
    if any(source.startswith("statement:") for source in sources) and any(
        source.startswith("note:") for source in sources
    ):
        return "statement_note"
    if all(source.startswith("note:") for source in sources if source):
        return "note_internal"
    return "unknown"
```

Do not change `check_group` in this task. This adds layer observability without changing existing rendered group labels.

- [x] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_report_frame.py::test_report_frame_classifies_statement_note_layer tests/test_report_frame.py::test_report_frame_classifies_note_internal_layer -q
uv run pytest tests/test_report_frame.py -q
```

Expected: report-frame tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/report_frame.py tests/test_report_frame.py
git commit -m "feat: expose report check layer classification"
```

---

### Task 7: Shared Design-Kit Contract For Audit Verification UI

**Files:**
- Modify: `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/dashboard-cockpit-kit.md`
- Modify: `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/cockpit-app-shell-kit.md`
- Modify: `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript/src/cockpitProfiles.ts`
- Modify: `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript/tests/validateArtifact.test.ts`

- [x] **Step 1: Add failing design-kit adapter test**

Append to `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript/tests/validateArtifact.test.ts`:

```typescript
test("evidence cockpit exposes audit verification report optional tabs", () => {
  assert.ok(cockpitProfiles.evidence_cockpit.optionalTabs.includes("보고서 순서"));
  assert.ok(cockpitProfiles.evidence_cockpit.optionalTabs.includes("검증 범위"));
});
```

- [x] **Step 2: Run RED**

Run:

```bash
npm --prefix /Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript test
```

Expected: fails because `보고서 순서` and `검증 범위` are not yet included in `evidence_cockpit.optionalTabs`.

- [x] **Step 3: Add optional tabs without creating a new profile**

In `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript/src/cockpitProfiles.ts`, replace the `evidence_cockpit` object with:

```typescript
  evidence_cockpit: {
    profile: "evidence_cockpit",
    labelKo: "근거 검토 Cockpit",
    intentKo: "근거, 원문, 검증 상태, 갭을 중심으로 판단",
    requiredTabs: commonCockpitTabs,
    optionalTabs: ["원문", "검증상태", "미해결 갭", "보고서 순서", "검증 범위", "기술 세부정보"],
  },
```

This is an additive profile extension. Do not add a new `audit_verification_cockpit` profile in this plan.

- [x] **Step 4: Add DART audit verification guidance to cockpit docs**

In `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/dashboard-cockpit-kit.md`, add this subsection under `### evidence_cockpit` after the optional tabs list:

```markdown
Audit verification report variant:

- Keep `evidence_cockpit`; do not create a separate DART-specific profile.
- Present validation results in company report order: 재무상태표, 손익계산서, 자본변동표, 현금흐름표, 주석.
- Use reader-facing `검증 범위` labels for row-level scope: `재무제표 본문-주석`, `주석 내부`, `재무제표 본문 간`, `전기 보고서`.
- Every finding row needs `검증 항목`, `기준 금액`, `확인 금액`, `차이`, `상태`, `판단 근거`, `근거 위치`, and `다음 행동` either in the row or one-click drilldown.
- Keep internal terms such as `harness`, `layer`, `check_type`, and raw source ids outside the primary reading surface; expose them only under `기술 세부정보` when needed.
```

In `/Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/cockpit-app-shell-kit.md`, replace the `## DART footing` paragraph with:

```markdown
## DART footing

DART footing uses the `evidence_cockpit` profile. Keep audit evidence, source
references, review queue, and note drawer dense and visible. The app shell
should organize workpaper navigation, not make the report feel like a marketing
site.

For audit verification reports, the main reading order follows the source
company report: 재무상태표, 손익계산서, 자본변동표, 현금흐름표, 주석. Row-level
scope appears as `검증 범위`; keep implementation words such as `harness` and
`layer` out of primary UI labels.
```

- [x] **Step 5: Run design-kit verification**

Run:

```bash
npm --prefix /Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript run typecheck
npm --prefix /Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript test
python3 /Users/kjun/vault/Harness/scripts/check_design_kit.py
```

Expected:

- TypeScript typecheck passes.
- TypeScript tests pass.
- `check_design_kit.py` prints `design kit verify ok`.

- [ ] **Step 6: Commit shared design-kit changes in the vault root repo**

Run:

```bash
git -C /Users/kjun/vault add \
  01_Projects/00_personal_agent_system/design-kit/dashboard-cockpit-kit.md \
  01_Projects/00_personal_agent_system/design-kit/cockpit-app-shell-kit.md \
  01_Projects/00_personal_agent_system/design-kit/typescript/src/cockpitProfiles.ts \
  01_Projects/00_personal_agent_system/design-kit/typescript/tests/validateArtifact.test.ts
git -C /Users/kjun/vault commit -m "feat: extend evidence cockpit for audit verification reports"
```

---

### Task 8: Report UI Validation Scope Labels

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Modify: `tests/test_cli_workpaper.py`

- [x] **Step 1: Add failing HTML regression test**

Append to `tests/test_cli_workpaper.py`:

```python
def test_html_report_shows_reader_facing_verification_scope_labels():
    statements = [
        _section(
            "statement:bs",
            "재무상태표",
            "statement",
            "",
            ReportTable(0, [["구분", "당기"], ["유형자산", "100"]], "재무상태표", SourceLocation("statement:bs", 0, 0)),
        )
    ]
    notes = [
        _section(
            "note:11",
            "유형자산",
            "note",
            "11",
            ReportTable(0, [["구분", "당기", "합계"], ["장부금액", "100", "100"]], "유형자산", SourceLocation("note:11", 0, 0)),
        )
    ]
    checks = [
        CheckResult(
            "bs-note",
            "primary_balance_reconciliation",
            "matched",
            "report",
            "11",
            "property_plant_equipment.balance",
            100,
            100,
            0,
            0,
            "financial statement line agrees to note ending balance",
            [
                CheckEvidence("재무상태표 유형자산", 100, "statement:bs/table:0/row:1/col:1"),
                CheckEvidence("주석 11 장부금액", 100, "note:11/table:0/row:1/col:1"),
            ],
        ),
        CheckResult(
            "total",
            "total_check",
            "matched",
            "note",
            "11",
            "장부금액 row total",
            100,
            100,
            0,
            0,
            "row total agrees",
            [CheckEvidence("장부금액", 100, "note:11/table:0/row:1/col:2")],
        ),
    ]

    html = render_audit_reconciliation_html(FullReport("sample.html", "Sample Co", statements, notes), checks)

    assert "검증 범위" in html
    assert "재무제표 본문-주석" in html
    assert "주석 내부" in html
    assert "원천 금액이 허용 차이 이내로 대사 완료됨." in html
    assert "harness" not in html.lower()
```

- [x] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_cli_workpaper.py::test_html_report_shows_reader_facing_verification_scope_labels -q
```

Expected: fails because the report table does not yet render `검증 범위`.

- [x] **Step 3: Render scope labels from `check_layer`**

In `src/dart_footing_reconciler/report_html.py`, add `check_layer` to the import from `dart_footing_reconciler.report_frame`:

```python
from dart_footing_reconciler.report_frame import (
    CANONICAL_STATEMENT_ORDER,
    CHECK_GROUP_ORDER,
    SourceTableFrame,
    build_report_frame,
    check_layer,
    statement_kind_from_source,
    statement_kind_from_title,
)
```

In `_report_frame_check_groups_html`, add `검증 범위` before `검증 항목` and `다음 행동` before `판단 근거`:

```python
                      <th>검증 범위</th>
                      <th>검증 항목</th>
                      <th>기준 금액</th>
                      <th>확인 금액</th>
                      <th>차이</th>
                      <th>상태</th>
                      <th>다음 행동</th>
                      <th>판단 근거</th>
                      <th>근거 위치</th>
```

In `_report_frame_check_row`, add the scope cell before the title cell and the action cell before the reason cell:

```python
        <td>{escape(_check_layer_label(check))}</td>
        <td>{escape(_report_frame_check_title(group, check))}</td>
        <td class="num">{_amount(check.expected)}</td>
        <td class="num">{_amount(check.actual)}</td>
        <td class="num">{_amount(check.difference)}</td>
        <td><span class="status {status_class}">{escape(status)}</span></td>
        <td class="review-action">{_review_action_cell(check)}</td>
        <td>{_reason_cell(check)}</td>
        <td class="source">{_source_cell(check)}</td>
```

Add this helper near `_report_frame_check_group_label`:

```python
def _check_layer_label(check: CheckResult) -> str:
    return {
        "statement_note": "재무제표 본문-주석",
        "note_internal": "주석 내부",
        "statement_cross": "재무제표 본문 간",
        "prior_report": "전기 보고서",
    }.get(check_layer(check), "기타")
```

- [x] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_cli_workpaper.py::test_html_report_shows_reader_facing_verification_scope_labels tests/test_cli_workpaper.py::test_html_report_renders_validations_in_report_form_order -q
```

Expected: both tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dart_footing_reconciler/report_html.py tests/test_cli_workpaper.py
git commit -m "feat: show verification scope in audit report"
```

---

### Task 9: Accuracy Evaluation Strategy Contract

**Files:**
- Create: `docs/validation/verification-accuracy-strategy.md`
- Create: `tests/test_validation_docs.py`

- [x] **Step 1: Add failing doc contract test**

Create `tests/test_validation_docs.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_accuracy_strategy_separates_report_volume_from_accuracy():
    text = (ROOT / "docs/validation/verification-accuracy-strategy.md").read_text(encoding="utf-8")

    assert "보고서 수는 정확도 지표가 아니다" in text
    for required in [
        "Gold Set",
        "Stratified Smoke",
        "Broad Corpus",
        "Adversarial Set",
        "false-match rate",
        "재무제표 본문-주석",
        "주석 내부",
        "현금흐름표-주석",
    ]:
        assert required in text
```

- [x] **Step 2: Run RED**

Run:

```bash
uv run pytest tests/test_validation_docs.py -q
```

Expected: fails with `FileNotFoundError` for `docs/validation/verification-accuracy-strategy.md`.

- [x] **Step 3: Create accuracy strategy document**

Create `docs/validation/verification-accuracy-strategy.md`:

```markdown
# Verification Accuracy Strategy

## Position

보고서 수는 정확도 지표가 아니다. More reports improve layout coverage,
industry variety, and regression discovery only when the corpus is stratified
and each evaluation tier has a clear purpose. Accuracy claims require reviewed
expectations, source evidence, and false-match review.

## Test Set Tiers

### Gold Set

Use 20-30 reviewed filings with expected primary outcomes. Each sample records
company, industry, report year, source file, expected validation outcomes,
reviewed evidence location, and reviewer note. This set measures accuracy.

### Stratified Smoke

Use 10-20 cached nonfinancial filings across different industries. This set
guards parser/render/harness regressions after every substantial change. The
2026-06-10 nonfinancial 10-company manifest is the first smoke set.

### Broad Corpus

Use 100+ cached filings to discover format drift, layout families, unknown
tables, and performance regressions. This set is not an accuracy score by
itself because most rows are not manually labeled.

### Adversarial Set

Use manually reviewed edge cases for false positives: sign reversals,
non-cash movements, subtotal rows, prior-year columns, duplicate labels,
mixed units, disclosure-only tables, and ambiguous note references.

## Metrics

- false-match rate: matched results whose evidence does not support the
  conclusion. This is the highest-risk metric.
- primary no-difference rate: primary checks with zero or tolerated difference.
- reviewed accuracy rate: labeled Gold Set checks where the automated judgment
  equals the reviewed expectation.
- parse-uncertain rate: checks blocked by source extraction or table-shape
  uncertainty.
- validation-relevant unknown layout count: unknown tables that likely affect
  validation.
- evidence completeness rate: checks that retain source locations for every
  material amount.
- layer-level rates: measure `재무제표 본문-주석`, `주석 내부`,
  `현금흐름표-주석`, `재무제표 본문 간`, and `전기 보고서` separately.

## Promotion Policy

A rule change can improve coverage only if it does not increase false matches
in the Gold Set or Adversarial Set. A higher match rate alone is not accepted.
Every accepted improvement must preserve source location, label uncertainty,
and a reviewer-readable next action for unresolved items.

## Near-Term Expansion

Keep the current nonfinancial 10-company smoke set for every harness/UI change.
Build the Gold Set next by reviewing representative samples from manufacturing,
automotive, biopharma, retail, construction, energy, logistics, software,
chemicals, and shipbuilding. Expand the Broad Corpus only after the Gold Set
can distinguish true accuracy gains from parser coverage gains.
```

- [x] **Step 4: Run GREEN**

Run:

```bash
uv run pytest tests/test_validation_docs.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add docs/validation/verification-accuracy-strategy.md tests/test_validation_docs.py
git commit -m "docs: define verification accuracy evaluation strategy"
```

---

### Task 10: Verification And 10-Company Corpus Smoke

**Files:**
- Modify: `docs/validation/2026-06-10-nonfinancial-industry-10.md`
- Read: `out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json`

- [x] **Step 1: Run focused harness and report UI tests**

Run:

```bash
uv run pytest \
  tests/test_verification_harness.py \
  tests/test_statement_note_harness.py \
  tests/test_note_internal_harness.py \
  tests/test_supporting_harnesses.py \
  tests/test_check_pipeline.py \
  tests/test_report_frame.py \
  tests/test_cli_workpaper.py::test_html_report_shows_reader_facing_verification_scope_labels \
  tests/test_validation_docs.py \
  -q
```

Expected: all selected tests pass.

- [x] **Step 2: Run design-kit gates**

Run:

```bash
npm --prefix /Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript run typecheck
npm --prefix /Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript test
python3 /Users/kjun/vault/Harness/scripts/check_design_kit.py
```

Expected:

- TypeScript typecheck passes.
- TypeScript tests pass.
- `check_design_kit.py` prints `design kit verify ok`.

- [x] **Step 3: Run full test suite**

Run:

```bash
uv run pytest -q
```

Expected: full suite passes.

- [x] **Step 4: Run nonfinancial 10-company no-fetch corpus**

Run:

```bash
uv run dart-footing workpaper-corpus \
  out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json \
  out/corpus/run_2026-06-10-harness-layer-nonfinancial-10 \
  --no-fetch
```

Expected command output includes:

```text
Generated 10/10 reports.
```

- [x] **Step 5: Extract corpus summary**

Run:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("out/corpus/run_2026-06-10-harness-layer-nonfinancial-10/corpus_result.json").read_text())
print(payload["summary"])
PY
```

Expected:

- `generated_reports` is `10`.
- `failed_samples` is `0`.
- No exception is raised while reading `corpus_result.json`.

- [x] **Step 6: Append validation note**

Append this section to `docs/validation/2026-06-10-nonfinancial-industry-10.md`:

````markdown
## Harness Layer Follow-Up

The verification pipeline was migrated from flat check assembly to internal
harness execution. The public `assemble_report_checks` output remains
`list[CheckResult]`, while `assemble_report_harness_runs` now exposes the
execution layers:

- `statement_note`: financial statement body ↔ note validation
- `note_internal`: validation inside note contents
- `statement_cross`: financial statement body ↔ financial statement body
- `prior_report`: current filing ↔ prior filing when provided

The report UI continues to use the shared `evidence_cockpit` app-shell contract
and now exposes reader-facing `검증 범위` labels instead of internal harness
terms.

Accuracy strategy note:

- Report count is a coverage and regression tool, not an accuracy metric.
- Accuracy claims require a reviewed Gold Set and false-match review.
- The 10-company nonfinancial corpus remains the Stratified Smoke set.

Post-migration verification:

```bash
npm --prefix /Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript run typecheck
npm --prefix /Users/kjun/vault/01_Projects/00_personal_agent_system/design-kit/typescript test
python3 /Users/kjun/vault/Harness/scripts/check_design_kit.py
uv run pytest -q
uv run dart-footing workpaper-corpus out/corpus/manifest_2026-06-10-nonfinancial-industry-10.json out/corpus/run_2026-06-10-harness-layer-nonfinancial-10 --no-fetch
```

Expected corpus gate: 10/10 generated, 0 failed samples.
````

- [ ] **Step 7: Commit**

Run:

```bash
git add docs/validation/2026-06-10-nonfinancial-industry-10.md
git commit -m "docs: record harness layer validation"
```

---

## Acceptance Criteria

- `assemble_report_checks()` remains the stable public assembly API for CLI and corpus callers.
- A new `assemble_report_harness_runs()` API exposes harness-level execution metadata.
- `VerificationContext` can carry semantic candidates without requiring all callers to provide them.
- Financial statement body ↔ note checks are executed through `StatementNoteHarness`.
- Cash-flow statement ↔ note checks remain inside `StatementNoteHarness` but are separated as a cash-flow strategy.
- Note-content checks are executed through `NoteInternalHarness`.
- Statement-to-statement and prior-report checks are explicit supporting harnesses.
- `CheckResult` dataclass is unchanged.
- Existing CLI and corpus callers do not need to change.
- Shared design-kit `evidence_cockpit` guidance includes DART audit verification report order and reader-facing `검증 범위` labels.
- The HTML report keeps source company report order and shows `검증 범위` plus `다음 행동` in validation rows without exposing `harness` as primary UI copy.
- `docs/validation/verification-accuracy-strategy.md` states that report count is not an accuracy metric and defines Gold Set, Stratified Smoke, Broad Corpus, Adversarial Set, false-match rate, and layer-level metrics.
- Focused harness tests pass.
- Design-kit TypeScript typecheck/tests and `check_design_kit.py` pass.
- Full `uv run pytest -q` passes.
- The existing nonfinancial 10-company no-fetch corpus gate generates 10/10 reports with 0 failed samples.

## Self-Review

- Spec coverage: 재무제표 본문↔주석 and 주석 내부 are explicit harness layers; cash-flow validation is a separate strategy inside statement-note; existing statement-cross and prior-report behavior remains visible. UI propagation and accuracy-evaluation policy are now covered by explicit tasks.
- Placeholder scan: no `TBD`, no vague "handle edge cases", no references to undefined types.
- Type consistency: `VerificationContext`, `VerificationHarness`, and `HarnessRun` are defined before use; `StatementNoteHarness`, `NoteInternalHarness`, `StatementCrossHarness`, and `PriorReportHarness` all implement `run(context) -> list[CheckResult]`.
- Interface stability: `CheckResult` and `assemble_report_checks()` stay backward compatible; new metadata is additive through `assemble_report_harness_runs()`. The shared cockpit contract is extended through optional tabs and guidance rather than a new profile.
