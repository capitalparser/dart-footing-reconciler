# Drawer Note Location and Validation Badges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the redundant statement-cell jump from statement-note drawers, render role-colored note locations, and replace unexplained numeric counters with semantic Korean badges.

**Architecture:** Keep the existing `CheckEvidence` roles as the source of truth. Specialize only the `statement_note_row_reconciliation` drawer and the shared table badge renderer. Deduplicate note locations by rendered target and suppress reconciliation counts already represented by the statement row badge.

**Tech Stack:** Python 3.11, pytest, generated standalone HTML/CSS/JavaScript, Playwright CLI for desktop browser QA.

## Global Constraints

- Do not run git commands.
- Do not add React, Next.js, or another frontend runtime.
- Footing and cash-flow reconciliation remain separate checks.
- Preserve every material amount's existing source cell.
- Do not expose internal check types, account keys, or reason codes.
- Apply changes with `apply_patch` and write failing tests before production code.

---

### Task 1: Role-colored note locations in the statement drawer

**Files:**
- Modify: `tests/test_report_html_new.py:406-480`
- Modify: `src/dart_footing_reconciler/report_html.py:779-900`
- Modify: `src/dart_footing_reconciler/report_html.py:2600-2630`

**Interfaces:**
- Consumes: `CheckEvidence.role` values `note_amount`, `candidate_note_amount`, and `missing_note_reference`.
- Produces: `_render_statement_note_location(...) -> str` and drawer CSS classes `drawer-note-locations`, `drawer-note-location-existence`, `drawer-note-location-completeness`.

- [ ] **Step 1: Write the failing renderer contract**

Update `test_statement_note_drawer_explains_comparison_note_roles_and_actions` with these assertions:

```python
assert "재무제표 해당 셀" not in content
assert "원문 위치" not in content
assert "<h4>주석 위치</h4>" in content
assert "실재성 · 주석 10" in content
assert "완전성 누락 · 주석 12" in content
assert 'class="drawer-source drawer-note-location-existence"' in content
assert 'class="drawer-source drawer-note-location-completeness"' in content
```

Add a second note-amount evidence pointing to the same rendered target and assert that `실재성 · 주석 10` occurs once.

- [ ] **Step 2: Verify the test fails for the intended reason**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py::test_statement_note_drawer_explains_comparison_note_roles_and_actions
```

Expected: FAIL because `재무제표 해당 셀` still exists and the `주석 위치` role classes do not exist.

- [ ] **Step 3: Implement role-colored note locations**

In `_render_statement_note_drawer_item`, remove `statement_source`. Render note targets through a helper with this contract:

```python
def _render_statement_note_locations(
    report: FullReport,
    check: CheckResult,
    note_amounts: list[CheckEvidence],
    missing_refs: list[CheckEvidence],
    render_map: _ReportRenderMap,
) -> str:
    locations: list[str] = []
    seen: set[tuple[str, str]] = set()
    for role_label, css_class, evidence_items in (
        ("실재성", "drawer-note-location-existence", note_amounts),
        ("완전성 누락", "drawer-note-location-completeness", missing_refs),
    ):
        for evidence in evidence_items:
            note_label = _note_number_label(evidence.label)
            key = (role_label, evidence.source)
            if key in seen:
                continue
            seen.add(key)
            locations.append(
                _render_named_evidence_source(
                    report,
                    check,
                    evidence,
                    len(locations),
                    render_map,
                    label=f"{role_label} · {note_label}",
                    css_class=css_class,
                )
            )
    if not locations:
        return ""
    return (
        '<section class="drawer-section drawer-note-locations">'
        '<h4>주석 위치</h4><div class="drawer-sources">'
        + "".join(locations)
        + "</div></section>"
    )
```

Extend `_render_named_evidence_source` and `_render_drawer_source_button` with a defaulted `css_class: str = ""` argument and append the escaped class only to these buttons.

- [ ] **Step 4: Add semantic colors without changing result colors**

Add CSS:

```css
.drawer-note-location-existence{border-color:#86c7a6;background:#edf9f2;color:#17663a;}
.drawer-note-location-existence:hover{background:#dff3e8;}
.drawer-note-location-completeness{border-color:#e6a09b;background:#fff0ef;color:#a4312b;}
.drawer-note-location-completeness:hover{background:#ffe2df;}
```

The colors identify evidence role only. Keep the existing drawer status badge as the pass/attention conclusion.

- [ ] **Step 5: Verify the drawer tests pass**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py::test_statement_note_drawer_explains_comparison_note_roles_and_actions tests/test_report_html_new.py::test_statement_note_drawer_names_unresolved_amount_instead_of_dash
```

Expected: `2 passed`.

### Task 2: Semantic validation count badges

**Files:**
- Modify: `tests/test_report_html_new.py:261-330`
- Modify: `src/dart_footing_reconciler/report_html.py:2140-2270`
- Modify: `src/dart_footing_reconciler/report_html.py:2290-2325`
- Modify: `src/dart_footing_reconciler/report_html.py:2590-2615`

**Interfaces:**
- Consumes: `annotations`, `drawer_indexes`, `row_drawer_indexes`, and `_statement_row_result_text`.
- Produces: visible labels `합계 검증 N건`, `대사 N건`, and `<상태> · N건`.

- [ ] **Step 1: Write failing tests for each visible count**

Add tests that generate two total checks on one note cell and two statement-note drawer items on one statement row. Assert:

```python
assert '<span class="cell-check-count" aria-label="합계 검증 2건">합계 검증 2건</span>' in content
assert '<span class="row-result-count">검증 완료 · 2건</span>' in content
assert '>2</span>' not in content
```

For a statement row, assert `대사 2건` is not also rendered inside the amount cell. For a non-statement note cell with two drawer items, assert:

```python
assert '<span class="cell-reconciliation-count" aria-label="대사 2건">대사 2건</span>' in content
```

- [ ] **Step 2: Verify the badge tests fail**

Run the new test node IDs with `uv run pytest -q`. Expected: FAIL because counters contain only `2` and row text is `검증 완료 2`.

- [ ] **Step 3: Render semantic labels and suppress duplicates**

Change the two count fragments to:

```python
count_badge = (
    '<span class="cell-check-count" aria-label="합계 검증 '
    f'{len(checks)}건">합계 검증 {len(checks)}건</span>'
    if len(checks) > 1
    else ""
)
```

```python
if len(drawer_indexes) > 1 and not (is_statement and row_drawer_indexes):
    inner += (
        '<span class="cell-reconciliation-count" '
        f'aria-label="대사 {len(drawer_indexes)}건">'
        f'대사 {len(drawer_indexes)}건</span>'
    )
```

Change `_statement_row_result_text` to return:

```python
return f"{label} · {len(checks)}건" if len(checks) > 1 else label
```

- [ ] **Step 4: Restyle badges as readable pills**

Replace absolute circular count rules with compact pills that do not cover amounts:

```css
.cell-check-count,.cell-reconciliation-count{display:inline-flex;align-items:center;margin-left:6px;padding:1px 6px;border-radius:999px;font-size:9px;font-weight:900;white-space:nowrap;vertical-align:middle;}
.cell-check-count{background:var(--sidebar);color:#fff;}
.cell-reconciliation-count{background:var(--accent);color:#fff;}
.row-result-count{display:inline-flex;align-items:center;margin-left:8px;padding:2px 7px;border-radius:999px;background:var(--accent-dim);color:var(--accent);font-size:9px;font-weight:900;vertical-align:middle;}
```

- [ ] **Step 5: Verify renderer regression coverage**

Run:

```bash
uv run pytest -q tests/test_report_html_new.py tests/test_report_html_cockpit.py tests/test_report_html_evidence.py
```

Expected: all locally available fixture-independent tests pass; any external fixture failure must be reported separately.

### Task 3: Regenerate and visually verify SK이터닉스

**Files:**
- Regenerate: `output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html`

**Interfaces:**
- Consumes: the unchanged CLI command and SK이터닉스 current/prior HTML files.
- Produces: standalone desktop workbench HTML.

- [ ] **Step 1: Regenerate the report**

Run:

```bash
uv run dart-footing workpaper-html \
  /Users/kjun/vault/01_Projects/09_dart_footing_reconciler/out/sk_eternix/2026_q1_financial.html \
  output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html \
  --company SK이터닉스 \
  --prior-html /Users/kjun/vault/01_Projects/09_dart_footing_reconciler/out/sk_eternix/2025_annual_financial.html \
  --tolerance 1
```

Expected: output path is written without traceback.

- [ ] **Step 2: Run static output assertions**

Run:

```bash
rg -n '재무제표 해당 셀|class="cell-check-count"[^>]*>[0-9]+</span>|class="cell-reconciliation-count"[^>]*>[0-9]+</span>' output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html
```

Expected: no matches.

Run:

```bash
rg -n '주석 위치|실재성 · 주석|완전성 누락 · 주석|합계 검증 [0-9]+건|대사 [0-9]+건' output/sk_eternix/sk_eternix_2026_q1_audit_workbench.html
```

Expected: each semantic label appears.

- [ ] **Step 3: Verify the desktop browser flow**

Serve the output, then use Playwright CLI to check one matched statement account, one missing-reference account, one multi-check total cell, and the separate scope. Confirm green and red note buttons jump to the correct note target and no statement-cell button appears.

- [ ] **Step 4: Run quality gates**

Run:

```bash
uv run ruff check src tests
uv run pytest -q
```

Record exact pass/fail totals. Separate missing external raw fixture failures from regressions caused by this plan.
