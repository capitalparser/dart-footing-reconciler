# Statement Note Row Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one source-backed amount reconciliation result for every financial-statement row that displays note references, then render an auditor-friendly drawer with the comparison, note roles, and explicit next action.

**Architecture:** Restore row-scoped note-reference facts in the semantic layer, then add a focused `StatementNoteReferenceHarness` that converts each referenced statement row into one result. Candidate note amounts are restricted to the displayed note numbers and ranked by account context and balance role without using amount equality as a pass criterion. The existing report frame routes the new check to the drawer; a specialized renderer presents reconciliation and related-note evidence in reviewer language.

**Tech Stack:** Python 3.12, dataclasses, existing DART parser/taxonomy/check harnesses, server-rendered HTML/CSS/JavaScript, pytest, Ruff, Vitest.

## Global Constraints

- Footing and cash flow reconciliation remain separate checks.
- Every material amount preserves exact source location.
- Label mapping uncertainty remains explicit through confidence and evidence.
- The engine runs without MCP and without React or Next.js.
- One material statement row with displayed note references produces one row-level result, not one result per note.
- Displayed note numbers are the only note search scope; no undisclosed note is inferred.
- Topic-only evidence never produces an amount-match verdict.
- Do not run git commands in this workspace.

---

### Task 1: Row-scoped note-reference semantic facts

**Files:**
- Modify: `src/dart_footing_reconciler/note_reference_validator.py`
- Modify: `src/dart_footing_reconciler/semantic_layer.py`
- Modify: `tests/test_note_reference_validator.py`
- Modify: `tests/test_semantic_layer.py`

**Interfaces:**
- Produces: `extract_note_ref_tokens(text: str) -> list[str]`
- Produces: `extract_plain_note_ref_tokens(text: str) -> list[str]`
- Produces: `SemanticNoteReferenceFact`
- Produces: `SemanticDataset.note_references_for_row(source: str) -> tuple[SemanticNoteReferenceFact, ...]`

- [ ] **Step 1: Write failing extraction tests**

```python
def test_extract_note_ref_tokens_supports_compact_multiple_refs_without_share_false_positive():
    assert extract_note_ref_tokens("유형자산 (주3,10,20)") == ["3", "10", "20"]
    assert extract_note_ref_tokens("보통주 3,343,585주") == []
    assert extract_note_ref_tokens("[주1]") == []


def test_extract_plain_note_ref_tokens_is_strictly_number_only():
    assert extract_plain_note_ref_tokens("5, 17") == ["5", "17"]
    assert extract_plain_note_ref_tokens("금액 5") == []
```

- [ ] **Step 2: Run extraction tests and confirm RED**

Run: `uv run pytest -q tests/test_note_reference_validator.py -k "note_ref_tokens or plain_note_ref"`

Expected: import or assertion failure because the reusable token functions are absent.

- [ ] **Step 3: Add shared guarded token extraction**

Implement keyword matching for `주`, `주석`, and `註`, normalize subnote tokens to their leading number, accept compact multiple-number separators, and keep plain-number parsing available only to callers that have already established a note-reference column.

```python
def extract_note_ref_tokens(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _PATTERN_NOTE_REF.finditer(text or ""):
        for token in _tokens_from_number_group(match.group(1)):
            if token not in seen:
                seen.add(token)
                found.append(token)
    return found


def extract_plain_note_ref_tokens(text: str) -> list[str]:
    if not _PLAIN_NOTE_NUMBER_GROUP_RE.fullmatch(text or ""):
        return []
    return _tokens_from_number_group(text)
```

- [ ] **Step 4: Write failing semantic-coordinate test**

```python
def test_semantic_dataset_indexes_inline_and_dedicated_column_refs_by_statement_row():
    statement = _section(
        "statement:bs", "재무상태표", "statement", "",
        _table("statement:bs", 0, [["구분", "주석", "당기"], ["유형자산 (주20)", "10", "100"]], "재무상태표"),
    )
    dataset = build_semantic_dataset(FullReport("s.html", "Co", [statement], []))
    refs = dataset.note_references_for_row("statement:bs/table:0/row:1/col:2")
    assert [(ref.note_no, ref.cell_source) for ref in refs] == [
        ("20", "statement:bs/table:0/row:1/col:0"),
        ("10", "statement:bs/table:0/row:1/col:1"),
    ]
```

- [ ] **Step 5: Run the semantic test and confirm RED**

Run: `uv run pytest -q tests/test_semantic_layer.py -k note_reference`

Expected: failure because `SemanticDataset` has no row-scoped reference index.

- [ ] **Step 6: Add the semantic fact and row index**

Add `SemanticNoteReferenceFact`, collect references for every source table, store them on `SemanticDataset`, and index by the normalized `.../table:N/row:R` source. Exact `cell_source` must be the cell that displayed the reference.

- [ ] **Step 7: Run focused tests and confirm GREEN**

Run: `uv run pytest -q tests/test_note_reference_validator.py tests/test_semantic_layer.py`

Expected: all tests pass.

### Task 2: One-result-per-statement-row amount reconciliation

**Files:**
- Create: `src/dart_footing_reconciler/statement_note_reference_harness.py`
- Create: `tests/test_statement_note_reference_harness.py`

**Interfaces:**
- Consumes: `SemanticDataset.note_references_for_row`
- Consumes: `classify_report(report) -> ClassifiedReport`
- Produces: `check_statement_note_references(report: FullReport, *, tolerance: int = 0, consolidation_basis: str = "unknown") -> list[CheckResult]`
- Produces: `StatementNoteReferenceHarness.run(context: VerificationContext) -> list[CheckResult]`
- Produces one check type: `statement_note_row_reconciliation`
- Evidence roles: `statement_amount`, `displayed_note_reference`, `note_amount`, `related_note_reference`, `candidate_note_amount`

- [ ] **Step 1: Write failing matched and mismatch tests**

```python
def test_row_reconciliation_uses_displayed_note_amount_and_emits_one_result():
    report = _report(
        statement_rows=[["유형자산 (주10,20)", "100"]],
        notes=[_note("10", "유형자산", [["구분", "당기"], ["기말 장부금액", "100"]]),
               _note("20", "약정사항", [["구분", "내용"], ["담보", "유형자산"]])],
    )
    checks = check_statement_note_references(report, tolerance=1)
    assert len(checks) == 1
    assert checks[0].status == MATCHED
    assert (checks[0].expected, checks[0].actual, checks[0].difference) == (100, 100, 0)
    assert {item.role for item in checks[0].evidence} >= {
        "statement_amount", "displayed_note_reference", "note_amount", "related_note_reference"
    }


def test_row_reconciliation_reports_numeric_mismatch_without_selecting_by_equality():
    report = _report(
        statement_rows=[["유형자산 (주10)", "100"]],
        notes=[_note("10", "유형자산", [["구분", "당기"], ["기말 장부금액", "120"]])],
    )
    check = check_statement_note_references(report, tolerance=1)[0]
    assert check.status == UNEXPLAINED_GAP
    assert (check.expected, check.actual, check.difference) == (100, 120, -20)
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `uv run pytest -q tests/test_statement_note_reference_harness.py -k "uses_displayed or numeric_mismatch"`

Expected: module import failure.

- [ ] **Step 3: Implement row extraction and candidate ranking**

Build rows from semantic references rather than taxonomy membership so unclassified-but-material rows are retained. Attach a classified line when available; otherwise use the source label as `account_key="unknown"`. Restrict note candidates to `displayed_note_numbers`.

Use a deterministic rank tuple based on direct normalized label overlap, account-key match, balance-role suitability, current-period suitability, and confidence. Do not include equality with the statement amount in the rank.

- [ ] **Step 4: Implement numeric result construction**

For a single top-ranked amount, set `expected` to the statement amount, `actual` to the note amount, and `difference = expected - actual`. Use the statement amount cell and note amount cell as exact evidence sources. Add every displayed note reference; mark non-selected existing references as `related_note_reference`.

- [ ] **Step 5: Write failing uncertainty and coverage tests**

```python
def test_row_reconciliation_does_not_pick_between_equal_rank_amounts():
    check = check_statement_note_references(_ambiguous_report(), tolerance=1)[0]
    assert check.status == PARSE_UNCERTAIN
    assert check.actual is None
    assert check.parse_uncertain_reason == "AMBIGUOUS_MULTIPLE"
    assert sum(e.role == "candidate_note_amount" for e in check.evidence) == 2


def test_every_material_statement_row_with_refs_gets_exactly_one_result_even_without_taxonomy():
    report = _report(statement_rows=[["회사고유공시계정 (주9)", "700"]], notes=[_note_text("9", "관련 설명")])
    checks = check_statement_note_references(report, tolerance=1)
    assert len(checks) == 1
    assert checks[0].status == PARSE_UNCERTAIN
    assert checks[0].expected == 700
```

- [ ] **Step 6: Run tests and confirm RED**

Run: `uv run pytest -q tests/test_statement_note_reference_harness.py -k "equal_rank or every_material"`

Expected: ambiguous selection or missing unclassified row.

- [ ] **Step 7: Implement honest unresolved states**

Return `PARSE_UNCERTAIN` with all candidate locations for equal top ranks; return `PARSE_UNCERTAIN` when the displayed note exists but has no direct amount; return `UNEXPLAINED_GAP` when a displayed note section is missing. Never emit `MATCHED` from topic-only evidence.

- [ ] **Step 8: Run the complete harness test file**

Run: `uv run pytest -q tests/test_statement_note_reference_harness.py`

Expected: all tests pass.

### Task 3: Pipeline and report-frame registration

**Files:**
- Modify: `src/dart_footing_reconciler/check_pipeline.py`
- Modify: `src/dart_footing_reconciler/report_frame.py`
- Modify: `tests/test_check_pipeline.py`
- Modify: `tests/test_report_frame.py`

**Interfaces:**
- Consumes: `StatementNoteReferenceHarness`
- Produces: a `statement_note_reference` harness run for each consolidated/separate slice
- Produces user labels for `statement_note_row_reconciliation`

- [ ] **Step 1: Write failing pipeline test**

```python
def test_default_pipeline_emits_one_row_reconciliation_per_referenced_statement_row():
    report = _referenced_statement_report(scope="consolidated")
    runs = assemble_report_harness_runs(report, None, tolerance=1)
    run = next(item for item in runs if item.harness_id == "statement_note_reference")
    assert run.layer == "statement_note"
    assert [check.check_type for check in run.checks] == ["statement_note_row_reconciliation"]
    assert run.checks[0].consolidation_basis == "consolidated"
```

- [ ] **Step 2: Run and confirm RED**

Run: `uv run pytest -q tests/test_check_pipeline.py -k row_reconciliation`

Expected: no harness run with id `statement_note_reference`.

- [ ] **Step 3: Register the harness without duplicating reference-existence checks**

Add `StatementNoteReferenceHarness()` to `default_report_harnesses()`. Its `run` method emits only row-level results; keep the existing generic `check_note_references` call in `StatementNoteHarness` so the established check order and text-reference coverage remain intact.

- [ ] **Step 4: Register user-facing report metadata**

Add the check type to `CHECK_GROUPS`, `CHECK_LAYERS`, `CHECK_METHOD_DESCRIPTIONS`, and `CHECK_DISPLAY_NAMES` as a drawer presentation under `재무제표-주석 대사`. Add target roles only if needed for annotation; the statement amount evidence remains the whole-row drawer anchor.

- [ ] **Step 5: Run focused integration tests**

Run: `uv run pytest -q tests/test_check_pipeline.py tests/test_report_frame.py`

Expected: all tests pass.

### Task 4: Auditor-friendly specialized drawer

**Files:**
- Modify: `src/dart_footing_reconciler/report_html.py`
- Modify: `tests/test_report_html_new.py`
- Modify: `tests/test_report_html_cockpit.py`

**Interfaces:**
- Consumes evidence roles from Task 2
- Produces a specialized card for `statement_note_row_reconciliation`
- Keeps generic cards byte-compatible for all other check types except shared styling additions

- [ ] **Step 1: Write failing specialized drawer test**

```python
def test_statement_note_drawer_explains_comparison_note_roles_and_actions(tmp_path):
    check = _statement_note_row_check(
        status=MATCHED,
        expected=100,
        actual=100,
        evidence=[
            CheckEvidence("유형자산", 100, "statement:bs/table:0/row:1/col:1", "statement_amount"),
            CheckEvidence("본문 표시 주석 10", None, "statement:bs/table:0/row:1/col:0", "displayed_note_reference"),
            CheckEvidence("주석 10 기말 장부금액", 100, "note:10/table:1/row:1/col:1", "note_amount"),
            CheckEvidence("주석 20 약정사항", None, "note:20", "related_note_reference"),
        ],
    )
    html = _export(report, [check], tmp_path)
    assert "무엇을 대사했나요" in html
    assert "재무제표 유형자산" in html
    assert "주석 10 기말 장부금액" in html
    assert "금액 대사" in html and "관련 공시" in html
    assert "재무제표 원문 보기" in html and "주석 원문 보기" in html
    assert "추가 조치가 필요하지 않습니다" in html
```

- [ ] **Step 2: Run and confirm RED**

Run: `uv run pytest -q tests/test_report_html_new.py -k statement_note_drawer`

Expected: missing specialized headings, role grouping, or source-button labels.

- [ ] **Step 3: Add a specialized renderer and role helpers**

Dispatch `statement_note_row_reconciliation` to `_render_statement_note_drawer_item`. Render: account/status header, scope/period, comparison sentence, three amount rows, `금액 대사` and `관련 공시` groups, reviewer explanation, status-specific next action, and exact source buttons. Do not display engine keys or reason codes.

- [ ] **Step 4: Add explicit unresolved amount copy**

When `actual is None`, show `금액 후보 확인 필요`, `주석 금액 확인 필요`, or `주석 원문 확인 필요` according to `parse_uncertain_reason`; do not render a bare dash as if the value were absent without explanation.

- [ ] **Step 5: Preserve row-click precedence**

When a statement row has multiple drawer checks, order `statement_note_row_reconciliation` first for the row trigger while preserving all checks in navigation. Add a regression assertion that the row's `data-open-drawer` points at the row reconciliation card.

- [ ] **Step 6: Run focused renderer tests**

Run: `uv run pytest -q tests/test_report_html_new.py tests/test_report_html_cockpit.py tests/test_report_html_evidence.py`

Expected: all tests pass.

### Task 5: SK이터닉스 coverage and browser QA

**Files:**
- Regenerate: `output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html`
- Modify only if a generalized defect is found: implementation and its focused regression test

**Interfaces:**
- Consumes the complete pipeline and renderer
- Produces quantified coverage and a visually verified desktop report

- [ ] **Step 1: Add or run the coverage audit**

Parse `/Users/kjun/vault/01_Projects/09_dart_footing_reconciler/out/sk_eternix/2026_q1_financial.html`, count material statement rows with semantic note references per scope, and compare them with unique `statement_note_row_reconciliation` statement-row anchors.

Expected:

```text
consolidated referenced_rows=54 reconciled_rows=54 missing=0 duplicate=0
separate referenced_rows=52 reconciled_rows=52 missing=0 duplicate=0
```

- [ ] **Step 2: Regenerate the workbench**

Use the existing `dart-footing workpaper-html` command and the same current/prior SK이터닉스 source pair used by the existing output. Confirm the generated file contains the scope switch and 54 specialized row cards.

- [ ] **Step 3: Run actual browser QA**

Check at desktop width:

- connected and separate switches expose only their own rows/cards;
- clicking a referenced balance-sheet and income-statement row opens the row-level card;
- matched, mismatch/attention, and unresolved cards use readable copy;
- both source buttons jump to and highlight the correct cells;
- related-note chips do not claim amount matching;
- no Python, React, Next.js, account key, status code, or parse reason is visible.

- [ ] **Step 4: Run focused and full verification**

Run:

```bash
uv run pytest -q tests/test_note_reference_validator.py tests/test_semantic_layer.py tests/test_statement_note_reference_harness.py tests/test_check_pipeline.py tests/test_report_frame.py tests/test_report_html_new.py tests/test_report_html_cockpit.py tests/test_report_html_evidence.py
uv run ruff check src tests
uv run pytest -q
npm test -- --run
```

Expected: focused tests and Ruff pass; full pytest and Vitest pass except already-documented unavailable external corpus fixtures, if still absent. Any new failure introduced by this work must be fixed before completion.
