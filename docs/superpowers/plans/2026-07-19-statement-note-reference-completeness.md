# Statement Note Reference Completeness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect note numbers omitted beside a financial-statement account, downgrade the row to `확인 필요`, and replace the verbose reconciliation drawer with a compact amount-and-completeness view.

**Architecture:** Extend the existing row-scoped `statement_note_row_reconciliation` result instead of emitting another card. The harness will compare displayed note numbers with conservative, exact-account candidates found across the same connected/separate report slice and emit `missing_note_reference` evidence. The HTML renderer will derive a compact completeness summary from evidence roles and keep exact in-report source-cell navigation.

**Tech Stack:** Python 3.11, frozen dataclasses, pytest, server-rendered HTML/CSS/JavaScript, Ruff.

## Global Constraints

- Footing and cash-flow reconciliation remain separate checks.
- Connected and separate report slices must never mix.
- Every material amount and missing-reference finding preserves an exact source row or cell.
- A missing note reference changes the user-facing conclusion to `확인 필요` even when amounts match.
- Only exact normalized account labels or same classified account keys with direct amount evidence may create a missing-reference finding.
- Internal account keys, check types, and parse reason codes must not appear in HTML.
- Do not add React, Next.js, or a JavaScript package/build layer.
- Do not run git commands in this workspace.

---

### Task 1: Missing Note Reference Detection

**Files:**
- Modify: `tests/test_statement_note_reference_harness.py`
- Modify: `src/dart_footing_reconciler/statement_note_reference_harness.py`

**Interfaces:**
- Consumes: `StatementReferenceRow`, `NoteAmountCandidate`, `ClassifiedNoteAmount`, and the existing row-scoped `displayed` tuple.
- Produces: `CheckEvidence(role="missing_note_reference")` with the omitted note number, direct account label, amount when available, and exact note source.

- [ ] **Step 1: Write a failing exact-label omission test**

Add a report where `유형자산 (주10)` equals note 10, while note 12 also contains an exact `유형자산` row. Assert that the single result has non-matched status, preserves the successful 100-to-100 amount comparison, and contains one `missing_note_reference` evidence pointing to `note:12/...`.

```python
def test_exact_account_in_undisplayed_note_is_reported_as_missing_reference():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주10)", "100"])],
        [
            _note("10", "유형자산", [["구분", "당기"], ["유형자산", "100"]]),
            _note("12", "담보", [["구분", "당기"], ["유형자산", "100"]]),
        ],
    )
    check = check_statement_note_references(report, tolerance=1)[0]
    assert check.status == PARSE_UNCERTAIN
    assert (check.expected, check.actual, check.difference) == (100, 100, 0)
    missing = [item for item in check.evidence if item.role == "missing_note_reference"]
    assert [(item.label, item.source) for item in missing] == [
        ("주석 12 유형자산", "note:12/table:12/row:1/col:1")
    ]
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
uv run pytest -q tests/test_statement_note_reference_harness.py::test_exact_account_in_undisplayed_note_is_reported_as_missing_reference
```

Expected: FAIL because the result is still `MATCHED` and has no `missing_note_reference` evidence.

- [ ] **Step 3: Write false-positive and displayed-reference tests**

Add two tests:

```python
def test_similar_detail_label_is_not_reported_as_missing_reference():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주10)", "100"])],
        [
            _note("10", "유형자산", [["구분", "당기"], ["유형자산", "100"]]),
            _note("12", "투자활동", [["구분", "당기"], ["유형자산 취득", "100"]]),
        ],
    )
    check = check_statement_note_references(report, tolerance=1)[0]
    assert check.status == MATCHED
    assert not any(item.role == "missing_note_reference" for item in check.evidence)

def test_account_in_another_displayed_note_is_not_missing():
    report = FullReport(
        "s.html",
        "Co",
        [_statement(["유형자산 (주10,12)", "100"])],
        [
            _note("10", "유형자산", [["구분", "당기"], ["유형자산", "100"]]),
            _note("12", "담보", [["구분", "당기"], ["유형자산", "100"]]),
        ],
    )
    check = check_statement_note_references(report, tolerance=1)[0]
    assert check.status == MATCHED
    assert not any(item.role == "missing_note_reference" for item in check.evidence)
    assert any(item.role == "related_note_reference" for item in check.evidence)
```

Both tests must assert that `missing_note_reference` is absent. The first remains `MATCHED`; the second remains `MATCHED` with one selected `note_amount` and the other displayed note represented as related evidence.

- [ ] **Step 4: Implement conservative missing-reference discovery**

In `check_statement_note_references`, calculate missing candidates before `_result_for_row`:

```python
missing_candidates = _missing_note_candidates(
    report,
    row,
    displayed,
    classified.note_amounts,
)
```

Add `_missing_note_candidates(...) -> list[NoteAmountCandidate]` that:

1. scans only notes in the already scope-sliced `report`;
2. excludes note numbers matching any displayed primary/subnote reference;
3. accepts direct table candidates only when `_normalize(candidate.label) == _normalize(row.label)`;
4. accepts classified candidates only when `row.account_key != "unknown"`, account keys match, a direct amount source exists, and the normalized labels are equal;
5. keeps the highest-ranked candidate per actual note number and sorts by note number/source;
6. never uses partial label containment for omission findings.

Pass `missing_candidates` into `_result_for_row`.

- [ ] **Step 5: Add evidence and status override in every result branch**

Add a helper that appends one evidence item per missing note:

```python
CheckEvidence(
    f"주석 {candidate.note_no} {candidate.label}".strip(),
    candidate.amount,
    candidate.source,
    role="missing_note_reference",
)
```

When a selected amount otherwise matches but missing evidence exists, keep `expected`, `actual`, and `difference` unchanged, set status to `PARSE_UNCERTAIN`, set a human Korean reason such as `재무제표 옆에 표시되지 않은 관련 주석번호가 확인됨`, and use `MISSING_DISPLAYED_NOTE_REFERENCE` only as an internal reason. Existing non-matched statuses remain non-matched while retaining missing evidence.

- [ ] **Step 6: Run harness tests and verify GREEN**

Run:

```bash
uv run pytest -q tests/test_statement_note_reference_harness.py
```

Expected: all tests pass.

---

### Task 2: Compact Completeness Drawer

**Files:**
- Modify: `tests/test_report_html_new.py`
- Modify: `src/dart_footing_reconciler/report_html.py`

**Interfaces:**
- Consumes evidence roles `displayed_note_reference`, `note_amount`, `candidate_note_amount`, `related_note_reference`, and `missing_note_reference`.
- Produces one compact `주석번호 완전성` section and source buttons named `재무제표 해당 셀`, `주석 해당 금액`, and `누락 후보 주석 위치`.

- [ ] **Step 1: Replace the existing drawer expectations with a failing compact contract**

Update `test_statement_note_drawer_explains_comparison_note_roles_and_actions` so its fixture includes a missing evidence item:

```python
CheckEvidence(
    "주석 12 유형자산",
    100,
    "note:12/table:12/row:1/col:1",
    role="missing_note_reference",
)
```

Assert:

```python
assert "주석번호 완전성" in content
assert "표시됨" in content
assert "금액 대사" in content
assert "누락" in content
assert "주석 10" in content
assert "주석 12" in content
assert "재무제표 해당 셀" in content
assert "주석 해당 금액" in content
assert "누락 후보 주석 위치" in content
assert "무엇을 대사했나요" not in content
assert "사용한 주석" not in content
assert "검증한 내용" not in content
assert "원문 위치" not in content
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py::test_statement_note_drawer_explains_comparison_note_roles_and_actions
```

Expected: FAIL on the missing compact labels and retained verbose sections.

- [ ] **Step 3: Render the compact completeness view**

In `_render_statement_note_drawer_item`:

- remove the comparison sentence and the `사용한 주석`/`검증한 내용` sections;
- keep the three amount cells directly under the header;
- collect `missing_note_reference` evidence;
- render `표시됨`, `금액 대사`, and `누락` rows under one `주석번호 완전성` heading;
- show `완전` when no displayed reference is broken and no missing evidence exists;
- show `확인 필요` when any missing evidence exists or the check is otherwise non-matched;
- use `확인 필요` as the specialized drawer status text for every non-matched statement-note result;
- retain only the necessary follow-up sentence.

Use the existing evidence source renderer, but rename buttons:

```python
label="재무제표 해당 셀"
label="주석 해당 금액"
label="누락 후보 주석 위치"
```

Render missing source buttons from `missing_note_reference` evidence. Do not add a separate `원문 위치` heading.

- [ ] **Step 4: Make row status wording consistent**

In `_statement_row_result_text`, detect rows containing `statement_note_row_reconciliation`. For those rows use `검증 완료` for `MATCHED` and `확인 필요` for every other status. Do not change cash-flow wording or generic result labels.

- [ ] **Step 5: Run renderer tests and verify GREEN**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py tests/test_report_html_cockpit.py tests/test_report_html_evidence.py
```

Expected: all fixture-independent tests pass; any corpus fixture failure must be reported separately as `FileNotFoundError`.

---

### Task 3: SK이터닉스 Regeneration and Verification

**Files:**
- Regenerate: `output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html`

**Interfaces:**
- Consumes the existing SK이터닉스 report-generation command and current report fixture.
- Produces the desktop HTML validation report with connected/separate scope switching and compact completeness drawers.

- [ ] **Step 1: Run focused Python verification**

Run:

```bash
uv run pytest -q \
  tests/test_note_reference_validator.py \
  tests/test_semantic_layer.py \
  tests/test_statement_note_reference_harness.py \
  tests/test_check_pipeline.py \
  tests/test_report_frame.py \
  tests/test_report_html_new.py
```

Expected: new and existing fixture-independent tests pass. Missing external corpus files are not product regressions and must be listed explicitly if encountered.

- [ ] **Step 2: Run static checks**

Run:

```bash
uv run ruff check src tests
```

Expected: `All checks passed!`

- [ ] **Step 3: Regenerate the report**

Run:

```bash
uv run dart-footing workpaper-html \
  /Users/kjun/vault/01_Projects/09_dart_footing_reconciler/out/sk_eternix/2026_q1_financial.html \
  output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html \
  --company SK이터닉스 \
  --prior-html /Users/kjun/vault/01_Projects/09_dart_footing_reconciler/out/sk_eternix/2025_annual_financial.html \
  --tolerance 1
```

Expected: exit 0. Confirm the generated file contains `주석번호 완전성`, `재무제표 해당 셀`, and no internal account/check/reason identifiers.

- [ ] **Step 4: Browser QA**

Serve `output/sk_eternix/` locally and verify with Playwright:

1. connected and separate scopes remain isolated;
2. a complete matched account shows `표시됨`, `금액 대사`, `완전`;
3. a missing-reference account shows `누락`, `확인 필요`, and the omitted note number;
4. all three source button types jump to the exact in-report row or cell;
5. verbose headings removed by Task 2 do not appear;
6. no functional console errors appear.

- [ ] **Step 5: Run the full suite and report the exact result**

Run:

```bash
uv run pytest -q
```

Report the exact pass/skip/fail totals. Separate missing external fixture failures from functional failures, and do not claim a fully green suite when fixtures are absent.
